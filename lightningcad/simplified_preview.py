from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

from .automatic_drawing import build_automatic_drawing_model


def _font(size: int):
    candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("C:/Windows/Fonts/simsun.ttc"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc"),
    ]
    for path in candidates:
        if path.is_file():
            try:
                return ImageFont.truetype(str(path), size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_simplified_preview(result: dict) -> np.ndarray:
    """Render the exact automatic CAD model on a clean white canvas.

    This renderer and the OpenCAD exporter consume the same canonical model,
    so preview geometry is not independently re-detected or re-created.
    """
    model = build_automatic_drawing_model(result)
    width = int(model["image_width"])
    height = int(model["image_height"])
    if width <= 0 or height <= 0:
        raise ValueError("简化图像尺寸无效。")

    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    thickness = max(1, min(3, round(max(width, height) / 1200)))

    for segment in model.get("lines", []):
        start = tuple(int(round(value)) for value in segment["start"])
        end = tuple(int(round(value)) for value in segment["end"])
        cv2.line(canvas, start, end, (20, 20, 20), thickness, cv2.LINE_AA)

    for curve in model.get("curves", []):
        points = np.asarray(curve.get("points", []), dtype=np.int32).reshape((-1, 1, 2))
        if len(points) >= 2:
            cv2.polylines(canvas, [points], bool(curve.get("closed", False)), (20, 20, 20), thickness, cv2.LINE_AA)

    for symbol in model.get("symbols", []):
        if symbol.get("kind") == "triangle":
            vertices = np.asarray(symbol.get("vertices", []), dtype=np.int32).reshape((-1, 1, 2))
            if len(vertices) >= 3:
                cv2.fillPoly(canvas, [vertices], (15, 15, 15), lineType=cv2.LINE_AA)
        elif symbol.get("kind") == "circle":
            center = symbol.get("center")
            radius = symbol.get("radius")
            if center is not None and radius is not None:
                cv2.circle(
                    canvas,
                    tuple(int(round(value)) for value in center),
                    max(1, int(round(radius))),
                    (20, 20, 20),
                    thickness,
                    cv2.LINE_AA,
                )

    pil = Image.fromarray(cv2.cvtColor(canvas, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil)
    for item in model.get("texts", []):
        value = str(item.get("text", "")).strip()
        if not value:
            continue
        box = item.get("bbox")
        if isinstance(box, (list, tuple)) and len(box) == 4:
            x, y, box_width, box_height = map(float, box)
            font_size = max(12, min(34, int(max(box_height, 12) * 1.15)))
            position = (int(x), int(y))
        else:
            x, baseline_y = item["position"]
            font_size = 16
            position = (int(x), int(baseline_y - font_size))
        draw.text(position, value, fill=(15, 15, 15), font=_font(font_size))

    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
