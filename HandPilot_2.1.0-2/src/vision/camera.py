from __future__ import annotations

import sys
import time
from pathlib import Path

import cv2
from PySide6.QtCore import QThread, Signal

from src.actions.cursor_mapper import CursorMapper
from src.core.config import ConfigStore
from src.core.models import CursorTarget, FrameResult, GestureName, GesturePrediction, HandControlState, HandData, StableGesture
from src.gestures.engine import GestureEngine
from src.vision.face_tracker import FaceTracker
from src.vision.tracker import HandTracker


class CameraThread(QThread):
    frame_ready = Signal(object)
    state_changed = Signal(str)
    error = Signal(str)
    action_error = Signal(str)

    def __init__(self, config_store: ConfigStore, hand_model_path: str | Path, face_model_path: str | Path, parent=None):
        super().__init__(parent)
        self.config_store = config_store
        self.hand_model_path = Path(hand_model_path)
        self.face_model_path = Path(face_model_path)
        self._running = True
        self._camera = None
        self._last_timestamp_ms = 0
        self._last_config: dict | None = None
        self._gesture_engine: GestureEngine | None = None
        self._cursor_mappers: dict[str, CursorMapper] = {}
        self._cursor_joint = 8

    def stop(self):
        self._running = False
        self.requestInterruption()

    def _open_camera(self, index: int, width: int, height: int, fps: int):
        backends = []
        if sys.platform == "darwin":
            backends.append(cv2.CAP_AVFOUNDATION)
        backends.append(cv2.CAP_ANY)
        for backend in backends:
            cap = cv2.VideoCapture(index, backend)
            if cap.isOpened():
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
                cap.set(cv2.CAP_PROP_FPS, fps)
                return cap
            cap.release()
        return None

    def _configure_cursor(self, config: dict):
        screen = config.get("screen", {})
        settings = config.get("action_settings", {})
        self._cursor_joint = int(settings.get("cursor_joint", 8))
        if self._cursor_joint not in range(21):
            self._cursor_joint = 8
        width = int(screen.get("width", 1920))
        height = int(screen.get("height", 1080))
        margin_x = float(settings.get("mapping_margin_x", 0.07))
        margin_y = float(settings.get("mapping_margin_y", 0.08))
        smoothing = float(settings.get("cursor_smoothing", 0.34))
        precision = float(settings.get("cursor_precision", 1.0))
        for mapper in self._cursor_mappers.values():
            mapper.reconfigure(width, height, margin_x, margin_y, smoothing, precision)

    def _action_failure(self, message: str):
        self.action_error.emit(message)

    def run(self):
        config = self.config_store.snapshot()
        self._last_config = config
        tracker = face_tracker = None
        try:
            self._configure_cursor(config)
            self._gesture_engine = GestureEngine(config)
            tracker = HandTracker(self.hand_model_path, config)
            if bool(config.get("face_guard", {}).get("enabled", True)):
                face_tracker = FaceTracker(self.face_model_path, config)
        except Exception as exc:
            self.error.emit(f"Failed to initialize vision pipeline: {exc}")
            return

        camera_cfg = config.get("camera", {})
        camera_index = int(camera_cfg.get("index", 0))
        width = int(camera_cfg.get("width", 960))
        height = int(camera_cfg.get("height", 540))
        requested_fps = int(camera_cfg.get("fps", 30))
        self._camera = self._open_camera(camera_index, width, height, requested_fps)
        if self._camera is None:
            self.error.emit(
                f"Could not open webcam {camera_index}. Grant camera permission to the app/terminal and close any other app using the camera."
            )
            if tracker:
                tracker.close()
            if face_tracker:
                face_tracker.close()
            return

        self.state_changed.emit("Camera online")
        frames = 0
        fps_window_start = time.monotonic()
        display_fps = 0.0
        last_face_conf = 0.0

        try:
            while self._running and not self.isInterruptionRequested():
                config = self.config_store.snapshot()
                if config != self._last_config:
                    self._last_config = config
                    self._gesture_engine.update_config(config)
                    self._configure_cursor(config)
                    # Face tracker settings are intentionally static for the
                    # session; restart after changing face-model settings.

                ok, frame = self._camera.read()
                if not ok or frame is None:
                    self.state_changed.emit("Camera frame unavailable")
                    time.sleep(0.03)
                    continue

                if bool(config.get("camera", {}).get("mirror", True)):
                    frame = cv2.flip(frame, 1)

                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                now_ms = int(time.monotonic() * 1000)
                self._last_timestamp_ms = max(self._last_timestamp_ms + 1, now_ms)

                faces = []
                if face_tracker is not None:
                    faces, last_face_conf = face_tracker.detect(rgb, self._last_timestamp_ms)

                hands, tracking_conf = tracker.detect(rgb, self._last_timestamp_ms)
                assert self._gesture_engine is not None
                hand_states = self._gesture_engine.process_all(hands, faces)
                control_index = self._gesture_engine.select_primary(hand_states)
                if control_index is not None and control_index < len(hand_states):
                    prediction = hand_states[control_index].prediction
                    stable = hand_states[control_index].stable
                else:
                    prediction = GesturePrediction()
                    stable = StableGesture()

                screen_w = int(config.get("screen", {}).get("width", 1920))
                screen_h = int(config.get("screen", {}).get("height", 1080))
                cursor = CursorTarget(screen_width=screen_w, screen_height=screen_h)

                # Each hand gets its own cursor mapper. Only a hand whose active
                # mapping is MOUSE_MOVE drives the desktop pointer, so a second
                # hand can independently scroll/click without fighting the cursor hand.
                mappings = config.get("mappings", {})
                multi_hand = bool(config.get("runtime", {}).get("multi_hand_enabled", True))
                active_cursor_keys: set[str] = set()
                for control in hand_states:
                    mapping = mappings.get(control.stable.gesture.value, {})
                    is_mouse_mode = (
                        bool(mapping.get("enabled", False))
                        and str(mapping.get("action", "")).upper() == "MOUSE_MOVE"
                        and control.stable.gesture != GestureName.NONE
                        and not control.hand.face_blocked
                    )
                    if is_mouse_mode and (multi_hand or control_index is None or hand_states[control_index].key == control.key):
                        active_cursor_keys.add(control.key)
                        mapper = self._cursor_mappers.get(control.key)
                        if mapper is None:
                            mapper = CursorMapper(
                                screen_w,
                                screen_h,
                                float(config.get("action_settings", {}).get("mapping_margin_x", 0.07)),
                                float(config.get("action_settings", {}).get("mapping_margin_y", 0.08)),
                                float(config.get("action_settings", {}).get("cursor_smoothing", 0.34)),
                                float(config.get("action_settings", {}).get("cursor_precision", 1.0)),
                            )
                            self._cursor_mappers[control.key] = mapper
                        sx, sy = mapper.update(control.hand.joint(self._cursor_joint)[:2])
                        control.cursor = CursorTarget(float(sx), float(sy), True, screen_w, screen_h)

                for key, mapper in list(self._cursor_mappers.items()):
                    if key not in active_cursor_keys:
                        mapper.reset()
                if control_index is not None and control_index < len(hand_states):
                    primary_cursor = hand_states[control_index].cursor
                    if primary_cursor.valid:
                        cursor = primary_cursor
                    elif active_cursor_keys:
                        for state in hand_states:
                            if state.cursor.valid:
                                cursor = state.cursor
                                break

                control_hand = hand_states[control_index].hand if control_index is not None and control_index < len(hand_states) else None

                frames += 1
                elapsed = time.monotonic() - fps_window_start
                if elapsed >= 0.75:
                    display_fps = frames / elapsed
                    frames = 0
                    fps_window_start = time.monotonic()

                if not hands:
                    status = "NO HAND"
                elif hand_states and all(state.hand.face_blocked for state in hand_states):
                    status = "HANDS BLOCKED · FACE"
                elif any(state.hand.face_blocked for state in hand_states):
                    status = "TRACKING · FACE GUARD"
                elif faces:
                    status = "TRACKING · FACE + HAND"
                elif len(hand_states) >= 2:
                    status = "TRACKING · 2 HANDS"
                else:
                    status = "TRACKING"

                result = FrameResult(
                    frame_bgr=frame,
                    hands=hands,
                    faces=faces,
                    prediction=prediction,
                    stable=stable,
                    cursor=cursor,
                    fps=display_fps,
                    tracking_confidence=tracking_conf,
                    face_confidence=last_face_conf,
                    status=status,
                    timestamp_ms=self._last_timestamp_ms,
                    hand_states=hand_states,
                )
                self.frame_ready.emit(result)
        except Exception as exc:
            self.error.emit(f"Camera loop stopped: {exc}")
        finally:
            if tracker:
                tracker.close()
            if face_tracker:
                face_tracker.close()
            if self._camera is not None:
                self._camera.release()
            self._camera = None
            self.state_changed.emit("Camera stopped")
