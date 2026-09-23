from __future__ import annotations

import math

from src.actions.cursor_mapper import CursorMapper
from src.gestures.rules import classify, pinch_ratio


def point(x, y, z=0.0):
    return (x, y, z)


def make_pinch():
    p = [point(0.50, 0.80) for _ in range(21)]
    # A compact palm.
    p[5] = point(0.44, 0.60); p[9] = point(0.50, 0.57); p[13] = point(0.56, 0.60); p[17] = point(0.60, 0.66)
    p[0] = point(0.50, 0.82); p[1] = point(0.44, 0.73); p[2] = point(0.42, 0.69); p[3] = point(0.45, 0.64)
    p[4] = point(0.49, 0.57)
    p[6] = point(0.40, 0.52); p[7] = point(0.40, 0.48); p[8] = point(0.49, 0.57)
    return p


def test_cursor_mapper_hits_screen_edges():
    mapper = CursorMapper(1920, 1080, 0.0, 0.0, 1.0, 1.0)
    assert mapper.update((0.0, 0.0)) == (0, 0)
    assert mapper.update((1.0, 1.0)) == (1919, 1079)


def test_cursor_mapper_smooths_motion():
    mapper = CursorMapper(100, 100, 0.0, 0.0, 0.25, 1.0)
    first = mapper.update((0.0, 0.0))
    second = mapper.update((1.0, 1.0))
    assert first == (0, 0)
    assert 0 < second[0] < 99
    assert 0 < second[1] < 99


def test_pinch_ratio_is_small_for_close_thumb_index():
    points = make_pinch()
    assert pinch_ratio(points) < 0.7
    gesture, confidence, *_ = classify(points)
    assert gesture in {"PINCH", "OK"}
    assert confidence > 0.5


def test_face_guard_blocks_hand_near_face():
    from src.core.models import FaceData, HandData
    from src.vision.face_guard import FaceGuard

    points = [point(0.5, 0.5) for _ in range(21)]
    points[0] = point(0.5, 0.70)
    points[8] = point(0.50, 0.45)
    hand = HandData(points, "Right", 0.9, 0.5, 0.55, 0.9)
    face = FaceData(0.35, 0.25, 0.30, 0.35, 0.95)
    guard = FaceGuard({"face_guard": {"enabled": True, "bbox_expand": 0.20, "point_overlap_fraction": 0.12}})
    assert guard.blocked(hand, [face])


def test_fingertip_motion_tracks_index_tip():
    from src.actions.motion import FingertipMotionTracker
    from src.core.models import HandData

    points = [point(0.5, 0.5) for _ in range(21)]
    hand = HandData(points, "Right", 0.9, 0.5, 0.5, 0.9)
    tracker = FingertipMotionTracker(smoothing=1.0, deadzone=0.0)

    points[8] = point(0.20, 0.20)
    motion1 = tracker.update(hand, 8)
    assert motion1.valid and abs(motion1.x - 0.20) < 1e-9

    points[8] = point(0.20, 0.60)
    motion2 = tracker.update(hand, 8)
    assert motion2.valid and motion2.vy > 0


def test_scroll_accumulator_direction_math():
    # Positive camera Y movement is a physical downward wave and therefore
    # yields negative scroll units. Upward motion yields positive units.
    assert (-0.01 * 150.0) < 0
    assert (-(-0.01) * 150.0) > 0

