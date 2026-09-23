from __future__ import annotations

from typing import Protocol, Sequence

from src.gestures.rules import classify as classify_rules


class GestureClassifier(Protocol):
    def classify(self, landmarks: Sequence[tuple[float, float, float]]) -> tuple[str, float, int, float, dict[str, float]]:
        ...


class RuleBasedClassifier:
    """Fast geometry classifier. Replace this with a learned classifier later."""

    def classify(self, landmarks):
        return classify_rules(landmarks)
