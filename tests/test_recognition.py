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
    assert create_overlay(prepared, result).shape == image.shape


def test_coloured_test_markers_are_detected(tmp_path):
    image = np.full((180, 240, 3), 255, dtype=np.uint8)
    cv2.fillPoly(image, [np.array([[40,60],[50,60],[45,72]], np.int32)], (255, 0, 0))
    cv2.fillPoly(image, [np.array([[160,40],[170,40],[165,52]], np.int32)], (0, 0, 255))
    path = tmp_path / "markers.png"
    cv2.imwrite(str(path), image)
    result, _ = analyze_image(path, use_ocr=False)
    assert len(result["colored_markers"]) == 2
    assert {item["color"] for item in result["colored_markers"]} == {"blue", "red"}
