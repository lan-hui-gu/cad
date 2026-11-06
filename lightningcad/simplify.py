from __future__ import annotations

import math

import numpy as np

from .geometry import snap_near_orthogonal


def _segment_data(segment: dict) -> dict | None:
    try:
        start = np.asarray(segment.get("start"), dtype=float)
        end = np.asarray(segment.get("end"), dtype=float)
    except (TypeError, ValueError):
        return None
    if start.shape != (2,) or end.shape != (2,):
        return None
    vector = end - start
    length = float(np.linalg.norm(vector))
    if length < 1e-6:
        return None
    direction = vector / length
    if direction[0] < 0 or (abs(direction[0]) < 1e-9 and direction[1] < 0):
        direction = -direction
    normal = np.array([-direction[1], direction[0]])
    midpoint = (start + end) / 2.0
    angle = math.degrees(math.atan2(direction[1], direction[0])) % 180.0
    return {
        "source": segment, "start": start, "end": end,
        "direction": direction, "normal": normal,
        "offset": float(np.dot(midpoint, normal)),
        "length": length, "angle": angle,
    }


def _group_geometry(group: list[dict]):
    weights = np.asarray([max(item["length"], 1.0) for item in group], dtype=float)
    directions = np.asarray([item["direction"] for item in group], dtype=float)
    direction = np.average(directions, axis=0, weights=weights)
    norm = float(np.linalg.norm(direction))
    direction = group[0]["direction"].copy() if norm < 1e-9 else direction / norm
    if direction[0] < 0 or (abs(direction[0]) < 1e-9 and direction[1] < 0):
        direction = -direction
    normal = np.array([-direction[1], direction[0]])
    offsets = [float(np.dot((item["start"] + item["end"]) / 2.0, normal)) for item in group]
    offset = float(np.median(offsets))
    angle = math.degrees(math.atan2(direction[1], direction[0])) % 180.0
    return direction, normal, offset, angle


def _interval_gap(first, second, direction):
    a = sorted((float(np.dot(first["start"], direction)), float(np.dot(first["end"], direction))))
    b = sorted((float(np.dot(second["start"], direction)), float(np.dot(second["end"], direction))))
    return max(0.0, max(a[0], b[0]) - min(a[1], b[1]))


def _can_join_group(group, item, angle_tolerance_deg, offset_tolerance_px, gap_tolerance_px):
    direction, normal, offset, angle = _group_geometry(group)
    angle_diff = abs(item["angle"] - angle)
    angle_diff = min(angle_diff, 180.0 - angle_diff)
    if angle_diff > angle_tolerance_deg:
        return False, float("inf")
    item_offset = float(np.dot((item["start"] + item["end"]) / 2.0, normal))
    offset_error = abs(item_offset - offset)
    if offset_error > offset_tolerance_px:
        return False, float("inf")
    gap = min(_interval_gap(existing, item, direction) for existing in group)
    if gap > gap_tolerance_px:
        return False, float("inf")
    return True, angle_diff + offset_error * 0.1 + gap * 0.01


def _merge_group_intervals(group, gap_tolerance_px, min_length_px, orthogonal_tolerance_deg):
    direction, normal, offset, _ = _group_geometry(group)
    intervals = []
    for item in group:
        p1 = float(np.dot(item["start"], direction))
        p2 = float(np.dot(item["end"], direction))
        intervals.append((min(p1, p2), max(p1, p2), item))
    intervals.sort(key=lambda item: item[0])

    interval_groups = []
    for interval in intervals:
        if not interval_groups or interval[0] - max(x[1] for x in interval_groups[-1]) > gap_tolerance_px:
            interval_groups.append([interval])
        else:
            interval_groups[-1].append(interval)

    output = []
    for interval_group in interval_groups:
        low = min(item[0] for item in interval_group)
        high = max(item[1] for item in interval_group)
        start = direction * low + normal * offset
        end = direction * high + normal * offset
        snapped_start, snapped_end, constraint = snap_near_orthogonal(
            start, end, tolerance_deg=orthogonal_tolerance_deg
        )
        start = np.asarray(snapped_start, dtype=float)
        end = np.asarray(snapped_end, dtype=float)
        length = float(np.linalg.norm(end - start))
        if length < min_length_px:
            continue
        angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180.0
        output.append({
            "id": "",
            "start": start.round(2).tolist(),
            "end": end.round(2).tolist(),
            "length_px": round(length, 2),
            "angle_deg": round(angle, 2),
            "orientation": (
                "horizontal" if min(angle, 180.0 - angle) <= 2.5
                else "vertical" if abs(angle - 90.0) <= 2.5
                else "oblique"
            ),
            "geometry_constraint": constraint,
            "source_ids": [item[2]["source"].get("id", "") for item in interval_group],
            "merged_count": len(interval_group),
            "intersection_count": 0,
            "category": "unmarked",
            "status": "unmarked",
        })
    return output


