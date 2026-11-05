from __future__ import annotations

from pathlib import Path

import ezdxf

from .categories import LINE_LAYERS, POINT_LAYERS


LAYER_COLORS = {
    "BUILDING_STRUCTURE": 7,
    "EXPOSED_AIR_TERMINATION": 3,
    "CONCEALED_AIR_TERMINATION": 4,
    "DOWN_CONDUCTOR": 1,
    "ANNOTATION_LEADER": 8,
    "DIMENSION_LINE": 5,
    "ARC": 6,
    "TEST_POINT": 1,
    "AIR_TERMINAL_ROD": 2,
    "ELEVATION": 6,
    "DOWN_CONDUCTOR_MARKER": 1,
    "GROUNDING_POINT": 3,
    "SPD": 4,
    "METAL_COMPONENT": 7,
    "METAL_PIPE": 7,
    "OCR_TEXT": 2,
    "REVIEW_NOTE": 8,
}


def _layer_name(category: str) -> str:
    mapping = {
        "building_structure": "BUILDING_STRUCTURE",
        "exposed_air_termination": "EXPOSED_AIR_TERMINATION",
        "concealed_air_termination": "CONCEALED_AIR_TERMINATION",
        "down_conductor": "DOWN_CONDUCTOR",
        "annotation_leader": "ANNOTATION_LEADER",
        "dimension_line": "DIMENSION_LINE",
        "test_point": "TEST_POINT",
        "air_terminal_rod": "AIR_TERMINAL_ROD",
        "elevation": "ELEVATION",
        "down_conductor_marker": "DOWN_CONDUCTOR_MARKER",
        "grounding_point": "GROUNDING_POINT",
        "spd": "SPD",
        "metal_component": "METAL_COMPONENT",
        "metal_pipe": "METAL_PIPE",
    }
    return mapping[category]


def export_dxf(drawing_model: dict, path: str | Path, mm_per_px: float | None = None) -> str:
    """Draw only user-confirmed semantic entities into an editable DXF."""
    if drawing_model.get("review_status") != "user_marked":
        raise ValueError("工程图模型尚未完成用户标记。")
    if mm_per_px is not None and mm_per_px <= 0:
        raise ValueError("比例标定 mm/px 必须大于 0")

    document = ezdxf.new("R2013")
    document.units = ezdxf.units.MM if mm_per_px else ezdxf.units.Unitless
    model = document.modelspace()

    required_layers = set(LAYER_COLORS)
    for category in LINE_LAYERS:
        required_layers.add(_layer_name(category))
    for category in POINT_LAYERS:
        required_layers.add(_layer_name(category))
    for name in sorted(required_layers):
        if name not in document.layers:
            document.layers.new(name, dxfattribs={"color": LAYER_COLORS.get(name, 7)})

    resize_scale = float(drawing_model.get("resize_scale", 1.0))
    factor = (mm_per_px / resize_scale) if mm_per_px else 1.0
    image_height = float(drawing_model["image_height"])

    def point(value):
        return (float(value[0]) * factor, (image_height - float(value[1])) * factor)

    for line in drawing_model.get("lines", []):
        layer = _layer_name(line["category"])
        model.add_line(point(line["start"]), point(line["end"]), dxfattribs={"layer": layer})

    for curve in drawing_model.get("curves", []):
        vertices = [point(value) for value in curve.get("points", [])]
        if len(vertices) >= 3:
            model.add_lwpolyline(vertices, dxfattribs={"layer": "ARC"})

    marker_size = max(3.0, 9.0 * factor)
    text_height = max(2.5, 4.0 * factor)

    for mark in drawing_model.get("points", []):
        category = mark["category"]
        layer = _layer_name(category)
        x, y = point(mark["position"])
        size = marker_size
        label = mark.get("label", "")

        if category == "test_point":
            vertices = [
                (x, y + size),
                (x - size * 0.78, y - size * 0.65),
                (x + size * 0.78, y - size * 0.65),
            ]
            model.add_solid([vertices[0], vertices[1], vertices[2], vertices[2]], dxfattribs={"layer": layer})
        elif category == "air_terminal_rod":
            model.add_circle((x, y), size * 0.45, dxfattribs={"layer": layer})
            model.add_line((x, y + size * 0.45), (x, y + size * 1.5), dxfattribs={"layer": layer})
        elif category == "elevation":
            model.add_line((x, y - size), (x, y + size), dxfattribs={"layer": layer})
            model.add_lwpolyline(
                [(x - size * 0.75, y), (x, y + size * 0.45), (x + size * 0.75, y)],
                dxfattribs={"layer": layer},
            )
        elif category == "down_conductor_marker":
            model.add_circle((x, y), size * 0.45, dxfattribs={"layer": layer})
            model.add_line((x - size, y), (x + size, y), dxfattribs={"layer": layer})
        elif category == "grounding_point":
            model.add_line((x, y + size), (x, y - size * 0.2), dxfattribs={"layer": layer})
            model.add_line((x - size, y - size * 0.2), (x + size, y - size * 0.2), dxfattribs={"layer": layer})
            model.add_line((x - size * 0.7, y - size * 0.55), (x + size * 0.7, y - size * 0.55), dxfattribs={"layer": layer})
            model.add_line((x - size * 0.35, y - size * 0.9), (x + size * 0.35, y - size * 0.9), dxfattribs={"layer": layer})
        elif category == "spd":
            model.add_lwpolyline(
                [(x - size, y - size * 0.6), (x + size, y - size * 0.6),
                 (x + size, y + size * 0.6), (x - size, y + size * 0.6)],
                close=True, dxfattribs={"layer": layer},
            )
            model.add_text("SPD", dxfattribs={"height": text_height, "layer": layer}).set_placement((x + size * 1.2, y))
        elif category == "metal_component":
            model.add_lwpolyline(
                [(x - size, y - size), (x + size, y - size),
                 (x + size, y + size), (x - size, y + size)],
                close=True, dxfattribs={"layer": layer},
            )
        elif category == "metal_pipe":
            model.add_circle((x, y), size * 0.8, dxfattribs={"layer": layer})

        if label:
            model.add_text(label, dxfattribs={"height": text_height, "layer": layer}).set_placement((x + size * 1.25, y + size * 1.25))

    for text in drawing_model.get("texts", []):
        content = text.get("text", "").strip()
        if content:
            model.add_text(
                content,
                dxfattribs={"height": text_height, "layer": "OCR_TEXT"},
            ).set_placement(point(text["position"]))

    note = "LightningCAD-AI：仅输出人工确认的图元"
    if not mm_per_px:
        note += "；坐标为像素，尚未完成实际尺寸标定"
    model.add_text(note, dxfattribs={"height": text_height, "layer": "REVIEW_NOTE"}).set_placement((0, 0))

    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    document.saveas(output)
    return str(output)
