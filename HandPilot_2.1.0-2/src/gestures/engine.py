from __future__ import annotations

import time
from dataclasses import dataclass, field
from collections.abc import Iterable

from src.core.models import GestureName, GesturePrediction, HandControlState, HandData, StableGesture
from src.gestures.classifier import GestureClassifier, RuleBasedClassifier
from src.vision.face_guard import FaceGuard
from src.vision.smoothing import LandmarkSmoother


class TemporalGestureStabilizer:
    """Candidate -> stable state machine with activation and release delays."""

    def __init__(self, min_confidence=0.60, activation_delay_ms=160, release_delay_ms=90, lost_hand_grace_ms=220):
        self.min_confidence = min_confidence
        self.activation_delay_ms = activation_delay_ms
        self.release_delay_ms = release_delay_ms
        self.lost_hand_grace_ms = lost_hand_grace_ms
        self._candidate = GestureName.NONE
        self._candidate_since = time.monotonic()
        self._stable = GestureName.NONE
        self._stable_confidence = 0.0
        self._last_seen = time.monotonic()
        self._release_since: float | None = None

    def reset(self) -> None:
        self.__init__(self.min_confidence, self.activation_delay_ms, self.release_delay_ms, self.lost_hand_grace_ms)

    def update(self, prediction: GesturePrediction) -> StableGesture:
        now = time.monotonic()
        valid = prediction.gesture != GestureName.NONE and prediction.confidence >= self.min_confidence

        if valid:
            self._last_seen = now
            self._release_since = None
            if prediction.gesture != self._candidate:
                self._candidate = prediction.gesture
                self._candidate_since = now
            age_ms = (now - self._candidate_since) * 1000.0
            changed = False
            if age_ms >= self.activation_delay_ms and self._stable != self._candidate:
                self._stable = self._candidate
                self._stable_confidence = prediction.confidence
                changed = True
            elif self._stable == self._candidate:
                self._stable_confidence = 0.82 * self._stable_confidence + 0.18 * prediction.confidence
            return StableGesture(self._stable, self._stable_confidence, age_ms, changed, changed)

        if self._stable != GestureName.NONE:
            if self._release_since is None:
                self._release_since = now
            release_age = (now - self._release_since) * 1000.0
            if release_age <= self.lost_hand_grace_ms or release_age < self.release_delay_ms:
                return StableGesture(
                    self._stable,
                    max(0.0, self._stable_confidence * 0.98),
                    0.0,
                    False,
                    False,
                )

        was_stable = self._stable
        self._stable = GestureName.NONE
        self._stable_confidence = 0.0
        self._candidate = GestureName.NONE
        self._candidate_since = now
        self._release_since = None
        return StableGesture(GestureName.NONE, 0.0, 0.0, was_stable, False)


@dataclass
class _HandState:
    smoother: LandmarkSmoother
    stabilizer: TemporalGestureStabilizer
    last_center: tuple[float, float] | None = None
    last_seen: float = field(default_factory=time.monotonic)


