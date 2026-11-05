from __future__ import annotations

from pathlib import Path

import ezdxf


LAYER_COLORS = {
    "BUILDING_REVIEW": 3,
    "STRIP_REVIEW": 2,
    "DIMENSION_REVIEW": 5,
    "LEADER_REVIEW": 4,
    "TEST_POINT_REVIEW": 1,
    "ROUND_SYMBOL_REVIEW": 6,
    "CURVE_REVIEW": 6,
    "OCR_TEXT": 2,
    "REVIEW_NOTE": 7,
    "LINE_REVIEW": 8,
}


def export_dxf(result: dict, path: str | Path, mm_per_px: float | None = None) -> str:
    """Export editable DXF entities. Without calibration, coordinates remain pixels."""
    if mm_per_px is not None and mm_per_px <= 0:
        raise ValueError("比例标定 mm/px 必须大于 0")

    document = ezdxf.new("R2013")
    document.units = ezdxf.units.MM if mm_per_px else ezdxf.units.Unitless
    model = document.modelspace()
    for name, color in LAYER_COLORS.items():
        if name not in document.layers:
            document.layers.new(name, dxfattribs={"color": color})

    resize_scale = float(result.get("resize_scale", 1.0))
    factor = (mm_per_px / resize_scale) if mm_per_px else 1.0
    height = float(result["image_height"])

    def point(value):
        return (float(value[0]) * factor, (height - float(value[1])) * factor)

    for line in result["lines"]:
        category = line.get("category", "")
        if category == "dimension_line_candidate":
            layer = "DIMENSION_REVIEW"
        elif category == "structure_or_strip_review_candidate":
            layer = "STRIP_REVIEW"
        elif category == "leader_candidate":
            layer = "LEADER_REVIEW"
        else:
            layer = "LINE_REVIEW"
        start = line.get("reconstructed_start") or line["start"]
        end = line.get("reconstructed_end") or line["end"]
        model.add_line(point(start), point(end), dxfattribs={"layer": layer})

    for contour in result["contours"]:
        vertices = contour.get("vertices") or []
        if len(vertices) >= 3:
            layer = "BUILDING_REVIEW" if contour.get("category") == "building_outline_candidate" else "LINE_REVIEW"
            model.add_lwpolyline([point(p) for p in vertices], close=True, dxfattribs={"layer": layer})

    for triangle in result["triangles"]:
        vertices = triangle.get("vertices") or []
        if len(vertices) == 3:
            model.add_lwpolyline([point(p) for p in vertices], close=True, dxfattribs={"layer": "TEST_POINT_REVIEW"})
            if triangle.get("label"):
                x, y = triangle["center"]
                model.add_text(
                    str(triangle["label"]),
                    dxfattribs={"height": max(12.0, 18.0 * factor), "layer": "OCR_TEXT"},
                ).set_placement(point((x + 10, y - 5)))

    for symbol in result["round_symbols"]:
        model.add_circle(
            point(symbol["center"]),
            max(1.0, float(symbol["radius_px"]) * factor),
            dxfattribs={"layer": "ROUND_SYMBOL_REVIEW"},
        )

    for curve in result["curves"]:
        vertices = curve.get("points") or []
        if len(vertices) >= 2:
            model.add_lwpolyline([point(p) for p in vertices], dxfattribs={"layer": "CURVE_REVIEW"})

    for text in result["texts"]:
        box = text.get("bbox")
        if not box:
            continue
        x, y, width, text_height = box
        model.add_text(
            str(text.get("text", "")),
            dxfattribs={"height": max(12.0, 18.0 * factor), "layer": "OCR_TEXT"},
        ).set_placement(point((x, y + text_height)))

    note = "识别候选图：未校核，不可直接作为正式检测成果"
    if not mm_per_px:
        note += "；当前坐标为像素，尚未进行毫米标定"
    model.add_text(note, dxfattribs={"height": max(18.0, 24.0 * factor), "layer": "REVIEW_NOTE"}).set_placement((0, 0))

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    document.saveas(output)
    return str(output)
