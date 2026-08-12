"""可视 PDF 编辑所需的核心数据结构与文件操作。"""

from __future__ import annotations

import io
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence, TypeAlias

from pypdf import PdfReader, PdfWriter

from .core import (
    PdfToolError,
    _as_pdf_path,
    _copy_metadata,
    _ensure_output_not_input,
    _open_reader,
    _write_verified,
)


Point: TypeAlias = tuple[float, float]
Stroke: TypeAlias = tuple[Point, ...]


@dataclass(frozen=True)
class TextEdit:
    """以页面左上角为原点放置的文本。"""

    page: int
    x: float
    y: float
    text: str
    font_size: float = 14.0
    color: str = "#1d1d1f"
    max_width: float = 280.0


@dataclass(frozen=True)
class InkEdit:
    """一组自由绘制笔画，可用于批注或手写签名。"""

    page: int
    strokes: tuple[Stroke, ...]
    width: float = 2.0
    color: str = "#111111"


@dataclass(frozen=True)
class SignatureEdit(InkEdit):
    """可在编辑器中被单独选中、移动和缩放的签名笔画。"""


@dataclass(frozen=True)
class RectEdit:
    """矩形标记；kind 为 highlight 或 whiteout。"""

    page: int
    x: float
    y: float
    width: float
    height: float
    kind: str = "highlight"
    color: str = "#ffe066"


PdfEdit: TypeAlias = TextEdit | InkEdit | SignatureEdit | RectEdit


def get_page_sizes(path: str | os.PathLike[str]) -> list[tuple[float, float]]:
    """返回页面在阅读方向上的宽高（PDF point）。"""

    reader = _open_reader(_as_pdf_path(path))
    sizes: list[tuple[float, float]] = []
    for page in reader.pages:
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        if int(page.rotation or 0) % 180:
            width, height = height, width
        sizes.append((width, height))
    return sizes


def extract_page_text(path: str | os.PathLike[str], page: int) -> str:
    """提取一页的文本，供复制或翻译使用。"""

    reader = _open_reader(_as_pdf_path(path))
    if not 0 <= page < len(reader.pages):
        raise PdfToolError(f"页码超出范围：{page + 1}")
    try:
        return (reader.pages[page].extract_text() or "").strip()
    except Exception as exc:
        raise PdfToolError(f"无法提取第 {page + 1} 页文本：{exc}") from exc


def _hex_color(value: str) -> tuple[float, float, float]:
    text = value.strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    if len(text) != 6:
        raise PdfToolError(f"无效颜色：{value}")
    try:
        values = tuple(int(text[index : index + 2], 16) / 255 for index in (0, 2, 4))
    except ValueError as exc:
        raise PdfToolError(f"无效颜色：{value}") from exc
    return values  # type: ignore[return-value]


def _font_for(text: str) -> str:
    """选择 ReportLab 内置字体；CJK 字体无需随程序捆绑字体文件。"""

    if all(ord(character) <= 255 for character in text):
        return "Helvetica"
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont

    name = "STSong-Light"
    if name not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(UnicodeCIDFont(name))
    return name


def _wrap_text(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    from reportlab.pdfbase import pdfmetrics

    lines: list[str] = []
    for paragraph in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if not paragraph:
            lines.append("")
            continue
        current = ""
        for character in paragraph:
            candidate = current + character
            if current and pdfmetrics.stringWidth(candidate, font_name, font_size) > max_width:
                lines.append(current)
                current = character
            else:
                current = candidate
        lines.append(current)
    return lines


def _make_overlay(width: float, height: float, edits: Sequence[PdfEdit]) -> PdfReader:
    try:
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise PdfToolError("缺少 PDF 编辑组件 ReportLab，请重新安装完整依赖。") from exc

    stream = io.BytesIO()
    drawing = canvas.Canvas(stream, pagesize=(width, height), pageCompression=1)
    for edit in edits:
        if isinstance(edit, TextEdit):
            if not edit.text.strip():
                continue
            font_size = max(5.0, min(96.0, float(edit.font_size)))
            font_name = _font_for(edit.text)
            drawing.setFont(font_name, font_size)
            drawing.setFillColorRGB(*_hex_color(edit.color))
            line_height = font_size * 1.25
            for index, line in enumerate(
                _wrap_text(edit.text, font_name, font_size, max(20.0, edit.max_width))
            ):
                drawing.drawString(edit.x, height - edit.y - font_size - index * line_height, line)
        elif isinstance(edit, InkEdit):
            drawing.setStrokeColorRGB(*_hex_color(edit.color))
            drawing.setLineWidth(max(0.5, min(30.0, float(edit.width))))
            drawing.setLineCap(1)
            drawing.setLineJoin(1)
            for stroke in edit.strokes:
                if not stroke:
                    continue
                path = drawing.beginPath()
                path.moveTo(stroke[0][0], height - stroke[0][1])
                if len(stroke) == 1:
                    path.lineTo(stroke[0][0] + 0.01, height - stroke[0][1] + 0.01)
                else:
                    for x, y in stroke[1:]:
                        path.lineTo(x, height - y)
                drawing.drawPath(path, stroke=1, fill=0)
        elif isinstance(edit, RectEdit):
            if edit.width <= 0 or edit.height <= 0:
                continue
            if edit.kind == "whiteout":
                drawing.setFillColorRGB(1, 1, 1)
            elif edit.kind == "highlight":
                drawing.setFillColorRGB(*_hex_color(edit.color))
                if hasattr(drawing, "setFillAlpha"):
                    drawing.setFillAlpha(0.35)
            else:
                raise PdfToolError(f"未知矩形编辑类型：{edit.kind}")
            drawing.rect(
                edit.x,
                height - edit.y - edit.height,
                edit.width,
                edit.height,
                stroke=0,
                fill=1,
            )
            if hasattr(drawing, "setFillAlpha"):
                drawing.setFillAlpha(1)
    drawing.save()
    stream.seek(0)
    return PdfReader(stream, strict=False)


def save_pdf_edits(
    input_path: str | os.PathLike[str],
    edits: Sequence[PdfEdit],
    output: str | os.PathLike[str],
) -> Path:
    """把文本、画笔、签名和矩形图层写入新的 PDF。"""

    source = _as_pdf_path(input_path)
    output_path = Path(output)
    _ensure_output_not_input(output_path, [source])
    reader = _open_reader(source)
    grouped: dict[int, list[PdfEdit]] = {}
    for edit in edits:
        if not 0 <= edit.page < len(reader.pages):
            raise PdfToolError(f"编辑项页码超出范围：{edit.page + 1}")
        grouped.setdefault(edit.page, []).append(edit)

    writer = PdfWriter()
    for index, source_page in enumerate(reader.pages):
        writer.add_page(source_page)
        page = writer.pages[-1]
        page_edits = grouped.get(index)
        if not page_edits:
            continue
        # 把 /Rotate 固化进内容流，使编辑器的左上角坐标与视觉页面保持一致。
        if int(page.rotation or 0) % 360:
            page.transfer_rotation_to_content()
        width = float(page.mediabox.width)
        height = float(page.mediabox.height)
        overlay = _make_overlay(width, height, page_edits)
        page.merge_page(overlay.pages[0])
    _copy_metadata(reader, writer)
    return _write_verified(writer, output_path, len(reader.pages))
