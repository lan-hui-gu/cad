from __future__ import annotations

import math

import numpy as np

from .geometry import snap_near_orthogonal


def _unit_direction(start, end) -> np.ndarray:
    vector = np.asarray(end, dtype=float) - np.asarray(start, dtype=float)
    length = float(np.linalg.norm(vector))
    if length < 1e-9:
        return np.zeros(2, dtype=float)
    vector /= length
    if vector[0] < 0 or (abs(vector[0]) < 1e-9 and vector[1] < 0):
        vector = -vector
    return vector


def _segment_data(segment: dict) -> dict | None:
    start = np.asarray(segment.get("start"), dtype=float)
    end = np.asarray(segment.get("end"), dtype=float)
    if start.shape != (2,) or end.shape != (2,):
        return None
    direction = _unit_direction(start, end)
    if np.linalg.norm(direction) < 1e-9:
        return None
    normal = np.array([-direction[1], direction[0]])
    midpoint = (start + end) / 2.0
    projections = sorted((float(np.dot(start, direction)), float(np.dot(end, direction))))
    return {
        "source": segment,
        "start": start,
        "end": end,
        "direction": direction,
        "normal": normal,
        "offset": float(np.dot(midpoint, normal)),
        "low": projections[0],
        "high": projections[1],
        "length": float(np.linalg.norm(end - start)),
    }


def _compatible(a: dict, b: dict, angle_tolerance_deg: float, offset_tolerance_px: float, gap_tolerance_px: float) -> bool:
    dot = float(np.clip(abs(np.dot(a["direction"], b["direction"])), -1.0, 1.0))
    angle = math.degrees(math.acos(dot))
    if angle > angle_tolerance_deg:
        return False

    direction = a["direction"] + b["direction"]
    norm = float(np.linalg.norm(direction))
    if norm < 1e-9:
        return False
    direction /= norm
    normal = np.array([-direction[1], direction[0]])
    mid_a = (a["start"] + a["end"]) / 2.0
    mid_b = (b["start"] + b["end"]) / 2.0
    if abs(float(np.dot(mid_a - mid_b, normal))) > offset_tolerance_px:
        return False

    endpoints_a = [float(np.dot(a["start"], direction)), float(np.dot(a["end"], direction))]
    endpoints_b = [float(np.dot(b["start"], direction)), float(np.dot(b["end"], direction))]
    low_a, high_a = min(endpoints_a), max(endpoints_a)
    low_b, high_b = min(endpoints_b), max(endpoints_b)
    gap = max(0.0, max(low_a, low_b) - min(high_a, high_b))
    return gap <= gap_tolerance_px


def simplify_segments(
    segments: list[dict],
    *,
    angle_tolerance_deg: float = 4.0,
    offset_tolerance_px: float = 7.0,
    gap_tolerance_px: float = 26.0,
    min_length_px: float = 18.0,
    orthogonal_tolerance_deg: float = 5.0,
) -> list[dict]:
    """Merge duplicate/collinear Hough fragments into clean reviewable segments.

    This stage intentionally does not assign engineering meaning. All output
    segments remain unmarked until a user labels them in the annotation UI.
    """
    data = [item for item in (_segment_data(s) for s in segments) if item is not None]
    if not data:
        return []

    parent = list(range(len(data)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(first: int, second: int) -> None:
        root_a, root_b = find(first), find(second)
        if root_a != root_b:
            parent[root_b] = root_a

    for i, first in enumerate(data):
        for j in range(i + 1, len(data)):
            if _compatible(
                first, data[j],
                angle_tolerance_deg=angle_tolerance_deg,
                offset_tolerance_px=offset_tolerance_px,
                gap_tolerance_px=gap_tolerance_px,
            ):
                union(i, j)

    groups: dict[int, list[dict]] = {}
    for index, item in enumerate(data):
        groups.setdefault(find(index), []).append(item)

    merged = []
    for group in groups.values():
        weights = np.asarray([max(item["length"], 1.0) for item in group], dtype=float)
        directions = np.asarray([item["direction"] for item in group], dtype=float)
        direction = np.average(directions, axis=0, weights=weights)
        direction_norm = float(np.linalg.norm(direction))
        if direction_norm < 1e-9:
            continue
        direction /= direction_norm
        if direction[0] < 0 or (abs(direction[0]) < 1e-9 and direction[1] < 0):
            direction = -direction
        normal = np.array([-direction[1], direction[0]])

        all_points = np.asarray(
            [point for item in group for point in (item["start"], item["end"])],
            dtype=float,
        )
        offsets = np.asarray([float(np.dot((item["start"] + item["end"]) / 2, normal)) for item in group])
        offset = float(np.average(offsets, weights=weights))
        projections = all_points @ direction
        start = direction * float(np.min(projections)) + normal * offset
        end = direction * float(np.max(projections)) + normal * offset

        snapped_start, snapped_end, constraint = snap_near_orthogonal(
            start, end, tolerance_deg=orthogonal_tolerance_deg
        )
        start = np.asarray(snapped_start, dtype=float)
        end = np.asarray(snapped_end, dtype=float)
        length = float(np.linalg.norm(end - start))
        if length < min_length_px:
            continue
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180.0
        merged.append({
            "id": "",
            "start": start.round(2).tolist(),
            "end": end.round(2).tolist(),
            "length_px": round(length, 2),
            "angle_deg": round(angle, 2),
            "orientation": "horizontal" if min(angle, 180 - angle) <= 5 else ("vertical" if abs(angle - 90) <= 5 else "oblique"),
            "geometry_constraint": constraint,
            "source_ids": [item["source"].get("id", "") for item in group],
            "merged_count": len(group),
            "category": "unmarked",
            "status": "unmarked",
        })

    merged.sort(key=lambda item: item["length_px"], reverse=True)
    for index, segment in enumerate(merged, start=1):
        segment["id"] = f"S{index:04d}"
    return merged


def apply_simplification(result: dict) -> dict:
    raw = result.get("raw_lines") or result.get("lines") or []
    result["lines"] = simplify_segments(raw)
    result["point_marks"] = result.get("point_marks", [])
    result["marking_complete"] = False
    result["simplification"] = {
        "raw_segment_count": len(raw),
        "simplified_segment_count": len(result["lines"]),
        "rule": "共线合并、重复消减、短间断合并、近水平/垂直正交约束",
    }
    return result
