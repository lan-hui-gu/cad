from __future__ import annotations

from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont


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
    """Render a clean white-background preview from the exact simplified geometry."""
    width = int(result["image_width"])
    height = int(result["image_height"])
    if width <= 0 or height <= 0:
        raise ValueError("简化图像尺寸无效。")

    canvas = np.full((height, width, 3), 255, dtype=np.uint8)
    thickness = max(1, min(3, round(max(width, height) / 1200)))

    for segment in result.get("lines", []):
        start = tuple(int(round(value)) for value in segment["start"])
        end = tuple(int(round(value)) for value in segment["end"])
        cv2.line(canvas, start, end, (20, 20, 20), thickness, cv2.LINE_AA)

    for curve in result.get("curves", []):
        points = np.asarray(curve.get("points", []), dtype=np.int32).reshape((-1, 1, 2))
        if len(points) >= 2:
            cv2.polylines(canvas, [points], bool(curve.get("closed", False)), (20, 20, 20), thickness, cv2.LINE_AA)

    triangle_items = []
    for key in ("triangles", "colored_markers"):
        triangle_items.extend(result.get(key, []))
    seen_centers = []
    for item in triangle_items:
        vertices = item.get("vertices")
        if not isinstance(vertices, list) or len(vertices) < 3:
            continue
        points = np.asarray(vertices, dtype=np.int32).reshape((-1, 1, 2))
        center = item.get("center")
        if center is None:
            center = np.mean(points.reshape(-1, 2), axis=0).tolist()
        if any(np.linalg.norm(np.asarray(center, dtype=float) - old) <= 5.0 for old in seen_centers):
            continue
        seen_centers.append(np.asarray(center, dtype=float))
        cv2.fillPoly(canvas, [points], (15, 15, 15), lineType=cv2.LINE_AA)

    for symbol in result.get("round_symbols", []):
        center = symbol.get("center")
        radius = symbol.get("radius_px")
        if center is None or radius is None:
            continue
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
    for item in result.get("texts", []):
        box = item.get("bbox")
        value = str(item.get("text", "")).strip()
        if not value or not isinstance(box, (list, tuple)) or len(box) != 4:
            continue
        x, y, box_width, box_height = map(float, box)
        font_size = max(12, min(34, int(max(box_height, 12) * 1.15)))
        draw.text((int(x), int(y)), value, fill=(15, 15, 15), font=_font(font_size))

    return cv2.cvtColor(np.asarray(pil), cv2.COLOR_RGB2BGR)
