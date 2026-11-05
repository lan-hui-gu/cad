from __future__ import annotations

import json
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from .dxf_export import export_dxf
from .recognition import analyze_image, create_overlay


class LightningCADApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LightningCAD-AI · 防雷检测草图识别与 DXF 重绘")
        self.geometry("1420x900")
        self.minsize(1050, 680)
        self.source_path: Path | None = None
        self.result: dict | None = None
        self.prepared: dict | None = None
        self.overlay = None
        self.photo = None
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
        ttk.Button(toolbar, text="开始识别", command=self.recognize).pack(side="left", padx=3)
        ttk.Button(toolbar, text="导出 DXF", command=self.save_dxf).pack(side="left", padx=3)
        ttk.Button(toolbar, text="导出 JSON", command=self.save_json).pack(side="left", padx=3)
        ttk.Button(toolbar, text="保存叠加图", command=self.save_overlay).pack(side="left", padx=3)

        settings = ttk.LabelFrame(self, text="识别设置", padding=8)
        settings.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(settings, text="照片旋转").pack(side="left")
        self.rotation = tk.StringVar(value="0")
        ttk.Combobox(settings, textvariable=self.rotation, values=("0", "90", "180", "270"), width=6, state="readonly").pack(side="left", padx=(4, 16))
        self.ocr_enabled = tk.BooleanVar(value=True)
        ttk.Checkbutton(settings, text="启用本地 RapidOCR", variable=self.ocr_enabled).pack(side="left", padx=4)
        ttk.Label(settings, text="比例标定 mm/px（未标定留空）").pack(side="left", padx=(18, 4))
        self.scale_value = tk.StringVar(value="")
        ttk.Entry(settings, textvariable=self.scale_value, width=12).pack(side="left")
        ttk.Label(settings, text="未标定 DXF 使用像素坐标").pack(side="left", padx=12)

        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        left = ttk.Frame(main, padding=5)
        right = ttk.Frame(main, padding=5)
        main.add(left, weight=4)
        main.add(right, weight=2)

        ttk.Label(left, text="识别叠加预览（橙：直线；绿：结构/接闪带待判别；红：测点；紫：曲线；黄：OCR）").pack(anchor="w")
        self.canvas = tk.Canvas(left, background="#e9edf1", highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", lambda _event: self._render())

        ttk.Label(right, text="识别候选（双击可编辑）").pack(anchor="w")
        self.tabs = ttk.Notebook(right)
        self.tabs.pack(fill="both", expand=True)
        self.line_tree = self._tree("线条", ("id", "category", "length_px"), ("编号", "类别", "长度 px"))
        self.symbol_tree = self._tree("测点", ("category", "label"), ("类别", "编号"))
        self.text_tree = self._tree("文字", ("text", "confidence", "category"), ("文字", "置信度", "类别"))
        for tree in (self.line_tree, self.symbol_tree, self.text_tree):
            tree.bind("<Double-1>", self.edit_selected)

        self.status = tk.StringVar(value="请导入俯视拍摄的防雷检测手绘草图。")
        ttk.Label(self, textvariable=self.status, relief="sunken", anchor="w", padding=6).pack(fill="x")

    def _tree(self, title, columns, headings):
        frame = ttk.Frame(self.tabs, padding=4)
        self.tabs.add(frame, text=title)
        tree = ttk.Treeview(frame, columns=columns, show="headings", height=16)
        for column, heading in zip(columns, headings):
            tree.heading(column, text=heading)
            tree.column(column, width=120, anchor="w")
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
        self.status.set(f"已导入：{self.source_path.name}")
        self._render_original()

    def _render_original(self):
        if not self.source_path:
            return
        try:
            image = cv2.imdecode(np.fromfile(str(self.source_path), dtype="uint8"), cv2.IMREAD_COLOR)
            self.overlay = image
            self._render()
        except Exception as exc:
            messagebox.showerror("图片读取失败", str(exc))

    def recognize(self):
        if not self.source_path:
            messagebox.showinfo("提示", "请先导入草图。")
            return
        try:
            self.status.set("正在进行图像识别，请稍候……")
            self.update_idletasks()
            self.result, self.prepared = analyze_image(
                self.source_path,
                rotation=int(self.rotation.get()),
                use_ocr=self.ocr_enabled.get(),
            )
            self.overlay = create_overlay(self.prepared, self.result)
            self._refresh_tables()
            self._render()
            summary = (
                f"识别完成：直线 {len(self.result['lines'])} 条；"
                f"轮廓 {len(self.result['contours'])} 个；"
                f"测点候选 {len(self.result['triangles'])} 个；"
                f"曲线 {len(self.result['curves'])} 条；"
                f"OCR 文字 {len(self.result['texts'])} 项。"
            )
            self.status.set(summary)
            if self.result["warnings"]:
                messagebox.showwarning("识别结果需复核", "\n".join(self.result["warnings"]))
        except Exception as exc:
            self.status.set("识别失败")
            messagebox.showerror("识别失败", f"{type(exc).__name__}: {exc}")

    def _refresh_tables(self):
        for tree in (self.line_tree, self.symbol_tree, self.text_tree):
            tree.delete(*tree.get_children())
        if not self.result:
            return
        for line in self.result["lines"]:
            self.line_tree.insert("", "end", iid=line["id"], values=(line["id"], line["category"], line["length_px"]))
        for index, symbol in enumerate(self.result["triangles"]):
            self.symbol_tree.insert("", "end", iid=f"TP{index}", values=(symbol["category"], symbol.get("label") or ""))
        for index, text in enumerate(self.result["texts"]):
            confidence = text.get("confidence")
            confidence_text = "" if confidence is None else f"{confidence:.3f}"
            self.text_tree.insert("", "end", iid=f"TX{index}", values=(text["text"], confidence_text, text["category"]))

    def edit_selected(self, event):
        tree = event.widget
        selected = tree.selection()
        if not selected or not self.result:
            return
        item_id = selected[0]
        if tree is self.line_tree:
            record = next((x for x in self.result["lines"] if x["id"] == item_id), None)
            if not record:
                return
            new_category = simpledialog.askstring(
                "修改线条类别",
                "输入类别（例如 building_structure_candidate、exposed_strip_candidate、dimension_line_candidate、leader_candidate）：",
                initialvalue=record["category"],
                parent=self,
            )
            if new_category:
                record["category"] = new_category.strip()
        elif tree is self.symbol_tree:
            index = int(item_id.replace("TP", ""))
            record = self.result["triangles"][index]
            label = simpledialog.askstring("修改测点编号", "输入测点编号：", initialvalue=record.get("label") or "", parent=self)
            if label is not None:
                record["label"] = label.strip()
        elif tree is self.text_tree:
            index = int(item_id.replace("TX", ""))
            record = self.result["texts"][index]
            new_text = simpledialog.askstring("修改 OCR 文字", "校正识别文字：", initialvalue=record["text"], parent=self)
            if new_text is not None:
                record["text"] = new_text.strip()
        self._refresh_tables()

    def _render(self):
        if self.overlay is None:
            return
        height, width = self.overlay.shape[:2]
        canvas_width = max(100, self.canvas.winfo_width())
        canvas_height = max(100, self.canvas.winfo_height())
        scale = min((canvas_width - 20) / width, (canvas_height - 20) / height)
        new_size = (max(1, int(width * scale)), max(1, int(height * scale)))
        rgb = cv2.cvtColor(self.overlay, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb).resize(new_size, Image.Resampling.LANCZOS)
        self.photo = ImageTk.PhotoImage(pil)
        self.canvas.delete("all")
        self.canvas.create_image(canvas_width // 2, canvas_height // 2, image=self.photo, anchor="center")

    def _scale(self) -> float | None:
        raw = self.scale_value.get().strip()
        if not raw:
            return None
        value = float(raw)
        if value <= 0:
            raise ValueError("比例标定值必须大于 0")
        return value

    def save_dxf(self):
        if not self.result:
            messagebox.showinfo("提示", "请先完成识别。")
            return
        filename = filedialog.asksaveasfilename(
            title="导出 DXF 工程图",
            defaultextension=".dxf",
            filetypes=[("DXF 文件", "*.dxf")],
        )
        if not filename:
            return
        try:
            export_dxf(self.result, filename, self._scale())
            messagebox.showinfo("导出完成", f"DXF 已保存：\n{filename}\n\n请在 CAD 软件中复核图层、尺寸和点位。")
        except Exception as exc:
            messagebox.showerror("DXF 导出失败", str(exc))

    def save_json(self):
        if not self.result:
            messagebox.showinfo("提示", "请先完成识别。")
            return
        filename = filedialog.asksaveasfilename(
            title="导出识别数据",
            defaultextension=".json",
            filetypes=[("JSON 文件", "*.json")],
        )
        if filename:
            Path(filename).write_text(json.dumps(self.result, ensure_ascii=False, indent=2), encoding="utf-8")
            messagebox.showinfo("导出完成", f"识别数据已保存：\n{filename}")

    def save_overlay(self):
        if self.overlay is None:
            messagebox.showinfo("提示", "请先导入照片或完成识别。")
            return
        filename = filedialog.asksaveasfilename(
            title="保存识别叠加图",
            defaultextension=".png",
            filetypes=[("PNG 图片", "*.png")],
        )
        if filename:
            cv2.imencode(".png", self.overlay)[1].tofile(filename)
            messagebox.showinfo("保存完成", f"预览图已保存：\n{filename}")


def main():
    app = LightningCADApp()
    app.mainloop()
