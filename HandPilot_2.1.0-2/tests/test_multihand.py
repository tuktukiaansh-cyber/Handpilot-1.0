from __future__ import annotations

import pytest

from src.core.models import GestureName, GesturePrediction, HandControlState, HandData, StableGesture


class FakeMouse:
    def __init__(self):
        self.position = (0, 0)
        self.clicks: list[str] = []
        self.scrolls: list[tuple[int, int]] = []

    def click(self, button, count=1):
        self.clicks.extend([getattr(button, "name", str(button))] * count)

    def scroll(self, x, y):
        self.scrolls.append((x, y))


class FakeKeyboard:
    def press(self, key):
        pass

    def release(self, key):
        pass


class FakeController:
    def __init__(self):
        self.mouse = FakeMouse()
        self.keyboard = FakeKeyboard()


def make_hand(label: str, x: float, y: float) -> HandData:
    points = [(x, y, 0.0) for _ in range(21)]
    points[8] = (x, y, 0.0)
    return HandData(points, label, 0.95, x, y, 0.95, False)


def make_state(key: str, gesture: GestureName, hand: HandData, changed: bool = True) -> HandControlState:
    prediction = GesturePrediction(gesture, 0.95, 1, hand_index=hand.source_index)
    stable = StableGesture(gesture, 0.95, 200.0, changed, changed)
    return HandControlState(key, hand, prediction, stable)


def test_two_hands_can_move_and_click_independently(monkeypatch):
    pytest.importorskip("pynput")
    import src.actions.executor as executor

    fake = FakeController()
    monkeypatch.setattr(executor, "InputController", lambda: fake)

    from src.actions.executor import ActionRouter

    config = {
        "runtime": {"automation_enabled": True, "multi_hand_enabled": True},
        "mappings": {
            "ONE": {"enabled": True, "action": "MOUSE_MOVE", "mode": "WHILE_ACTIVE", "cooldown_ms": 0},
            "PINCH": {"enabled": True, "action": "LEFT_CLICK", "mode": "ON_ENTER", "cooldown_ms": 1000},
        },
        "action_settings": {"cursor_deadzone_px": 0.0, "scroll_sensitivity": 150.0},
    }
    router = ActionRouter(config)

    right = make_hand("Right", 0.80, 0.20)
    right.source_index = 0
    right_state = make_state("RIGHT", GestureName.ONE, right, changed=False)
    right_state.cursor.x, right_state.cursor.y = 1200, 300
    right_state.cursor.valid = True

    left = make_hand("Left", 0.25, 0.60)
    left.source_index = 1
    left_state = make_state("LEFT", GestureName.PINCH, left, changed=True)

    router.update_all([right_state, left_state])

    assert fake.mouse.position == (1200, 300)
    assert fake.mouse.clicks == ["left"]


def test_two_same_gestures_have_independent_cooldowns(monkeypatch):
    pytest.importorskip("pynput")
    import src.actions.executor as executor

    fake = FakeController()
    monkeypatch.setattr(executor, "InputController", lambda: fake)

    from src.actions.executor import ActionRouter

    config = {
        "runtime": {"automation_enabled": True, "multi_hand_enabled": True},
        "mappings": {
            "PINCH": {"enabled": True, "action": "LEFT_CLICK", "mode": "ON_ENTER", "cooldown_ms": 5000},
        },
    }
    router = ActionRouter(config)

    left = make_hand("Left", 0.2, 0.5); left.source_index = 0
    right = make_hand("Right", 0.8, 0.5); right.source_index = 1

    router.update_all([
        make_state("LEFT", GestureName.PINCH, left, True),
        make_state("RIGHT", GestureName.PINCH, right, True),
    ])

    assert fake.mouse.clicks == ["left", "left"]


def test_gesture_engine_keeps_independent_left_right_states():
    from src.gestures.engine import GestureEngine

    class FakeClassifier:
        def classify(self, points):
            return ("ONE" if points[0][0] < 0.5 else "TWO", 0.95, 1, 1.0, {})

    config = {
        "tracking": {
            "smoothing_alpha": 1.0,
            "gesture_min_confidence": 0.5,
            "activation_delay_ms": 0,
            "release_delay_ms": 0,
            "lost_hand_grace_ms": 0,
        },
        "face_guard": {"enabled": False},
        "runtime": {"preferred_hand": "AUTO"},
        "mappings": {},
    }
    engine = GestureEngine(config, classifier=FakeClassifier())
    left = make_hand("Left", 0.2, 0.5)
    right = make_hand("Right", 0.8, 0.5)
    controls = engine.process_all([left, right], [])

    assert [control.key for control in controls] == ["LEFT", "RIGHT"]
    assert [control.stable.gesture for control in controls] == [GestureName.ONE, GestureName.TWO]

    # Change only the left hand. The right hand's stable gesture must remain TWO.
    left2 = make_hand("Left", 0.25, 0.5)
    right2 = make_hand("Right", 0.8, 0.5)
    controls2 = engine.process_all([left2, right2], [])
    assert controls2[1].stable.gesture == GestureName.TWO
