from __future__ import annotations

from pathlib import Path
import time

import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision

from src.core.models import FaceData


class FaceTracker:
    """Lightweight BlazeFace short-range detector used as an interaction guard."""

    def __init__(self, model_path: str | Path, config: dict):
        face_cfg = config.get("face_guard", {})
        base_options = python.BaseOptions(
            model_asset_path=str(model_path),
            # Keep face detection on CPU on macOS for the same Metal stability reason.
            delegate=python.BaseOptions.Delegate.CPU,
        )
        options = vision.FaceDetectorOptions(
            base_options=base_options,
            running_mode=vision.RunningMode.VIDEO,
            min_detection_confidence=float(face_cfg.get("detection_confidence", 0.55)),
            min_suppression_threshold=float(face_cfg.get("suppression_threshold", 0.30)),
        )
        self._detector = vision.FaceDetector.create_from_options(options)
        self.interval = max(1, int(face_cfg.get("detection_interval_frames", 2)))
        self.hold_ms = max(0, int(face_cfg.get("hold_ms", 500)))
        self._frame_count = 0
        self._last_faces: list[FaceData] = []
        self._last_timestamp = 0.0

    def close(self) -> None:
        self._detector.close()

    def detect(self, frame_rgb, timestamp_ms: int) -> tuple[list[FaceData], float]:
        self._frame_count += 1
        now = time.monotonic()
        if self._frame_count % self.interval != 0 and self._last_faces:
            age_ms = (now - self._last_timestamp) * 1000.0
            if age_ms <= self.hold_ms:
                return self._last_faces, max((f.score for f in self._last_faces), default=0.0)

        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=frame_rgb)
        result = self._detector.detect_for_video(image, timestamp_ms)
        faces: list[FaceData] = []
        for detection in result.detections:
            bbox = detection.bounding_box
            height, width = frame_rgb.shape[:2]
            width = max(1, int(width))
            height = max(1, int(height))
            score = float(detection.categories[0].score or 0.0) if detection.categories else 0.0
            faces.append(
                FaceData(
                    max(0.0, bbox.origin_x / width),
                    max(0.0, bbox.origin_y / height),
                    max(0.0, bbox.width / width),
                    max(0.0, bbox.height / height),
                    score,
                )
            )
        if not faces and self._last_faces and (now - self._last_timestamp) * 1000.0 <= self.hold_ms:
            # Keep the last known face briefly through a missed detector frame.
            return self._last_faces, max((f.score for f in self._last_faces), default=0.0)
        self._last_faces = faces
        self._last_timestamp = now
        return faces, max((f.score for f in faces), default=0.0)
