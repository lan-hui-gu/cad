import ezdxf

from lightningcad.dxf_export import export_dxf


def test_semantic_dxf_export_and_audit(tmp_path):
    drawing_model = {
        "review_status": "user_marked",
        "image_width": 300,
        "image_height": 200,
        "resize_scale": 1.0,
        "lines": [
            {
                "id": "S1",
                "category": "building_structure",
                "start": [10, 10],
                "end": [200, 10],
            },
            {
                "id": "S2",
                "category": "exposed_air_termination",
                "start": [10, 100],
                "end": [200, 100],
            },
        ],
        "curves": [
            {"id": "C1", "category": "arc", "points": [[40, 40], [50, 30], [60, 28], [70, 35]]}
        ],
        "points": [
            {"id": "P1", "category": "test_point", "position": [50, 50], "label": "Y1"},
            {"id": "P2", "category": "grounding_point", "position": [90, 90], "label": ""},
        ],
        "texts": [
            {"text": "5.3m", "position": [110, 60], "layer": "OCR_TEXT"}
        ],
    }
    path = tmp_path / "drawing.dxf"
    export_dxf(drawing_model, path, mm_per_px=10)
    document = ezdxf.readfile(path)
    audit = document.audit()
    assert not audit.errors
    assert "BUILDING_STRUCTURE" in document.layers
    assert "EXPOSED_AIR_TERMINATION" in document.layers
    assert "TEST_POINT" in document.layers
    assert "ARC" in document.layers
    assert len(document.modelspace()) >= 8
