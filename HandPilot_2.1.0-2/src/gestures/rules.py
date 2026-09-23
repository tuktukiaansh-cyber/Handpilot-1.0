from __future__ import annotations

from dataclasses import dataclass

from .geometry import angle, clamp01, distance

WRIST = 0
THUMB_CMC, THUMB_MCP, THUMB_IP, THUMB_TIP = 1, 2, 3, 4
INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP = 5, 6, 7, 8
MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP = 9, 10, 11, 12
RING_MCP, RING_PIP, RING_DIP, RING_TIP = 13, 14, 15, 16
PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP = 17, 18, 19, 20

FINGER_GROUPS = {
    "index": (INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP),
    "middle": (MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP),
    "ring": (RING_MCP, RING_PIP, RING_DIP, RING_TIP),
    "pinky": (PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP),
}


@dataclass(slots=True)
class FingerState:
    extended: bool
    confidence: float


def _finger_state(points, group) -> FingerState:
    mcp, pip, dip, tip = group
    wrist = points[WRIST]
    pip_a = angle(points[mcp], points[pip], points[dip])
    dip_a = angle(points[pip], points[dip], points[tip])
    radial = distance(points[tip], wrist) - distance(points[pip], wrist)

    score_pip = clamp01((pip_a - 125.0) / 50.0)
    score_dip = clamp01((dip_a - 135.0) / 45.0)
    score_radial = clamp01((radial + 0.015) / 0.060)
    score = 0.50 * score_pip + 0.30 * score_dip + 0.20 * score_radial
    return FingerState(score >= 0.52, score if score >= 0.5 else 1.0 - score)


def _thumb_state(points) -> FingerState:
    mcp_a = angle(points[THUMB_CMC], points[THUMB_MCP], points[THUMB_IP])
    ip_a = angle(points[THUMB_MCP], points[THUMB_IP], points[THUMB_TIP])
    extension = distance(points[THUMB_TIP], points[WRIST]) > distance(points[THUMB_IP], points[WRIST]) + 0.018
    separation = distance(points[THUMB_TIP], points[INDEX_MCP])

    score_angle = 0.5 * clamp01((mcp_a - 115.0) / 65.0) + 0.5 * clamp01((ip_a - 125.0) / 55.0)
    score_extension = clamp01((separation - 0.025) / 0.09) if extension else 0.0
    score = 0.70 * score_angle + 0.30 * score_extension
    return FingerState(score >= 0.53, score if score >= 0.5 else 1.0 - score)


def finger_states(points) -> dict[str, FingerState]:
    states = {name: _finger_state(points, group) for name, group in FINGER_GROUPS.items()}
    states["thumb"] = _thumb_state(points)
    return states


def pinch_ratio(points) -> float:
    palm_width = max(distance(points[5], points[17]), 0.035)
    return distance(points[THUMB_TIP], points[INDEX_TIP]) / palm_width


def pinch_strength(points) -> float:
    ratio = pinch_ratio(points)
    return clamp01((0.62 - ratio) / 0.27)


def thumb_direction(points) -> tuple[str, float]:
    thumb = points[THUMB_TIP]
    palm_y = sum(points[i][1] for i in (WRIST, INDEX_MCP, PINKY_MCP)) / 3.0
    dy = palm_y - thumb[1]
    magnitude = clamp01(abs(dy) / 0.16)
    if dy > 0.032:
        return "UP", magnitude
    if dy < -0.032:
        return "DOWN", magnitude
    return "SIDE", 0.0


def classify(points):
    """Return (gesture_name, confidence, finger_count, pinch_ratio, features)."""
    states = finger_states(points)
    extended_nonthumb = sum(states[name].extended for name in FINGER_GROUPS)
    count = extended_nonthumb + int(states["thumb"].extended)
    quality = sum(state.confidence for state in states.values()) / 5.0
    ratio = pinch_ratio(points)
    p_strength = pinch_strength(points)
    features = {
        "pinch_ratio": ratio,
        "pinch_strength": p_strength,
        "hand_quality": quality,
        "index_extended": float(states["index"].extended),
        "middle_extended": float(states["middle"].extended),
        "ring_extended": float(states["ring"].extended),
        "pinky_extended": float(states["pinky"].extended),
        "thumb_extended": float(states["thumb"].extended),
    }

    # IMPORTANT: pinch/OK must be checked before fist/counting. A closed pinch
    # can otherwise look exactly like a fist to a finger-extension classifier.
    if p_strength >= 0.55:
        other_extended = sum(states[name].extended for name in ("middle", "ring", "pinky"))
        if other_extended >= 2:
            return "OK", clamp01(0.72 + 0.28 * p_strength), count, ratio, features
        return "PINCH", clamp01(0.70 + 0.30 * p_strength), count, ratio, features

    if states["thumb"].extended and extended_nonthumb == 0:
        direction, strength = thumb_direction(points)
        if direction == "UP":
            return "THUMBS_UP", clamp01(0.70 + 0.30 * strength), 1, ratio, features
        if direction == "DOWN":
            return "THUMBS_DOWN", clamp01(0.70 + 0.30 * strength), 1, ratio, features

    if count == 0:
        return "FIST", clamp01(0.70 + 0.30 * quality), 0, ratio, features
    if count == 5:
        return "OPEN_PALM", clamp01(0.73 + 0.27 * quality), 5, ratio, features
    if count in (1, 2, 3, 4):
        # One/two/three/four are based on extension count. The thumb-only pose
        # is intentionally reserved for thumbs-up/down rather than ONE.
        if extended_nonthumb > 0:
            name = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR"}[extended_nonthumb]
            return name, clamp01(0.62 + 0.38 * quality), extended_nonthumb, ratio, features

    return "NONE", 0.25, count, ratio, features