def _intersection_parameters(first, second):
    p = np.asarray(first["start"], dtype=float)
    r = np.asarray(first["end"], dtype=float) - p
    q = np.asarray(second["start"], dtype=float)
    s = np.asarray(second["end"], dtype=float) - q
    denominator = r[0] * s[1] - r[1] * s[0]
    if abs(float(denominator)) < 1e-8:
        return None
    delta = q - p
    t = (delta[0] * s[1] - delta[1] * s[0]) / denominator
    u = (delta[0] * r[1] - delta[1] * r[0]) / denominator
    if -1e-6 <= t <= 1.000001 and -1e-6 <= u <= 1.000001:
        return float(t), float(u), p + t * r
    return None


def _split_at_intersections(segments: list[dict], min_piece_px: float = 4.0):
    breakpoints = [
        [(0.0, np.asarray(item["start"], dtype=float)), (1.0, np.asarray(item["end"], dtype=float))]
        for item in segments
    ]
    intersections = []
    for i, first in enumerate(segments):
        for j in range(i + 1, len(segments)):
            second = segments[j]
            hit = _intersection_parameters(first, second)
            if hit is None:
                continue
            t, u, point = hit
            len_a, len_b = float(first["length_px"]), float(second["length_px"])
            interior_a = min(t * len_a, (1 - t) * len_a) >= 1.5
            interior_b = min(u * len_b, (1 - u) * len_b) >= 1.5
            if not interior_a and not interior_b:
                continue
            if interior_a:
                breakpoints[i].append((t, point))
            if interior_b:
                breakpoints[j].append((u, point))
            intersections.append({
                "point": point.round(2).tolist(),
                "line_ids": [first["id"], second["id"]],
                "status": "topology_node",
            })

    output = []
    for index, item in enumerate(segments):
        ordered = sorted(breakpoints[index], key=lambda pair: pair[0])
        unique = []
        for t, point in ordered:
            if not unique or float(np.linalg.norm(point - unique[-1][1])) > 0.75:
                unique.append((t, point))
        count = sum(1 for hit in intersections if item["id"] in hit["line_ids"])
        for part_index, ((_, start), (_, end)) in enumerate(zip(unique, unique[1:]), start=1):
            length = float(np.linalg.norm(end - start))
            if length < min_piece_px:
                continue
            angle = math.degrees(math.atan2(end[1] - start[1], end[0] - start[0])) % 180.0
            output.append({
                **item,
                "id": "",
                "start": start.round(2).tolist(),
                "end": end.round(2).tolist(),
                "length_px": round(length, 2),
                "angle_deg": round(angle, 2),
                "orientation": (
                    "horizontal" if min(angle, 180.0 - angle) <= 2.5
                    else "vertical" if abs(angle - 90.0) <= 2.5
                    else "oblique"
                ),
                "intersection_count": count,
                "split_part": part_index,
            })
    for index, item in enumerate(output, start=1):
        item["id"] = f"S{index:04d}"
    return output, intersections


def _build_topology(segments: list[dict], tolerance_px: float = 1.5) -> dict:
    nodes = []

    def node_for(point):
        p = np.asarray(point, dtype=float)
        for node in nodes:
            if float(np.linalg.norm(p - np.asarray(node["position"], dtype=float))) <= tolerance_px:
                return node
        node = {"id": f"N{len(nodes) + 1:04d}", "position": p.round(2).tolist(), "edges": []}
        nodes.append(node)
        return node

    edges = []
    for item in segments:
        a, b = node_for(item["start"]), node_for(item["end"])
        a["edges"].append(item["id"])
        b["edges"].append(item["id"])
        item["start_node"], item["end_node"] = a["id"], b["id"]
        edges.append({"id": item["id"], "start_node": a["id"], "end_node": b["id"]})
    return {"nodes": nodes, "edges": edges}


