from __future__ import annotations

import math
from pathlib import Path

import cv2
import numpy as np

from .geometry import fit_circle, snap_near_orthogonal
from .ocr import run_rapid_ocr


def read_image(path: str | Path) -> np.ndarray:
    data = np.fromfile(str(path), dtype=np.uint8)
    image = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if image is None:
        raise ValueError(f"无法读取图片：{path}")
    return image


def rotate_image(image: np.ndarray, degrees: int) -> np.ndarray:
    rotations = {
        0: None,
        90: cv2.ROTATE_90_CLOCKWISE,
        180: cv2.ROTATE_180,
        270: cv2.ROTATE_90_COUNTERCLOCKWISE,
    }
    if degrees not in rotations:
        raise ValueError("旋转角度只能是 0、90、180 或 270 度")
    return image.copy() if degrees == 0 else cv2.rotate(image, rotations[degrees])


def _line_orientation(angle: float) -> str:
    horizontal = min(angle, 180.0 - angle)
    vertical = abs(angle - 90.0)
    if horizontal <= 12.0:
        return "horizontal_candidate"
    if vertical <= 12.0:
        return "vertical_candidate"
    return "oblique_candidate"


def _detect_lines(edges: np.ndarray) -> list[dict]:
    height, width = edges.shape[:2]
    minimum = max(12, int(min(height, width) * 0.025))
    threshold = max(20, min(48, int(min(height, width) * 0.15)))
    max_gap = max(5, int(min(height, width) * 0.012))
    raw = cv2.HoughLinesP(edges, 1, np.pi / 180.0, threshold=threshold, minLineLength=minimum, maxLineGap=max_gap)
    if raw is None:
        return []
    segments = []
    for row in raw[:, 0, :]:
        x1, y1, x2, y2 = map(int, row)
        length = math.hypot(x2 - x1, y2 - y1)
        if length < minimum:
            continue
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        segments.append({
            "id": f"L{len(segments) + 1:04d}",
            "start": [x1, y1], "end": [x2, y2],
            "length_px": round(length, 2), "angle_deg": round(angle, 2),
            "orientation": _line_orientation(angle),
            "category": "line_review_candidate", "status": "needs_review",
        })
    segments.sort(key=lambda item: item["length_px"], reverse=True)
    kept = []
    for item in segments:
        a, b = np.asarray(item["start"], dtype=float), np.asarray(item["end"], dtype=float)
        direction = b - a
        direction /= max(float(np.linalg.norm(direction)), 1e-9)
        normal = np.array([-direction[1], direction[0]])
        midpoint = (a + b) / 2.0
        interval = sorted((float(np.dot(a, direction)), float(np.dot(b, direction))))
        duplicate = False
        for old in kept:
            oa, ob = np.asarray(old["start"], dtype=float), np.asarray(old["end"], dtype=float)
            old_direction = ob - oa
            old_direction /= max(float(np.linalg.norm(old_direction)), 1e-9)
            angle_diff = math.degrees(math.acos(float(np.clip(abs(np.dot(direction, old_direction)), -1.0, 1.0))))
            perpendicular = abs(float(np.dot(midpoint - (oa + ob) / 2.0, normal)))
            old_interval = sorted((float(np.dot(oa, direction)), float(np.dot(ob, direction))))
            overlap = max(0.0, min(interval[1], old_interval[1]) - max(interval[0], old_interval[0]))
            shorter = max(1.0, min(interval[1] - interval[0], old_interval[1] - old_interval[0]))
            if angle_diff <= 1.5 and perpendicular <= 2.4 and overlap / shorter >= 0.55:
                duplicate = True
                break
        if not duplicate:
            kept.append(item)
    return kept[:600]


