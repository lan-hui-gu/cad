from __future__ import annotations

import math
import re
from statistics import median

from .ocr import parse_dimension_text


PURE_DIMENSION_LABEL = re.compile(r"^\s*[0-9]+(?:[.,][0-9]+)?\s*(?:mm|cm|m|米)\s*$", re.IGNORECASE)


def _valid_point(point) -> bool:
    return (
        isinstance(point, (list, tuple))
        and len(point) == 2
        and all(isinstance(value, (int, float)) and math.isfinite(float(value)) for value in point)
    )


def _text_center(item: dict) -> list[float] | None:
    box = item.get("bbox")
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return None
    x, y, width, height = map(float, box)
    return [x + width / 2.0, y + height / 2.0]


def _inside_region(point, region: dict | None) -> bool:
    if region is None:
        return True
    if not _valid_point(point):
        return False
    x1, y1, x2, y2 = region.get("expanded_bbox", [0, 0, 0, 0])
    return x1 <= float(point[0]) <= x2 and y1 <= float(point[1]) <= y2


def _bbox_intersects_region(box, region: dict | None) -> bool:
    if region is None:
        return True
    if not isinstance(box, (list, tuple)) or len(box) != 4:
        return False
    x, y, width, height = map(float, box)
    x1, y1, x2, y2 = region.get("expanded_bbox", [0, 0, 0, 0])
    return x + width >= x1 and x <= x2 and y + height >= y1 and y <= y2


def infer_mm_per_px(result: dict) -> dict:
    """Estimate image scale from OCR dimensions linked to detected dimension lines."""
    resize_scale = float(result.get("resize_scale", 1.0) or 1.0)
    if resize_scale <= 0:
        resize_scale = 1.0
    raw_by_id = {
        item.get("id"): item
        for item in result.get("raw_lines", [])
        if item.get("id")
    }
    candidates = []
    max_dimension = max(
        float(result.get("image_width", 0) or 0),
        float(result.get("image_height", 0) or 0),
        1.0,
    )
    max_text_line_distance = max(80.0, max_dimension * 0.18)

    region = result.get("drawing_region")
    for item in result.get("dimensions", []):
        text_value = str(item.get("text", "")).strip()
        parsed = item.get("dimension") or parse_dimension_text(text_value)
        if not parsed or parsed.get("value_mm") is None:
            continue
        # Material notes such as "7 mm steel plate" are not plan dimensions.
        if not PURE_DIMENSION_LABEL.fullmatch(text_value):
            continue
        line = raw_by_id.get(item.get("nearest_line_id"))
        if not line:
            continue
        if region and not _bbox_intersects_region(
            [min(line["start"][0], line["end"][0]), min(line["start"][1], line["end"][1]),
             abs(line["end"][0] - line["start"][0]), abs(line["end"][1] - line["start"][1])],
            region,
        ):
            continue
        distance = item.get("nearest_line_distance_px")
        if distance is not None and float(distance) > max_text_line_distance:
            continue
        try:
            length_work_px = math.dist(line["start"], line["end"])
            value_mm = float(parsed["value_mm"])
        except (KeyError, TypeError, ValueError):
            continue
        minimum_dimension_line_px = max(
            24.0,
            min(float(result.get("image_width", 0) or 0), float(result.get("image_height", 0) or 0)) * 0.12,
        )
        if length_work_px < minimum_dimension_line_px or value_mm <= 0:
            continue
        angle = math.degrees(math.atan2(
            float(line["end"][1]) - float(line["start"][1]),
            float(line["end"][0]) - float(line["start"][0]),
        )) % 180.0
        horizontal_deviation = min(angle, 180.0 - angle)
        vertical_deviation = abs(angle - 90.0)
        if min(horizontal_deviation, vertical_deviation) > 20.0:
            continue
        length_original_px = length_work_px / resize_scale
        mm_per_px = value_mm / length_original_px
        if not 1e-5 <= mm_per_px <= 1e5:
            continue
        candidates.append({
            "text": str(item.get("text", parsed.get("text", ""))),
            "value_mm": value_mm,
            "line_id": line.get("id"),
            "line_length_work_px": round(length_work_px, 3),
            "text_to_line_distance_px": distance,
            "mm_per_px": mm_per_px,
        })

    if not candidates:
        return {
            "mm_per_px": None,
            "confidence": "none",
            "source": "pixel_units",
            "candidates": [],
            "message": "未找到可关联的带单位尺寸文字，CAD 将使用图像像素作为绘图单位。",
        }

    values = [item["mm_per_px"] for item in candidates]
    center = median(values)
    relative_deviations = [abs(value - center) / max(center, 1e-12) for value in values]
    spread = median(relative_deviations) if relative_deviations else 0.0

    if len(values) == 1:
        confidence = "low"
        message = "仅找到一组尺寸标定候选，比例为自动估算值，请勿视为现场实测比例。"
    elif spread <= 0.12:
        confidence = "high" if len(values) >= 3 else "medium"
        message = "多组尺寸标定结果基本一致，已采用中位数比例。"
    elif spread <= 0.25:
        confidence = "low"
        message = "尺寸标定候选存在一定偏差，已采用中位数比例，建议核对图纸尺寸。"
    else:
        return {
            "mm_per_px": None,
            "confidence": "conflict",
            "source": "pixel_units",
            "candidates": candidates,
            "message": "多组尺寸标定结果差异较大，未自动采用比例，CAD 将使用图像像素作为绘图单位。",
        }

    return {
        "mm_per_px": center,
        "confidence": confidence,
        "source": "ocr_dimension_estimate",
        "candidates": candidates,
        "message": message,
    }


