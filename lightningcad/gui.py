from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from .categories import CURVE_CATEGORIES, LINE_CATEGORIES, POINT_CATEGORIES
from .drawing_model import build_drawing_model
from .opencad import export_with_opencad, find_opencad_executable
from .recognition import analyze_image
from .simplify import apply_simplification


LINE_COLORS = {
    "unmarked": (0, 165, 255),
    "building_structure": (30, 180, 30),
    "exposed_air_termination": (30, 30, 230),
    "concealed_air_termination": (200, 50, 200),
    "down_conductor": (230, 100, 20),
    "annotation_leader": (0, 210, 220),
    "dimension_line": (255, 140, 0),
    "ignore": (120, 120, 120),
}


class LightningCADApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LightningCAD-AI · 识别 → 拓扑简化 → 标记 → OpenCADStudio 原生绘图")
        self.geometry("1560x960")
        self.minsize(1120, 720)
        self.source_path: Path | None = None
        self.result: dict | None = None
        self.prepared: dict | None = None
        self.overlay: np.ndarray | None = None
        self.photo = None
        self.stage = "empty"
        self.selected_line_id: str | None = None
        self.selected_curve_id: str | None = None
        self.selected_point_id: str | None = None
        self.point_mode = False
        self.view_scale = 1.0
        self.view_offset_x = 0.0
        self.view_offset_y = 0.0
        self.opencad_exe = tk.StringVar(value=find_opencad_executable() or "")
        self.open_after_export = tk.BooleanVar(value=True)
        self._build_ui()

    def _build_ui(self):
        style = ttk.Style(self)
        try:
            if "vista" in style.theme_names():
                style.theme_use("vista")
        except tk.TclError:
            pass

        toolbar = ttk.Frame(self, padding=8)
        toolbar.pack(fill="x")
        ttk.Button(toolbar, text="导入草图", command=self.open_image).pack(side="left", padx=3)
        ttk.Button(toolbar, text="1.识别原始线条", command=self.recognize).pack(side="left", padx=3)
        ttk.Button(toolbar, text="2.简化线条", command=self.simplify).pack(side="left", padx=3)
        ttk.Button(toolbar, text="3.完成标记", command=self.finish_marking).pack(side="left", padx=3)
        ttk.Button(toolbar, text="4.OpenCADStudio 原生绘图", command=self.save_to_opencad).pack(side="left", padx=3)
        ttk.Button(toolbar, text="导出项目 JSON", command=self.save_json).pack(side="left", padx=3)
        ttk.Button(toolbar, text="保存当前预览", command=self.save_overlay).pack(side="left", padx=3)

        settings = ttk.LabelFrame(self, text="照片、比例与 CAD 引擎设置", padding=7)
        settings.pack(fill="x", padx=10, pady=(0, 7))
        ttk.Label(settings, text="照片旋转").pack(side="left")
        self.rotation = tk.StringVar(value="0")
        ttk.Combobox(settings, textvariable=self.rotation, values=("0", "90", "180", "270"), width=6, state="readonly").pack(side="left", padx=(4, 16))
        self.ocr_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings, text="本地 RapidOCR 文字识别", variable=self.ocr_enabled).pack(side="left", padx=4)
        ttk.Label(settings, text="比例标定（原始照片 mm/px，未知可留空）").pack(side="left", padx=(18, 4))
        self.scale_value = tk.StringVar(value="")
        ttk.Entry(settings, textvariable=self.scale_value, width=12).pack(side="left")
        ttk.Label(settings, text="未标定时按像素单位绘图").pack(side="left", padx=8)
        ttk.Label(settings, text="OpenCADStudio v2026.44").pack(side="left", padx=(12, 3))
        ttk.Entry(settings, textvariable=self.opencad_exe, width=32).pack(side="left", padx=3)
        ttk.Button(settings, text="选择 EXE", command=self.choose_opencad).pack(side="left", padx=3)
        ttk.Checkbutton(settings, text="完成后打开 CAD 图纸", variable=self.open_after_export).pack(side="left", padx=5)

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        left = ttk.Frame(main, padding=5)
        right = ttk.Frame(main, padding=5)
        main.add(left, weight=4)
        main.add(right, weight=2)

        ttk.Label(left, text="图纸工作区：简化后点击线段选择；曲线可在列表中选择；启用点位模式后点击图纸放置符号。").pack(anchor="w")
        self.canvas = tk.Canvas(left, background="#e9edf1", highlightthickness=0, cursor="crosshair")
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._render())
        self.canvas.bind("<Button-1>", self.on_canvas_click)

        controls = ttk.LabelFrame(right, text="人工标记工具", padding=8)
        controls.pack(fill="x", pady=(0, 7))

        ttk.Label(controls, text="直线类别").grid(row=0, column=0, sticky="w")
        self.line_category_label = tk.StringVar(value="建筑结构")
        ttk.Combobox(controls, textvariable=self.line_category_label, values=list(LINE_CATEGORIES.keys()), state="readonly", width=15).grid(row=0, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(controls, text="标记选中线段", command=self.apply_line_mark).grid(row=0, column=2, padx=3)
        ttk.Button(controls, text="清除", command=self.clear_line_mark).grid(row=0, column=3, padx=3)

        ttk.Label(controls, text="弧线类别").grid(row=1, column=0, sticky="w")
        self.curve_category_label = tk.StringVar(value="弧线")
        ttk.Combobox(controls, textvariable=self.curve_category_label, values=list(CURVE_CATEGORIES.keys()), state="readonly", width=15).grid(row=1, column=1, sticky="ew", padx=4, pady=2)
        ttk.Button(controls, text="标记选中弧线", command=self.apply_curve_mark).grid(row=1, column=2, padx=3)
        ttk.Button(controls, text="清除", command=self.clear_curve_mark).grid(row=1, column=3, padx=3)

        ttk.Label(controls, text="点位/符号").grid(row=2, column=0, sticky="w")
        self.point_category_label = tk.StringVar(value="测点")
        ttk.Combobox(controls, textvariable=self.point_category_label, values=list(POINT_CATEGORIES.keys()), state="readonly", width=15).grid(row=2, column=1, sticky="ew", padx=4, pady=2)
        self.point_button = ttk.Button(controls, text="在图上添加点位", command=self.toggle_point_mode)
        self.point_button.grid(row=2, column=2, padx=3)
        ttk.Button(controls, text="标记选中点位", command=self.apply_point_mark).grid(row=2, column=3, padx=3)
        ttk.Button(controls, text="删除选中点位", command=self.delete_selected_point).grid(row=3, column=3, padx=3)
        controls.columnconfigure(1, weight=1)

        ttk.Label(right, text="简化结果与人工确认").pack(anchor="w")
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.line_tree = self._tree("简化直线", ("id", "category", "length", "merged", "status"), ("编号", "类别", "长度(px)", "合并段", "状态"))
        self.curve_tree = self._tree("弧线候选", ("id", "geometry", "length", "status"), ("编号", "识别类型", "长度(px)", "状态"))
        self.point_tree = self._tree("点位符号", ("id", "category", "label", "position", "status"), ("编号", "类别", "文字", "坐标(px)", "状态"))
        self.text_tree = self._tree("OCR 文字", ("text", "confidence", "status"), ("识别文字", "置信度", "状态"))
        self.line_tree.bind("<<TreeviewSelect>>", self.on_line_select)
        self.curve_tree.bind("<<TreeviewSelect>>", self.on_curve_select)
        self.point_tree.bind("<<TreeviewSelect>>", self.on_point_select)
        self.point_tree.bind("<Double-1>", self.edit_point_label)
        self.text_tree.bind("<Double-1>", self.edit_ocr_text)

        self.status = tk.StringVar(value="请导入俯视拍摄的防雷检测手绘草图。工作流程：识别 → 拓扑简化 → 标记 → OpenCADStudio 原生绘图。")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=6).pack(fill="x")

    def _tree(self, title, columns, headings):
        frame = ttk.Frame(self.tabs, padding=4)
        self.tabs.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=16)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=105, anchor="w")
        tree.pack(fill="both", expand=True)
        return tree

    def open_image(self):
        filename = filedialog.askopenfilename(
            title="选择俯视拍摄的防雷草图",
            filetypes=[("图片", "*.jpg *.jpeg *.png *.bmp *.tif *.tiff"), ("全部文件", "*.*")],
        )
        if not filename:
            return
        self.source_path = Path(filename)
        self.result = None
        self.prepared = None
        self.overlay = None
        self.stage = "loaded"
        self.selected_line_id = self.selected_curve_id = self.selected_point_id = None
        self.point_mode = False
        self.status.set(f"已导入：{self.source_path.name}。下一步请点击“1.识别原始线条”。")
        self._render_original()

    def _render_original(self):
        if not self.source_path:
            return
        try:
            image = cv2.imdecode(np.fromfile(str(self.source_path), dtype=np.uint8), cv2.IMREAD_COLOR)
            self.overlay = image
            self._render()
        except Exception as exc:
            messagebox.showerror("图片读取失败", str(exc))

    def recognize(self):
        if not self.source_path:
            messagebox.showinfo("提示", "请先导入草图。")
            return
        try:
            self.status.set("正在识别原始线条、弧线和 OCR 文字……")
            self.update_idletasks()
            self.result, self.prepared = analyze_image(
                self.source_path, rotation=int(self.rotation.get()), use_ocr=self.ocr_enabled.get()
            )
            self.stage = "recognized"
            self.selected_line_id = self.selected_curve_id = self.selected_point_id = None
            self.result["lines"] = []
            self.result["point_marks"] = [
                {
                    "id": f"P{index:04d}",
                    "position": [round(float(marker["center"][0]), 2), round(float(marker["center"][1]), 2)],
                    "category": "test_point",
                    "label": marker.get("label", ""),
                    "status": "needs_review",
                    "source": "colored_triangle",
                }
                for index, marker in enumerate(self.result.get("colored_markers", []), start=1)
            ]
            self.result["marking_complete"] = False
            self._refresh_tables()
            self._compose_overlay()
            self._render()
            self.status.set(
                f"原始识别完成：直线候选 {len(self.result.get('raw_lines', []))} 条，"
                f"弧线候选 {len(self.result.get('curves', []))} 条。尚未生成 CAD，请进入第二步简化。"
            )
            if self.result.get("warnings"):
                messagebox.showwarning("识别提示", "\n".join(self.result["warnings"]))
        except Exception as exc:
            self.status.set("识别失败")
            messagebox.showerror("识别失败", f"{type(exc).__name__}: {exc}")

    def simplify(self):
        if not self.result:
            messagebox.showinfo("提示", "请先完成第一步原始线条识别。")
            return
        try:
            apply_simplification(self.result)
            self.stage = "simplified"
            self.selected_line_id = self.selected_curve_id = self.selected_point_id = None
            for curve in self.result.get("curves", []):
                curve["category"] = "unmarked"
                curve["status"] = "unmarked"
            self.result["marking_complete"] = False
            self._refresh_tables()
            self._compose_overlay()
            self._render()
            stats = self.result["simplification"]
            self.status.set(
                f"简化完成：原始 {stats['raw_segment_count']} 段 → 合并简化后 {stats['simplified_segment_count']} 段。"
                "请逐条选择直线/弧线并标记类别。"
            )
        except Exception as exc:
            messagebox.showerror("线条简化失败", f"{type(exc).__name__}: {exc}")

    def _refresh_tables(self):
        for tree in (self.line_tree, self.curve_tree, self.point_tree, self.text_tree):
            tree.delete(*tree.get_children())
        if not self.result:
            return

        for line in self.result.get("lines", []):
            category = line.get("category", "unmarked")
            label = next((name for name, key in LINE_CATEGORIES.items() if key == category), "待标记")
            status = "已标记" if line.get("status") == "marked" else "待标记"
            self.line_tree.insert("", "end", iid=line["id"], values=(line["id"], label, line["length_px"], line.get("merged_count", 1), status))

        for curve in self.result.get("curves", []):
            status = "已标记" if curve.get("status") == "marked" else "待标记"
            self.curve_tree.insert("", "end", iid=curve["id"], values=(curve["id"], curve.get("geometry_candidate", "曲线"), curve.get("length_px", ""), status))

        for point in self.result.get("point_marks", []):
            label = next((name for name, key in POINT_CATEGORIES.items() if key == point["category"]), "待标记")
            position = point["position"]
            status = "已确认" if point.get("status") == "marked" else "待确认"
            self.point_tree.insert("", "end", iid=point["id"], values=(point["id"], label, point.get("label", ""), f"{position[0]:.1f}, {position[1]:.1f}", status))

        for index, item in enumerate(self.result.get("texts", [])):
            confidence = item.get("confidence")
            confidence_text = "" if confidence is None else f"{confidence:.3f}"
            status = "已确认" if item.get("approved", False) else "待核对（双击校正并确认）"
            self.text_tree.insert("", "end", iid=f"TX{index}", values=(item["text"], confidence_text, status))

    def on_line_select(self, _event=None):
        selected = self.line_tree.selection()
        self.selected_line_id = selected[0] if selected else None
        self.selected_curve_id = None
        self._compose_overlay()
        self._render()

    def on_curve_select(self, _event=None):
        selected = self.curve_tree.selection()
        self.selected_curve_id = selected[0] if selected else None
        self.selected_line_id = None
        self._compose_overlay()
        self._render()

    def on_point_select(self, _event=None):
        selected = self.point_tree.selection()
        self.selected_point_id = selected[0] if selected else None
        self._compose_overlay()
        self._render()

    def apply_point_mark(self):
        if not self.result or not self.selected_point_id:
            messagebox.showinfo("提示", "请先选择一个待确认的点位符号。")
            return
        point = next((item for item in self.result.get("point_marks", []) if item["id"] == self.selected_point_id), None)
        if point is None:
            return
        point["category"] = POINT_CATEGORIES[self.point_category_label.get()]
        point["status"] = "marked"
        self._invalidate_marking()
        self._refresh_tables()
        self._compose_overlay()
        self._render()
        self.status.set(f"点位 {point.get('id')} 已确认为“{self.point_category_label.get()}”。")

    def on_canvas_click(self, event):
        if not self.result or self.stage not in ("simplified", "marked"):
            return
        image_point = self._canvas_to_image(event.x, event.y)
        if image_point is None:
            return
        if self.point_mode:
            self._add_point_mark(image_point)
            return

        candidates = self.result.get("lines", [])
        if not candidates:
            return
        nearest = min(candidates, key=lambda line: self._distance_to_segment(image_point, line["start"], line["end"]))
        distance = self._distance_to_segment(image_point, nearest["start"], nearest["end"])
        tolerance = max(10.0, 12.0 / max(self.view_scale, 0.01))
        if distance <= tolerance:
            self.selected_line_id = nearest["id"]
            self.selected_curve_id = None
            self.line_tree.selection_set(nearest["id"])
            self.line_tree.focus(nearest["id"])
            self.line_tree.see(nearest["id"])
            self._compose_overlay()
            self._render()
            self.status.set(f"已选择线段 {nearest['id']}，长度 {nearest['length_px']} px。选择类别后点击“标记选中线段”。")

    @staticmethod
    def _distance_to_segment(point, start, end):
        p = np.asarray(point, dtype=float)
        a = np.asarray(start, dtype=float)
        b = np.asarray(end, dtype=float)
        vector = b - a
        denominator = float(np.dot(vector, vector))
        if denominator < 1e-9:
            return float(np.linalg.norm(p - a))
        t = max(0.0, min(1.0, float(np.dot(p - a, vector) / denominator)))
        return float(np.linalg.norm(p - (a + t * vector)))

    def apply_line_mark(self):
        if not self.result or self.stage not in ("simplified", "marked"):
            messagebox.showinfo("提示", "请先识别并简化线条。")
            return
        if not self.selected_line_id:
            messagebox.showinfo("提示", "请先在图上或右侧列表中选择一条线段。")
            return
        category = LINE_CATEGORIES[self.line_category_label.get()]
        line = next((item for item in self.result["lines"] if item["id"] == self.selected_line_id), None)
        if line is None:
            return
        line["category"] = category
        line["status"] = "marked"
        self._invalidate_marking()
        self._refresh_tables()
        self._compose_overlay()
        self._render()
        self.status.set(f"线段 {line['id']} 已标记为“{self.line_category_label.get()}”。")

    def clear_line_mark(self):
        if not self.result or not self.selected_line_id:
            messagebox.showinfo("提示", "请先选择需要清除标记的线段。")
            return
        line = next((item for item in self.result["lines"] if item["id"] == self.selected_line_id), None)
        if line:
            line["category"] = "unmarked"
            line["status"] = "unmarked"
            self._invalidate_marking()
            self._refresh_tables()
            self._compose_overlay()
            self._render()

    def apply_curve_mark(self):
        if not self.result or self.stage not in ("simplified", "marked"):
            messagebox.showinfo("提示", "请先识别并简化图形。")
            return
        if not self.selected_curve_id:
            messagebox.showinfo("提示", "请先在“弧线候选”列表中选择一条曲线。")
            return
        curve = next((item for item in self.result.get("curves", []) if item["id"] == self.selected_curve_id), None)
        if not curve:
            return
        curve["category"] = CURVE_CATEGORIES[self.curve_category_label.get()]
        curve["status"] = "marked"
        self._invalidate_marking()
        self._refresh_tables()
        self._compose_overlay()
        self._render()

    def clear_curve_mark(self):
        if not self.result or not self.selected_curve_id:
            messagebox.showinfo("提示", "请先选择需要清除标记的弧线。")
            return
        curve = next((item for item in self.result.get("curves", []) if item["id"] == self.selected_curve_id), None)
        if curve:
            curve["category"] = "unmarked"
            curve["status"] = "unmarked"
            self._invalidate_marking()
            self._refresh_tables()
            self._compose_overlay()
            self._render()

    def toggle_point_mode(self):
        if not self.result or self.stage not in ("simplified", "marked"):
            messagebox.showinfo("提示", "请先完成线条简化。")
            return
        self.point_mode = not self.point_mode
        if self.point_mode:
            self.point_button.configure(text="点击图纸放置点位")
            self.canvas.configure(cursor="tcross")
            self.status.set(f"点位标记模式：{self.point_category_label.get()}。请在图纸上点击位置。")
        else:
            self.point_button.configure(text="在图上添加点位")
            self.canvas.configure(cursor="crosshair")
            self.status.set("已退出点位标记模式。")

    def _add_point_mark(self, position):
        category_label = self.point_category_label.get()
        category = POINT_CATEGORIES[category_label]
        label = ""
        if category != "ignore":
            default_label = f"Y{len(self.result.get('point_marks', [])) + 1}" if category == "test_point" else ""
            label = simpledialog.askstring("点位文字", f"输入{category_label}编号/文字（可留空）：", initialvalue=default_label, parent=self)
            if label is None:
                return
        point_id = f"P{len(self.result.get('point_marks', [])) + 1:04d}"
        self.result.setdefault("point_marks", []).append({
            "id": point_id,
            "position": [round(float(position[0]), 2), round(float(position[1]), 2)],
            "category": category,
            "label": label.strip(),
            "status": "marked",
        })
        self._invalidate_marking()
        self._refresh_tables()
        self._compose_overlay()
        self._render()
        self.status.set(f"已添加{category_label} {point_id}。")

    def delete_selected_point(self):
        if not self.result or not self.selected_point_id:
            messagebox.showinfo("提示", "请先在点位列表中选择一个点位。")
            return
        self.result["point_marks"] = [item for item in self.result.get("point_marks", []) if item["id"] != self.selected_point_id]
        self.selected_point_id = None
        self._invalidate_marking()
        self._refresh_tables()
        self._compose_overlay()
        self._render()

    def edit_point_label(self, _event=None):
        if not self.result:
            return
        selected = self.point_tree.selection()
        if not selected:
            return
        point = next((item for item in self.result.get("point_marks", []) if item["id"] == selected[0]), None)
        if not point:
            return
        label = simpledialog.askstring("修改点位文字", "输入编号/文字：", initialvalue=point.get("label", ""), parent=self)
        if label is not None:
            point["label"] = label.strip()
            point["status"] = "marked"
            self._invalidate_marking()
            self._refresh_tables()
            self._compose_overlay()
            self._render()

    def edit_ocr_text(self, _event=None):
        if not self.result:
            return
        selected = self.text_tree.selection()
        if not selected:
            return
        index = int(selected[0].replace("TX", ""))
        record = self.result["texts"][index]
        new_text = simpledialog.askstring("校正并确认 OCR 文字", "请核对 OCR 内容，确认后该文字才会进入 CAD：", initialvalue=record["text"], parent=self)
        if new_text is not None:
            record["text"] = new_text.strip()
            record["approved"] = bool(record["text"])
            self._invalidate_marking()
            self._refresh_tables()
            self._compose_overlay()
            self._render()

    def _invalidate_marking(self):
        if self.result is not None:
            self.result["marking_complete"] = False
            self.stage = "marked"

    def finish_marking(self):
        if not self.result or self.stage not in ("simplified", "marked"):
            messagebox.showinfo("提示", "请先完成线条识别和简化。")
            return
        valid_lines = set(LINE_CATEGORIES.values()) - {"ignore"}
        marked_lines = [item for item in self.result.get("lines", []) if item.get("category") in valid_lines]
        marked_curves = [item for item in self.result.get("curves", []) if item.get("category") == "arc"]
        valid_points = set(POINT_CATEGORIES.values()) - {"ignore"}
        marked_points = [item for item in self.result.get("point_marks", []) if item.get("category") in valid_points and item.get("status") == "marked"]
        approved_texts = [item for item in self.result.get("texts", []) if item.get("approved", False)]
        if not marked_lines and not marked_curves and not marked_points and not approved_texts:
            messagebox.showwarning("没有可绘制图元", "请至少标记一条线路/弧线、添加一个点位，或确认一项文字。")
            return
        self.result["marking_complete"] = True
        self.stage = "marked"
        messagebox.showinfo(
            "标记完成",
            f"已确认直线：{len(marked_lines)} 条；弧线：{len(marked_curves)} 条；"
            f"点位：{len(marked_points)} 个；文字：{len(approved_texts)} 项。\n"
            "下一步将仅按这些人工确认的图元交由 OpenCADStudio 原生绘制 DWG/DXF。",
        )
        self.status.set("标记已确认。现在可以使用 OpenCADStudio v2026.44 原生生成 DWG/DXF 工程图。")

    def _compose_overlay(self):
        if self.prepared is None:
            return
        image = self.prepared["image"].copy()

        if self.stage == "recognized":
            for line in self.result.get("raw_lines", []):
                start = tuple(int(round(v)) for v in line["start"])
                end = tuple(int(round(v)) for v in line["end"])
                cv2.line(image, start, end, (150, 150, 150), 1, cv2.LINE_AA)
        else:
            for line in self.result.get("lines", []):
                category = line.get("category", "unmarked")
                color = LINE_COLORS.get(category, LINE_COLORS["unmarked"])
                thickness = 4 if line["id"] == self.selected_line_id else 2
                start = tuple(int(round(v)) for v in line["start"])
                end = tuple(int(round(v)) for v in line["end"])
                cv2.line(image, start, end, color, thickness, cv2.LINE_AA)
                if line["id"] == self.selected_line_id:
                    midpoint = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
                    cv2.putText(image, line["id"], midpoint, cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 0, 255), 2, cv2.LINE_AA)

            for curve in self.result.get("curves", []):
                points = np.asarray(curve.get("points", []), dtype=np.int32).reshape((-1, 1, 2))
                if len(points) >= 2:
                    color = (200, 0, 200) if curve.get("category") == "arc" else (180, 100, 180)
                    thickness = 4 if curve["id"] == self.selected_curve_id else 2
                    cv2.polylines(image, [points], False, color, thickness, cv2.LINE_AA)

        for point in self.result.get("point_marks", []):
            x, y = (int(round(v)) for v in point["position"])
            category = point.get("category")
            if category == "test_point":
                pts = np.asarray([[x, y - 10], [x - 8, y + 7], [x + 8, y + 7]], dtype=np.int32)
                cv2.fillPoly(image, [pts], (0, 0, 230))
            elif category == "air_terminal_rod":
                cv2.circle(image, (x, y), 7, (0, 180, 0), 2)
            elif category == "elevation":
                cv2.line(image, (x, y - 10), (x, y + 10), (200, 0, 200), 2)
                cv2.circle(image, (x, y), 3, (200, 0, 200), -1)
            else:
                cv2.circle(image, (x, y), 7, (0, 180, 220), 2)
            if point.get("label"):
                cv2.putText(image, point["label"], (x + 9, y - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 230), 1, cv2.LINE_AA)
            if point["id"] == self.selected_point_id:
                cv2.circle(image, (x, y), 13, (255, 0, 255), 2)

        for item in self.result.get("texts", []):
            box = item.get("bbox")
            if not box:
                continue
            x, y, width, height = map(int, box)
            color = (0, 200, 0) if item.get("approved", False) else (0, 220, 255)
            cv2.rectangle(image, (x, y), (x + width, y + height), color, 1)

        self.overlay = image

    def _render(self):
        if self.overlay is None:
            return
        height, width = self.overlay.shape[:2]
        canvas_width = max(100, self.canvas.winfo_width())
        canvas_height = max(100, self.canvas.winfo_height())
        self.view_scale = min((canvas_width - 24) / width, (canvas_height - 24) / height)
        new_size = (max(1, int(width * self.view_scale)), max(1, int(height * self.view_scale)))
        self.view_offset_x = (canvas_width - new_size[0]) / 2.0
        self.view_offset_y = (canvas_height - new_size[1]) / 2.0
        rgb = cv2.cvtColor(self.overlay, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb).resize(new_size, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(pil)
        self.canvas.delete("all")
        self.canvas.create_image(self.view_offset_x, self.view_offset_y, image=self.photo, anchor="nw")

    def _canvas_to_image(self, x: float, y: float):
        if self.prepared is None or self.view_scale <= 0:
            return None
        image_x = (x - self.view_offset_x) / self.view_scale
        image_y = (y - self.view_offset_y) / self.view_scale
        height, width = self.prepared["image"].shape[:2]
        if not (0 <= image_x < width and 0 <= image_y < height):
            return None
        return (image_x, image_y)

    def _scale(self) -> float | None:
        raw = self.scale_value.get().strip()
        if not raw:
            return None
        value = float(raw)
        if value <= 0:
            raise ValueError("比例标定值必须大于 0")
        return value

    def choose_opencad(self):
        filename = filedialog.askopenfilename(
            title="选择 OpenCADStudio v2026.44 程序",
            filetypes=[("OpenCADStudio", "OpenCADStudio.exe"), ("Windows 程序", "*.exe")],
        )
        if filename:
            self.opencad_exe.set(filename)

    def save_to_opencad(self):
        if not self.result:
            messagebox.showinfo("提示", "请先完成识别、简化和标记。")
            return
        if not self.result.get("marking_complete"):
            messagebox.showwarning("尚未完成标记", "必须先点击“3.完成标记”，软件才会按已确认图元生成工程图。")
            return
        executable = find_opencad_executable(self.opencad_exe.get().strip() or None)
        if not executable:
            messagebox.showerror(
                "未找到 OpenCADStudio",
                "本程序不再内置其他 CAD 绘图引擎。\n请安装 OpenCADStudio v2026.44，并在设置栏选择 OpenCADStudio.exe。",
            )
            return
        self.opencad_exe.set(executable)
        filename = filedialog.asksaveasfilename(
            title="由 OpenCADStudio 原生生成防雷检测工程图",
            defaultextension=".dwg",
            initialfile=f"{self.source_path.stem if self.source_path else 'LightningCAD'}_CAD.dwg",
            filetypes=[("OpenCADStudio DWG", "*.dwg"), ("DXF 文件", "*.dxf")],
        )
        if not filename:
            return
        overwrite = Path(filename).exists()
        if overwrite and not messagebox.askyesno("确认覆盖", f"文件已存在，是否覆盖？\n{filename}"):
            return
        try:
            drawing_model = build_drawing_model(self.result)
            self.status.set("正在启动 OpenCADStudio v2026.44 原生绘图引擎……")
            self.update_idletasks()
            outcome = export_with_opencad(
                drawing_model, filename, executable, self._scale(),
                overwrite=overwrite, open_after=self.open_after_export.get(),
            )
            messagebox.showinfo(
                "OpenCADStudio 绘图完成",
                f"已通过 OpenCADStudio {outcome['version']} 原生创建并校验文件：\n"
                f"{outcome['path']}\n\nCAD 实体：{outcome['created']} 个\n"
                f"格式：{outcome['format']} {outcome['target_version']}\n"
                f"保存校验：通过\n已自动打开：{'是' if outcome['opened'] else '否'}",
            )
            self.status.set(f"OpenCADStudio 原生绘图完成：{outcome['path']}")
        except Exception as exc:
            self.status.set("OpenCADStudio 绘图失败")
            messagebox.showerror("OpenCADStudio 绘图失败", f"{type(exc).__name__}: {exc}")

    def save_json(self):
        if not self.result:
            messagebox.showinfo("提示", "请先识别草图。")
            return
        filename = filedialog.asksaveasfilename(title="导出识别与标记项目", defaultextension=".json", filetypes=[("JSON 文件", "*.json")])
        if filename:
            Path(filename).write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("导出完成", f"项目数据已保存：\n{filename}")

    def save_overlay(self):
        if self.overlay is None:
            messagebox.showinfo("提示", "请先导入照片或完成识别。")
            return
        filename = filedialog.asksaveasfilename(title="保存当前识别/标记预览", defaultextension=".png", filetypes=[("PNG 图片", "*.png")])
        if filename:
            cv2.imencode(".png", self.overlay)[1].tofile(filename)
            messagebox.showinfo("保存完成", f"预览图已保存：\n{filename}")


def main():
    app = LightningCADApp()
    app.mainloop()
