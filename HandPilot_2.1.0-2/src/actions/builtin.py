from __future__ import annotations

import math
import shlex
import subprocess
import sys
from typing import Any

from pynput import keyboard, mouse

from src.actions.base import Action
from src.actions.cursor_mapper import CursorMapper
from src.actions.motion import FingertipMotionTracker
from src.core.models import HandData


_SPECIAL_KEYS = (
    "alt", "cmd", "ctrl", "shift", "tab", "space", "enter", "esc",
    "left", "right", "up", "down", "page_up", "page_down",
    "home", "end", "backspace", "delete", "media_play_pause",
    "media_volume_up", "media_volume_down", "media_volume_mute", "media_next",
    "media_previous", "media_stop",
)
_KEY_ALIASES = {name: getattr(keyboard.Key, name) for name in _SPECIAL_KEYS if hasattr(keyboard.Key, name)}


class InputController:
    def __init__(self):
        self.keyboard = keyboard.Controller()
        self.mouse = mouse.Controller()

    def key_from_name(self, value: str):
        normalized = str(value).strip()
        lower = normalized.lower()
        if lower in _KEY_ALIASES:
            return _KEY_ALIASES[lower]
        if len(normalized) == 1:
            return normalized
        if lower.startswith("f") and lower[1:].isdigit():
            return getattr(keyboard.Key, lower)
        raise ValueError(f"Unknown key: {value}")

    @staticmethod
    def screen_size_from_config(config: dict) -> tuple[int, int]:
        screen = config.get("screen", {})
        return max(1, int(screen.get("width", 1920))), max(1, int(screen.get("height", 1080)))


class KeyActionMixin:
    def _press_keys(self, keys: list[str]):
        controller: InputController = self.controller
        resolved = [controller.key_from_name(key) for key in keys]
        for key in resolved:
            controller.keyboard.press(key)
        for key in reversed(resolved):
            controller.keyboard.release(key)


class MediaKeyAction(Action, KeyActionMixin):
    def __init__(self, controller: InputController, key_name: str, name: str):
        self.controller = controller
        self.key_name = key_name
        self.name = name

    def execute(self, payload=None):
        self._press_keys([self.key_name])


class MouseClickAction(Action):
    def __init__(self, controller: InputController, button: str):
        self.controller = controller
        self.button = getattr(mouse.Button, button)
        self.name = f"{button.upper()}_CLICK"

    def execute(self, payload=None):
        self.controller.mouse.click(self.button, 1)


class HotkeyAction(Action, KeyActionMixin):
    name = "HOTKEY"

    def __init__(self, controller: InputController):
        self.controller = controller

    def execute(self, payload=None):
        keys = list((payload or {}).get("keys", []))
        if not keys:
            raise ValueError("HOTKEY requires payload.keys")
        self._press_keys(keys)


