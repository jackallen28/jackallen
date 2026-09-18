"""Build packs/example-source.pdf, the source the example pack points at.

The example pack demonstrates `page` + `bbox` figures, which need a real PDF
to crop from. It used to point at a licensed Checkpoints extract that is
gitignored, so the example was broken on every fresh clone and the test that
validates it failed for anyone but its author. This draws a stand-in: two
pages with a figure in the box each question claims, invented for the purpose
and safe to commit.

    python packs/make_example_source.py
"""
from pathlib import Path

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas as rl_canvas

OUT = Path(__file__).resolve().parent / "example-source.pdf"
PAGE_W, PAGE_H = A4


def _frame(c, bbox, caption):
    """Draw inside the bbox the pack declares (PDF points, top-left origin)."""
    x0, top, x1, bottom = bbox
    y0, y1 = PAGE_H - bottom, PAGE_H - top
    c.setLineWidth(1)
    c.rect(x0, y0, x1 - x0, y1 - y0)
    c.setFont("Helvetica", 9)
    c.drawString(x0 + 8, y1 - 16, caption)


def main() -> None:
    c = rl_canvas.Canvas(str(OUT), pagesize=A4)

    c.setFont("Helvetica-Bold", 12)
    c.drawString(52, PAGE_H - 60, "Question 1/ 41")
    _frame(c, [52, 154, 449, 329], "Connected masses over a pulley (stand-in figure)")
    c.setFont("Helvetica", 10)
    c.drawString(52, PAGE_H - 360, "Two masses are connected by a light string over a pulley.")
    c.showPage()

    c.setFont("Helvetica-Bold", 12)
    c.drawString(52, PAGE_H - 60, "Question 2/ 118")
    _frame(c, [52, 154, 517, 325], "Photocell apparatus (stand-in figure)")
    c.setFont("Helvetica", 10)
    c.drawString(52, PAGE_H - 360, "Light falls on a photocell connected to a variable supply.")
    c.showPage()

    # Pages 2-4 are filler: the pack's last question cites page 5, and a
    # page/bbox figure is only valid if the page is really there.
    for n in range(2, 5):
        c.setFont("Helvetica", 10)
        c.drawString(52, PAGE_H - 60, f"(page {n}, no figure cited by the example)")
        c.showPage()

    c.setFont("Helvetica-Bold", 12)
    c.drawString(52, PAGE_H - 60, "Question 4/ 193")
    _frame(c, [52, 154, 360, 389], "Ek max against frequency for calcium (stand-in)")
    c.setFont("Helvetica", 10)
    c.drawString(52, PAGE_H - 420, "A graph of maximum kinetic energy against frequency.")
    c.showPage()

    c.save()
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