def simplify_segments(
    segments: list[dict],
    *,
    angle_tolerance_deg: float = 2.0,
    offset_tolerance_px: float = 3.2,
    gap_tolerance_px: float = 9.0,
    min_length_px: float = 12.0,
    orthogonal_tolerance_deg: float = 3.0,
    split_intersections: bool = True,
) -> list[dict]:
    """Conservatively merge collinear fragments and preserve intersections/topology."""
    data = [item for item in (_segment_data(segment) for segment in segments) if item is not None]
    if not data:
        return []
    data.sort(key=lambda item: (item["angle"], item["offset"], -item["length"]))
    groups: list[list[dict]] = []
    for item in data:
        candidates = []
        for group in groups:
            okay, score = _can_join_group(
                group, item, angle_tolerance_deg, offset_tolerance_px, gap_tolerance_px
            )
            if okay:
                candidates.append((score, group))
        if candidates:
            min(candidates, key=lambda pair: pair[0])[1].append(item)
        else:
            groups.append([item])

    merged = []
    for group in groups:
        merged.extend(_merge_group_intervals(
            group, gap_tolerance_px, min_length_px, orthogonal_tolerance_deg
        ))
    merged.sort(key=lambda item: (item["orientation"], item["start"][1], item["start"][0], -item["length_px"]))
    for index, item in enumerate(merged, start=1):
        item["id"] = f"M{index:04d}"

    output = _split_at_intersections(merged)[0] if split_intersections else merged
    output.sort(key=lambda item: (item["start"][1], item["start"][0], item["end"][1], item["end"][0]))
    for index, item in enumerate(output, start=1):
        item["id"] = f"S{index:04d}"
    _build_topology(output)
    return output


def detect_primary_drawing_region(result: dict) -> dict | None:
    """Find the dominant closed sketch contour and a generous annotation margin."""
    width = int(result.get("image_width", 0) or 0)
    height = int(result.get("image_height", 0) or 0)
    image_area = max(1, width * height)
    candidates = []
    for contour in result.get("contours", []):
        box = contour.get("bbox")
        if not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        x, y, box_width, box_height = map(float, box)
        area = float(contour.get("area_px2", 0) or 0)
        fraction = area / image_area
        if box_width < 24 or box_height < 24:
            continue
        if not 0.004 <= fraction <= 0.72:
            continue
        if contour.get("category") != "building_outline_candidate" and contour.get("vertex_count") != 4:
            continue
        aspect = box_width / max(box_height, 1.0)
        if not 0.12 <= aspect <= 8.0:
            continue
        candidates.append((area, [x, y, box_width, box_height], fraction))

    if not candidates:
        return None

    area, box, fraction = max(candidates, key=lambda item: item[0])
    x, y, box_width, box_height = box
    margin_x = max(32.0, box_width * 0.20)
    margin_y = max(32.0, box_height * 0.16)
    expanded = [
        max(0.0, x - margin_x),
        max(0.0, y - margin_y),
        min(float(width), x + box_width + margin_x),
        min(float(height), y + box_height + margin_y),
    ]
    return {
        "source": "largest_closed_contour",
        "bbox": [round(value, 2) for value in box],
        "expanded_bbox": [round(value, 2) for value in expanded],
        "area_fraction": round(fraction, 4),
        "margin_px": [round(margin_x, 2), round(margin_y, 2)],
    }


def _segment_intersects_region(segment: dict, region: dict) -> bool:
    x1, y1, x2, y2 = region["expanded_bbox"]
    try:
        ax, ay = map(float, segment["start"])
        bx, by = map(float, segment["end"])
    except (KeyError, TypeError, ValueError):
        return False
    return max(ax, bx) >= x1 and min(ax, bx) <= x2 and max(ay, by) >= y1 and min(ay, by) <= y2


def apply_simplification(result: dict) -> dict:
    raw = result.get("raw_lines") or result.get("lines") or []
    region = detect_primary_drawing_region(result)
    region_raw = [item for item in raw if _segment_intersects_region(item, region)] if region else list(raw)
    lines = simplify_segments(region_raw)
    result["drawing_region"] = region
    result["raw_lines_for_drawing"] = region_raw
    result["lines"] = lines
    result["point_marks"] = result.get("point_marks", [])
    result["marking_complete"] = False
    topology = _build_topology(lines)
    result["topology"] = topology
    result["intersections"] = [
        {"point": node["position"], "line_ids": node["edges"], "status": "topology_node"}
        for node in topology["nodes"] if len(node["edges"]) >= 3
    ]
    result["simplification"] = {
        "raw_segment_count": len(raw),
        "region_candidate_segment_count": len(region_raw),
        "region_filter_applied": region is not None,
        "merged_segment_count": len({source for line in lines for source in line.get("source_ids", [])}),
        "simplified_segment_count": len(lines),
        "intersection_count": len(result["intersections"]),
        "rule": "主轮廓区域筛选、严格共线合并、短间断合并、交点拆分、近正交约束、拓扑节点重建",
    }
    return result
