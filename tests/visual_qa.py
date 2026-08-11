"""生成带可见内容的样例，供 Poppler 渲染检查。

这是人工/交付前 QA 脚本，不参与应用运行。
"""

from pathlib import Path

from reportlab.lib.colors import HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen.canvas import Canvas

from pdf_tool.core import delete_pages, merge_pdfs


def make_sample(path: Path, title: str, color: str, pages: int) -> Path:
    canvas = Canvas(str(path), pagesize=A4)
    width, height = A4
    for page_number in range(1, pages + 1):
        canvas.setFillColor(HexColor(color))
        canvas.rect(0, 0, width, height, fill=1, stroke=0)
        canvas.setFillColor(white)
        canvas.setFont("Helvetica-Bold", 34)
        canvas.drawString(54, height - 100, title)
        canvas.setFont("Helvetica", 18)
        canvas.drawString(54, height - 145, f"Page {page_number} of {pages}")
        canvas.setLineWidth(2)
        canvas.line(54, height - 175, width - 54, height - 175)
        canvas.setFont("Helvetica", 12)
        canvas.drawString(54, 72, "PDF Tool visual verification sample")
        canvas.showPage()
    canvas.save()
    return path


def main() -> None:
    qa_dir = Path("tmp/pdfs").resolve()
    qa_dir.mkdir(parents=True, exist_ok=True)
    first = make_sample(qa_dir / "source_a.pdf", "SOURCE A", "#0071E3", 2)
    second = make_sample(qa_dir / "source_b.pdf", "SOURCE B", "#34A853", 2)
    merged = merge_pdfs([first, second], qa_dir / "merged.pdf")
    delete_pages(merged, "2,4", qa_dir / "deleted.pdf")
    print(merged)
    print(qa_dir / "deleted.pdf")


if __name__ == "__main__":
    main()
