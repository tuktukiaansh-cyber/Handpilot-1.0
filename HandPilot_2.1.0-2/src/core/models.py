from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class GestureName(str, Enum):
    NONE = "NONE"
    OPEN_PALM = "OPEN_PALM"
    FIST = "FIST"
    THUMBS_UP = "THUMBS_UP"
    THUMBS_DOWN = "THUMBS_DOWN"
    ONE = "ONE"
    TWO = "TWO"
    THREE = "THREE"
    FOUR = "FOUR"
    PINCH = "PINCH"
    OK = "OK"


@dataclass(slots=True)
class FaceData:
    """A normalized face bounding box in image coordinates."""

    x: float
    y: float
    width: float
    height: float
    score: float = 0.0

    @property
    def center(self) -> tuple[float, float]:
        return (self.x + self.width / 2.0, self.y + self.height / 2.0)

    def expanded(self, factor: float = 0.15) -> "FaceData":
        pad_x = self.width * factor
        pad_y = self.height * factor
        return FaceData(
            max(0.0, self.x - pad_x),
            max(0.0, self.y - pad_y),
            min(1.0, self.width + 2 * pad_x),
            min(1.0, self.height + 2 * pad_y),
            self.score,
        )

    def contains(self, point: tuple[float, float], padding: float = 0.0) -> bool:
        px, py = point
        return (
            self.x - padding <= px <= self.x + self.width + padding
            and self.y - padding <= py <= self.y + self.height + padding
        )


@dataclass(slots=True)
class HandData:
    landmarks: list[tuple[float, float, float]]
    handedness: str = "Unknown"
    handedness_score: float = 0.0
    center_x: float = 0.5
    center_y: float = 0.5
    tracking_score: float = 0.0
    face_blocked: bool = False
    source_index: int = 0

    def joint(self, index: int) -> tuple[float, float, float]:
        return self.landmarks[index]

    @property
    def wrist(self) -> tuple[float, float, float]:
        return self.landmarks[0]

    @property
    def index_tip(self) -> tuple[float, float, float]:
        return self.landmarks[8]

    @property
    def thumb_tip(self) -> tuple[float, float, float]:
        return self.landmarks[4]


@dataclass(slots=True)
class GesturePrediction:
    gesture: GestureName = GestureName.NONE
    confidence: float = 0.0
    finger_count: int = 0
    hand_index: int = 0
    pinch_ratio: float = 1.0
    features: dict[str, float] = field(default_factory=dict)


@dataclass(slots=True)
class StableGesture:
    gesture: GestureName = GestureName.NONE
    confidence: float = 0.0
    age_ms: float = 0.0
    changed: bool = False
    action_eligible: bool = False


@dataclass(slots=True)
class CursorTarget:
    x: float = 0.0
    y: float = 0.0
    valid: bool = False
    screen_width: int = 0
    screen_height: int = 0


@dataclass(slots=True)
class HandControlState:
    """The complete independent control state for one physical hand."""

    key: str
    hand: HandData
    prediction: GesturePrediction
    stable: StableGesture
    cursor: CursorTarget = field(default_factory=CursorTarget)


@dataclass(slots=True)
class FrameResult:
    frame_bgr: Any
    hands: list[HandData] = field(default_factory=list)
    faces: list[FaceData] = field(default_factory=list)
    prediction: GesturePrediction = field(default_factory=GesturePrediction)
    stable: StableGesture = field(default_factory=StableGesture)
    cursor: CursorTarget = field(default_factory=CursorTarget)
    fps: float = 0.0
    tracking_confidence: float = 0.0
    face_confidence: float = 0.0
    status: str = "Starting camera"
    timestamp_ms: int = 0
    hand_states: list[HandControlState] = field(default_factory=list)
