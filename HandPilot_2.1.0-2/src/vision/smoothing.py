from __future__ import annotations

import math


class LandmarkSmoother:
    """Per-hand exponential smoothing with reset on a new hand identity."""

    def __init__(self, alpha: float = 0.45):
        self.alpha = max(0.05, min(1.0, alpha))
        self._previous: list[tuple[float, float, float]] | None = None
        self._handedness: str | None = None

    def reset(self) -> None:
        self._previous = None
        self._handedness = None

    def smooth(self, landmarks: list[tuple[float, float, float]], handedness: str = "Unknown") -> list[tuple[float, float, float]]:
        if self._previous is None or len(self._previous) != len(landmarks) or (
            self._handedness not in (None, "Unknown")
            and handedness not in ("Unknown", self._handedness)
        ):
            self._previous = list(landmarks)
            self._handedness = handedness
            return list(landmarks)

        self._handedness = handedness if handedness != "Unknown" else self._handedness
        a = self.alpha
        result = [tuple(a * n + (1.0 - a) * o for o, n in zip(old, new)) for old, new in zip(self._previous, landmarks)]
        self._previous = result
        return result

    @staticmethod
    def motion(previous: tuple[float, float], current: tuple[float, float]) -> float:
        return math.hypot(current[0] - previous[0], current[1] - previous[1])
