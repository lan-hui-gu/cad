import pytest

from lightningcad.drawing_model import build_drawing_model


def test_drawing_model_requires_user_marking():
    with pytest.raises(ValueError):
        build_drawing_model({"marking_complete": False})


def test_drawing_model_contains_only_confirmed_features():
    result = {
        "marking_complete": True,
        "image_width": 400,
        "image_height": 300,
        "resize_scale": 1.0,
        "lines": [
            {"id": "S1", "start": [10, 10], "end": [100, 10], "category": "building_structure"},
            {"id": "S2", "start": [10, 20], "end": [100, 20], "category": "unmarked"},
            {"id": "S3", "start": [10, 30], "end": [100, 30], "category": "ignore"},
        ],
        "point_marks": [
            {"id": "P1", "position": [50, 50], "category": "test_point", "label": "Y1"},
            {"id": "P2", "position": [60, 60], "category": "unmarked", "label": ""},
        ],
    }
    model = build_drawing_model(result)
    assert len(model["lines"]) == 1
    assert len(model["points"]) == 1
    assert model["points"][0]["label"] == "Y1"
