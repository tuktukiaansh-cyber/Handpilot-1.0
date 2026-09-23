from __future__ import annotations

from dataclasses import dataclass, field

from src.gestures.geometry import clamp01


@dataclass(slots=True)
class CursorMapper:
    """Map a normalized camera joint to an absolute desktop coordinate."""

    screen_width: int
    screen_height: int
    margin_x: float = 0.08
    margin_y: float = 0.08
    smoothing: float = 0.30
    precision: float = 1.0
    _filtered: tuple[float, float] | None = field(default=None, init=False, repr=False)
    _last: tuple[int, int] | None = field(default=None, init=False, repr=False)

    def __post_init__(self):
        self.screen_width = max(1, int(self.screen_width))
        self.screen_height = max(1, int(self.screen_height))

    def reset(self) -> None:
        self._filtered = None
        self._last = None

    @property
    def last(self) -> tuple[int, int] | None:
        return self._last

    def reconfigure(self, screen_width: int, screen_height: int, margin_x: float, margin_y: float, smoothing: float, precision: float) -> None:
        changed_screen = (self.screen_width, self.screen_height) != (int(screen_width), int(screen_height))
        self.screen_width = max(1, int(screen_width))
        self.screen_height = max(1, int(screen_height))
        self.margin_x = max(0.0, min(0.25, float(margin_x)))
        self.margin_y = max(0.0, min(0.25, float(margin_y)))
        self.smoothing = max(0.02, min(1.0, float(smoothing)))
        self.precision = max(0.5, min(2.0, float(precision)))
        if changed_screen:
            self.reset()

    def update(self, point: tuple[float, float]) -> tuple[int, int]:
        x, y = point
        x = clamp01((x - self.margin_x) / max(0.05, 1.0 - 2.0 * self.margin_x))
        y = clamp01((y - self.margin_y) / max(0.05, 1.0 - 2.0 * self.margin_y))
        x = clamp01(0.5 + (x - 0.5) * self.precision)
        y = clamp01(0.5 + (y - 0.5) * self.precision)

        if self._filtered is None:
            fx, fy = x, y
        else:
            a = self.smoothing
            fx = self._filtered[0] + a * (x - self._filtered[0])
            fy = self._filtered[1] + a * (y - self._filtered[1])
        self._filtered = (fx, fy)

        self._last = (
            int(round(fx * (self.screen_width - 1))),
            int(round(fy * (self.screen_height - 1))),
        )
        return self._last