class GestureEngine:
    """Independent gesture state machines for up to two simultaneous hands."""

    def __init__(self, config: dict, classifier: GestureClassifier | None = None):
        self.classifier = classifier or RuleBasedClassifier()
        self.face_guard = FaceGuard(config)
        self._states: dict[str, _HandState] = {}
        self._preferred_hand = "AUTO"
        self._last_primary_key: str | None = None
        self._config = config
        self.update_config(config)

    def _new_state(self, config: dict) -> _HandState:
        tracking = config.get("tracking", {})
        return _HandState(
            smoother=LandmarkSmoother(float(tracking.get("smoothing_alpha", 0.45))),
            stabilizer=TemporalGestureStabilizer(
                float(tracking.get("gesture_min_confidence", 0.60)),
                int(tracking.get("activation_delay_ms", 160)),
                int(tracking.get("release_delay_ms", 90)),
                int(tracking.get("lost_hand_grace_ms", 220)),
            ),
        )

    def update_config(self, config: dict) -> None:
        self._config = config
        tracking = config.get("tracking", {})
        for state in self._states.values():
            state.smoother.alpha = max(0.05, min(1.0, float(tracking.get("smoothing_alpha", 0.45))))
            state.stabilizer.min_confidence = float(tracking.get("gesture_min_confidence", 0.60))
            state.stabilizer.activation_delay_ms = int(tracking.get("activation_delay_ms", 160))
            state.stabilizer.release_delay_ms = int(tracking.get("release_delay_ms", 90))
            state.stabilizer.lost_hand_grace_ms = int(tracking.get("lost_hand_grace_ms", 220))
        self._preferred_hand = str(config.get("runtime", {}).get("preferred_hand", "AUTO")).upper()
        self.face_guard.update_config(config)

    @staticmethod
    def _canonical_handedness(hand: HandData) -> str:
        label = hand.handedness.upper()
        if label.startswith("LEFT"):
            return "LEFT"
        if label.startswith("RIGHT"):
            return "RIGHT"
        return ""

    def _assign_keys(self, hands: list[HandData]) -> list[str]:
        """Prefer MediaPipe handedness; fall back to nearest tracked slot."""
        result: list[str] = [""] * len(hands)
        used: set[str] = set()

        # First pass: reliable LEFT/RIGHT identity.
        for idx, hand in enumerate(hands):
            key = self._canonical_handedness(hand)
            if key and key not in used:
                result[idx] = key
                used.add(key)

        # Second pass: anonymous identities. This mainly covers temporary
        # handedness loss; nearest previous anonymous/side slot wins.
        candidates = [key for key in self._states if key.startswith("HAND_") and key not in used]
        for idx, hand in enumerate(hands):
            if result[idx]:
                continue
            best_key = None
            best_distance = float("inf")
            for key in candidates:
                previous = self._states[key].last_center
                if previous is None:
                    continue
                distance = (hand.center_x - previous[0]) ** 2 + (hand.center_y - previous[1]) ** 2
                if distance < best_distance:
                    best_key = key
                    best_distance = distance
            if best_key is None:
                for slot in range(2):
                    candidate = f"HAND_{slot}"
                    if candidate not in used:
                        best_key = candidate
                        break
            if best_key is None:
                best_key = f"HAND_{idx}"
            result[idx] = best_key
            used.add(best_key)
            if best_key in candidates:
                candidates.remove(best_key)

        return result

    def _hand_state(self, key: str) -> _HandState:
        state = self._states.get(key)
        if state is None:
            state = self._new_state(self._config)
            self._states[key] = state
        state.last_seen = time.monotonic()
        return state

    def process_all(self, hands: Iterable[HandData], faces) -> list[HandControlState]:
        hands = list(hands)
        for hand in hands:
            hand.face_blocked = self.face_guard.blocked(hand, faces)

        keys = self._assign_keys(hands)
        controls: list[HandControlState] = []
        seen_keys = set(keys)
        now = time.monotonic()

        for index, (key, hand) in enumerate(zip(keys, hands, strict=False)):
            state = self._hand_state(key)
            state.last_center = (hand.center_x, hand.center_y)
            if hand.face_blocked:
                state.smoother.reset()
                prediction = GesturePrediction(hand_index=index)
                stable = state.stabilizer.update(prediction)
            else:
                hand.landmarks = state.smoother.smooth(hand.landmarks, hand.handedness)
                gesture, confidence, count, ratio, features = self.classifier.classify(hand.landmarks)
                prediction = GesturePrediction(
                    GestureName(gesture) if gesture in GestureName._value2member_map_ else GestureName.NONE,
                    confidence,
                    count,
                    index,
                    ratio,
                    features,
                )
                stable = state.stabilizer.update(prediction)
            controls.append(HandControlState(key, hand, prediction, stable))

        # Forget stale anonymous slots after a short absence; LEFT/RIGHT state
        # is retained longer because handedness provides a stable identity.
        for key in list(self._states):
            if key.startswith("HAND_") and key not in seen_keys:
                if now - self._states[key].last_seen > 1.0:
                    del self._states[key]

        return controls

    def select_primary(self, controls: list[HandControlState]) -> int | None:
        if not controls:
            self._last_primary_key = None
            return None

        preferred = self._preferred_hand
        if preferred in ("LEFT", "RIGHT"):
            for index, control in enumerate(controls):
                if self._canonical_handedness(control.hand) == preferred:
                    self._last_primary_key = control.key
                    return index

        # Keep the previously primary hand if it is still present.
        if self._last_primary_key:
            for index, control in enumerate(controls):
                if control.key == self._last_primary_key:
                    return index

        # Prefer whichever hand currently has the configured mouse-move gesture.
        mapping = self._config.get("mappings", {})
        for index, control in enumerate(controls):
            entry = mapping.get(control.stable.gesture.value, {})
            if str(entry.get("action", "")).upper() == "MOUSE_MOVE" and entry.get("enabled", False):
                self._last_primary_key = control.key
                return index

        index = max(range(len(controls)), key=lambda i: controls[i].hand.handedness_score)
        self._last_primary_key = controls[index].key
        return index

    def process(self, hands: Iterable[HandData], faces):
        """Backward-compatible single-primary view used by older callers."""
        hand_list = list(hands)
        controls = self.process_all(hand_list, faces)
        primary_index = self.select_primary(controls)
        if primary_index is None:
            prediction = GesturePrediction()
            stable = StableGesture()
            return prediction, stable, hand_list, None
        primary = controls[primary_index]
        return primary.prediction, primary.stable, [control.hand for control in controls], primary_index
