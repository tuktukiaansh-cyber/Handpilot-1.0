from __future__ import annotations

import time
from collections.abc import Callable, Iterable

from src.actions.base import Action
from src.actions.builtin import (
    HotkeyAction,
    InputController,
    LaunchAppAction,
    MediaKeyAction,
    MouseClickAction,
    MouseMoveAction,
    ScrollAction,
    SystemShortcutAction,
)
from src.core.models import GestureName, GesturePrediction, HandControlState, HandData


class ActionRouter:
    """Executes mappings independently for each detected hand."""

    def __init__(self, config: dict, on_error: Callable[[str], None] | None = None):
        self.controller = InputController()
        self._on_error = on_error
        self.actions: dict[str, Action] = {
            "LEFT_CLICK": MouseClickAction(self.controller, "left"),
            "RIGHT_CLICK": MouseClickAction(self.controller, "right"),
            "MIDDLE_CLICK": MouseClickAction(self.controller, "middle"),
            "MEDIA_PLAY_PAUSE": MediaKeyAction(self.controller, "media_play_pause", "MEDIA_PLAY_PAUSE"),
            "VOLUME_UP": MediaKeyAction(self.controller, "media_volume_up", "VOLUME_UP"),
            "VOLUME_DOWN": MediaKeyAction(self.controller, "media_volume_down", "VOLUME_DOWN"),
            "MUTE": MediaKeyAction(self.controller, "media_volume_mute", "MUTE"),
            "HOTKEY": HotkeyAction(self.controller),
            "LAUNCH_APP": LaunchAppAction(),
            "MOUSE_MOVE": MouseMoveAction(self.controller),
            "SCROLL": ScrollAction(self.controller),
            "NEXT_WINDOW": SystemShortcutAction(self.controller, "NEXT_WINDOW"),
            "PREVIOUS_WINDOW": SystemShortcutAction(self.controller, "PREVIOUS_WINDOW"),
            "NEXT_DESKTOP": SystemShortcutAction(self.controller, "NEXT_DESKTOP"),
            "PREVIOUS_DESKTOP": SystemShortcutAction(self.controller, "PREVIOUS_DESKTOP"),
        }
        self._mapping: dict = {}
        self._cooldowns: dict[str, float] = {}
        self._enabled = False
        self._last_gesture_by_hand: dict[str, GestureName] = {}
        self.update_config(config)

    def update_config(self, config: dict) -> None:
        self._mapping = config.get("mappings", {})
        self._enabled = bool(config.get("runtime", {}).get("automation_enabled", False))
        for action in self.actions.values():
            if hasattr(action, "configure"):
                action.configure(config)  # type: ignore[attr-defined]

    def _can_fire(self, hand_key: str, gesture: GestureName, cooldown_ms: int) -> bool:
        now = time.monotonic()
        key = f"{hand_key}:{gesture.value}"
        last = self._cooldowns.get(key, -1e9)
        if (now - last) * 1000.0 < max(0, cooldown_ms):
            return False
        self._cooldowns[key] = now
        return True

    def _mapping_allows_hand(self, mapping: dict, hand: HandData) -> bool:
        requested = str(mapping.get("hand", "ANY")).upper()
        if requested in ("", "ANY", "AUTO", "BOTH"):
            return True
        label = hand.handedness.upper()
        return (requested == "LEFT" and label.startswith("LEFT")) or (requested == "RIGHT" and label.startswith("RIGHT"))

    def _safe_reset_previous(self, hand_key: str, current: GestureName) -> None:
        previous = self._last_gesture_by_hand.get(hand_key, GestureName.NONE)
        if current == previous:
            return
        previous_mapping = self._mapping.get(previous.value, {})
        previous_action = self.actions.get(str(previous_mapping.get("action", "")).upper())
        if previous_action is not None:
            reset_for_hand = getattr(previous_action, "reset_for_hand", None)
            if callable(reset_for_hand):
                reset_for_hand(hand_key)
            else:
                previous_action.reset()
        self._last_gesture_by_hand[hand_key] = current

    def update_all(self, controls: Iterable[HandControlState]) -> None:
        controls = list(controls)
        seen = {control.key for control in controls}

        # Reset motion actions for hands that disappeared entirely.
        for hand_key in set(self._last_gesture_by_hand) - seen:
            previous = self._last_gesture_by_hand.pop(hand_key)
            mapping = self._mapping.get(previous.value, {})
            action = self.actions.get(str(mapping.get("action", "")).upper())
            if action is not None:
                reset_for_hand = getattr(action, "reset_for_hand", None)
                if callable(reset_for_hand):
                    reset_for_hand(hand_key)
                else:
                    action.reset()

        for control in controls:
            self.update_hand(control)

    def update_hand(self, control: HandControlState) -> None:
        hand_key = control.key
        gesture = control.stable.gesture
        self._safe_reset_previous(hand_key, gesture)

        if not self._enabled or gesture == GestureName.NONE or control.hand.face_blocked:
            return

        mapping = self._mapping.get(gesture.value, {})
        if not mapping or not mapping.get("enabled", False):
            return
        if not self._mapping_allows_hand(mapping, control.hand):
            return

        action_name = str(mapping.get("action", "")).upper()
        action = self.actions.get(action_name)
        if action is None:
            self._report(f"Unknown action '{action_name}' for {gesture.value}")
            return

        mode = str(mapping.get("mode", "ON_ENTER")).upper()
        payload = dict(mapping.get("payload", {}))
        payload.update({
            "hand": control.hand,
            "hand_key": hand_key,
            "prediction": control.prediction,
            "stable": control.stable,
            "cursor_target": (int(control.cursor.x), int(control.cursor.y)) if control.cursor.valid else None,
        })
        cooldown_ms = int(mapping.get("cooldown_ms", 700))

        try:
            if mode == "ON_ENTER":
                if control.stable.changed and self._can_fire(hand_key, gesture, cooldown_ms):
                    action.execute(payload)
            elif mode == "WHILE_ACTIVE":
                if action_name in ("MOUSE_MOVE", "SCROLL"):
                    action.update(payload)
                elif self._can_fire(hand_key, gesture, cooldown_ms):
                    action.update(payload)
        except Exception as exc:
            self._report(f"{action_name} failed for {hand_key}: {exc}")


    def reset(self) -> None:
        """Reset per-hand action state without touching the OS input controller."""
        self._cooldowns.clear()
        self._last_gesture_by_hand.clear()
        for action in self.actions.values():
            reset = getattr(action, "reset", None)
            if callable(reset):
                reset()

    # Compatibility with V2 callers.
    def update(self, gesture, changed, hands, prediction, cursor_target=None) -> None:
        hand = hands[prediction.hand_index] if hands and prediction.hand_index < len(hands) else (hands[0] if hands else None)
        if hand is None:
            return
        key = "LEFT" if hand.handedness.upper().startswith("LEFT") else "RIGHT" if hand.handedness.upper().startswith("RIGHT") else "HAND_0"
        from src.core.models import StableGesture
        control = HandControlState(
            key,
            hand,
            prediction,
            StableGesture(gesture, prediction.confidence, 0.0, changed, changed),
        )
        if cursor_target is not None:
            control.cursor.x, control.cursor.y = cursor_target
            control.cursor.valid = True
        self.update_hand(control)

    def _report(self, message: str) -> None:
        if self._on_error:
            self._on_error(message)
