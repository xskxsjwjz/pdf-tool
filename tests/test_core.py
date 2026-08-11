from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from pypdf import PdfReader, PdfWriter

from pdf_tool.core import (
    PdfToolError,
    delete_pages,
    extract_pages,
    inspect_pdf,
    merge_pdfs,
    parse_page_spec,
    rotate_pages,
    split_pdf,
)


def make_pdf(path: Path, widths: list[int]) -> Path:
    writer = PdfWriter()
    for width in widths:
        writer.add_blank_page(width=width, height=700)
    writer.add_metadata({"/Title": path.stem})
    with path.open("wb") as stream:
        writer.write(stream)
    return path


class CoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.first = make_pdf(self.root / "first.pdf", [101, 102, 103])
        self.second = make_pdf(self.root / "second.pdf", [201, 202])

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_page_spec(self) -> None:
        self.assertEqual(parse_page_spec("1, 3-5，5", 6), [0, 2, 3, 4])
        self.assertEqual(parse_page_spec("", 3, allow_empty=True), [0, 1, 2])
        with self.assertRaises(PdfToolError):
            parse_page_spec("2-7", 6)

    def test_inspect_and_merge(self) -> None:
        self.assertEqual(inspect_pdf(self.first).page_count, 3)
        output = merge_pdfs([self.first, self.second], self.root / "merged.pdf")
        reader = PdfReader(str(output))
        self.assertEqual(len(reader.pages), 5)
        self.assertEqual([int(page.mediabox.width) for page in reader.pages], [101, 102, 103, 201, 202])

    def test_delete_pages(self) -> None:
        output = delete_pages(self.first, "2", self.root / "deleted.pdf")
        reader = PdfReader(str(output))
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual([int(page.mediabox.width) for page in reader.pages], [101, 103])
        with self.assertRaises(PdfToolError):
            delete_pages(self.first, "1-3", self.root / "empty.pdf")

    def test_extract_pages(self) -> None:
        output = extract_pages(self.first, "3,1", self.root / "extracted.pdf")
        reader = PdfReader(str(output))
        # 页码表达式按文档原顺序输出，避免意外重排。
        self.assertEqual([int(page.mediabox.width) for page in reader.pages], [101, 103])

    def test_rotate_pages(self) -> None:
        output = rotate_pages(self.first, "2", 90, self.root / "rotated.pdf")
        reader = PdfReader(str(output))
        self.assertEqual([page.rotation for page in reader.pages], [0, 90, 0])

    def test_split_pdf(self) -> None:
        outputs = split_pdf(self.first, self.root / "split")
        self.assertEqual(len(outputs), 3)
        self.assertTrue(all(len(PdfReader(str(path)).pages) == 1 for path in outputs))


if __name__ == "__main__":
    unittest.main()