def _collect_triangles(result: dict) -> list[dict]:
    candidates = []
    for source_name in ("triangles", "colored_markers"):
        for item in result.get(source_name, []):
            vertices = item.get("vertices")
            if not isinstance(vertices, list) or len(vertices) < 3:
                continue
            vertices = [list(map(float, point)) for point in vertices if _valid_point(point)]
            if len(vertices) < 3:
                continue
            center = item.get("center")
            if not _valid_point(center):
                xs = [point[0] for point in vertices]
                ys = [point[1] for point in vertices]
                center = [(min(xs) + max(xs)) / 2.0, (min(ys) + max(ys)) / 2.0]
            candidates.append({
                "kind": "triangle",
                "vertices": vertices,
                "center": list(map(float, center)),
                "label": str(item.get("label") or "").strip(),
                "source": source_name,
            })

    unique = []
    for item in candidates:
        nearby = [old for old in unique if math.dist(item["center"], old["center"]) <= 5.0]
        if nearby:
            old = min(nearby, key=lambda other: math.dist(item["center"], other["center"]))
            if item["label"] and not old["label"]:
                old["label"] = item["label"]
            continue
        unique.append(item)

    texts = result.get("texts", [])
    label_radius = max(28.0, min(90.0, max(
        float(result.get("image_width", 0) or 0),
        float(result.get("image_height", 0) or 0),
    ) * 0.055))
    for symbol in unique:
        if symbol["label"]:
            continue
        nearby = []
        for text in texts:
            center = _text_center(text)
            if center is None:
                continue
            distance = math.dist(symbol["center"], center)
            if distance <= label_radius:
                nearby.append((distance, str(text.get("text", "")).strip()))
        if nearby:
            symbol["label"] = min(nearby, key=lambda item: item[0])[1]
    return unique


def build_automatic_drawing_model(result: dict) -> dict:
    """Build CAD-ready geometry directly from simplified recognition output."""
    if not result:
        raise ValueError("没有可用的简化结果。请先执行“简化线条”，再自动生成 CAD。")

    lines = []
    for index, segment in enumerate(result.get("lines", []), start=1):
        if not _valid_point(segment.get("start")) or not _valid_point(segment.get("end")):
            continue
        if math.dist(segment["start"], segment["end"]) < 1e-3:
            continue
        lines.append({
            "id": segment.get("id", f"AUTO-L{index:04d}"),
            "category": "auto_geometry",
            "start": list(map(float, segment["start"])),
            "end": list(map(float, segment["end"])),
            "source_ids": list(segment.get("source_ids", [])),
        })

    curves = []
    region = result.get("drawing_region")
    for index, curve in enumerate(result.get("curves", []), start=1):
        points = curve.get("points") or []
        points = [list(map(float, point)) for point in points if _valid_point(point)]
        if len(points) >= 2 and any(_inside_region(point, region) for point in points):
            curves.append({
                "id": curve.get("id", f"AUTO-C{index:04d}"),
                "category": "arc",
                "points": points,
                "closed": bool(curve.get("closed", False)),
            })

    symbols = [item for item in _collect_triangles(result) if _inside_region(item.get("center"), region)]
    for symbol in result.get("round_symbols", []):
        center = symbol.get("center")
        radius = symbol.get("radius_px")
        if _valid_point(center) and _inside_region(center, region) and isinstance(radius, (int, float)) and float(radius) > 0:
            symbols.append({
                "kind": "circle",
                "center": list(map(float, center)),
                "radius": float(radius),
                "label": "",
                "source": "round_symbol",
            })

    texts = []
    for item in result.get("texts", []):
        box = item.get("bbox")
        value = str(item.get("text", "")).strip()
        if not value or not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        parsed = item.get("dimension") or parse_dimension_text(value)
        has_explicit_unit = bool(parsed and parsed.get("unit") in {"m", "cm", "mm"})
        if not has_explicit_unit and not _bbox_intersects_region(box, region):
            continue
        x, y, width, height = map(float, box)
        texts.append({
            "text": value,
            "position": [x, y + height],
            "bbox": [x, y, width, height],
            "category": "auto_text",
            "confidence": item.get("confidence"),
            "source_category": item.get("category", "annotation_text_candidate"),
        })

    if not lines and not curves and not symbols and not texts:
        raise ValueError("简化结果中没有可绘制的几何对象。")

    calibration = infer_mm_per_px(result)
    return {
        "review_status": "auto_simplified",
        "geometry_source": "simplified_result",
        "image_width": int(result["image_width"]),
        "image_height": int(result["image_height"]),
        "resize_scale": float(result.get("resize_scale", 1.0)),
        "lines": lines,
        "curves": curves,
        "points": [],
        "symbols": symbols,
        "texts": texts,
        "calibration": calibration,
        "source_path": result.get("source_path", ""),
        "statistics": {
            "line_count": len(lines),
            "curve_count": len(curves),
            "symbol_count": len(symbols),
            "text_count": len(texts),
        },
    }
