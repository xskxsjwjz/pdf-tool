"""PDF 简工具的 Tkinter 图形界面。"""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk

from . import __version__
from .core import (
    PdfInfo,
    PdfToolError,
    delete_pages,
    extract_pages,
    inspect_pdf,
    merge_pdfs,
    rotate_pages,
    split_pdf,
)

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    _RootWindow = TkinterDnD.Tk
    DND_AVAILABLE = True
except ImportError:
    DND_FILES = "DND_Files"
    _RootWindow = tk.Tk
    DND_AVAILABLE = False


OPERATIONS = {
    "合并 PDF": "merge",
    "删除页面": "delete",
    "提取页面": "extract",
    "旋转页面": "rotate",
    "拆分为单页": "split",
}

HELP_TEXT = {
    "merge": "列表顺序就是合并顺序，可用上移、下移调整。",
    "delete": "选中一个 PDF，输入要删除的页码，例如 1,3-5。",
    "extract": "选中一个 PDF，输入要保留到新文件的页码。",
    "rotate": "选中一个 PDF；页码留空表示旋转全部页面。",
    "split": "选中一个 PDF，将在目标文件夹中生成每页一个 PDF。",
}


def _format_size(size: int) -> str:
    value = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{size} B"


def _resource_path(relative_path: str) -> Path:
    """Locate a source-tree or PyInstaller bundled resource."""

    bundle_root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))
    bundled = bundle_root / relative_path
    if bundled.is_file():
        return bundled
    return Path(__file__).resolve().parent.parent / relative_path


