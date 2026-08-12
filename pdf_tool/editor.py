"""PDF 2.0 可视编辑器。"""

from __future__ import annotations

import math
import os
import threading
import tkinter as tk
from dataclasses import dataclass
from pathlib import Path
from tkinter import colorchooser, filedialog, messagebox, ttk

from .core import PdfToolError
from .editing import (
    InkEdit,
    PdfEdit,
    RectEdit,
    SignatureEdit,
    TextEdit,
    extract_page_text,
    get_page_sizes,
    save_pdf_edits,
)
from .translation import translate_text


@dataclass(frozen=True)
class SignatureTemplate:
    strokes: tuple[tuple[tuple[float, float], ...], ...]
    aspect: float


class SignatureDialog:
    """一个不落盘的手写签名板。"""

    def __init__(self, parent: tk.Misc) -> None:
        self.result: SignatureTemplate | None = None
        self.strokes: list[list[tuple[float, float]]] = []
        self.current: list[tuple[float, float]] | None = None
        self.window = tk.Toplevel(parent)
        self.window.title("手写签名")
        self.window.geometry("640x350")
        self.window.resizable(False, False)
        self.window.transient(parent)
        self.window.grab_set()

        body = ttk.Frame(self.window, padding=18)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="请在下方签名", font=("Segoe UI", 15, "bold")).pack(anchor="w")
        ttk.Label(body, text="签名只保存在本次编辑内存中，不会单独上传或保存。", foreground="#6e6e73").pack(
            anchor="w", pady=(2, 10)
        )
        self.canvas = tk.Canvas(
            body,
            width=600,
            height=210,
            bg="white",
            highlightthickness=1,
            highlightbackground="#d2d2d7",
            cursor="pencil",
        )
        self.canvas.pack(fill="x")
        self.canvas.create_line(35, 174, 565, 174, fill="#e5e5ea", dash=(4, 4))
        self.canvas.bind("<ButtonPress-1>", self._press)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._release)

        buttons = ttk.Frame(body)
        buttons.pack(fill="x", pady=(12, 0))
        ttk.Button(buttons, text="撤销一笔", command=self._undo).pack(side="left")
        ttk.Button(buttons, text="清空", command=self._clear).pack(side="left", padx=(8, 0))
        ttk.Button(buttons, text="取消", command=self.window.destroy).pack(side="right")
        ttk.Button(buttons, text="使用此签名", command=self._accept).pack(side="right", padx=(0, 8))
        self.window.protocol("WM_DELETE_WINDOW", self.window.destroy)
        self.window.wait_window()

    def _press(self, event: tk.Event) -> None:
        self.current = [(float(event.x), float(event.y))]
        self.strokes.append(self.current)

    def _drag(self, event: tk.Event) -> None:
        if self.current is None:
            return
        point = (float(event.x), float(event.y))
        previous = self.current[-1]
        if math.dist(previous, point) < 1.5:
            return
        self.current.append(point)
        self.canvas.create_line(*previous, *point, fill="#111111", width=3, capstyle="round", tags="ink")

    def _release(self, _event: tk.Event) -> None:
        self.current = None

    def _redraw(self) -> None:
        self.canvas.delete("ink")
        for stroke in self.strokes:
            if len(stroke) == 1:
                x, y = stroke[0]
                self.canvas.create_oval(x - 1, y - 1, x + 1, y + 1, fill="#111111", tags="ink")
            elif stroke:
                points = [coordinate for point in stroke for coordinate in point]
                self.canvas.create_line(
                    *points, fill="#111111", width=3, capstyle="round", joinstyle="round", smooth=True, tags="ink"
                )

    def _undo(self) -> None:
        if self.strokes:
            self.strokes.pop()
            self._redraw()

    def _clear(self) -> None:
        self.strokes.clear()
        self._redraw()

    def _accept(self) -> None:
        points = [point for stroke in self.strokes for point in stroke]
        if not points:
            messagebox.showwarning("还没有签名", "请先在签名板上书写。", parent=self.window)
            return
        min_x = min(point[0] for point in points)
        max_x = max(point[0] for point in points)
        min_y = min(point[1] for point in points)
        max_y = max(point[1] for point in points)
        width = max(1.0, max_x - min_x)
        height = max(1.0, max_y - min_y)
        normalized = tuple(
            tuple(((x - min_x) / width, (y - min_y) / width) for x, y in stroke)
            for stroke in self.strokes
            if stroke
        )
        self.result = SignatureTemplate(normalized, height / width)
        self.window.destroy()


