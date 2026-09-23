from __future__ import annotations

import cv2

from src.core.models import CursorTarget, FaceData, HandControlState, HandData, StableGesture

CONNECTIONS = (
    (0, 1), (1, 2), (2, 3), (3, 4),
    (0, 5), (5, 6), (6, 7), (7, 8),
    (5, 9), (9, 10), (10, 11), (11, 12),
    (9, 13), (13, 14), (14, 15), (15, 16),
    (13, 17), (17, 18), (18, 19), (19, 20),
    (0, 17),
)

GREEN = (110, 235, 170)
PURPLE = (205, 125, 255)
RED = (90, 95, 245)
WHITE = (242, 244, 250)
MUTED = (160, 166, 178)
DARK = (20, 22, 28)


def _rounded_box(frame, p1, p2, fill):
    overlay = frame.copy()
    cv2.rectangle(overlay, p1, p2, fill, -1)
    cv2.addWeighted(overlay, 0.84, frame, 0.16, 0, frame)


def draw_overlay(
    frame,
    hands: list[HandData],
    faces: list[FaceData],
    cursor: CursorTarget,
    stable: StableGesture,
    status: str,
    control_index: int | None = None,
    show_face_boxes: bool = True,
    hand_states: list[HandControlState] | None = None,
):
    output = frame.copy()
    h, w = output.shape[:2]

    if show_face_boxes:
        for face in faces:
            x1 = int(face.x * w)
            y1 = int(face.y * h)
            x2 = int((face.x + face.width) * w)
            y2 = int((face.y + face.height) * h)
            cv2.rectangle(output, (x1, y1), (x2, y2), PURPLE, 2, cv2.LINE_AA)
            label = f"FACE  {face.score * 100:.0f}%"
            cv2.putText(output, label, (x1 + 6, max(20, y1 - 7)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, PURPLE, 1, cv2.LINE_AA)

    state_by_source: dict[int, HandControlState] = {}
    if hand_states:
        state_by_source = {state.hand.source_index: state for state in hand_states}

    for hand_idx, hand in enumerate(hands):
        pts = [
            (max(0, min(w - 1, int(x * w))), max(0, min(h - 1, int(y * h))))
            for x, y, _ in hand.landmarks
        ]
        blocked = hand.face_blocked
        line_color = RED if blocked else GREEN
        point_color = RED if blocked else PURPLE
        for a, b in CONNECTIONS:
            cv2.line(output, pts[a], pts[b], line_color, 2, cv2.LINE_AA)
        for idx, (x, y) in enumerate(pts):
            radius = 6 if idx in (4, 8, 12, 16, 20) else 3
            cv2.circle(output, (x, y), radius, point_color, -1, cv2.LINE_AA)
            if idx in (4, 8, 12, 16, 20):
                cv2.circle(output, (x, y), radius + 4, point_color, 1, cv2.LINE_AA)

        cx, cy = pts[0]
        state = state_by_source.get(hand.source_index)
        label = f"{hand.handedness}  {hand.handedness_score * 100:.0f}%"
        if state is not None:
            gesture = state.stable.gesture.value.replace("_", " ")
            action = ""
            if state.cursor.valid:
                action = " · MOUSE"
            label = f"{state.key} · {gesture}{action}"
        if hand_idx == control_index:
            label = "PRIMARY  ·  " + label
        cv2.putText(output, label, (cx + 10, cy - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.46, WHITE, 1, cv2.LINE_AA)
        if blocked:
            cv2.putText(output, "HAND PAUSED — FACE", (cx + 10, cy + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.46, RED, 1, cv2.LINE_AA)
        elif state is not None and state.stable.gesture.value == "TWO":
            cv2.putText(output, "SCROLL MODE", (cx + 10, cy + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.43, GREEN, 1, cv2.LINE_AA)
        elif state is not None and state.stable.gesture.value == "ONE":
            cv2.putText(output, "MOUSE MODE", (cx + 10, cy + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.43, GREEN, 1, cv2.LINE_AA)

    if hand_states:
        for state in hand_states:
            if not state.cursor.valid:
                continue
            ix = int(state.hand.index_tip[0] * w)
            iy = int(state.hand.index_tip[1] * h)
            cv2.circle(output, (ix, iy), 11, GREEN, 2, cv2.LINE_AA)
            cv2.circle(output, (ix, iy), 2, WHITE, -1, cv2.LINE_AA)

    if control_index is not None and 0 <= control_index < len(hands):
        hand = hands[control_index]
        ix = int(hand.index_tip[0] * w)
        iy = int(hand.index_tip[1] * h)
        ring = RED if hand.face_blocked else GREEN
        cv2.circle(output, (ix, iy), 15, ring, 2, cv2.LINE_AA)
        cv2.circle(output, (ix, iy), 3, WHITE, -1, cv2.LINE_AA)
        cv2.line(output, (ix - 23, iy), (ix + 23, iy), ring, 1, cv2.LINE_AA)
        cv2.line(output, (ix, iy - 23), (ix, iy + 23), ring, 1, cv2.LINE_AA)

    if cursor.valid:
        _rounded_box(output, (16, 16), (258, 56), DARK)
        cv2.putText(output, f"CURSOR  {int(cursor.x):4d} × {int(cursor.y):4d}", (28, 42), cv2.FONT_HERSHEY_SIMPLEX, 0.52, GREEN, 1, cv2.LINE_AA)

    _rounded_box(output, (w - 316, 16), (w - 16, 68), DARK)
    gesture = stable.gesture.value.replace("_", " ")
    cv2.putText(output, gesture, (w - 302, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.78, GREEN if gesture != "NONE" else MUTED, 2, cv2.LINE_AA)

    if "BLOCKED" in status:
        _rounded_box(output, (16, h - 58), (348, h - 16), (45, 35, 58))
        cv2.putText(output, status, (30, h - 31), cv2.FONT_HERSHEY_SIMPLEX, 0.5, RED, 1, cv2.LINE_AA)

    return output
