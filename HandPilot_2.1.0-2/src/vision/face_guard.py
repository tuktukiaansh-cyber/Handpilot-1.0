from __future__ import annotations

from src.core.models import FaceData, HandData


class FaceGuard:
    """Prevents hand gestures/actions while the hand is on or in front of a face."""

    IMPORTANT_POINTS = (0, 4, 8, 12, 20)

    def __init__(self, config: dict):
        self.update_config(config)

    def update_config(self, config: dict) -> None:
        cfg = config.get("face_guard", {})
        self.enabled = bool(cfg.get("enabled", True))
        self.expand = float(cfg.get("bbox_expand", 0.18))
        self.point_fraction = float(cfg.get("point_overlap_fraction", 0.15))

    def blocked(self, hand: HandData, faces: list[FaceData]) -> bool:
        if not self.enabled or not faces:
            return False

        # First check the hand's important joints. This is intentionally more
        # sensitive than bbox IoU so a finger touching the face also blocks control.
        for face in faces:
            box = face.expanded(self.expand)
            if any(box.contains(hand.landmarks[idx][:2]) for idx in self.IMPORTANT_POINTS):
                return True

            inside = sum(box.contains(point[:2]) for point in hand.landmarks)
            if inside / max(1, len(hand.landmarks)) >= self.point_fraction:
                return True
        return False