def _detect_colored_markers(image: np.ndarray) -> list[dict]:
    """Detect saturated blue/red triangular markers separately from grey linework."""
    hsv = cv2.cvtColor(image, cv2.COLOR_BGR2HSV)
    masks = {
        "blue": cv2.inRange(hsv, np.array([90, 100, 70], dtype=np.uint8), np.array([135, 255, 255], dtype=np.uint8)),
        "red": cv2.inRange(hsv, np.array([0, 100, 70], dtype=np.uint8), np.array([30, 255, 255], dtype=np.uint8)),
    }
    found = []
    for color, mask in masks.items():
        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        for contour in contours:
            area = abs(float(cv2.contourArea(contour)))
            if not 1.5 <= area <= 90:
                continue
            x, y, width, height = cv2.boundingRect(contour)
            if min(width, height) < 2 or max(width, height) > 18:
                continue
            perimeter = float(cv2.arcLength(contour, True))
            if perimeter <= 0:
                continue
            polygon = cv2.approxPolyDP(contour, 0.15 * perimeter, True)
            if len(polygon) != 3 or area / max(1.0, float(width * height)) < 0.16:
                continue
            moments = cv2.moments(contour)
            if abs(moments["m00"]) < 1e-9:
                continue
            center = [float(moments["m10"] / moments["m00"]), float(moments["m01"] / moments["m00"])]
            found.append({
                "center": center, "bbox": [int(x), int(y), int(width), int(height)],
                "vertices": polygon.reshape(-1, 2).astype(int).tolist(),
                "color": color, "category": "test_point_candidate",
                "label": "", "status": "needs_review",
            })
    found.sort(key=lambda item: (item["center"][1], item["center"][0]))
    unique = []
    for marker in found:
        if not any(math.dist(marker["center"], old["center"]) < 4.0 for old in unique):
            unique.append(marker)
    return unique[:100]

def _detect_contours(binary: np.ndarray) -> list[dict]:
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    image_area = binary.shape[0] * binary.shape[1]
    output = []
    for contour in contours:
        area = abs(float(cv2.contourArea(contour)))
        perimeter = float(cv2.arcLength(contour, True))
        if area < 30 or perimeter < 35:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        if width < 12 or height < 12:
            continue
        approximation = cv2.approxPolyDP(contour, max(2.0, 0.025 * perimeter), True)
        vertices = approximation.reshape(-1, 2).astype(int).tolist()
        rectangular = len(vertices) == 4 and area > image_area * 0.004
        output.append({
            "bbox": [int(x), int(y), int(width), int(height)],
            "area_px2": round(area, 2),
            "vertices": vertices,
            "vertex_count": len(vertices),
            "category": "building_outline_candidate" if rectangular else "contour_candidate",
            "status": "needs_review",
        })
    output.sort(key=lambda item: item["area_px2"], reverse=True)
    return output[:100]


def _detect_triangles(binary: np.ndarray) -> list[dict]:
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for contour in contours:
        area = abs(float(cv2.contourArea(contour)))
        if area < 60 or area > 12000:
            continue
        perimeter = cv2.arcLength(contour, True)
        polygon = cv2.approxPolyDP(contour, 0.07 * perimeter, True)
        if len(polygon) != 3:
            continue
        x, y, width, height = cv2.boundingRect(contour)
        if min(width, height) < 5 or max(width, height) / max(1, min(width, height)) > 4.5:
            continue
        hull_area = float(cv2.contourArea(cv2.convexHull(contour)))
        fill_ratio = area / max(1.0, width * height)
        solidity = area / max(1.0, hull_area)
        if fill_ratio < 0.30 or solidity < 0.70:
            continue
        points = polygon.reshape(-1, 2).astype(int).tolist()
        found.append({
            "bbox": [int(x), int(y), int(width), int(height)],
            "center": [float(x + width / 2), float(y + height / 2)],
            "vertices": points,
            "category": "test_point_candidate",
            "label": None,
            "status": "needs_review",
        })
    return found[:80]


def _detect_round_symbols(binary: np.ndarray) -> list[dict]:
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    output = []
    for contour in contours:
        area = float(cv2.contourArea(contour))
        if not 40 <= area <= 5000:
            continue
        perimeter = cv2.arcLength(contour, True)
        if perimeter <= 0:
            continue
        circularity = 4.0 * math.pi * area / (perimeter * perimeter)
        if circularity < 0.72:
            continue
        (x, y), radius = cv2.minEnclosingCircle(contour)
        if 3 <= radius <= 32:
            output.append({
                "center": [float(x), float(y)],
                "radius_px": float(radius),
                "category": "round_symbol_candidate",
                "status": "needs_review",
            })
    return output[:80]


