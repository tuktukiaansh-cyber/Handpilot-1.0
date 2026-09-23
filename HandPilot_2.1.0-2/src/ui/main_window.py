from __future__ import annotations

from pathlib import Path
import json
import sys

import cv2
from PySide6.QtCore import Qt, Slot, QTimer
from PySide6.QtGui import QImage, QPixmap, QGuiApplication
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from src.core.config import ConfigStore
from src.core.models import FrameResult
from src.core.restart import request_application_restart
from src.actions.executor import ActionRouter
from src.ui.styles import DARK_QSS
from src.vision.camera import CameraThread
from src.vision.renderer import draw_overlay


class MainWindow(QMainWindow):
    def __init__(self, config_store: ConfigStore, hand_model_path: Path, face_model_path: Path):
        super().__init__()
        self.config_store = config_store
        self.hand_model_path = hand_model_path
        self.face_model_path = face_model_path
        self.worker: CameraThread | None = None
        # IMPORTANT on macOS: pynput.keyboard.Controller() queries the system
        # keyboard input source during construction. macOS 27 requires those
        # TIS/HIToolbox calls on the main dispatch queue, so the desktop-input
        # router must be owned and invoked by this GUI thread, never CameraThread.
        self.action_router = ActionRouter(self.config_store.snapshot(), on_error=self._on_action_error)

        self.setWindowTitle("HandPilot — Gesture Computer Control")
        self.resize(1380, 880)
        self.setMinimumSize(1120, 760)
        self.setStyleSheet(DARK_QSS)
        self._sync_screen_geometry()

        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        self.tabs.addTab(self._build_live_tab(), "Live")
        self.tabs.addTab(self._build_mappings_tab(), "Mappings")
        self.tabs.addTab(self._build_settings_tab(), "Settings")

        self._refresh_mappings()
        self._load_settings()
        self._start_camera()

    def _sync_screen_geometry(self):
        screen = QGuiApplication.primaryScreen()
        if screen:
            geometry = screen.geometry()
            self.config_store.update_path("screen.width", geometry.width(), save=False)
            self.config_store.update_path("screen.height", geometry.height(), save=False)

    def _card(self):
        card = QFrame()
        card.setObjectName("Card")
        return card

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("Section")
        return label

    def _build_live_tab(self):
        root = QWidget()
        outer = QVBoxLayout(root)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("HandPilot")
        title.setObjectName("Title")
        subtitle = QLabel("Local vision · hand + face awareness · desktop control")
        subtitle.setObjectName("Subtitle")
        header.addWidget(title)
        header.addSpacing(12)
        header.addWidget(subtitle)
        header.addStretch()
        self.restart_btn = QPushButton("Restart camera")
        self.restart_btn.clicked.connect(self._restart_camera)
        header.addWidget(self.restart_btn)
        self.automation_toggle = QPushButton("Automation OFF")
        self.automation_toggle.setCheckable(True)
        self.automation_toggle.clicked.connect(self._toggle_automation)
        header.addWidget(self.automation_toggle)
        outer.addLayout(header)

        body = QHBoxLayout()
        body.setSpacing(14)

        video_card = self._card()
        video_layout = QVBoxLayout(video_card)
        self.video = QLabel("Waiting for camera…")
        self.video.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.video.setMinimumSize(760, 520)
        self.video.setStyleSheet("background:#080a0e;border-radius:14px;")
        video_layout.addWidget(self.video)
        self.video_hint = QLabel("ONE = fingertip mouse · TWO = fingertip wave scroll · PINCH = left click · OK = right click · use BOTH hands independently")
        self.video_hint.setObjectName("Subtitle")
        video_layout.addWidget(self.video_hint)
        body.addWidget(video_card, 3)

        side = QVBoxLayout()
        side.setSpacing(12)

        gesture_card = self._card()
        g = QVBoxLayout(gesture_card)
        g.addWidget(self._section("CURRENT GESTURE"))
        self.gesture = QLabel("NONE")
        self.gesture.setObjectName("GestureValue")
        self.gesture_conf = QLabel("0%")
        self.gesture_conf.setObjectName("MetricValue")
        g.addWidget(self.gesture)
        g.addWidget(QLabel("Stable confidence"))
        g.addWidget(self.gesture_conf)
        self.pinch_label = QLabel("Pinch: —")
        self.cursor_label = QLabel("Cursor: —")
        g.addWidget(self.pinch_label)
        g.addWidget(self.cursor_label)
        side.addWidget(gesture_card)

        stats = self._card()
        grid = QGridLayout(stats)
        self.fps_label = QLabel("0.0")
        self.fps_label.setObjectName("MetricValue")
        self.track_label = QLabel("0%")
        self.track_label.setObjectName("MetricValue")
        self.face_label = QLabel("0%")
        self.face_label.setObjectName("MetricValue")
        self.hands_label = QLabel("0")
        self.hands_label.setObjectName("MetricValue")
        self.status_label = QLabel("Starting…")
        self.status_label.setObjectName("StatusGood")
        rows = [("FPS", self.fps_label), ("Hand confidence", self.track_label), ("Face confidence", self.face_label), ("Hands", self.hands_label), ("Status", self.status_label)]
        for row, (name, value) in enumerate(rows):
            grid.addWidget(QLabel(name), row, 0)
            grid.addWidget(value, row, 1)
        side.addWidget(stats)

        control = self._card()
        c = QVBoxLayout(control)
        c.addWidget(self._section("CONTROL"))
        self.control_hand_label = QLabel("No control hand")
        self.face_guard_label = QLabel("Face guard: ON")
        self.face_guard_label.setObjectName("StatusGood")
        self.mapping_summary = QLabel("Automation OFF")
        self.mapping_summary.setObjectName("Subtitle")
        self.hand_roles_label = QLabel("Hands: —")
        self.hand_roles_label.setWordWrap(True)
        self.hand_roles_label.setObjectName("Subtitle")
        c.addWidget(self.control_hand_label)
        c.addWidget(self.face_guard_label)
        c.addWidget(self.hand_roles_label)
        c.addWidget(self.mapping_summary)
        side.addWidget(control)
        side.addStretch()
        body.addLayout(side, 1)
        outer.addLayout(body, 1)
        return root

    def _build_mappings_tab(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)
        info = QLabel("Map stable gestures to desktop actions. ON ENTER actions fire once per stable transition; WHILE ACTIVE actions update continuously.")
        info.setWordWrap(True)
        info.setObjectName("Subtitle")
        layout.addWidget(info)

        self.mapping_table = QTableWidget(0, 7)
        self.mapping_table.setHorizontalHeaderLabels(["Gesture", "Hand", "Enabled", "Action", "Mode", "Cooldown ms", "Payload JSON"])
        self.mapping_table.verticalHeader().setVisible(False)
        self.mapping_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        layout.addWidget(self.mapping_table, 1)

        row = QHBoxLayout()
        save = QPushButton("Save mappings")
        save.setObjectName("Primary")
        save.clicked.connect(self._save_mappings)
        row.addWidget(save)
        row.addStretch()
        layout.addLayout(row)
        return root

    def _build_settings_tab(self):
        root = QWidget()
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 18, 18, 18)

        card = self._card()
        form = QFormLayout(card)
        self.camera_index = QSpinBox(); self.camera_index.setRange(0, 10)
        self.camera_width = QSpinBox(); self.camera_width.setRange(320, 1920); self.camera_width.setSingleStep(160)
        self.camera_height = QSpinBox(); self.camera_height.setRange(240, 1080); self.camera_height.setSingleStep(120)
        self.camera_fps = QSpinBox(); self.camera_fps.setRange(15, 60)
        self.mirror = QCheckBox("Mirror preview")
        form.addRow("Camera index", self.camera_index)
        form.addRow("Capture width", self.camera_width)
        form.addRow("Capture height", self.camera_height)
        form.addRow("Target camera FPS", self.camera_fps)
        form.addRow("Preview", self.mirror)

        self.preferred_hand = QComboBox(); self.preferred_hand.addItems(["AUTO", "LEFT", "RIGHT"])
        self.multi_hand = QCheckBox("Enable independent two-hand control")
        self.face_guard = QCheckBox("Pause hand control while hand overlaps face")
        self.show_face = QCheckBox("Show face box")
        form.addRow("Primary hand", self.preferred_hand)
        form.addRow("Multi-hand control", self.multi_hand)
        form.addRow("Face guard", self.face_guard)
        form.addRow("Face overlay", self.show_face)

        self.smoothing = QDoubleSpinBox(); self.smoothing.setRange(0.05, 1.0); self.smoothing.setSingleStep(0.05); self.smoothing.setDecimals(2)
        self.min_conf = QDoubleSpinBox(); self.min_conf.setRange(0.30, 0.99); self.min_conf.setSingleStep(0.02); self.min_conf.setDecimals(2)
        self.activation = QSpinBox(); self.activation.setRange(40, 1000); self.activation.setSuffix(" ms")
        self.release = QSpinBox(); self.release.setRange(30, 1000); self.release.setSuffix(" ms")
        form.addRow("Landmark smoothing", self.smoothing)
        form.addRow("Gesture confidence", self.min_conf)
        form.addRow("Activation delay", self.activation)
        form.addRow("Release delay", self.release)

        self.cursor_joint = QComboBox(); self.cursor_joint.addItem("Index fingertip", 8); self.cursor_joint.addItem("Wrist", 0); self.cursor_joint.addItem("Thumb tip", 4)
        self.margin_x = QDoubleSpinBox(); self.margin_x.setRange(0.0, 0.25); self.margin_x.setSingleStep(0.01); self.margin_x.setDecimals(2)
        self.margin_y = QDoubleSpinBox(); self.margin_y.setRange(0.0, 0.25); self.margin_y.setSingleStep(0.01); self.margin_y.setDecimals(2)
        self.cursor_smooth = QDoubleSpinBox(); self.cursor_smooth.setRange(0.02, 1.0); self.cursor_smooth.setSingleStep(0.02); self.cursor_smooth.setDecimals(2)
        self.cursor_precision = QDoubleSpinBox(); self.cursor_precision.setRange(0.5, 2.0); self.cursor_precision.setSingleStep(0.05); self.cursor_precision.setDecimals(2)
        self.cursor_deadzone = QDoubleSpinBox(); self.cursor_deadzone.setRange(0.0, 30.0); self.cursor_deadzone.setSingleStep(0.5); self.cursor_deadzone.setDecimals(1); self.cursor_deadzone.setSuffix(" px")
        self.scroll_sensitivity = QDoubleSpinBox(); self.scroll_sensitivity.setRange(10.0, 500.0); self.scroll_sensitivity.setSingleStep(10.0); self.scroll_sensitivity.setDecimals(0)
        self.scroll_threshold = QDoubleSpinBox(); self.scroll_threshold.setRange(0.0005, 0.03); self.scroll_threshold.setSingleStep(0.0005); self.scroll_threshold.setDecimals(4)
        self.scroll_axis_lock = QDoubleSpinBox(); self.scroll_axis_lock.setRange(0.0, 1.5); self.scroll_axis_lock.setSingleStep(0.05); self.scroll_axis_lock.setDecimals(2)
        form.addRow("Cursor joint", self.cursor_joint)
        form.addRow("Active-area X margin", self.margin_x)
        form.addRow("Active-area Y margin", self.margin_y)
        form.addRow("Cursor smoothing", self.cursor_smooth)
        form.addRow("Cursor precision", self.cursor_precision)
        form.addRow("Cursor deadzone", self.cursor_deadzone)
        form.addRow("Two-finger scroll sensitivity", self.scroll_sensitivity)
        form.addRow("Scroll minimum movement", self.scroll_threshold)
        form.addRow("Scroll vertical lock", self.scroll_axis_lock)
        layout.addWidget(card)

        buttons = QHBoxLayout()
        self.save_restart_btn = QPushButton("Save & restart")
        self.save_restart_btn.setObjectName("Primary")
        self.save_restart_btn.clicked.connect(self._save_settings)
        reset = QPushButton("Reset all settings")
        reset.setObjectName("Danger")
        reset.clicked.connect(self._reset_config)
        buttons.addWidget(self.save_restart_btn); buttons.addWidget(reset); buttons.addStretch()
        layout.addLayout(buttons)
        layout.addStretch()
        return root

    def _load_settings(self):
        cfg = self.config_store.snapshot()
        camera = cfg.get("camera", {}); tracking = cfg.get("tracking", {}); action = cfg.get("action_settings", {}); face = cfg.get("face_guard", {})
        self.camera_index.setValue(int(camera.get("index", 0))); self.camera_width.setValue(int(camera.get("width", 960))); self.camera_height.setValue(int(camera.get("height", 540))); self.camera_fps.setValue(int(camera.get("fps", 30)))
        self.mirror.setChecked(bool(camera.get("mirror", True)))
        hand = str(cfg.get("runtime", {}).get("preferred_hand", "AUTO")).upper(); self.preferred_hand.setCurrentText(hand if hand in ("AUTO", "LEFT", "RIGHT") else "AUTO")
        self.multi_hand.setChecked(bool(cfg.get("runtime", {}).get("multi_hand_enabled", True)))
        self.face_guard.setChecked(bool(face.get("enabled", True))); self.show_face.setChecked(bool(face.get("show_face_box", True)))
        self.smoothing.setValue(float(tracking.get("smoothing_alpha", 0.45))); self.min_conf.setValue(float(tracking.get("gesture_min_confidence", 0.62))); self.activation.setValue(int(tracking.get("activation_delay_ms", 150))); self.release.setValue(int(tracking.get("release_delay_ms", 100)))
        self.cursor_joint.setCurrentIndex(max(0, self.cursor_joint.findData(int(action.get("cursor_joint", 8)))))
        self.margin_x.setValue(float(action.get("mapping_margin_x", 0.07))); self.margin_y.setValue(float(action.get("mapping_margin_y", 0.08))); self.cursor_smooth.setValue(float(action.get("cursor_smoothing", 0.34))); self.cursor_precision.setValue(float(action.get("cursor_precision", 1.0))); self.cursor_deadzone.setValue(float(action.get("cursor_deadzone_px", 1.25)))
        self.scroll_sensitivity.setValue(float(action.get("scroll_sensitivity", 150.0))); self.scroll_threshold.setValue(float(action.get("scroll_threshold", 0.003))); self.scroll_axis_lock.setValue(float(action.get("scroll_axis_lock", 0.72)))
        self._set_automation_visual(bool(cfg.get("runtime", {}).get("automation_enabled", False)))

    @staticmethod
    def _action_names() -> list[str]:
        return ["NONE", "LEFT_CLICK", "RIGHT_CLICK", "MIDDLE_CLICK", "MOUSE_MOVE", "SCROLL", "MEDIA_PLAY_PAUSE", "VOLUME_UP", "VOLUME_DOWN", "MUTE", "NEXT_WINDOW", "PREVIOUS_WINDOW", "NEXT_DESKTOP", "PREVIOUS_DESKTOP", "HOTKEY", "LAUNCH_APP"]

    def _refresh_mappings(self):
        mappings = self.config_store.get("mappings", {})
        gestures = list(mappings.keys())
        self.mapping_table.setRowCount(len(gestures))
        for row, gesture in enumerate(gestures):
            entry = mappings[gesture]
            self.mapping_table.setItem(row, 0, QTableWidgetItem(gesture))
            hand_filter = QComboBox(); hand_filter.addItems(["ANY", "LEFT", "RIGHT"]); hand_filter.setCurrentText(str(entry.get("hand", "ANY")).upper()); self.mapping_table.setCellWidget(row, 1, hand_filter)
            enabled = QCheckBox(); enabled.setChecked(bool(entry.get("enabled", False))); self.mapping_table.setCellWidget(row, 2, enabled)
            action = QComboBox(); action.addItems(self._action_names()); action.setCurrentText(str(entry.get("action", "NONE"))); self.mapping_table.setCellWidget(row, 3, action)
            mode = QComboBox(); mode.addItems(["ON_ENTER", "WHILE_ACTIVE"]); mode.setCurrentText(str(entry.get("mode", "ON_ENTER")).upper()); self.mapping_table.setCellWidget(row, 4, mode)
            self.mapping_table.setItem(row, 5, QTableWidgetItem(str(entry.get("cooldown_ms", 700))))
            payload_text = json.dumps(entry.get("payload", {}), separators=(",", ":"))
            self.mapping_table.setItem(row, 6, QTableWidgetItem(payload_text))
        self.mapping_table.resizeColumnsToContents()

    def _save_mappings(self):
        cfg = self.config_store.snapshot(); mappings = cfg.get("mappings", {})
        for row in range(self.mapping_table.rowCount()):
            gesture = self.mapping_table.item(row, 0).text()
            entry = mappings.setdefault(gesture, {})
            hand_filter = self.mapping_table.cellWidget(row, 1); enabled = self.mapping_table.cellWidget(row, 2); action = self.mapping_table.cellWidget(row, 3); mode = self.mapping_table.cellWidget(row, 4)
            entry["hand"] = hand_filter.currentText().strip().upper() if hand_filter else "ANY"
            entry["enabled"] = bool(enabled.isChecked()) if enabled else False
            entry["action"] = action.currentText().strip().upper() if action else "NONE"
            entry["mode"] = mode.currentText().strip().upper() if mode else "ON_ENTER"
            try: entry["cooldown_ms"] = max(0, int(self.mapping_table.item(row, 5).text()))
            except (ValueError, AttributeError): entry["cooldown_ms"] = 700
            raw_payload = self.mapping_table.item(row, 6).text().strip() if self.mapping_table.item(row, 6) else "{}"
            try:
                payload = json.loads(raw_payload or "{}")
                if not isinstance(payload, dict):
                    raise ValueError("payload must be a JSON object")
                entry["payload"] = payload
            except (json.JSONDecodeError, ValueError) as exc:
                QMessageBox.warning(self, "Invalid payload", f"{gesture}: {exc}")
                return
        cfg["mappings"] = mappings; self.config_store.replace(cfg); self._set_automation_visual(bool(cfg.get("runtime", {}).get("automation_enabled", False)))
        QMessageBox.information(self, "Saved", "Gesture mappings saved.")

    def _save_settings(self):
        cfg = self.config_store.snapshot()
        cfg["camera"].update({
            "index": self.camera_index.value(),
            "width": self.camera_width.value(),
            "height": self.camera_height.value(),
            "fps": self.camera_fps.value(),
            "mirror": self.mirror.isChecked(),
        })
        cfg["runtime"]["preferred_hand"] = self.preferred_hand.currentText()
        cfg["runtime"]["multi_hand_enabled"] = self.multi_hand.isChecked()
        cfg["face_guard"]["enabled"] = self.face_guard.isChecked()
        cfg["face_guard"]["show_face_box"] = self.show_face.isChecked()
        cfg["tracking"].update({
            "smoothing_alpha": self.smoothing.value(),
            "gesture_min_confidence": self.min_conf.value(),
            "activation_delay_ms": self.activation.value(),
            "release_delay_ms": self.release.value(),
        })
        cfg["action_settings"].update({
            "cursor_joint": int(self.cursor_joint.currentData()),
            "mapping_margin_x": self.margin_x.value(),
            "mapping_margin_y": self.margin_y.value(),
            "cursor_smoothing": self.cursor_smooth.value(),
            "cursor_precision": self.cursor_precision.value(),
            "cursor_deadzone_px": self.cursor_deadzone.value(),
            "scroll_sensitivity": self.scroll_sensitivity.value(),
            "scroll_threshold": self.scroll_threshold.value(),
            "scroll_axis_lock": self.scroll_axis_lock.value(),
        })
        self.config_store.replace(cfg)

        # These settings affect the process-wide vision stack. Restart the
        # actual application, not merely the camera thread. The relaunch
        # helper waits until this process has exited before starting main.py.
        self.save_restart_btn.setEnabled(False)
        self.save_restart_btn.setText("Restarting…")
        self.status_label.setText("Saving settings · restarting HandPilot…")
        QTimer.singleShot(50, self._restart_application)

    def _restart_application(self):
        try:
            self._stop_camera()
            request_application_restart(Path(__file__).resolve().parents[2], sys.argv[1:])
        except Exception as exc:
            self.save_restart_btn.setEnabled(True)
            self.save_restart_btn.setText("Save & restart")
            self.status_label.setText("Restart failed")
            self.error_message("Could not restart HandPilot", str(exc))
            return
        QApplication.instance().quit()

    def _reset_config(self):
        answer = QMessageBox.question(self, "Reset config", "Reset mappings and settings to the packaged defaults?")
        if answer != QMessageBox.StandardButton.Yes: return
        if self.config_store.path.exists(): self.config_store.path.unlink()
        self.config_store.replace(self.config_store._load()); self._load_settings(); self._refresh_mappings(); self._restart_camera()

    def _set_automation_visual(self, enabled: bool):
        self.automation_toggle.blockSignals(True); self.automation_toggle.setChecked(enabled); self.automation_toggle.setText("Automation ON" if enabled else "Automation OFF"); self.automation_toggle.blockSignals(False)
        self.mapping_summary.setText("Computer actions are enabled" if enabled else "Recognition only · computer actions disabled")

    @Slot()
    def _toggle_automation(self):
        enabled = self.automation_toggle.isChecked(); self.config_store.update_path("runtime.automation_enabled", enabled); self.automation_toggle.setText("Automation ON" if enabled else "Automation OFF")
        self.mapping_summary.setText("Computer actions are enabled" if enabled else "Recognition only · computer actions disabled")

    def _start_camera(self):
        if not self.hand_model_path.exists() or not self.face_model_path.exists():
            self.error_message("Models missing", "Run:\n\npython tools/download_model.py")
            return
        self._sync_screen_geometry()
        self.worker = CameraThread(self.config_store, self.hand_model_path, self.face_model_path)
        self.worker.frame_ready.connect(self._on_frame); self.worker.state_changed.connect(self.status_label.setText); self.worker.error.connect(self._on_error); self.worker.action_error.connect(self._on_action_error)
        self.worker.start()

    def _restart_camera(self):
        self._stop_camera(); self._start_camera()

    def _stop_camera(self):
        if self.worker is None: return
        self.worker.stop(); self.worker.wait(3000); self.worker = None
        self.action_router.reset()

    @Slot(object)
    def _on_frame(self, result: FrameResult):
        cfg = self.config_store.snapshot()
        primary_index = result.prediction.hand_index if result.hands and result.prediction.hand_index < len(result.hands) else None
        frame = draw_overlay(
            result.frame_bgr,
            result.hands,
            result.faces,
            result.cursor,
            result.stable,
            result.status,
            primary_index,
            bool(cfg.get("face_guard", {}).get("show_face_box", True)),
            result.hand_states,
        )
        self.video.setPixmap(self._frame_to_pixmap(frame))

        # CameraThread is vision-only. Desktop input is deliberately executed
        # from this MainWindow slot, which runs on the Qt GUI/main thread. This
        # avoids macOS 27 HIToolbox/TIS queue assertions in pynput keyboard.
        try:
            multi_hand = bool(cfg.get("runtime", {}).get("multi_hand_enabled", True))
            action_states = result.hand_states if multi_hand else ([] if primary_index is None else [result.hand_states[primary_index]] if primary_index < len(result.hand_states) else [])
            self.action_router.update_all(action_states)
        except Exception as exc:
            self._on_action_error(f"Desktop action error: {exc}")

        self.gesture.setText(result.stable.gesture.value.replace("_", " "))
        self.gesture_conf.setText(f"{result.stable.confidence * 100:.0f}%")
        self.fps_label.setText(f"{result.fps:.1f}")
        self.track_label.setText(f"{result.tracking_confidence * 100:.0f}%")
        self.face_label.setText(f"{result.face_confidence * 100:.0f}%")
        self.hands_label.setText(str(len(result.hands)))
        self.status_label.setText(result.status)
        if result.prediction.pinch_ratio < 1.0:
            self.pinch_label.setText(f"Pinch distance: {result.prediction.pinch_ratio:.2f}× palm width")
        else:
            self.pinch_label.setText("Pinch: —")
        self.cursor_label.setText(f"Cursor: {int(result.cursor.x)}, {int(result.cursor.y)}" if result.cursor.valid else "Cursor: paused")

        if result.hand_states:
            role_parts = []
            for state in result.hand_states:
                label = state.hand.handedness.title() if state.hand.handedness else state.key
                gesture = state.stable.gesture.value.replace("_", " ")
                mapping = cfg.get("mappings", {}).get(state.stable.gesture.value, {})
                action = str(mapping.get("action", "NONE")).upper() if mapping.get("enabled", False) else "OFF"
                if state.hand.face_blocked:
                    action = "FACE PAUSED"
                role_parts.append(f"{label}: {gesture} → {action}")
            self.hand_roles_label.setText("Hands:  " + "   |   ".join(role_parts))
        else:
            self.hand_roles_label.setText("Hands: —")

        if primary_index is not None:
            hand = result.hands[primary_index]
            self.control_hand_label.setText(f"Primary: {hand.handedness} · {hand.handedness_score * 100:.0f}%")
            self.face_guard_label.setText("Face guard: BLOCKED" if hand.face_blocked else "Face guard: clear")
            self.face_guard_label.setObjectName("StatusWarn" if hand.face_blocked else "StatusGood")
            self.face_guard_label.style().unpolish(self.face_guard_label)
            self.face_guard_label.style().polish(self.face_guard_label)
        else:
            self.control_hand_label.setText("No primary hand")
            self.face_guard_label.setText("Face guard: waiting")

    @staticmethod
    def _frame_to_pixmap(frame):
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB); h, w, channels = rgb.shape; image = QImage(rgb.data, w, h, channels * w, QImage.Format.Format_RGB888); return QPixmap.fromImage(image.copy())

    @Slot(str)
    def _on_error(self, message): self.error_message("HandPilot error", message)

    @Slot(str)
    def _on_action_error(self, message): self.status_label.setText(message)

    def error_message(self, title, message): QMessageBox.critical(self, title, message)

    def closeEvent(self, event): self._stop_camera(); event.accept()
