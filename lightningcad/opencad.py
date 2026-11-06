from __future__ import annotations

import json
import os
import secrets
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path


class OpenCADStudioError(RuntimeError):
    pass


LAYERS = {
    "building_structure": ("BUILDING_STRUCTURE", 7),
    "exposed_air_termination": ("EXPOSED_AIR_TERMINATION", 3),
    "concealed_air_termination": ("CONCEALED_AIR_TERMINATION", 4),
    "down_conductor": ("DOWN_CONDUCTOR", 1),
    "annotation_leader": ("ANNOTATION_LEADER", 8),
    "dimension_line": ("DIMENSION_LINE", 5),
    "arc": ("ARC", 6),
    "test_point": ("TEST_POINT", 1),
    "air_terminal_rod": ("AIR_TERMINAL_ROD", 2),
    "elevation": ("ELEVATION", 6),
    "down_conductor_marker": ("DOWN_CONDUCTOR_MARKER", 1),
    "grounding_point": ("GROUNDING_POINT", 3),
    "spd": ("SPD", 4),
    "metal_component": ("METAL_COMPONENT", 7),
    "metal_pipe": ("METAL_PIPE", 7),
    "ocr_text": ("OCR_TEXT", 2),
    "auto_geometry": ("SIMPLIFIED_GEOMETRY", 7),
    "auto_symbol": ("SIMPLIFIED_SYMBOL", 1),
    "auto_text": ("SIMPLIFIED_TEXT", 7),
}


def find_opencad_executable(explicit_path: str | Path | None = None) -> str | None:
    if explicit_path:
        candidate = Path(explicit_path).expanduser()
        if candidate.is_file():
            return str(candidate.resolve())
    found = shutil.which("OpenCADStudio.exe") or shutil.which("OpenCADStudio")
    if found:
        return str(Path(found).resolve())
    roots = [
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "OpenCADStudio" / "OpenCADStudio.exe",
        Path(os.environ.get("LOCALAPPDATA", "")) / "OpenCADStudio" / "OpenCADStudio.exe",
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "OpenCADStudio" / "OpenCADStudio.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "OpenCADStudio" / "OpenCADStudio.exe",
    ]
    return next((str(p.resolve()) for p in roots if p.is_file()), None)


def _pt(point, height: float, factor: float) -> list[float]:
    return [float(point[0]) * factor, (height - float(point[1])) * factor, 0.0]


def _valid_symbol_position(position) -> bool:
    return isinstance(position, (list, tuple)) and len(position) == 2 and all(isinstance(value, (int, float)) for value in position)


