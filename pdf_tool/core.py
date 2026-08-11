"""PDF 文件操作核心。

本模块不依赖 GUI，可以独立调用或测试。所有单文件输出先写入临时文件，
重新读取校验成功后再替换目标文件，尽量避免留下不完整的 PDF。
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from pypdf import PdfReader, PdfWriter


class PdfToolError(Exception):
    """可直接展示给用户的 PDF 操作错误。"""


@dataclass(frozen=True)
class PdfInfo:
    path: Path
    page_count: int
    size_bytes: int


def _as_pdf_path(path: str | os.PathLike[str]) -> Path:
    pdf_path = Path(path).expanduser().resolve()
    if not pdf_path.is_file():
        raise PdfToolError(f"文件不存在：{pdf_path}")
    if pdf_path.suffix.lower() != ".pdf":
        raise PdfToolError(f"不是 PDF 文件：{pdf_path.name}")
    return pdf_path


def _open_reader(path: Path) -> PdfReader:
    try:
        reader = PdfReader(str(path), strict=False)
        if reader.is_encrypted:
            try:
                unlocked = reader.decrypt("")
            except Exception as exc:  # pypdf 会针对不同加密方式抛出不同异常
                raise PdfToolError(f"暂不支持有密码的 PDF：{path.name}") from exc
            if not unlocked:
                raise PdfToolError(f"暂不支持有密码的 PDF：{path.name}")
        # 立即访问页面树，让损坏文件在真正处理前就报错。
        len(reader.pages)
        return reader
    except PdfToolError:
        raise
    except Exception as exc:
        raise PdfToolError(f"无法读取 PDF“{path.name}”：{exc}") from exc


def inspect_pdf(path: str | os.PathLike[str]) -> PdfInfo:
    """读取 PDF 的基础信息，并验证其页面树。"""

    pdf_path = _as_pdf_path(path)
    reader = _open_reader(pdf_path)
    return PdfInfo(pdf_path, len(reader.pages), pdf_path.stat().st_size)


def parse_page_spec(spec: str, total_pages: int, *, allow_empty: bool = False) -> list[int]:
    """把 ``1,3-5`` 形式的页码解析为从 0 开始的、有序页码列表。"""

    if total_pages < 1:
        raise PdfToolError("PDF 没有可操作的页面。")

    normalized = spec.strip().replace("，", ",").replace("；", ",").replace(";", ",")
    if not normalized:
        if allow_empty:
            return list(range(total_pages))
        raise PdfToolError("请输入页码，例如：1,3-5。")

    tokens = [token for token in re.split(r"[\s,]+", normalized) if token]
    pages: set[int] = set()
    for token in tokens:
        match = re.fullmatch(r"(\d+)(?:\s*-\s*(\d+))?", token)
        if not match:
            raise PdfToolError(f"页码格式不正确：{token}。示例：1,3-5")
        start = int(match.group(1))
        end = int(match.group(2) or start)
        if start < 1 or end < 1 or start > end:
            raise PdfToolError(f"无效页码范围：{token}")
        if end > total_pages:
            raise PdfToolError(f"页码 {end} 超出范围；该 PDF 只有 {total_pages} 页。")
        pages.update(range(start - 1, end))

    return sorted(pages)


def _copy_metadata(reader: PdfReader, writer: PdfWriter) -> None:
    metadata = reader.metadata
    if not metadata:
        return
    safe_metadata = {
        str(key): str(value)
        for key, value in metadata.items()
        if key and value is not None and str(key).startswith("/")
    }
    if safe_metadata:
        try:
            writer.add_metadata(safe_metadata)
        except Exception:
            # 元数据异常不应阻止页面本身的基础操作。
            pass


def _ensure_output_not_input(output: Path, inputs: Iterable[Path]) -> None:
    resolved_output = output.expanduser().resolve()
    if any(resolved_output == item.resolve() for item in inputs):
        raise PdfToolError("输出文件不能覆盖正在读取的源 PDF。")


def _write_verified(writer: PdfWriter, output: Path, expected_pages: int) -> Path:
    output = output.expanduser().resolve()
    if output.suffix.lower() != ".pdf":
        output = output.with_suffix(".pdf")
    output.parent.mkdir(parents=True, exist_ok=True)

    temp_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", suffix=".pdf", prefix=".pdf_tool_", dir=output.parent, delete=False
        ) as stream:
            temp_path = Path(stream.name)
            writer.write(stream)

        checked = PdfReader(str(temp_path), strict=False)
        actual_pages = len(checked.pages)
        if actual_pages != expected_pages:
            raise PdfToolError(
                f"输出校验失败：预计 {expected_pages} 页，实际 {actual_pages} 页。"
            )
        os.replace(temp_path, output)
        return output
    except PdfToolError:
        raise
    except Exception as exc:
        raise PdfToolError(f"写入 PDF 失败：{exc}") from exc
    finally:
        if temp_path is not None and temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass


def merge_pdfs(
    inputs: Sequence[str | os.PathLike[str]], output: str | os.PathLike[str]
) -> Path:
    """按传入顺序合并多个 PDF。"""

    if len(inputs) < 2:
        raise PdfToolError("合并至少需要 2 个 PDF。")
    input_paths = [_as_pdf_path(path) for path in inputs]
    output_path = Path(output)
    _ensure_output_not_input(output_path, input_paths)

    writer = PdfWriter()
    expected_pages = 0
    first_reader: PdfReader | None = None
    for path in input_paths:
        reader = _open_reader(path)
        if first_reader is None:
            first_reader = reader
        for page in reader.pages:
            writer.add_page(page)
            expected_pages += 1
    if first_reader is not None:
        _copy_metadata(first_reader, writer)
    return _write_verified(writer, output_path, expected_pages)


def delete_pages(
    input_path: str | os.PathLike[str], page_spec: str, output: str | os.PathLike[str]
) -> Path:
    """删除指定页面。页码从 1 开始。"""

    source = _as_pdf_path(input_path)
    output_path = Path(output)
    _ensure_output_not_input(output_path, [source])
    reader = _open_reader(source)
    deleted = set(parse_page_spec(page_spec, len(reader.pages)))
    if len(deleted) >= len(reader.pages):
        raise PdfToolError("不能删除全部页面；PDF 至少要保留 1 页。")

    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index not in deleted:
            writer.add_page(page)
    _copy_metadata(reader, writer)
    return _write_verified(writer, output_path, len(reader.pages) - len(deleted))


def extract_pages(
    input_path: str | os.PathLike[str], page_spec: str, output: str | os.PathLike[str]
) -> Path:
    """把指定页面提取到一个新 PDF。"""

    source = _as_pdf_path(input_path)
    output_path = Path(output)
    _ensure_output_not_input(output_path, [source])
    reader = _open_reader(source)
    selected = parse_page_spec(page_spec, len(reader.pages))

    writer = PdfWriter()
    for index in selected:
        writer.add_page(reader.pages[index])
    _copy_metadata(reader, writer)
    return _write_verified(writer, output_path, len(selected))


def rotate_pages(
    input_path: str | os.PathLike[str],
    page_spec: str,
    angle: int,
    output: str | os.PathLike[str],
) -> Path:
    """顺时针旋转指定页面；页码留空时旋转全部页面。"""

    if angle not in {90, 180, 270}:
        raise PdfToolError("旋转角度只能是 90、180 或 270 度。")
    source = _as_pdf_path(input_path)
    output_path = Path(output)
    _ensure_output_not_input(output_path, [source])
    reader = _open_reader(source)
    selected = set(parse_page_spec(page_spec, len(reader.pages), allow_empty=True))

    writer = PdfWriter()
    for index, page in enumerate(reader.pages):
        if index in selected:
            page.rotate(angle)
        writer.add_page(page)
    _copy_metadata(reader, writer)
    return _write_verified(writer, output_path, len(reader.pages))


def split_pdf(
    input_path: str | os.PathLike[str], output_dir: str | os.PathLike[str]
) -> list[Path]:
    """把 PDF 拆成每页一个文件。"""

    source = _as_pdf_path(input_path)
    reader = _open_reader(source)
    directory = Path(output_dir).expanduser().resolve()
    directory.mkdir(parents=True, exist_ok=True)
    width = max(3, len(str(len(reader.pages))))
    results: list[Path] = []
    for index, page in enumerate(reader.pages, start=1):
        writer = PdfWriter()
        writer.add_page(page)
        _copy_metadata(reader, writer)
        target = directory / f"{source.stem}_第{index:0{width}d}页.pdf"
        results.append(_write_verified(writer, target, 1))
    return results
