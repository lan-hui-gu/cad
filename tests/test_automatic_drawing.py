import numpy as np
import pytest

from lightningcad.automatic_drawing import build_automatic_drawing_model
from lightningcad.simplified_preview import render_simplified_preview
from lightningcad.opencad import drawing_model_to_opencad_entities


def sample_result():
    return {
        "source_path": "sample.png",
        "image_width": 300,
        "image_height": 200,
        "resize_scale": 1.0,
        "drawing_region": {"expanded_bbox": [0, 0, 250, 190]},
        "raw_lines": [
            {"id": "L1", "start": [10, 180], "end": [210, 180], "length_px": 200},
            {"id": "L2", "start": [20, 20], "end": [20, 120], "length_px": 100},
        ],
        "lines": [
            {"id": "S1", "start": [10, 180], "end": [210, 180]},
            {"id": "S2", "start": [20, 20], "end": [20, 120]},
        ],
        "curves": [
            {"id": "C1", "points": [[40, 50], [50, 40], [60, 45]]},
            {"id": "C2", "points": [[270, 160], [280, 170], [290, 180]]},
        ],
        "triangles": [
            {"center": [20, 20], "vertices": [[15, 25], [25, 25], [20, 14]], "label": "Y1"}
        ],
        "colored_markers": [
            {"center": [20.5, 20], "vertices": [[16, 25], [25, 25], [20, 15]], "label": ""}
        ],
        "round_symbols": [
            {"center": [100, 100], "radius_px": 5},
            {"center": [280, 180], "radius_px": 5},
        ],
        "texts": [
            {"text": "9.4m", "bbox": [70, 5, 30, 12], "category": "dimension_text_candidate", "confidence": 0.9},
            {"text": "页眉杂字", "bbox": [270, 160, 25, 12], "category": "annotation_text_candidate", "confidence": 0.8}
        ],
        "dimensions": [
            {"text": "9.4m", "dimension": {"value_mm": 9400}, "nearest_line_id": "L1", "nearest_line_distance_px": 12}
        ],
    }


def test_automatic_model_uses_all_simplified_lines_without_marking():
    model = build_automatic_drawing_model(sample_result())
    assert model["review_status"] == "auto_simplified"
    assert len(model["lines"]) == 2
    assert all(line["category"] == "auto_geometry" for line in model["lines"])
    assert len(model["curves"]) == 1
    assert len(model["symbols"]) == 2
    assert len(model["texts"]) == 1
    assert model["calibration"]["mm_per_px"] == 47.0


def test_automatic_model_requires_simplified_geometry():
    with pytest.raises(ValueError, match="没有可绘制的几何对象"):
        build_automatic_drawing_model({"image_width": 10, "image_height": 10, "lines": []})


def test_simplified_preview_is_clean_white_canvas_and_contains_geometry():
    preview = render_simplified_preview(sample_result())
    assert preview.shape == (200, 300, 3)
    assert np.all(preview[0, 0] == 255)
    assert np.any(preview[180, 100] < 255)


def test_automatic_model_converts_directly_to_native_opencad_entities():
    model = build_automatic_drawing_model(sample_result())
    entities = drawing_model_to_opencad_entities(model, mm_per_px=model["calibration"]["mm_per_px"])
    types = {item["type"] for item in entities}
    layers = {item["layer"] for item in entities}
    assert {"Line", "LwPolyline", "Solid", "Circle", "Text"} <= types
    assert {"SIMPLIFIED_GEOMETRY", "SIMPLIFIED_SYMBOL", "SIMPLIFIED_TEXT", "ARC"} <= layers
