from __future__ import annotations

import math
from typing import Iterable

import numpy as np


def segment_angle(a: Iterable[float], b: Iterable[float]) -> float:
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180.0


def snap_near_orthogonal(
    a: Iterable[float], b: Iterable[float], tolerance_deg: float = 12.0
) -> tuple[list[float], list[float], str]:
    """Snap only near-horizontal/vertical segments; preserve oblique geometry."""
    p1 = np.asarray(a, dtype=float)
    p2 = np.asarray(b, dtype=float)
    vector = p2 - p1
    length = float(np.linalg.norm(vector))
    if length < 1e-9:
        return p1.tolist(), p2.tolist(), "degenerate"

    angle = segment_angle(p1, p2)
    hdiff = min(angle, 180.0 - angle)
    vdiff = abs(angle - 90.0)
    midpoint = (p1 + p2) / 2.0
    half = length / 2.0

    if hdiff <= tolerance_deg:
        left = np.array([midpoint[0] - half, midpoint[1]])
        right = np.array([midpoint[0] + half, midpoint[1]])
        if vector[0] < 0:
            left, right = right, left
        return left.tolist(), right.tolist(), "snapped_horizontal"

    if vdiff <= tolerance_deg:
        top = np.array([midpoint[0], midpoint[1] - half])
        bottom = np.array([midpoint[0], midpoint[1] + half])
        if vector[1] < 0:
            top, bottom = bottom, top
        return top.tolist(), bottom.tolist(), "snapped_vertical"

    return p1.tolist(), p2.tolist(), "preserved_oblique"


def fit_circle(points: Iterable[Iterable[float]]) -> dict:
    """Return a conservative circle/arc fit candidate using algebraic least squares."""
    pts = np.asarray(list(points), dtype=float)
    if len(pts) < 5:
        return {"geometry": "insufficient_points", "fit": None}

    x, y = pts[:, 0], pts[:, 1]
    matrix = np.column_stack((2 * x, 2 * y, np.ones_like(x)))
    target = x * x + y * y
    try:
        cx, cy, constant = np.linalg.lstsq(matrix, target, rcond=None)[0]
        radius_sq = float(constant + cx * cx + cy * cy)
        if radius_sq <= 0:
            raise ValueError("non-positive radius")
        radius = math.sqrt(radius_sq)
        radial = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        residual = float(np.mean(np.abs(radial - radius)) / max(radius, 1e-9))
        if residual <= 0.08:
            return {
                "geometry": "arc_candidate",
                "fit": {
                    "center": [float(cx), float(cy)],
                    "radius": float(radius),
                    "relative_residual": residual,
                },
            }
    except (ValueError, np.linalg.LinAlgError, FloatingPointError):
        pass
    return {"geometry": "free_curve_candidate", "fit": None}


def calibrate_mm_per_px(pixel_distance: float, real_distance_mm: float) -> float:
    if pixel_distance <= 0 or real_distance_mm <= 0:
        raise ValueError("标定距离必须大于 0")
    return real_distance_mm / pixel_distance


def intersection_angle(a1, a2, b1, b2) -> float | None:
    first = np.asarray(a2, dtype=float) - np.asarray(a1, dtype=float)
    second = np.asarray(b2, dtype=float) - np.asarray(b1, dtype=float)
    if np.linalg.norm(first) < 1e-9 or np.linalg.norm(second) < 1e-9:
        return None
    cosine = float(np.dot(first, second) / (np.linalg.norm(first) * np.linalg.norm(second)))
    return math.degrees(math.acos(float(np.clip(abs(cosine), 0.0, 1.0))))
