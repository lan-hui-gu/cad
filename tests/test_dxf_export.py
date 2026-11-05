import ezdxf

from lightningcad.dxf_export import export_dxf


def test_dxf_export_and_audit(tmp_path):
    result = {
        "image_width": 300,
        "image_height": 200,
        "resize_scale": 1.0,
        "lines": [
            {
                "id": "L1",
                "start": [10, 10],
                "end": [200, 10],
                "reconstructed_start": [10, 10],
                "reconstructed_end": [200, 10],
                "category": "structure_or_strip_review_candidate",
            }
        ],
        "contours": [
            {"vertices": [[10, 10], [200, 10], [200, 100], [10, 100]], "category": "building_outline_candidate"}
        ],
        "triangles": [
            {"vertices": [[20, 20], [30, 20], [25, 10]], "center": [25, 15], "label": "Y1"}
        ],
        "round_symbols": [{"center": [50, 50], "radius_px": 5}],
        "curves": [{"points": [[60, 60], [70, 55], [80, 60]]}],
        "texts": [{"text": "5.3m", "bbox": [100, 30, 35, 15]}],
    }
    path = tmp_path / "drawing.dxf"
    export_dxf(result, path, mm_per_px=10)
    document = ezdxf.readfile(path)
    assert not document.audit().errors
    assert "BUILDING_REVIEW" in document.layers
    assert "TEST_POINT_REVIEW" in document.layers
    assert len(document.modelspace()) >= 5
