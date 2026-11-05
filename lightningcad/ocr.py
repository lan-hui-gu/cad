from __future__ import annotations

import re
from typing import Any

import numpy as np


DIMENSION_RE = re.compile(
    r"(?<![A-Za-z])([0-9]+(?:[.,][0-9]+)?)\s*(mm|cm|m|米)?",
    re.IGNORECASE,
)


def parse_dimension_text(text: str) -> dict[str, Any] | None:
    normalized = str(text).replace("Ｏ", "0").replace("ｍ", "m").strip()
    match = DIMENSION_RE.search(normalized)
    if not match:
        return None

    value = float(match.group(1).replace(",", "."))
    unit = (match.group(2) or "").lower()
    if unit in ("m", "米"):
        value_mm = value * 1000.0
    elif unit == "cm":
        value_mm = value * 10.0
    elif unit == "mm":
        value_mm = value
    else:
        value_mm = None
        unit = "unknown"

    return {"text": normalized, "value": value, "unit": unit, "value_mm": value_mm}


def _box_to_rect(box: Any) -> list[int] | None:
    try:
        points = np.asarray(box, dtype=float)
        if points.shape == (4, 2):
            x1, y1 = points.min(axis=0)
            x2, y2 = points.max(axis=0)
            return [int(x1), int(y1), int(x2 - x1), int(y2 - y1)]
        if points.size == 4:
            x, y, width, height = points.reshape(-1)
            return [int(x), int(y), int(width), int(height)]
    except (TypeError, ValueError):
        return None
    return None


def run_rapid_ocr(image: np.ndarray) -> tuple[list[dict], str | None]:
    """Run local RapidOCR with ONNX Runtime CPU; no network/API calls are made here."""
    try:
        from rapidocr import RapidOCR
    except ImportError:
        return [], "未安装 RapidOCR；可安装项目依赖后启用 OCR。"

    try:
        engine = RapidOCR()
        result = engine(image)
        boxes = getattr(result, "boxes", None)
        texts = getattr(result, "txts", None)
        scores = getattr(result, "scores", None)

        if texts is None and isinstance(result, (list, tuple)) and len(result) >= 3:
            boxes, texts, scores = result[0], result[1], result[2]

        if texts is None:
            return [], "RapidOCR 已运行，但当前返回结构未包含可读取的文本结果。"

        output = []
        for index, raw_text in enumerate(texts):
            text = str(raw_text).strip()
            if not text:
                continue
            box = _box_to_rect(boxes[index]) if boxes is not None and index < len(boxes) else None
            score = float(scores[index]) if scores is not None and index < len(scores) else None
            parsed = parse_dimension_text(text)
            output.append({
                "text": text,
                "confidence": score,
                "bbox": box,
                "category": "dimension_text_candidate" if parsed else "annotation_text_candidate",
                "dimension": parsed,
                "status": "needs_review",
            })
        return output, None if output else "RapidOCR 未检测到文字。"
    except Exception as exc:
        return [], f"RapidOCR 运行失败：{type(exc).__name__}: {exc}"
