import numpy as np
import pytest

from lightningcad.automatic_drawing import build_automatic_drawing_model
from lightningcad.simplified_preview import render_simplified_preview


def sample_result():
    return {
        "source_path": "sample.png",
        "image_width": 300,
        "image_height": 200,
        "resize_scale": 1.0,
        "raw_lines": [
            {"id": "L1", "start": [10, 180], "end": [210, 180], "length_px": 200},
            {"id": "L2", "start": [20, 20], "end": [20, 120], "length_px": 100},
        ],
        "lines": [
            {"id": "S1", "start": [10, 180], "end": [210, 180]},
            {"id": "S2", "start": [20, 20], "end": [20, 120]},
        ],
        "curves": [{"id": "C1", "points": [[40, 50], [50, 40], [60, 45]]}],
        "triangles": [
            {"center": [20, 20], "vertices": [[15, 25], [25, 25], [20, 14]], "label": "Y1"}
        ],
        "colored_markers": [
            {"center": [20.5, 20], "vertices": [[16, 25], [25, 25], [20, 15]], "label": ""}
        ],
        "round_symbols": [{"center": [100, 100], "radius_px": 5}],
        "texts": [
            {"text": "9.4m", "bbox": [70, 5, 30, 12], "category": "dimension_text_candidate", "confidence": 0.9}
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
    with pytest.raises(ValueError, match="简化线段"):
        build_automatic_drawing_model({"image_width": 10, "image_height": 10, "lines": []})


def test_simplified_preview_is_clean_white_canvas_and_contains_geometry():
    preview = render_simplified_preview(sample_result())
    assert preview.shape == (200, 300, 3)
    assert np.all(preview[0, 0] == 255)
    assert np.any(preview[180, 100] < 255)
