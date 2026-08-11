"""PDF 简工具。"""

from .core import (
    PdfInfo,
    PdfToolError,
    delete_pages,
    extract_pages,
    inspect_pdf,
    merge_pdfs,
    parse_page_spec,
    rotate_pages,
    split_pdf,
)

__all__ = [
    "PdfInfo",
    "PdfToolError",
    "delete_pages",
    "extract_pages",
    "inspect_pdf",
    "merge_pdfs",
    "parse_page_spec",
    "rotate_pages",
    "split_pdf",
]

__version__ = "1.0.0"
