from lightningcad.simplify import simplify_segments, apply_simplification


def test_collinear_fragments_are_merged_and_left_unmarked():
    raw = [
        {"id": "L1", "start": [10, 20], "end": [100, 21]},
        {"id": "L2", "start": [105, 20], "end": [200, 20]},
        {"id": "L3", "start": [10, 80], "end": [200, 80]},
    ]
    simplified = simplify_segments(raw)
    assert len(simplified) == 2
    long_line = max(simplified, key=lambda item: item["length_px"])
    assert long_line["length_px"] > 180
    assert long_line["merged_count"] == 2
    assert long_line["category"] == "unmarked"
    assert long_line["status"] == "unmarked"


def test_apply_simplification_keeps_raw_candidates():
    result = {
        "raw_lines": [
            {"id": "L1", "start": [0, 0], "end": [100, 0]},
            {"id": "L2", "start": [101, 1], "end": [200, 1]},
        ],
        "image_width": 200,
        "image_height": 100,
    }
    apply_simplification(result)
    assert len(result["raw_lines"]) == 2
    assert len(result["lines"]) == 1
    assert result["marking_complete"] is False
