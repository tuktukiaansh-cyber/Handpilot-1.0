from __future__ import annotations

import math


def distance(a, b) -> float:
    return math.sqrt(sum((a[i] - b[i]) ** 2 for i in range(min(len(a), len(b)))))


def angle(a, b, c) -> float:
    bax = a[0] - b[0]
    bay = a[1] - b[1]
    baz = (a[2] if len(a) > 2 else 0.0) - (b[2] if len(b) > 2 else 0.0)
    bcx = c[0] - b[0]
    bcy = c[1] - b[1]
    bcz = (c[2] if len(c) > 2 else 0.0) - (b[2] if len(b) > 2 else 0.0)
    dot = bax * bcx + bay * bcy + baz * bcz
    na = math.sqrt(bax * bax + bay * bay + baz * baz)
    nc = math.sqrt(bcx * bcx + bcy * bcy + bcz * bcz)
    if na <= 1e-8 or nc <= 1e-8:
        return 0.0
    value = max(-1.0, min(1.0, dot / (na * nc)))
    return math.degrees(math.acos(value))


def clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t
