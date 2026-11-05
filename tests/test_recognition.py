import cv2
import numpy as np

from lightningcad.recognition import analyze_image, create_overlay
from lightningcad.simplify import apply_simplification


def test_synthetic_sketch_recognition(tmp_path):
    image = np.full((600, 800, 3), 255, dtype=np.uint8)
    cv2.rectangle(image, (120, 100), (650, 480), (0, 0, 0), 3)
    triangle = np.array([[180, 150], [205, 150], [192, 125]], dtype=np.int32)
    cv2.fillPoly(image, [triangle], (0, 0, 0))
    path = tmp_path / "sample.png"
    cv2.imwrite(str(path), image)

    result, prepared = analyze_image(path, use_ocr=False)
    assert len(result["raw_lines"]) > 0
    assert result["lines"] == []
    assert result["image_width"] == 800

    apply_simplification(result)
    assert len(result["lines"]) > 0
    overlay = create_overlay(prepared, result)
    assert overlay.shape == image.shape