def _detect_curves(binary: np.ndarray) -> list[dict]:
    contours, _ = cv2.findContours(binary, cv2.RETR_LIST, cv2.CHAIN_APPROX_NONE)
    output = []
    for contour in contours:
        if len(contour) < 24:
            continue
        points = contour.reshape(-1, 2).astype(float)
        chord = float(np.linalg.norm(points[-1] - points[0]))
        perimeter = float(cv2.arcLength(contour, False))
        if chord < 12 or perimeter < 40:
            continue
        ratio = perimeter / chord
        x, y, width, height = cv2.boundingRect(contour)
        aspect = max(width, height) / max(1, min(width, height))
        if ratio < 1.10 or aspect < 1.25:
            continue
        simplified = cv2.approxPolyDP(contour, 2.0, False).reshape(-1, 2).astype(int)
        fit = fit_circle(simplified)
        output.append({
            "id": f"C{len(output) + 1:04d}",
            "points": simplified.tolist(),
            "bbox": [int(x), int(y), int(width), int(height)],
            "length_px": round(perimeter, 2),
            "geometry": fit["geometry"],
            "fit": fit["fit"],
            "geometry_candidate": "arc_candidate" if fit["geometry"] == "arc_candidate" else "free_curve_candidate",
            "category": "unmarked",
            "status": "unmarked",
        })
    output.sort(key=lambda item: item["length_px"], reverse=True)
    return output[:50]


def _rect_center(box: list[int] | None) -> tuple[float, float] | None:
    if not box or len(box) != 4:
        return None
    x, y, width, height = box
    return x + width / 2.0, y + height / 2.0


def _point_segment_distance(point, start, end) -> float:
    p = np.asarray(point, dtype=float)
    a = np.asarray(start, dtype=float)
    b = np.asarray(end, dtype=float)
    vector = b - a
    denominator = float(np.dot(vector, vector))
    if denominator < 1e-9:
        return float(np.linalg.norm(p - a))
    t = max(0.0, min(1.0, float(np.dot(p - a, vector) / denominator)))
    return float(np.linalg.norm(p - (a + t * vector)))


