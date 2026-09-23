from __future__ import annotations

from pathlib import Path

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from src.core.models import HandData


class HandTracker:
    """Thin adapter around the MediaPipe Hand Landmarker Tasks API."""

    def __init__(self, model_path: str | Path, config: dict):
        tracking = config.get("tracking", {})
        base_options = python.BaseOptions(
            model_asset_path=str(model_path),
            # Keep inference on CPU on macOS; this avoids the native Metal/Drishti path.
            delegate=python.BaseOptions.Delegate.CPU,
        )
        options = vision.HandLandmarkerOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            num_hands=max(1, min(2, int(tracking.get("num_hands", 2)))),
            min_hand_detection_confidence=float(tracking.get("detection_confidence", 0.55)),
            min_hand_presence_confidence=float(tracking.get("presence_confidence", 0.55)),
            min_tracking_confidence=float(tracking.get("tracking_confidence", 0.55)),
        )
        self._detector = vision.HandLandmarker.create_from_options(options)

    def close(self) -> None:
        self._detector.close()

    def detect(self, frame_rgb, timestamp_ms: int) -> tuple[list[HandData], float]:
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._detector.detect_for_video(image, timestamp_ms)
        hands: list[HandData] = []
        scores: list[float] = []

        for idx, landmarks in enumerate(result.hand_landmarks):
            points = [(float(lm.x), float(lm.y), float(lm.z)) for lm in landmarks]
            handedness = "Unknown"
            handedness_score = 0.0
            if idx < len(result.handedness) and result.handedness[idx]:
                category = result.handedness[idx][0]
                handedness = str(category.category_name or "Unknown")
                handedness_score = float(category.score or 0.0)
                scores.append(handedness_score)

            center_x = sum(p[0] for p in points) / max(1, len(points))
            center_y = sum(p[1] for p in points) / max(1, len(points))
            hands.append(
                HandData(
                    points,
                    handedness,
                    handedness_score,
                    center_x,
                    center_y,
                    handedness_score,
                    False,
                    idx,
                )
            )

        tracking_conf = sum(scores) / len(scores) if scores else 0.0
        return hands, tracking_conf
