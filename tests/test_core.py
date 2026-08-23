from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from pypdf import PdfReader, PdfWriter

from pdf_tool.core import (
    PdfToolError,
    delete_pages,
    extract_pages,
    inspect_pdf,
    images_to_pdf,
    merge_pdfs,
    parse_page_spec,
    rotate_pages,
    split_pdf,
)
from pdf_tool.editing import (
    InkEdit,
    RectEdit,
    SignatureEdit,
    TextEdit,
    extract_page_text,
    get_page_sizes,
    save_pdf_edits,
)
from pdf_tool.translation import translate_text
from pdf_tool.editor import PdfEditorWindow


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

    def test_images_to_pdf_preserves_order_and_handles_transparency(self) -> None:
        first = self.root / "first.png"
        second = self.root / "second.jpg"
        Image.new("RGBA", (120, 80), (255, 0, 0, 128)).save(first)
        Image.new("RGB", (240, 160), "blue").save(second, quality=90)
        output = images_to_pdf([second, first], self.root / "images.pdf")
        reader = PdfReader(str(output))
        self.assertEqual(len(reader.pages), 2)
        self.assertEqual((float(reader.pages[0].mediabox.width), float(reader.pages[0].mediabox.height)), (240.0, 160.0))
        self.assertEqual((float(reader.pages[1].mediabox.width), float(reader.pages[1].mediabox.height)), (120.0, 80.0))

    def test_images_to_pdf_rejects_invalid_inputs(self) -> None:
        image = self.root / "image.png"
        Image.new("RGB", (10, 10), "white").save(image)
        with self.assertRaises(PdfToolError):
            images_to_pdf([self.first], self.root / "bad.pdf")
        self.assertEqual(images_to_pdf([image], image).suffix, ".pdf")

    def test_save_visual_edits(self) -> None:
        edits = [
            TextEdit(0, 20, 30, "Hello PDF", 16, "#123456"),
            InkEdit(0, (((30, 80), (50, 90), (75, 72)),), 2.5, "#111111"),
            SignatureEdit(0, (((120, 145), (150, 132), (190, 148)),), 2.2, "#111111"),
            RectEdit(0, 15, 100, 70, 18, "highlight", "#ffe066"),
            RectEdit(1, 10, 20, 30, 12, "whiteout"),
        ]
        output = save_pdf_edits(self.first, edits, self.root / "edited.pdf")
        reader = PdfReader(str(output))
        self.assertEqual(len(reader.pages), 3)
        self.assertIn("Hello PDF", reader.pages[0].extract_text())
        self.assertEqual(extract_page_text(output, 0), "Hello PDF")
        with self.assertRaises(PdfToolError):
            save_pdf_edits(self.first, edits, self.first)

    def test_visual_edits_support_cjk_and_rotated_pages(self) -> None:
        rotated = self.root / "rotated_source.pdf"
        writer = PdfWriter()
        writer.add_blank_page(width=200, height=300).rotate(90)
        with rotated.open("wb") as stream:
            writer.write(stream)
        self.assertEqual(get_page_sizes(rotated), [(300.0, 200.0)])
        output = save_pdf_edits(
            rotated,
            [TextEdit(0, 20, 20, "签名确认", 14), InkEdit(0, (((20, 60), (90, 70)),))],
            self.root / "rotated_edited.pdf",
        )
        result = PdfReader(str(output))
        self.assertEqual(len(result.pages), 1)
        self.assertEqual(result.pages[0].rotation, 0)
        self.assertEqual((float(result.pages[0].mediabox.width), float(result.pages[0].mediabox.height)), (300.0, 200.0))

    def test_translate_text_libretranslate_payload(self) -> None:
        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            def read(self):
                return b'{"translatedText": "Hello"}'

        with patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            result = translate_text("你好", "en", "https://translate.example/translate", api_key="secret")
        self.assertEqual(result, "Hello")
        request = mocked.call_args.args[0]
        self.assertIn(b'"target": "en"', request.data)
        self.assertIn(b'"api_key": "secret"', request.data)
        with self.assertRaises(PdfToolError):
            translate_text("text", "en", "http://translate.example/translate")

    def test_signature_can_be_moved_and_resized(self) -> None:
        signature = SignatureEdit(
            0,
            (((10, 10), (55, 35), (110, 60)),),
            2.2,
            "#111111",
        )
        editor = PdfEditorWindow.__new__(PdfEditorWindow)
        editor.edits = [signature]
        editor.undo_stack = []
        editor.redo_stack = []
        editor.page_index = 0
        editor.page_sizes = [(500.0, 400.0)]
        editor.selected_signature = 0
        editor.signature_drag = "move"
        editor.signature_drag_start = (50.0, 30.0)
        editor.signature_drag_original = signature
        editor.signature_drag_history_saved = False
        editor._redraw_edits = lambda: None

        editor._drag_selected_signature((70.0, 60.0))
        moved = editor.edits[0]
        self.assertIsInstance(moved, SignatureEdit)
        self.assertEqual(editor._signature_bbox(moved), (30.0, 40.0, 130.0, 90.0))

        editor.signature_drag = "se"
        editor.signature_drag_start = (130.0, 90.0)
        editor.signature_drag_original = moved
        editor.signature_drag_history_saved = False
        editor._drag_selected_signature((230.0, 140.0))
        resized = editor.edits[0]
        self.assertEqual(editor._signature_bbox(resized), (30.0, 40.0, 230.0, 140.0))
        self.assertAlmostEqual(resized.width, 4.4)
        self.assertEqual(len(editor.undo_stack), 2)


if __name__ == "__main__":
    unittest.main()