def analyze_image(path: str | Path, rotation: int = 0, use_ocr: bool = True) -> tuple[dict, dict]:
    original = read_image(path)
    rotated = rotate_image(original, rotation)
    height, width = rotated.shape[:2]
    resize_scale = min(1.0, 2600.0 / max(height, width))
    work = cv2.resize(
        rotated, None, fx=resize_scale, fy=resize_scale,
        interpolation=cv2.INTER_AREA
    ) if resize_scale < 1 else rotated.copy()

    gray = cv2.cvtColor(work, cv2.COLOR_BGR2GRAY)
    enhanced = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(gray)
    blurred = cv2.GaussianBlur(enhanced, (3, 3), 0)
    block = max(15, min(51, (min(work.shape[:2]) // 20) | 1))
    binary = cv2.adaptiveThreshold(
        blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, block, 9
    )
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, np.ones((2, 2), np.uint8))
    edges = cv2.Canny(blurred, 45, 135, L2gradient=True)

    raw_lines = _detect_lines(edges)
    lines: list[dict] = []
    contours = _detect_contours(binary)
    triangles = _detect_triangles(binary)
    colored_markers = _detect_colored_markers(work)
    round_symbols = _detect_round_symbols(binary)
    curves = _detect_curves(binary)

    texts: list[dict] = []
    warnings: list[str] = []
    if use_ocr:
        texts, warning = run_rapid_ocr(work)
        if warning:
            warnings.append(warning)

    dimensions = []
    for text in texts:
        if text.get("category") != "dimension_text_candidate":
            continue
        center = _rect_center(text.get("bbox"))
        nearest = None
        if center:
            for line in raw_lines:
                midpoint = np.mean([line["start"], line["end"]], axis=0)
                distance = float(np.linalg.norm(np.asarray(center) - midpoint))
                if nearest is None or distance < nearest[0]:
                    nearest = (distance, line)
        dimensions.append({
            "text": text["text"],
            "bbox": text.get("bbox"),
            "dimension": text.get("dimension"),
            "nearest_line_id": nearest[1]["id"] if nearest else None,
            "nearest_line_distance_px": round(nearest[0], 2) if nearest else None,
            "category": "dimension_candidate",
            "status": "needs_review",
        })

    label_radius = max(30.0, min(80.0, max(work.shape[:2]) * 0.06))
    for marker in colored_markers:
        best = None
        for text in texts:
            text_center = _rect_center(text.get("bbox"))
            if text_center is None:
                continue
            distance = math.dist(marker["center"], text_center)
            if best is None or distance < best[0]:
                best = (distance, text)
        if best and best[0] <= label_radius:
            marker["label"] = best[1]["text"].strip()

    # Engineering semantics are not inferred automatically.
    # The user labels simplified geometry in the annotation stage.

    intersections = []
    for i, first in enumerate(lines):
        for second in lines[i + 1:]:
            p = np.asarray(first["start"], dtype=float)
            r = np.asarray(first["end"], dtype=float) - p
            q = np.asarray(second["start"], dtype=float)
            s = np.asarray(second["end"], dtype=float) - q
            denominator = r[0] * s[1] - r[1] * s[0]
            if abs(denominator) < 1e-8:
                continue
            delta = q - p
            t = (delta[0] * s[1] - delta[1] * s[0]) / denominator
            u = (delta[0] * r[1] - delta[1] * r[0]) / denominator
            if 0 <= t <= 1 and 0 <= u <= 1:
                angle = abs(first["angle_deg"] - second["angle_deg"]) % 180
                angle = min(angle, 180 - angle)
                intersections.append({
                    "point": (p + t * r).round(2).tolist(),
                    "line_ids": [first["id"], second["id"]],
                    "angle_difference_deg": round(angle, 2),
                    "right_angle_candidate": abs(angle - 90) <= 12,
                    "status": "needs_review",
                })

    if not dimensions:
        warnings.append("未建立可靠尺寸关联；OCR 数值和尺寸线必须人工核对。")
    warnings.append("带 X 标记的边线可能是建筑结构或明装接闪带，必须人工确认。")
    warnings.append("带箭头/弯钩的细线属于说明引线候选；图例引下线符号需单独确认。")
    warnings.append("本结果为识别候选，不是已审核的检测成果。")

    result = {
        "source_path": str(path),
        "rotation": rotation,
        "image_width": int(work.shape[1]),
        "image_height": int(work.shape[0]),
        "resize_scale": float(resize_scale),
        "raw_lines": raw_lines,
        "lines": lines,
        "point_marks": [],
        "marking_complete": False,
        "contours": contours,
        "triangles": triangles,
        "colored_markers": colored_markers,
        "round_symbols": round_symbols,
        "curves": curves,
        "texts": texts,
        "dimensions": dimensions,
        "intersections": intersections,
        "warnings": warnings,
        "calibration": {"mm_per_px": None, "status": "未标定：坐标为像素"},
    }
    prepared = {"image": work, "binary": binary, "edges": edges}
    return result, prepared


def create_overlay(prepared: dict, result: dict) -> np.ndarray:
    image = prepared["image"].copy()
    colors = {
        "dimension_line_candidate": (255, 130, 20),
        "structure_or_strip_review_candidate": (40, 190, 80),
        "line_review_candidate": (0, 165, 255),
    }
    for line in result["lines"]:
        start = tuple(map(int, line["start"]))
        end = tuple(map(int, line["end"]))
        color = colors.get(line["category"], (180, 80, 190))
        cv2.line(image, start, end, color, 2, cv2.LINE_AA)
        cv2.circle(image, start, 3, color, -1)
        cv2.circle(image, end, 3, color, -1)

    for triangle in result["triangles"]:
        points = np.asarray(triangle["vertices"], dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(image, [points], True, (20, 20, 230), 2, cv2.LINE_AA)
        x, y, width, _ = triangle["bbox"]
        label = triangle.get("label") or "TP?"
        cv2.putText(image, label, (x + width + 3, max(14, y)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (20, 20, 230), 1)

    for marker in result.get("colored_markers", []):
        points = np.asarray(marker["vertices"], dtype=np.int32).reshape((-1, 1, 2))
        color = (255, 80, 30) if marker.get("color") == "blue" else (20, 80, 240)
        cv2.polylines(image, [points], True, color, 2, cv2.LINE_AA)
        if marker.get("label"):
            x, y, width, _ = marker["bbox"]
            cv2.putText(image, marker["label"], (x + width + 3, max(14, y)), cv2.FONT_HERSHEY_SIMPLEX, 0.45, color, 1)

    for symbol in result["round_symbols"]:
        x, y = map(int, symbol["center"])
        cv2.circle(image, (x, y), int(symbol["radius_px"]), (0, 200, 220), 2)

    for curve in result["curves"]:
        points = np.asarray(curve["points"], dtype=np.int32).reshape((-1, 1, 2))
        if len(points) >= 2:
            cv2.polylines(image, [points], False, (190, 50, 190), 2, cv2.LINE_AA)

    for text in result["texts"]:
        box = text.get("bbox")
        if box:
            x, y, width, height = map(int, box)
            cv2.rectangle(image, (x, y), (x + width, y + height), (0, 220, 255), 1)
    return image
