import pytest

from lightningcad.opencad import drawing_model_to_opencad_entities


def model():
    return {
        "review_status": "user_marked", "image_width": 300, "image_height": 200, "resize_scale": 1.0,
        "lines": [
            {"category": "building_structure", "start": [10, 10], "end": [200, 10]},
            {"category": "dimension_line", "start": [20, 180], "end": [250, 180]},
        ],
        "curves": [{"category": "arc", "points": [[40, 40], [50, 30], [60, 28]]}],
        "points": [{"category": "test_point", "position": [50, 50], "label": "Y1"}],
        "texts": [{"text": "5.3 m", "position": [110, 60]}],
    }


def test_native_entities_and_layers():
    entities = drawing_model_to_opencad_entities(model(), mm_per_px=2)
    types = {e["type"] for e in entities}
    layers = {e["layer"] for e in entities}
    assert {"Line", "LwPolyline", "Solid", "Text"} <= types
    assert {"BUILDING_STRUCTURE", "DIMENSION_LINE", "TEST_POINT", "ARC"} <= layers


def test_coordinate_conversion_and_scale():
    entities = drawing_model_to_opencad_entities(model(), mm_per_px=2)
    line = next(e for e in entities if e["type"] == "Line" and e["layer"] == "BUILDING_STRUCTURE")
    assert line["start"] == [20.0, 380.0, 0.0]
    assert line["end"] == [400.0, 380.0, 0.0]


def test_review_and_scale_validation():
    data = model()
    data["review_status"] = "not_reviewed"
    with pytest.raises(ValueError, match="尚未完成"):
        drawing_model_to_opencad_entities(data)
    with pytest.raises(ValueError, match="大于 0"):
        drawing_model_to_opencad_entities(model(), mm_per_px=0)


def test_unconfirmed_point_candidate_is_omitted():
    data = model()
    data["points"][0]["status"] = "needs_review"
    entities = drawing_model_to_opencad_entities(data)
    assert not any(e.get("layer") == "TEST_POINT" for e in entities)


def test_save_verified_supplies_document_id_from_state():
    from lightningcad.opencad import OpenCADStudioSession

    session = OpenCADStudioSession.__new__(OpenCADStudioSession)
    session.document_id = None
    calls = []

    def fake_request(method, path, payload=None, timeout=30):
        calls.append((method, path, payload, timeout))
        if method == "POST" and path == "/documents":
            return {"ok": True}
        if method == "GET" and path == "/state":
            return {"document_id": 42, "documents": [{"id": 42, "title": "Untitled"}]}
        if method == "POST" and path == "/save_verified":
            return {"ok": True, "verified": True}
        raise AssertionError(f"Unexpected request: {method} {path}")

    session.request = fake_request
    session.create_document()
    result = session.save_verified("C:/out/test.dwg", "dwg", "2018", False)

    save_call = next(call for call in calls if call[1] == "/save_verified")
    assert session.document_id == 42
    assert save_call[2]["document_id"] == 42
    assert result["verified"] is True