class TextDialog:
    def __init__(self, parent: tk.Misc, font_size: str) -> None:
        self.result: tuple[str, float] | None = None
        self.window = tk.Toplevel(parent)
        self.window.title("添加文字")
        self.window.geometry("480x285")
        self.window.transient(parent)
        self.window.grab_set()
        body = ttk.Frame(self.window, padding=16)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text="文字内容（支持多行）").pack(anchor="w")
        self.text = tk.Text(body, height=8, wrap="word", font=("Segoe UI", 11), undo=True)
        self.text.pack(fill="both", expand=True, pady=(6, 10))
        footer = ttk.Frame(body)
        footer.pack(fill="x")
        ttk.Label(footer, text="字号").pack(side="left")
        self.size = ttk.Spinbox(footer, from_=5, to=96, width=6)
        self.size.set(font_size)
        self.size.pack(side="left", padx=(6, 0))
        ttk.Button(footer, text="取消", command=self.window.destroy).pack(side="right")
        ttk.Button(footer, text="添加", command=self._accept).pack(side="right", padx=(0, 8))
        self.text.focus_set()
        self.window.bind("<Control-Return>", lambda _event: self._accept())
        self.window.wait_window()

    def _accept(self) -> None:
        text = self.text.get("1.0", "end-1c").strip()
        try:
            size = float(self.size.get())
        except ValueError:
            messagebox.showwarning("字号无效", "字号应为 5 到 96。", parent=self.window)
            return
        if not text or not 5 <= size <= 96:
            messagebox.showwarning("内容不完整", "请输入文字，并使用 5 到 96 的字号。", parent=self.window)
            return
        self.result = (text, size)
        self.window.destroy()


