from __future__ import annotations

import math
from dataclasses import dataclass
from time import monotonic

from src.core.models import HandData


@dataclass(slots=True)
class TipMotion:
    """Filtered motion of a single landmark, expressed in normalized camera units."""

    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    speed: float = 0.0
    valid: bool = False
    timestamp: float = 0.0


class FingertipMotionTracker:
    """Tracks one joint over time instead of treating each frame independently.

    The important point is deliberately the *index fingertip* (landmark #8).
    This gives both air-mouse and two-finger scrolling a stable, intuitive control
    point at the top of the raised finger.
    """

    def __init__(self, smoothing: float = 0.45, deadzone: float = 0.0025):
        self.smoothing = max(0.02, min(1.0, float(smoothing)))
        self.deadzone = max(0.0, float(deadzone))
        self._point: tuple[float, float] | None = None
        self._velocity: tuple[float, float] = (0.0, 0.0)
        self._last_time: float | None = None

    def reset(self) -> None:
        self._point = None
        self._velocity = (0.0, 0.0)
        self._last_time = None

    @property
    def point(self) -> tuple[float, float] | None:
        return self._point

    @property
    def velocity(self) -> tuple[float, float]:
        return self._velocity

    def update(self, hand: HandData | None, joint_index: int = 8) -> TipMotion:
        if hand is None or hand.face_blocked or not hand.landmarks:
            self.reset()
            return TipMotion()

        try:
            x, y, _ = hand.joint(int(joint_index))
        except (IndexError, ValueError):
            self.reset()
            return TipMotion()

        now = monotonic()
        if self._point is None or self._last_time is None:
            self._point = (float(x), float(y))
            self._velocity = (0.0, 0.0)
            self._last_time = now
            return TipMotion(self._point[0], self._point[1], 0.0, 0.0, 0.0, True, now)

        dt = max(1.0 / 120.0, min(0.2, now - self._last_time))
        alpha = self.smoothing
        fx = self._point[0] + alpha * (float(x) - self._point[0])
        fy = self._point[1] + alpha * (float(y) - self._point[1])
        raw_vx = (fx - self._point[0]) / dt
        raw_vy = (fy - self._point[1]) / dt
        vx = self._velocity[0] + alpha * (raw_vx - self._velocity[0])
        vy = self._velocity[1] + alpha * (raw_vy - self._velocity[1])

        # Very small movement is camera/landmark noise. Keep position, but
        # suppress its velocity so scrolling/cursor movement does not jitter.
        if math.hypot(fx - self._point[0], fy - self._point[1]) < self.deadzone:
            vx = vy = 0.0

        self._point = (fx, fy)
        self._velocity = (vx, vy)
        self._last_time = now
        return TipMotion(fx, fy, vx, vy, math.hypot(vx, vy), True, now)