class LaunchAppAction(Action):
    name = "LAUNCH_APP"

    def execute(self, payload=None):
        app = str((payload or {}).get("app", "")).strip()
        if not app:
            raise ValueError("LAUNCH_APP requires payload.app")
        if sys.platform == "darwin":
            subprocess.Popen(["open", "-a", app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif sys.platform.startswith("win"):
            subprocess.Popen(f'start "" "{app}"', shell=True)
        else:
            subprocess.Popen(shlex.split(app), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class MouseMoveAction(Action):
    name = "MOUSE_MOVE"

    def __init__(self, controller: InputController):
        self.controller = controller
        self.deadzone_px = 1.25
        self._last_screen_by_hand: dict[str, tuple[int, int]] = {}

    def configure(self, config: dict):
        settings = config.get("action_settings", {})
        self.deadzone_px = max(0.0, float(settings.get("cursor_deadzone_px", 1.25)))

    def reset(self):
        self._last_screen_by_hand.clear()

    def reset_for_hand(self, hand_key: str):
        self._reset_hand(hand_key)

    def _reset_hand(self, hand_key: str):
        self._last_screen_by_hand.pop(hand_key, None)

    def update(self, payload=None):
        payload = payload or {}
        hand: HandData | None = payload.get("hand")
        hand_key = str(payload.get("hand_key", "HAND_0"))
        target = payload.get("cursor_target")
        if hand is None or hand.face_blocked or target is None:
            self._reset_hand(hand_key)
            return
        target = (int(target[0]), int(target[1]))
        last = self._last_screen_by_hand.get(hand_key)
        if last is not None:
            dx = target[0] - last[0]
            dy = target[1] - last[1]
            if abs(dx) <= self.deadzone_px and abs(dy) <= self.deadzone_px:
                return
        self.controller.mouse.position = target
        self._last_screen_by_hand[hand_key] = target

    def execute(self, payload=None):
        self.update(payload)


class ScrollAction(Action):
    name = "SCROLL"

    def __init__(self, controller: InputController):
        self.controller = controller
        self.sensitivity = 150.0
        self.min_motion = 0.003
        self.axis_lock = 0.72
        self.tracker_smoothing = 0.50
        self.tracker_deadzone = 0.0018
        self._trackers: dict[str, FingertipMotionTracker] = {}
        self._accumulators: dict[str, float] = {}
        self._last_points: dict[str, tuple[float, float]] = {}

    def configure(self, config: dict):
        settings = config.get("action_settings", {})
        self.sensitivity = max(10.0, float(settings.get("scroll_sensitivity", 150.0)))
        self.min_motion = max(0.0005, float(settings.get("scroll_threshold", 0.003)))
        self.axis_lock = max(0.0, min(1.0, float(settings.get("scroll_axis_lock", 0.72))))
        self.tracker_smoothing = max(0.02, min(1.0, float(settings.get("scroll_tracking_smoothing", 0.50))))
        self.tracker_deadzone = max(0.0, float(settings.get("scroll_motion_deadzone", 0.0018)))
        for tracker in self._trackers.values():
            tracker.smoothing = self.tracker_smoothing
            tracker.deadzone = self.tracker_deadzone

    def _reset_hand(self, hand_key: str):
        tracker = self._trackers.pop(hand_key, None)
        if tracker is not None:
            tracker.reset()
        self._accumulators.pop(hand_key, None)
        self._last_points.pop(hand_key, None)

    def reset(self):
        for tracker in self._trackers.values():
            tracker.reset()
        self._trackers.clear()
        self._accumulators.clear()
        self._last_points.clear()

    def reset_for_hand(self, hand_key: str):
        self._reset_hand(hand_key)

    def execute(self, payload=None):
        self.update(payload)

    def update(self, payload=None):
        payload = payload or {}
        hand: HandData | None = payload.get("hand")
        hand_key = str(payload.get("hand_key", "HAND_0"))
        if hand is None or hand.face_blocked:
            self._reset_hand(hand_key)
            return

        tracker = self._trackers.get(hand_key)
        if tracker is None:
            tracker = FingertipMotionTracker(self.tracker_smoothing, self.tracker_deadzone)
            self._trackers[hand_key] = tracker
        motion = tracker.update(hand, joint_index=8)
        if not motion.valid:
            return

        previous = self._last_points.get(hand_key)
        if previous is None:
            self._last_points[hand_key] = (motion.x, motion.y)
            return

        dx = motion.x - previous[0]
        dy = motion.y - previous[1]
        self._last_points[hand_key] = (motion.x, motion.y)

        if abs(dy) < self.min_motion:
            return
        if abs(dy) < abs(dx) * self.axis_lock:
            return

        accumulator = self._accumulators.get(hand_key, 0.0)
        accumulator += -dy * self.sensitivity
        whole = math.trunc(accumulator)
        if whole == 0:
            self._accumulators[hand_key] = accumulator
            return
        whole = max(-12, min(12, whole))
        accumulator -= whole
        self._accumulators[hand_key] = accumulator
        self.controller.mouse.scroll(0, whole)


class SystemShortcutAction(Action):
    """Platform-aware window/desktop switching using normal OS shortcuts."""

    _SHORTCUTS = {
        "NEXT_WINDOW": {"darwin": ["cmd", "tab"], "win32": ["alt", "tab"], "linux": ["alt", "tab"]},
        "PREVIOUS_WINDOW": {"darwin": ["cmd", "shift", "tab"], "win32": ["alt", "shift", "tab"], "linux": ["alt", "shift", "tab"]},
        "NEXT_DESKTOP": {"darwin": ["ctrl", "right"], "win32": ["cmd", "ctrl", "right"], "linux": ["ctrl", "alt", "right"]},
        "PREVIOUS_DESKTOP": {"darwin": ["ctrl", "left"], "win32": ["cmd", "ctrl", "left"], "linux": ["ctrl", "alt", "left"]},
    }

    def __init__(self, controller: InputController, name: str):
        self.controller = controller
        self.name = name

    def execute(self, payload=None):
        platform_key = "win32" if sys.platform.startswith("win") else "darwin" if sys.platform == "darwin" else "linux"
        keys = self._SHORTCUTS[self.name][platform_key]
        resolved = [self.controller.key_from_name(key) for key in keys]
        for key in resolved:
            self.controller.keyboard.press(key)
        for key in reversed(resolved):
            self.controller.keyboard.release(key)


class NoOpAction(Action):
    name = "NONE"

    def execute(self, payload=None):
        return