def drawing_model_to_opencad_entities(model: dict, mm_per_px: float | None = None) -> list[dict]:
    if model.get("review_status") not in {"user_marked", "auto_simplified"}:
        raise ValueError("工程图模型尚未完成自动简化或人工标记。")
    if mm_per_px is not None and mm_per_px <= 0:
        raise ValueError("比例标定 mm/px 必须大于 0。")
    height = float(model["image_height"])
    resize = float(model.get("resize_scale", 1.0))
    if resize <= 0:
        raise ValueError("图像缩放比例必须大于 0。")
    factor = (float(mm_per_px) if mm_per_px is not None else 1.0) / resize
    size = max(3.0, 7.0 * factor)
    text_height = max(2.5, 4.0 * factor)
    entities = []

    def line(a, b, layer):
        name, color = LAYERS[layer]
        entities.append({"type": "Line", "start": _pt(a, height, factor), "end": _pt(b, height, factor), "layer": name, "color": color})

    def text(value, pos, layer="ocr_text", height_px=None):
        value = str(value).strip()
        if not value:
            return
        if layer not in LAYERS:
            layer = "ocr_text"
        name, color = LAYERS[layer]
        entity_height = max(2.5, float(height_px) * factor) if height_px is not None else text_height
        entities.append({"type": "Text", "value": value, "position": _pt(pos, height, factor), "height": entity_height, "rotation_deg": 0.0, "layer": name, "color": color})

    for item in model.get("lines", []):
        if item.get("category") in LAYERS:
            line(item["start"], item["end"], item["category"])

    for item in model.get("curves", []):
        points = item.get("points") or []
        if len(points) >= 2:
            name, color = LAYERS["arc"]
            entities.append({"type": "LwPolyline", "vertices": [_pt(p, height, factor) for p in points], "closed": bool(item.get("closed", False)), "layer": name, "color": color})

    for symbol in model.get("symbols", []):
        kind = symbol.get("kind")
        name, color = LAYERS["auto_symbol"]
        if kind == "triangle":
            vertices = symbol.get("vertices") or []
            if len(vertices) >= 3:
                entities.append({
                    "type": "Solid",
                    "corners": [_pt(point, height, factor) for point in vertices[:4]],
                    "layer": name,
                    "color": color,
                })
            label = str(symbol.get("label", "")).strip()
            if label and _valid_symbol_position(symbol.get("label_position")):
                text(label, symbol["label_position"], "auto_text")
        elif kind == "circle":
            center = symbol.get("center")
            radius = float(symbol.get("radius", 0))
            if isinstance(center, (list, tuple)) and len(center) == 2 and radius > 0:
                entities.append({
                    "type": "Circle",
                    "center": _pt(center, height, factor),
                    "radius": radius * factor,
                    "layer": name,
                    "color": color,
                })

    for mark in model.get("points", []):
        if mark.get("status", "marked") != "marked":
            continue
        category = mark.get("category", "")
        if category not in LAYERS:
            continue
        x, y = map(float, mark["position"])
        name, color = LAYERS[category]
        label = str(mark.get("label", "")).strip()
        if category == "test_point":
            corners = [[x, y + size], [x - size * .78, y - size * .65], [x + size * .78, y - size * .65]]
            entities.append({"type": "Solid", "corners": [_pt(p, height, factor) for p in corners], "layer": name, "color": color})
        elif category == "air_terminal_rod":
            entities.append({"type": "Circle", "center": _pt([x, y], height, factor), "radius": size * .45, "layer": name, "color": color})
            line([x, y], [x, y - size * 1.6], category)
        elif category == "elevation":
            line([x, y - size], [x, y + size], category)
            line([x - size, y], [x, y - size * .45], category)
            line([x - size, y], [x, y + size * .45], category)
        elif category == "down_conductor_marker":
            entities.append({"type": "Circle", "center": _pt([x, y], height, factor), "radius": size * .45, "layer": name, "color": color})
            line([x - size, y], [x + size, y], category)
        elif category == "grounding_point":
            line([x, y - size], [x, y], category)
            line([x - size, y], [x + size, y], category)
            line([x - size * .7, y + size * .35], [x + size * .7, y + size * .35], category)
            line([x - size * .35, y + size * .7], [x + size * .35, y + size * .7], category)
        elif category in {"spd", "metal_component"}:
            corners = [[x-size,y-size],[x+size,y-size],[x+size,y+size],[x-size,y+size]]
            entities.append({"type": "LwPolyline", "vertices": [_pt(p, height, factor) for p in corners], "closed": True, "layer": name, "color": color})
            if category == "spd":
                text("SPD", [x + size * 1.2, y], category)
        elif category == "metal_pipe":
            entities.append({"type": "Circle", "center": _pt([x, y], height, factor), "radius": size * .8, "layer": name, "color": color})
        if label:
            text(label, [x + size * 1.25, y - size * 1.1], category)

    for item in model.get("texts", []):
        box = item.get("bbox")
        text_height_px = float(box[3]) if isinstance(box, (list, tuple)) and len(box) == 4 else None
        text(item.get("text", ""), item["position"], item.get("category", "ocr_text"), text_height_px)
    if not entities:
        raise ValueError("没有可交给 OpenCADStudio 绘制的已确认图元。")
    return entities