class TranslationDialog:
    LANGUAGES = {
        "简体中文": "zh",
        "English": "en",
        "日本語": "ja",
        "한국어": "ko",
        "Français": "fr",
        "Deutsch": "de",
        "Español": "es",
    }

    def __init__(self, parent: tk.Misc, source_text: str, on_insert) -> None:
        self.on_insert = on_insert
        self.busy = False
        self.window = tk.Toplevel(parent)
        self.window.title("翻译文字")
        self.window.geometry("780x650")
        self.window.minsize(650, 520)
        self.window.transient(parent)

        body = ttk.Frame(self.window, padding=18)
        body.pack(fill="both", expand=True)
        body.columnconfigure(0, weight=1)
        body.rowconfigure(2, weight=1)
        body.rowconfigure(5, weight=1)
        ttk.Label(body, text="翻译当前页文字", font=("Segoe UI", 16, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(
            body,
            text="隐私提示：点击“开始翻译”后，下方原文会发送到你配置的翻译服务。",
            foreground="#b25000",
        ).grid(row=1, column=0, sticky="w", pady=(3, 10))
        self.source = tk.Text(body, wrap="word", font=("Segoe UI", 10), undo=True)
        self.source.grid(row=2, column=0, sticky="nsew")
        self.source.insert("1.0", source_text)

        settings = ttk.Frame(body)
        settings.grid(row=3, column=0, sticky="ew", pady=10)
        settings.columnconfigure(1, weight=1)
        ttk.Label(settings, text="服务地址").grid(row=0, column=0, sticky="w")
        self.endpoint = ttk.Entry(settings)
        self.endpoint.insert(0, os.environ.get("PDFTOOL_TRANSLATE_ENDPOINT", "https://libretranslate.com/translate"))
        self.endpoint.grid(row=0, column=1, sticky="ew", padx=(8, 12))
        ttk.Label(settings, text="API Key（可选）").grid(row=0, column=2, sticky="w")
        self.api_key = ttk.Entry(settings, show="●", width=18)
        self.api_key.insert(0, os.environ.get("PDFTOOL_TRANSLATE_API_KEY", ""))
        self.api_key.grid(row=0, column=3, sticky="ew", padx=(8, 0))

        ttk.Label(settings, text="目标语言").grid(row=1, column=0, sticky="w", pady=(8, 0))
        self.language = ttk.Combobox(settings, values=list(self.LANGUAGES), state="readonly", width=14)
        self.language.set("简体中文")
        self.language.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=(8, 0))
        self.run_button = ttk.Button(settings, text="开始翻译", command=self._translate)
        self.run_button.grid(row=1, column=3, sticky="e", pady=(8, 0))

        ttk.Label(body, text="译文").grid(row=4, column=0, sticky="w", pady=(2, 5))
        self.result = tk.Text(body, wrap="word", font=("Segoe UI", 10), undo=True)
        self.result.grid(row=5, column=0, sticky="nsew")
        footer = ttk.Frame(body)
        footer.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        self.status = ttk.Label(footer, text="可编辑提取结果后再翻译")
        self.status.pack(side="left")
        ttk.Button(footer, text="关闭", command=self.window.destroy).pack(side="right")
        ttk.Button(footer, text="添加译文到页面", command=self._insert).pack(side="right", padx=(0, 8))

    def _translate(self) -> None:
        if self.busy:
            return
        source = self.source.get("1.0", "end-1c")
        endpoint = self.endpoint.get()
        api_key = self.api_key.get()
        target = self.LANGUAGES[self.language.get()]
        self.busy = True
        self.run_button.configure(state="disabled")
        self.status.configure(text="正在翻译…")

        def worker() -> None:
            try:
                result = translate_text(source, target, endpoint, api_key=api_key)
                self.window.after(0, self._finished, result, None)
            except Exception as exc:
                self.window.after(0, self._finished, "", str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _finished(self, result: str, error: str | None) -> None:
        if not self.window.winfo_exists():
            return
        self.busy = False
        self.run_button.configure(state="normal")
        if error:
            self.status.configure(text="翻译失败")
            messagebox.showerror("翻译失败", error, parent=self.window)
            return
        self.result.delete("1.0", "end")
        self.result.insert("1.0", result)
        self.status.configure(text="翻译完成；可编辑译文或添加到页面")

    def _insert(self) -> None:
        value = self.result.get("1.0", "end-1c").strip()
        if not value:
            messagebox.showwarning("没有译文", "请先完成翻译或手动输入译文。", parent=self.window)
            return
        self.on_insert(value)
        self.window.destroy()


class PdfEditorWindow:
    BG = "#f5f5f7"
    CARD = "#ffffff"
    BLUE = "#0071e3"

    def __init__(self, parent: tk.Misc, source_path: str | Path | None = None) -> None:
        self.parent = parent
        self.window = tk.Toplevel(parent)
        self.window.title("PDF 简工具 2.0 · 可视编辑")
        self.window.geometry("1180x820")
        self.window.minsize(900, 650)
        self.window.configure(bg=self.BG)
        self.source_path: Path | None = None
        self.page_sizes: list[tuple[float, float]] = []
        self.page_index = 0
        self.edits: list[PdfEdit] = []
        self.undo_stack: list[tuple[PdfEdit, ...]] = []
        self.redo_stack: list[tuple[PdfEdit, ...]] = []
        self.photo = None
        self.render_scale_x = 1.0
        self.render_scale_y = 1.0
        self.render_generation = 0
        self.mode = "pen"
        self.color = "#111111"
        self.drag_points: list[tuple[float, float]] | None = None
        self.drag_start: tuple[float, float] | None = None
        self.signature: SignatureTemplate | None = None
        self.pending_text: str | None = None
        self.selected_signature: int | None = None
        self.signature_drag: str | None = None
        self.signature_drag_start: tuple[float, float] | None = None
        self.signature_drag_original: SignatureEdit | None = None
        self.signature_drag_history_saved = False
        self.busy = False

        self.page_var = tk.StringVar(value="尚未打开文件")
        self.status_var = tk.StringVar(value="打开 PDF 后即可编辑")
        self.zoom_var = tk.StringVar(value="125%")
        self.font_size_var = tk.StringVar(value="14")
        self._build_ui()
        if source_path:
            self.load_pdf(Path(source_path))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.window, padding=14)
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        header = ttk.Frame(outer)
        header.grid(row=0, column=0, sticky="ew")
        ttk.Label(header, text="可视编辑", font=("Segoe UI", 20, "bold")).pack(side="left")
        ttk.Label(header, text="文字 · 批注 · 遮盖 · 手写签名", foreground="#6e6e73").pack(
            side="left", padx=(12, 0), pady=(8, 0)
        )
        ttk.Button(header, text="另存为 PDF", command=self.save_as).pack(side="right")
        ttk.Button(header, text="打开 PDF", command=self.open_dialog).pack(side="right", padx=(0, 8))

        toolbar = ttk.Frame(outer, padding=(0, 12, 0, 10))
        toolbar.grid(row=1, column=0, sticky="ew")
        ttk.Button(toolbar, text="‹ 上一页", command=lambda: self.change_page(-1)).pack(side="left")
        ttk.Label(toolbar, textvariable=self.page_var, width=16, anchor="center").pack(side="left", padx=4)
        ttk.Button(toolbar, text="下一页 ›", command=lambda: self.change_page(1)).pack(side="left")
        ttk.Label(toolbar, text="缩放").pack(side="left", padx=(14, 4))
        zoom = ttk.Combobox(toolbar, textvariable=self.zoom_var, values=("75%", "100%", "125%", "150%", "200%"), state="readonly", width=6)
        zoom.pack(side="left")
        zoom.bind("<<ComboboxSelected>>", lambda _event: self.render_page())

        ttk.Separator(toolbar, orient="vertical").pack(side="left", fill="y", padx=12)
        for text, mode in (("选择/调整", "select"), ("画笔", "pen"), ("文字", "text"), ("荧光笔", "highlight"), ("遮盖", "whiteout")):
            ttk.Button(toolbar, text=text, command=lambda value=mode: self.set_mode(value)).pack(side="left", padx=(0, 5))
        ttk.Button(toolbar, text="手写签名", command=self.create_signature).pack(side="left", padx=(2, 5))
        self.color_button = ttk.Button(toolbar, text="颜色", command=self.choose_color)
        self.color_button.pack(side="left", padx=(2, 5))
        ttk.Label(toolbar, text="字号").pack(side="left", padx=(5, 3))
        ttk.Spinbox(toolbar, textvariable=self.font_size_var, from_=5, to=96, width=5).pack(side="left")

        ttk.Button(toolbar, text="清空本页", command=self.clear_page).pack(side="right")
        ttk.Button(toolbar, text="重做", command=self.redo).pack(side="right", padx=(0, 5))
        ttk.Button(toolbar, text="撤销", command=self.undo).pack(side="right", padx=(0, 5))
        ttk.Button(toolbar, text="翻译本页", command=self.open_translation).pack(side="right", padx=(0, 12))

        canvas_frame = ttk.Frame(outer)
        canvas_frame.grid(row=2, column=0, sticky="nsew")
        canvas_frame.columnconfigure(0, weight=1)
        canvas_frame.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(canvas_frame, bg="#d9d9de", highlightthickness=0, cursor="pencil")
        xbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        ybar = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=xbar.set, yscrollcommand=ybar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        ybar.grid(row=0, column=1, sticky="ns")
        xbar.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<ButtonPress-1>", self._canvas_press)
        self.canvas.bind("<B1-Motion>", self._canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._canvas_release)
        self.canvas.bind("<MouseWheel>", self._mousewheel)
        self.window.bind("<Delete>", lambda _event: self.delete_selected())

        footer = ttk.Frame(outer, padding=(0, 9, 0, 0))
        footer.grid(row=3, column=0, sticky="ew")
        ttk.Label(footer, textvariable=self.status_var, foreground="#6e6e73").pack(side="left")
        ttk.Label(footer, text="提示：所有编辑都需“另存为”后才会写入文件", foreground="#6e6e73").pack(side="right")

    def open_dialog(self) -> None:
        if self.edits and not messagebox.askyesno("放弃当前编辑？", "打开新文件会丢弃尚未保存的编辑，继续吗？", parent=self.window):
            return
        path = filedialog.askopenfilename(parent=self.window, title="打开 PDF", filetypes=(("PDF 文件", "*.pdf"),))
        if path:
            self.load_pdf(Path(path))

    def load_pdf(self, path: Path) -> None:
        try:
            sizes = get_page_sizes(path)
        except PdfToolError as exc:
            messagebox.showerror("无法打开 PDF", str(exc), parent=self.window)
            return
        self.source_path = path.resolve()
        self.page_sizes = sizes
        self.page_index = 0
        self.edits.clear()
        self.undo_stack.clear()
        self.redo_stack.clear()
        self.selected_signature = None
        self.window.title(f"PDF 简工具 2.0 · {path.name}")
        self.render_page()

    def _zoom(self) -> float:
        try:
            return float(self.zoom_var.get().rstrip("%")) / 100
        except ValueError:
            return 1.25

    def render_page(self) -> None:
        if self.source_path is None:
            return
        self.render_generation += 1
        generation = self.render_generation
        path = self.source_path
        index = self.page_index
        zoom = self._zoom()
        self.page_var.set(f"第 {index + 1} / {len(self.page_sizes)} 页")
        self.status_var.set("正在渲染页面…")

        def worker() -> None:
            try:
                import pypdfium2 as pdfium

                document = pdfium.PdfDocument(str(path))
                page = document[index]
                bitmap = page.render(scale=zoom)
                image = bitmap.to_pil().convert("RGB").copy()
                bitmap.close()
                page.close()
                document.close()
                self.window.after(0, self._render_finished, generation, image, None)
            except Exception as exc:
                self.window.after(0, self._render_finished, generation, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _render_finished(self, generation: int, image, error: str | None) -> None:
        if generation != self.render_generation or not self.window.winfo_exists():
            return
        if error:
            self.status_var.set("页面渲染失败")
            messagebox.showerror("无法预览", f"页面渲染失败：{error}", parent=self.window)
            return
        from PIL import ImageTk

        self.photo = ImageTk.PhotoImage(image)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, image=self.photo, anchor="nw", tags="page")
        self.canvas.configure(scrollregion=(0, 0, image.width, image.height))
        width, height = self.page_sizes[self.page_index]
        self.render_scale_x = image.width / width
        self.render_scale_y = image.height / height
        self._redraw_edits()
        count = sum(edit.page == self.page_index for edit in self.edits)
        self.status_var.set(f"{self.source_path.name} · 本页 {count} 项编辑 · 当前工具：{self._mode_name()}")

    def change_page(self, delta: int) -> None:
        if not self.page_sizes:
            return
        target = self.page_index + delta
        if 0 <= target < len(self.page_sizes):
            self.page_index = target
            self.selected_signature = None
            self.render_page()

    def set_mode(self, mode: str) -> None:
        self.mode = mode
        self.signature = None
        self.pending_text = None
        self.selected_signature = None
        cursors = {"select": "arrow", "pen": "pencil", "text": "xterm", "highlight": "crosshair", "whiteout": "crosshair"}
        self.canvas.configure(cursor=cursors.get(mode, "crosshair"))
        self._redraw_edits()
        self.status_var.set(f"当前工具：{self._mode_name()}；在页面上操作")

    def _mode_name(self) -> str:
        return {
            "pen": "画笔",
            "select": "选择/调整",
            "text": "文字",
            "text_pending": "放置译文",
            "highlight": "荧光笔",
            "whiteout": "遮盖",
            "signature": "放置签名",
        }.get(self.mode, self.mode)

    def choose_color(self) -> None:
        result = colorchooser.askcolor(self.color, title="选择批注颜色", parent=self.window)
        if result[1]:
            self.color = result[1]

    def create_signature(self) -> None:
        if self.source_path is None:
            messagebox.showwarning("尚未打开 PDF", "请先打开要签名的 PDF。", parent=self.window)
            return
        dialog = SignatureDialog(self.window)
        if dialog.result:
            self.signature = dialog.result
            self.mode = "signature"
            self.selected_signature = None
            self.canvas.configure(cursor="crosshair")
            self.status_var.set("签名已准备好；请在页面上点击签名左上角位置")

    def _pdf_point(self, event: tk.Event) -> tuple[float, float]:
        x = self.canvas.canvasx(event.x) / self.render_scale_x
        y = self.canvas.canvasy(event.y) / self.render_scale_y
        width, height = self.page_sizes[self.page_index]
        return max(0.0, min(width, x)), max(0.0, min(height, y))

    def _canvas_press(self, event: tk.Event) -> None:
        if self.source_path is None or self.photo is None:
            return
        point = self._pdf_point(event)
        if self.mode == "select":
            self._select_signature_at(point)
        elif self.mode == "text":
            dialog = TextDialog(self.window, self.font_size_var.get())
            if dialog.result:
                text, size = dialog.result
                self.font_size_var.set(f"{size:g}")
                self._add_edit(TextEdit(self.page_index, *point, text, size, self.color))
        elif self.mode == "text_pending" and self.pending_text:
            try:
                size = float(self.font_size_var.get())
            except ValueError:
                size = 14.0
            self._add_edit(TextEdit(self.page_index, *point, self.pending_text, size, self.color))
            self.pending_text = None
            self.mode = "text"
        elif self.mode == "signature" and self.signature:
            page_width, page_height = self.page_sizes[self.page_index]
            width = min(180.0, max(40.0, page_width - point[0]))
            height = width * self.signature.aspect
            top = min(point[1], max(0.0, page_height - height))
            strokes = tuple(
                tuple((point[0] + x * width, top + y * width) for x, y in stroke)
                for stroke in self.signature.strokes
            )
            signature = SignatureEdit(self.page_index, strokes, 2.2, self.color)
            self._add_edit(signature)
            self.selected_signature = len(self.edits) - 1
            self.signature = None
            self.mode = "select"
            self.canvas.configure(cursor="arrow")
            self._redraw_edits()
            self.status_var.set("签名已放置；拖动签名可移动，拖动四角控制点可缩放")
        elif self.mode == "pen":
            self.drag_points = [point]
        elif self.mode in {"highlight", "whiteout"}:
            self.drag_start = point

    def _canvas_drag(self, event: tk.Event) -> None:
        if self.source_path is None:
            return
        point = self._pdf_point(event)
        if self.mode == "select" and self.signature_drag and self.signature_drag_original:
            self._drag_selected_signature(point)
        elif self.mode == "pen" and self.drag_points is not None:
            if math.dist(self.drag_points[-1], point) < 0.8:
                return
            self.drag_points.append(point)
            self._draw_temp_ink()
        elif self.mode in {"highlight", "whiteout"} and self.drag_start:
            self.canvas.delete("temp")
            x1, y1 = self.drag_start
            fill = self.color if self.mode == "highlight" else "white"
            self.canvas.create_rectangle(
                x1 * self.render_scale_x,
                y1 * self.render_scale_y,
                point[0] * self.render_scale_x,
                point[1] * self.render_scale_y,
                fill=fill,
                outline="#888888",
                stipple="gray25" if self.mode == "highlight" else "",
                tags="temp",
            )

    def _canvas_release(self, event: tk.Event) -> None:
        if self.mode == "select" and self.signature_drag:
            self.signature_drag = None
            self.signature_drag_start = None
            self.signature_drag_original = None
            self.signature_drag_history_saved = False
            if self.selected_signature is not None:
                edit = self.edits[self.selected_signature]
                if isinstance(edit, SignatureEdit):
                    left, top, right, bottom = self._signature_bbox(edit)
                    self.status_var.set(
                        f"签名位置：({left:.0f}, {top:.0f}) · 大小：{right-left:.0f} × {bottom-top:.0f} pt"
                    )
        elif self.mode == "pen" and self.drag_points is not None:
            points = tuple(self.drag_points)
            self.drag_points = None
            self.canvas.delete("temp")
            if points:
                self._add_edit(InkEdit(self.page_index, (points,), 2.0, self.color))
        elif self.mode in {"highlight", "whiteout"} and self.drag_start:
            end = self._pdf_point(event)
            start = self.drag_start
            self.drag_start = None
            self.canvas.delete("temp")
            x = min(start[0], end[0])
            y = min(start[1], end[1])
            width = abs(end[0] - start[0])
            height = abs(end[1] - start[1])
            if width >= 2 and height >= 2:
                self._add_edit(RectEdit(self.page_index, x, y, width, height, self.mode, self.color))

    def _draw_temp_ink(self) -> None:
        self.canvas.delete("temp")
        if not self.drag_points:
            return
        points = [
            coordinate
            for x, y in self.drag_points
            for coordinate in (x * self.render_scale_x, y * self.render_scale_y)
        ]
        if len(points) >= 4:
            self.canvas.create_line(
                *points, fill=self.color, width=max(1, 2 * self.render_scale_x), smooth=True, capstyle="round", tags="temp"
            )

    def _add_edit(self, edit: PdfEdit) -> None:
        self._remember_state()
        self.edits.append(edit)
        self._redraw_edits()
        self.status_var.set(f"已添加{self._mode_name()}；共 {len(self.edits)} 项未保存编辑")

    def _redraw_edits(self) -> None:
        self.canvas.delete("edit")
        sx, sy = self.render_scale_x, self.render_scale_y
        for edit_index, edit in enumerate(self.edits):
            if edit.page != self.page_index:
                continue
            if isinstance(edit, TextEdit):
                self.canvas.create_text(
                    edit.x * sx,
                    edit.y * sy,
                    text=edit.text,
                    anchor="nw",
                    width=edit.max_width * sx,
                    fill=edit.color,
                    font=("Segoe UI", max(5, round(edit.font_size * sy))),
                    tags="edit",
                )
            elif isinstance(edit, InkEdit):
                for stroke in edit.strokes:
                    points = [coordinate for x, y in stroke for coordinate in (x * sx, y * sy)]
                    if len(points) >= 4:
                        self.canvas.create_line(
                            *points,
                            fill=edit.color,
                            width=max(1, edit.width * sx),
                            smooth=True,
                            capstyle="round",
                            joinstyle="round",
                            tags="edit",
                        )
                    elif len(points) == 2:
                        x, y = points
                        radius = max(1, edit.width * sx / 2)
                        self.canvas.create_oval(x - radius, y - radius, x + radius, y + radius, fill=edit.color, tags="edit")
            elif isinstance(edit, RectEdit):
                self.canvas.create_rectangle(
                    edit.x * sx,
                    edit.y * sy,
                    (edit.x + edit.width) * sx,
                    (edit.y + edit.height) * sy,
                    fill=edit.color if edit.kind == "highlight" else "white",
                    outline="",
                    stipple="gray25" if edit.kind == "highlight" else "",
                    tags="edit",
                )
        if self.selected_signature is not None and 0 <= self.selected_signature < len(self.edits):
            selected = self.edits[self.selected_signature]
            if isinstance(selected, SignatureEdit) and selected.page == self.page_index:
                self._draw_signature_handles(selected)
        self.canvas.tag_raise("edit")

    @staticmethod
    def _signature_bbox(edit: SignatureEdit) -> tuple[float, float, float, float]:
        points = [point for stroke in edit.strokes for point in stroke]
        if not points:
            return 0.0, 0.0, 1.0, 1.0
        left = min(point[0] for point in points)
        top = min(point[1] for point in points)
        right = max(point[0] for point in points)
        bottom = max(point[1] for point in points)
        return left, top, max(left + 1.0, right), max(top + 1.0, bottom)

    def _signature_handles(self, edit: SignatureEdit) -> dict[str, tuple[float, float]]:
        left, top, right, bottom = self._signature_bbox(edit)
        return {
            "nw": (left, top),
            "ne": (right, top),
            "sw": (left, bottom),
            "se": (right, bottom),
        }

    def _draw_signature_handles(self, edit: SignatureEdit) -> None:
        sx, sy = self.render_scale_x, self.render_scale_y
        left, top, right, bottom = self._signature_bbox(edit)
        self.canvas.create_rectangle(
            left * sx,
            top * sy,
            right * sx,
            bottom * sy,
            outline=self.BLUE,
            width=2,
            dash=(5, 3),
            tags="edit",
        )
        radius = 5
        for x, y in self._signature_handles(edit).values():
            x *= sx
            y *= sy
            self.canvas.create_rectangle(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                fill="white",
                outline=self.BLUE,
                width=2,
                tags="edit",
            )

    def _select_signature_at(self, point: tuple[float, float]) -> None:
        tolerance = 9 / max(0.1, min(self.render_scale_x, self.render_scale_y))
        if self.selected_signature is not None and 0 <= self.selected_signature < len(self.edits):
            current = self.edits[self.selected_signature]
            if isinstance(current, SignatureEdit) and current.page == self.page_index:
                for handle, handle_point in self._signature_handles(current).items():
                    if math.dist(point, handle_point) <= tolerance:
                        self.signature_drag = handle
                        self.signature_drag_start = point
                        self.signature_drag_original = current
                        self.signature_drag_history_saved = False
                        self.canvas.configure(cursor="sizing")
                        return

        for index in range(len(self.edits) - 1, -1, -1):
            edit = self.edits[index]
            if not isinstance(edit, SignatureEdit) or edit.page != self.page_index:
                continue
            left, top, right, bottom = self._signature_bbox(edit)
            if left - tolerance <= point[0] <= right + tolerance and top - tolerance <= point[1] <= bottom + tolerance:
                self.selected_signature = index
                self.signature_drag = "move"
                self.signature_drag_start = point
                self.signature_drag_original = edit
                self.signature_drag_history_saved = False
                self.canvas.configure(cursor="fleur")
                self._redraw_edits()
                self.status_var.set("签名已选中；拖动可移动，拖动四角可等比例缩放，Delete 可删除")
                return

        self.selected_signature = None
        self.signature_drag = None
        self.signature_drag_original = None
        self.canvas.configure(cursor="arrow")
        self._redraw_edits()

    def _drag_selected_signature(self, point: tuple[float, float]) -> None:
        if (
            self.selected_signature is None
            or self.signature_drag_start is None
            or self.signature_drag_original is None
            or not 0 <= self.selected_signature < len(self.edits)
        ):
            return
        if not self.signature_drag_history_saved:
            self._remember_state()
            self.signature_drag_history_saved = True

        original = self.signature_drag_original
        page_width, page_height = self.page_sizes[self.page_index]
        left, top, right, bottom = self._signature_bbox(original)
        original_width = max(1.0, right - left)
        original_height = max(1.0, bottom - top)

        if self.signature_drag == "move":
            dx = point[0] - self.signature_drag_start[0]
            dy = point[1] - self.signature_drag_start[1]
            dx = max(-left, min(page_width - right, dx))
            dy = max(-top, min(page_height - bottom, dy))
            strokes = tuple(tuple((x + dx, y + dy) for x, y in stroke) for stroke in original.strokes)
            updated = SignatureEdit(original.page, strokes, original.width, original.color)
        else:
            opposite = {
                "nw": (right, bottom),
                "ne": (left, bottom),
                "sw": (right, top),
                "se": (left, top),
            }[self.signature_drag]
            scale_x = abs(point[0] - opposite[0]) / original_width
            scale_y = abs(point[1] - opposite[1]) / original_height
            scale = max(20.0 / original_width, scale_x, scale_y)
            scale = min(scale, page_width / original_width, page_height / original_height)
            new_width = original_width * scale
            new_height = original_height * scale
            new_left = opposite[0] - new_width if "w" in self.signature_drag else opposite[0]
            new_top = opposite[1] - new_height if "n" in self.signature_drag else opposite[1]
            new_left = max(0.0, min(page_width - new_width, new_left))
            new_top = max(0.0, min(page_height - new_height, new_top))
            strokes = tuple(
                tuple(
                    (
                        new_left + (x - left) * scale,
                        new_top + (y - top) * scale,
                    )
                    for x, y in stroke
                )
                for stroke in original.strokes
            )
            updated = SignatureEdit(
                original.page,
                strokes,
                max(0.6, min(12.0, original.width * scale)),
                original.color,
            )
        self.edits[self.selected_signature] = updated
        self._redraw_edits()

    def _remember_state(self) -> None:
        self.undo_stack.append(tuple(self.edits))
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.redo_stack.clear()

    def delete_selected(self) -> None:
        if self.selected_signature is None or not 0 <= self.selected_signature < len(self.edits):
            return
        if not isinstance(self.edits[self.selected_signature], SignatureEdit):
            return
        self._remember_state()
        self.edits.pop(self.selected_signature)
        self.selected_signature = None
        self.signature_drag = None
        self._redraw_edits()
        self.status_var.set("已删除所选签名")

    def undo(self) -> None:
        if self.undo_stack:
            self.redo_stack.append(tuple(self.edits))
            self.edits = list(self.undo_stack.pop())
            self.selected_signature = None
            self._redraw_edits()
            self.status_var.set(f"已撤销；剩余 {len(self.edits)} 项编辑")

    def redo(self) -> None:
        if self.redo_stack:
            self.undo_stack.append(tuple(self.edits))
            self.edits = list(self.redo_stack.pop())
            self.selected_signature = None
            self._redraw_edits()
            self.status_var.set(f"已重做；共 {len(self.edits)} 项编辑")

    def clear_page(self) -> None:
        page_edits = [edit for edit in self.edits if edit.page == self.page_index]
        if not page_edits:
            return
        if not messagebox.askyesno("清空本页？", f"将移除本页的 {len(page_edits)} 项编辑。", parent=self.window):
            return
        self._remember_state()
        self.edits = [edit for edit in self.edits if edit.page != self.page_index]
        self.selected_signature = None
        self._redraw_edits()

    def open_translation(self) -> None:
        if self.source_path is None:
            messagebox.showwarning("尚未打开 PDF", "请先打开 PDF。", parent=self.window)
            return
        try:
            text = extract_page_text(self.source_path, self.page_index)
        except PdfToolError as exc:
            messagebox.showerror("无法提取文字", str(exc), parent=self.window)
            return
        if not text:
            messagebox.showinfo(
                "未提取到文字",
                "此页可能是扫描件，当前版本不含 OCR。你仍可在翻译窗口粘贴文字。",
                parent=self.window,
            )
        TranslationDialog(self.window, text, self._prepare_translated_text)

    def _prepare_translated_text(self, text: str) -> None:
        self.pending_text = text
        self.mode = "text_pending"
        self.canvas.configure(cursor="crosshair")
        self.status_var.set("译文已准备好；请点击页面上的放置位置")

    def save_as(self) -> None:
        if self.source_path is None or self.busy:
            if self.source_path is None:
                messagebox.showwarning("尚未打开 PDF", "请先打开要编辑的 PDF。", parent=self.window)
            return
        result = filedialog.asksaveasfilename(
            parent=self.window,
            title="另存编辑后的 PDF",
            initialdir=str(self.source_path.parent),
            initialfile=f"{self.source_path.stem}_已编辑.pdf",
            defaultextension=".pdf",
            filetypes=(("PDF 文件", "*.pdf"),),
        )
        if not result:
            return
        self.busy = True
        self.status_var.set("正在写入并校验 PDF…")
        source = self.source_path
        edits = tuple(self.edits)

        def worker() -> None:
            try:
                output = save_pdf_edits(source, edits, result)
                self.window.after(0, self._save_finished, output, None)
            except Exception as exc:
                self.window.after(0, self._save_finished, None, str(exc))

        threading.Thread(target=worker, daemon=True).start()

    def _save_finished(self, output: Path | None, error: str | None) -> None:
        if not self.window.winfo_exists():
            return
        self.busy = False
        if error:
            self.status_var.set("保存失败")
            messagebox.showerror("保存失败", error, parent=self.window)
            return
        self.status_var.set(f"已保存：{output}")
        messagebox.showinfo("保存完成", f"编辑后的 PDF 已保存并校验：\n{output}", parent=self.window)

    def _mousewheel(self, event: tk.Event) -> str:
        self.canvas.yview_scroll(-1 if event.delta > 0 else 1, "units")
        return "break"
