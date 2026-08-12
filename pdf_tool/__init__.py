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
    "InkEdit",
    "PdfEdit",
    "RectEdit",
    "SignatureEdit",
    "TextEdit",
    "extract_page_text",
    "get_page_sizes",
    "save_pdf_edits",
]

__version__ = "2.0.0"
