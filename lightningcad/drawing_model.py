from __future__ import annotations

from .categories import CURVE_CATEGORIES, LINE_LAYERS, POINT_LAYERS


def build_drawing_model(result: dict) -> dict:
    """Create a clean semantic drawing model from user-confirmed annotations only."""
    if not result.get("marking_complete", False):
        raise ValueError("请先完成图元标记，再生成工程图。")

    lines = []
    for segment in result.get("lines", []):
        category = segment.get("category", "unmarked")
        if category not in LINE_LAYERS:
            continue
        lines.append({
            "id": segment["id"],
            "category": category,
            "layer": LINE_LAYERS[category],
            "start": list(segment["start"]),
            "end": list(segment["end"]),
            "geometry": "line",
        })

    curves = []
    for curve in result.get("curves", []):
        category = curve.get("category", "unmarked")
        if category != "arc":
            continue
        points = curve.get("points") or []
        if len(points) >= 3:
            curves.append({
                "id": curve["id"],
                "category": "arc",
                "layer": "弧线",
                "points": [list(point) for point in points],
                "geometry": "polyline_approximation",
            })

    points = []
    for point in result.get("point_marks", []):
        if point.get("status", "marked") != "marked":
            continue
        category = point.get("category", "unmarked")
        if category not in POINT_LAYERS:
            continue
        points.append({
            "id": point["id"],
            "category": category,
            "layer": POINT_LAYERS[category],
            "position": list(point["position"]),
            "label": str(point.get("label", "")).strip(),
        })

    texts = []
    for item in result.get("texts", []):
        if not item.get("approved", False):
            continue
        box = item.get("bbox")
        if not box:
            continue
        x, y, width, height = box
        texts.append({
            "text": str(item.get("text", "")).strip(),
            "position": [float(x), float(y + height)],
            "layer": "OCR_TEXT",
        })

    if not lines and not curves and not points and not texts:
        raise ValueError("没有已确认的图元。请至少标记线路、弧线、点位或确认文字。")

    return {
        "image_width": int(result["image_width"]),
        "image_height": int(result["image_height"]),
        "resize_scale": float(result.get("resize_scale", 1.0)),
        "lines": lines,
        "curves": curves,
        "points": points,
        "texts": texts,
        "source_path": result.get("source_path", ""),
        "review_status": "user_marked",
    }