class PdfToolApp:
    BG = "#f5f5f7"
    CARD = "#ffffff"
    TEXT = "#1d1d1f"
    SUBTLE = "#6e6e73"
    BLUE = "#0071e3"

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.files: list[PdfInfo] = []
        self.busy = False

        self.operation_var = tk.StringVar(value="合并 PDF")
        self.page_var = tk.StringVar()
        self.angle_var = tk.StringVar(value="90° 顺时针")
        self.output_var = tk.StringVar()
        self.help_var = tk.StringVar(value=HELP_TEXT["merge"])
        self.status_var = tk.StringVar(value="准备就绪")

        self._configure_window()
        self._configure_styles()
        self._build_ui()
        self._configure_drop()

    def _configure_window(self) -> None:
        self.root.title("PDF 简工具")
        self.root.geometry("940x700")
        self.root.minsize(820, 620)
        self.root.configure(bg=self.BG)
        try:
            self.root.iconname("PDF 简工具")
        except tk.TclError:
            pass

    def _configure_styles(self) -> None:
        style = ttk.Style(self.root)
        if "vista" in style.theme_names():
            style.theme_use("vista")
        style.configure("App.TFrame", background=self.BG)
        style.configure("Card.TFrame", background=self.CARD)
        style.configure(
            "Title.TLabel",
            background=self.BG,
            foreground=self.TEXT,
            font=("Segoe UI", 24, "bold"),
        )
        style.configure(
            "Subtitle.TLabel",
            background=self.BG,
            foreground=self.SUBTLE,
            font=("Segoe UI", 10),
        )
        style.configure(
            "Section.TLabel",
            background=self.CARD,
            foreground=self.TEXT,
            font=("Segoe UI", 11, "bold"),
        )
        style.configure(
            "Body.TLabel", background=self.CARD, foreground=self.TEXT, font=("Segoe UI", 9)
        )
        style.configure(
            "Hint.TLabel", background=self.CARD, foreground=self.SUBTLE, font=("Segoe UI", 9)
        )
        style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), padding=(18, 8))
        style.configure("Tool.TButton", font=("Segoe UI", 9), padding=(10, 6))
        style.configure("Treeview", rowheight=28, font=("Segoe UI", 9), borderwidth=0)
        style.configure("Treeview.Heading", font=("Segoe UI", 9, "bold"))

    def _build_ui(self) -> None:
        outer = ttk.Frame(self.root, style="App.TFrame", padding=(28, 24, 28, 18))
        outer.pack(fill="both", expand=True)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(2, weight=1)

        ttk.Label(outer, text="PDF 简工具", style="Title.TLabel").grid(row=0, column=0, sticky="w")
        drag_note = "支持拖入 PDF 或文件夹" if DND_AVAILABLE else "可从文件或文件夹添加 PDF"
        ttk.Label(
            outer,
            text=f"合并、删页、提取、旋转与拆分。{drag_note}。",
            style="Subtitle.TLabel",
        ).grid(row=1, column=0, sticky="w", pady=(2, 16))

        file_card = ttk.Frame(outer, style="Card.TFrame", padding=16)
        file_card.grid(row=2, column=0, sticky="nsew")
        file_card.columnconfigure(0, weight=1)
        file_card.rowconfigure(2, weight=1)

        ttk.Label(file_card, text="PDF 文件", style="Section.TLabel").grid(
            row=0, column=0, sticky="w"
        )
        toolbar = ttk.Frame(file_card, style="Card.TFrame")
        toolbar.grid(row=1, column=0, sticky="ew", pady=(10, 10))
        for text, command in (
            ("添加文件", self.add_files_dialog),
            ("添加文件夹", self.add_folder_dialog),
            ("移除", self.remove_selected),
            ("清空", self.clear_files),
            ("上移", lambda: self.move_selected(-1)),
            ("下移", lambda: self.move_selected(1)),
        ):
            ttk.Button(toolbar, text=text, command=command, style="Tool.TButton").pack(
                side="left", padx=(0, 7)
            )

        table_frame = ttk.Frame(file_card, style="Card.TFrame")
        table_frame.grid(row=2, column=0, sticky="nsew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)
        columns = ("order", "name", "pages", "size", "path")
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended", height=8
        )
        headings = {"order": "顺序", "name": "文件名", "pages": "页数", "size": "大小", "path": "位置"}
        widths = {"order": 52, "name": 230, "pages": 58, "size": 76, "path": 390}
        for column in columns:
            self.tree.heading(column, text=headings[column])
            self.tree.column(
                column,
                width=widths[column],
                minwidth=45,
                stretch=column in {"name", "path"},
                anchor="center" if column in {"order", "pages", "size"} else "w",
            )
        scrollbar = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", lambda _event: self._suggest_output(force=True))

        options = ttk.Frame(outer, style="Card.TFrame", padding=16)
        options.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        options.columnconfigure(1, weight=1)
        ttk.Label(options, text="操作", style="Section.TLabel").grid(row=0, column=0, sticky="w")
        self.operation_box = ttk.Combobox(
            options,
            textvariable=self.operation_var,
            values=list(OPERATIONS),
            state="readonly",
            width=18,
            font=("Segoe UI", 10),
        )
        self.operation_box.grid(row=0, column=1, sticky="w", padx=(16, 0))
        self.operation_box.bind("<<ComboboxSelected>>", self._operation_changed)
        ttk.Label(options, textvariable=self.help_var, style="Hint.TLabel").grid(
            row=1, column=0, columnspan=3, sticky="w", pady=(8, 14)
        )

        ttk.Label(options, text="页码", style="Body.TLabel").grid(row=2, column=0, sticky="w")
        self.page_entry = ttk.Entry(options, textvariable=self.page_var, font=("Segoe UI", 10))
        self.page_entry.grid(row=2, column=1, sticky="ew", padx=(16, 12))
        self.angle_box = ttk.Combobox(
            options,
            textvariable=self.angle_var,
            values=("90° 顺时针", "180°", "270° 顺时针"),
            state="readonly",
            width=16,
        )
        self.angle_box.grid(row=2, column=2, sticky="e")

        ttk.Label(options, text="输出", style="Body.TLabel").grid(
            row=3, column=0, sticky="w", pady=(12, 0)
        )
        ttk.Entry(options, textvariable=self.output_var, font=("Segoe UI", 10)).grid(
            row=3, column=1, sticky="ew", padx=(16, 12), pady=(12, 0)
        )
        ttk.Button(options, text="选择…", command=self.choose_output, style="Tool.TButton").grid(
            row=3, column=2, sticky="e", pady=(12, 0)
        )

        footer = ttk.Frame(outer, style="App.TFrame")
        footer.grid(row=4, column=0, sticky="ew", pady=(14, 0))
        footer.columnconfigure(1, weight=1)
        self.progress = ttk.Progressbar(footer, mode="indeterminate", length=120)
        self.progress.grid(row=0, column=0, sticky="w", padx=(0, 12))
        ttk.Label(footer, textvariable=self.status_var, style="Subtitle.TLabel").grid(
            row=0, column=1, sticky="w"
        )
        self.run_button = ttk.Button(
            footer, text="开始处理", command=self.run_operation, style="Primary.TButton"
        )
        ttk.Button(footer, text="关于与许可", command=self.show_about, style="Tool.TButton").grid(
            row=0, column=2, sticky="e", padx=(0, 8)
        )
        self.run_button.grid(row=0, column=3, sticky="e")
        self._operation_changed()

    def show_about(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("关于 PDF 简工具")
        window.geometry("720x560")
        window.minsize(580, 440)
        window.configure(bg=self.BG)
        window.transient(self.root)

        container = ttk.Frame(window, style="App.TFrame", padding=20)
        container.pack(fill="both", expand=True)
        ttk.Label(container, text=f"PDF 简工具 {__version__}", style="Title.TLabel").pack(
            anchor="w"
        )
        ttk.Label(
            container,
            text="项目代码采用 MIT License；下方包含二进制分发所需的第三方声明。",
            style="Subtitle.TLabel",
        ).pack(anchor="w", pady=(4, 12))

        viewer = scrolledtext.ScrolledText(
            container,
            wrap="word",
            font=("Consolas", 9),
            background=self.CARD,
            foreground=self.TEXT,
            relief="flat",
            padx=12,
            pady=12,
        )
        viewer.pack(fill="both", expand=True)
        sections: list[str] = []
        for title, relative in (
            ("PDF SIMPLE TOOL LICENSE", "LICENSE"),
            ("THIRD-PARTY NOTICES", "THIRD_PARTY_NOTICES.md"),
            ("PYTHON LICENSE", "licenses/PYTHON_LICENSE.txt"),
        ):
            try:
                content = _resource_path(relative).read_text(encoding="utf-8")
            except OSError:
                content = f"Unable to load bundled notice: {relative}"
            sections.append(f"{'=' * 72}\n{title}\n{'=' * 72}\n\n{content}")
        viewer.insert("1.0", "\n\n".join(sections))
        viewer.configure(state="disabled")
        ttk.Button(container, text="关闭", command=window.destroy, style="Tool.TButton").pack(
            anchor="e", pady=(12, 0)
        )

    def _configure_drop(self) -> None:
        if not DND_AVAILABLE:
            return
        for widget in (self.root, self.tree):
            try:
                widget.drop_target_register(DND_FILES)
                widget.dnd_bind("<<Drop>>", self._on_drop)
            except tk.TclError:
                pass

    def _on_drop(self, event: tk.Event) -> str:
        try:
            paths = [Path(item) for item in self.root.tk.splitlist(event.data)]
            self.add_paths(paths)
        except Exception as exc:
            messagebox.showerror("无法添加", str(exc), parent=self.root)
        return "break"

    def add_files_dialog(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self.root, title="选择 PDF", filetypes=(("PDF 文件", "*.pdf"), ("所有文件", "*.*"))
        )
        if paths:
            self.add_paths(Path(path) for path in paths)

    def add_folder_dialog(self) -> None:
        folder = filedialog.askdirectory(parent=self.root, title="选择包含 PDF 的文件夹")
        if folder:
            self.add_paths([Path(folder)])

    def add_paths(self, paths) -> None:
        candidates: list[Path] = []
        for path in paths:
            path = Path(path)
            if path.is_dir():
                candidates.extend(sorted(path.glob("*.pdf"), key=lambda item: item.name.lower()))
            elif path.suffix.lower() == ".pdf":
                candidates.append(path)

        known = {info.path.resolve() for info in self.files}
        errors: list[str] = []
        added = 0
        for path in candidates:
            try:
                resolved = path.resolve()
                if resolved in known:
                    continue
                info = inspect_pdf(resolved)
                self.files.append(info)
                known.add(resolved)
                added += 1
            except PdfToolError as exc:
                errors.append(str(exc))
        self._refresh_tree()
        self._suggest_output(force=not self.output_var.get())
        self.status_var.set(f"已添加 {added} 个 PDF，共 {len(self.files)} 个")
        if errors:
            preview = "\n".join(errors[:5])
            if len(errors) > 5:
                preview += f"\n另有 {len(errors) - 5} 个文件无法读取。"
            messagebox.showwarning("部分文件未添加", preview, parent=self.root)
        elif not candidates:
            messagebox.showinfo("没有 PDF", "所选位置中没有找到 PDF 文件。", parent=self.root)

    def _refresh_tree(self, selected_indices: list[int] | None = None) -> None:
        self.tree.delete(*self.tree.get_children())
        for index, info in enumerate(self.files):
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=(
                    index + 1,
                    info.path.name,
                    info.page_count,
                    _format_size(info.size_bytes),
                    str(info.path.parent),
                ),
            )
        for index in selected_indices or []:
            if 0 <= index < len(self.files):
                self.tree.selection_add(str(index))
        if selected_indices:
            self.tree.focus(str(selected_indices[0]))
            self.tree.see(str(selected_indices[0]))

    def _selected_indices(self) -> list[int]:
        return sorted(int(item) for item in self.tree.selection())

    def remove_selected(self) -> None:
        selected = self._selected_indices()
        if not selected:
            return
        for index in reversed(selected):
            self.files.pop(index)
        self._refresh_tree()
        self._suggest_output(force=True)
        self.status_var.set(f"共 {len(self.files)} 个 PDF")

    def clear_files(self) -> None:
        self.files.clear()
        self.output_var.set("")
        self._refresh_tree()
        self.status_var.set("列表已清空")

    def move_selected(self, direction: int) -> None:
        selected = self._selected_indices()
        if len(selected) != 1:
            if selected:
                messagebox.showinfo("调整顺序", "一次请选择一个文件进行移动。", parent=self.root)
            return
        index = selected[0]
        target = index + direction
        if not 0 <= target < len(self.files):
            return
        self.files[index], self.files[target] = self.files[target], self.files[index]
        self._refresh_tree([target])

    def _operation_changed(self, _event=None) -> None:
        operation = OPERATIONS[self.operation_var.get()]
        self.help_var.set(HELP_TEXT[operation])
        page_enabled = operation in {"delete", "extract", "rotate"}
        self.page_entry.configure(state="normal" if page_enabled else "disabled")
        self.angle_box.configure(state="readonly" if operation == "rotate" else "disabled")
        self._suggest_output(force=True)

    def _source_for_single_operation(self, *, complain: bool) -> PdfInfo | None:
        selected = self._selected_indices()
        if len(selected) == 1:
            return self.files[selected[0]]
        if len(self.files) == 1 and not selected:
            return self.files[0]
        if complain:
            messagebox.showwarning("请选择文件", "请在列表中选中 1 个要处理的 PDF。", parent=self.root)
        return None

    def _default_output(self) -> Path | None:
        if not self.files:
            return None
        operation = OPERATIONS[self.operation_var.get()]
        if operation == "merge":
            parent = self.files[0].path.parent
            return parent / "合并结果.pdf"
        source = self._source_for_single_operation(complain=False)
        if source is None:
            return None
        suffixes = {
            "delete": "_已删除页面.pdf",
            "extract": "_提取页面.pdf",
            "rotate": "_已旋转.pdf",
            "split": "_拆分",
        }
        return source.path.parent / f"{source.path.stem}{suffixes[operation]}"

    def _suggest_output(self, _event=None, *, force: bool = False) -> None:
        if force or not self.output_var.get().strip():
            default = self._default_output()
            if default is not None:
                self.output_var.set(str(default))

    def choose_output(self) -> None:
        operation = OPERATIONS[self.operation_var.get()]
        initial = Path(self.output_var.get()) if self.output_var.get().strip() else self._default_output()
        initial_dir = str(initial.parent) if initial else None
        if operation == "split":
            result = filedialog.askdirectory(
                parent=self.root, title="选择拆分结果文件夹", initialdir=initial_dir
            )
        else:
            result = filedialog.asksaveasfilename(
                parent=self.root,
                title="保存 PDF",
                initialdir=initial_dir,
                initialfile=initial.name if initial else "输出.pdf",
                defaultextension=".pdf",
                filetypes=(("PDF 文件", "*.pdf"),),
            )
        if result:
            self.output_var.set(result)

    def _validate_request(self):
        if not self.files:
            raise PdfToolError("请先添加 PDF 文件。")
        operation = OPERATIONS[self.operation_var.get()]
        output_text = self.output_var.get().strip()
        if not output_text:
            raise PdfToolError("请选择输出位置。")
        output = Path(output_text)

        if operation == "merge":
            if len(self.files) < 2:
                raise PdfToolError("合并至少需要 2 个 PDF。")
            return operation, [info.path for info in self.files], output, "", 0

        source = self._source_for_single_operation(complain=False)
        if source is None:
            raise PdfToolError("请在列表中选中 1 个要处理的 PDF。")
        page_spec = self.page_var.get().strip()
        angle_map = {"90° 顺时针": 90, "180°": 180, "270° 顺时针": 270}
        return operation, [source.path], output, page_spec, angle_map[self.angle_var.get()]

    def run_operation(self) -> None:
        if self.busy:
            return
        try:
            request = self._validate_request()
        except PdfToolError as exc:
            messagebox.showwarning("还不能开始", str(exc), parent=self.root)
            return

        self.busy = True
        self.run_button.configure(state="disabled")
        self.progress.start(12)
        self.status_var.set("正在处理…")
        threading.Thread(target=self._worker, args=(request,), daemon=True).start()

    def _worker(self, request) -> None:
        operation, inputs, output, page_spec, angle = request
        try:
            if operation == "merge":
                results = [merge_pdfs(inputs, output)]
            elif operation == "delete":
                results = [delete_pages(inputs[0], page_spec, output)]
            elif operation == "extract":
                results = [extract_pages(inputs[0], page_spec, output)]
            elif operation == "rotate":
                results = [rotate_pages(inputs[0], page_spec, angle, output)]
            else:
                results = split_pdf(inputs[0], output)
            self.root.after(0, self._operation_finished, results, None)
        except Exception as exc:
            if isinstance(exc, PdfToolError):
                error = str(exc)
            else:
                error = f"处理失败：{exc}"
            self.root.after(0, self._operation_finished, [], error)

    def _operation_finished(self, results: list[Path], error: str | None) -> None:
        self.busy = False
        self.progress.stop()
        self.run_button.configure(state="normal")
        if error:
            self.status_var.set("处理失败")
            messagebox.showerror("处理失败", error, parent=self.root)
            return

        if len(results) == 1:
            message = f"已生成：\n{results[0]}"
        else:
            message = f"已生成 {len(results)} 个 PDF：\n{results[0].parent}"
        self.status_var.set(f"完成，共生成 {len(results)} 个 PDF")
        messagebox.showinfo("处理完成", message, parent=self.root)


def main() -> None:
    root = _RootWindow()
    PdfToolApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