class OpenCADStudioSession:
    """Local-only HTTP session using OpenCADStudio's documented native automation API."""

    def __init__(self, executable: str | Path, startup_timeout: float = 90.0):
        self.executable = str(Path(executable).resolve())
        self.document_id: int | str | None = None
        if not Path(self.executable).is_file():
            raise FileNotFoundError(f"找不到 OpenCADStudio：{self.executable}")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.bind(("127.0.0.1", 0))
            self.port = probe.getsockname()[1]
        self.token = secrets.token_urlsafe(32)
        env = os.environ.copy()
        env["OCS_API_TOKEN"] = self.token
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        self.process = subprocess.Popen(
            [self.executable, "--http", str(self.port)],
            cwd=str(Path(self.executable).parent), env=env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        self.base_url = f"http://127.0.0.1:{self.port}/api/v1"
        deadline = time.monotonic() + startup_timeout
        last_error = None
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise OpenCADStudioError(f"OpenCADStudio HTTP 服务退出，代码 {self.process.returncode}。")
            try:
                ready = self.request("GET", "/ready", timeout=2)
                version = str(ready.get("version") or ready.get("build_version") or "")
                if not version:
                    state = self.request("GET", "/state", timeout=2)
                    version = str(state.get("version") or state.get("build_version") or "")
                if not version.lstrip("v").startswith("2026.44"):
                    raise OpenCADStudioError(f"需要 OpenCADStudio v2026.44，当前版本：{version or '未知'}。")
                self.version = version
                return
            except OpenCADStudioError as exc:
                last_error = exc
                if "需要 OpenCADStudio" in str(exc):
                    self.close()
                    raise
            except Exception as exc:
                last_error = exc
            time.sleep(.25)
        self.close()
        raise OpenCADStudioError(f"OpenCADStudio v2026.44 服务启动超时：{last_error or '无就绪响应'}")

    def request(self, method: str, path: str, payload: dict | None = None, timeout: float = 30) -> dict:
        data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {"Authorization": f"Bearer {self.token}", "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(self.base_url + path, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            try:
                detail = json.loads(body)
            except json.JSONDecodeError:
                detail = {"message": body}
            code = detail.get("code", "unknown")
            message = detail.get("error") or detail.get("message") or body
            raise OpenCADStudioError(f"OpenCADStudio HTTP {exc.code}: {code}: {message}") from exc
        except (urllib.error.URLError, TimeoutError) as exc:
            raise OpenCADStudioError(f"无法连接 OpenCADStudio 本地服务：{exc}") from exc
        try:
            result = json.loads(body) if body else {}
        except json.JSONDecodeError as exc:
            raise OpenCADStudioError(f"OpenCADStudio 返回无效 JSON：{body[:300]}") from exc
        if isinstance(result, dict) and result.get("ok") is False:
            raise OpenCADStudioError(f"OpenCADStudio 操作失败 [{result.get('code', 'unknown')}]：{result.get('message', result)}")
        return result

    def read_state(self):
        """Refresh the active document snapshot and retain its explicit id."""
        state = self.request("GET", "/state")
        candidates = [state]
        if isinstance(state, dict):
            candidates.extend([state.get("state"), state.get("result")])
            result = state.get("result")
            if isinstance(result, dict):
                candidates.append(result.get("state"))
        document_id = next(
            (
                candidate.get("document_id")
                for candidate in candidates
                if isinstance(candidate, dict) and candidate.get("document_id") is not None
            ),
            None,
        )
        if document_id is None:
            raise OpenCADStudioError(
                f"OpenCADStudio /state 未返回活动图纸 document_id：{json.dumps(state, ensure_ascii=False)[:800]}"
            )
        self.document_id = document_id
        return state

    def create_document(self):
        self.request("POST", "/documents", {})
        return self.read_state()

    def create_entities(self, entities):
        return self.request("POST", "/entities", {"entities": entities}, timeout=180)

    def save_verified(self, path, target_format, target_version, overwrite):
        if self.document_id is None:
            self.read_state()
        return self.request("POST", "/save_verified", {
            "document_id": self.document_id,
            "path": path,
            "target_format": target_format,
            "target_version": target_version,
            "overwrite": bool(overwrite),
        }, timeout=240)

    def close(self):
        process = getattr(self, "process", None)
        if process is None or process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=5)
        except Exception:
            try:
                process.kill()
                process.wait(timeout=3)
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, *_exc):
        self.close()


def _payload(response):
    result = response.get("result")
    return result if isinstance(result, dict) else response


def export_with_opencad(model, output_path, executable, mm_per_px=None, *, overwrite=False, open_after=True):
    output = Path(output_path).expanduser().resolve()
    extension = output.suffix.lower()
    if extension not in {".dwg", ".dxf"}:
        raise ValueError("输出格式只支持 .dwg 或 .dxf。")
    if output.exists() and not overwrite:
        raise FileExistsError(f"目标文件已存在：{output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    entities = drawing_model_to_opencad_entities(model, mm_per_px)
    exe = str(Path(executable).resolve())

    with OpenCADStudioSession(exe) as session:
        session.create_document()
        created_response = session.create_entities(entities)
        created = _payload(created_response)
        fmt = "dwg" if extension == ".dwg" else "dxf"
        version = "2018" if fmt == "dwg" else "2000"
        saved_response = session.save_verified(str(output), fmt, version, overwrite)
        saved = _payload(saved_response)
        if saved.get("verified", saved_response.get("verified")) is not True:
            raise OpenCADStudioError(f"OpenCADStudio 未确认保存结果：{json.dumps(saved, ensure_ascii=False)[:800]}")
        app_version = session.version
        created_count = int(created.get("created", len(entities)))
        layers_created = created.get("layers_created", [])

    if not output.is_file() or output.stat().st_size <= 0:
        raise OpenCADStudioError("OpenCADStudio 返回保存成功，但没有生成有效文件。")
    opened = False
    if open_after:
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0
        subprocess.Popen([exe, str(output)], cwd=str(output.parent),
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, creationflags=flags)
        opened = True
    return {
        "path": str(output), "version": app_version, "created": created_count,
        "requested_entities": len(entities), "layers_created": layers_created,
        "verified": True, "opened": opened, "format": fmt.upper(), "target_version": version,
    }
