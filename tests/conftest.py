import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# Point the whole test run at a throwaway Blitz folder BEFORE blitz.config is
# imported, because several modules bind their paths at import time. Without
# this, a test that does not patch every one of them writes into the real
# ~/Documents/Blitz — which is how figure crops, an indexing guide and an
# installed lexicon ended up there.
_TEST_ROOT = Path(tempfile.mkdtemp(prefix="blitz-tests-"))
os.environ["BLITZ_ROOT"] = str(_TEST_ROOT)
atexit.register(shutil.rmtree, _TEST_ROOT, True)

from blitz import db                                    # noqa: E402
from blitz.corpus.sample import load_sample             # noqa: E402


@pytest.fixture
def conn(tmp_path):
    connection = db.connect(tmp_path / "test.sqlite3")
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture
def seeded(conn):
    """An index holding both sample banks."""
    load_sample(conn, "business-management")
    load_sample(conn, "physics")
    return conn


# --- shared PDF fixtures ----------------------------------------------------
# Synthetic books shaped like the real Checkpoints, so the pipeline is exercised
# without licensed material in the repo. Shared by the ingest and draft tests.

from reportlab.lib.pagesizes import A4          # noqa: E402
from reportlab.lib.units import mm              # noqa: E402
from reportlab.pdfgen import canvas as rl_canvas  # noqa: E402

PAGE_W, PAGE_H = A4
LEFT = 20 * mm


@pytest.fixture
def fake_book(tmp_path):
    path = tmp_path / "fake-checkpoints.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)

    def rule(y):
        c.setLineWidth(0.5)
        c.line(LEFT, y, PAGE_W - LEFT, y)

    def text(y, s, size=10, font="Helvetica"):
        c.setFont(font, size)
        c.drawString(LEFT, y, s)

    # --- page 1: a diagram above its question, then a multiple choice ---------
    y = PAGE_H - 25 * mm
    c.setLineWidth(1)
    for i in range(8):                       # a vector diagram
        c.rect(LEFT + i * 7 * mm, y - 32 * mm, 6 * mm, 30 * mm)
    y -= 40 * mm
    rule(y)

    y -= 10 * mm
    text(y, "Question 12/ 11")
    y -= 7 * mm
    text(y, "The graph above shows the motion. Which one best describes it?")
    for opt in ("A Constant speed followed by no motion",
                "B Increasing speed followed by constant speed",
                "C Increasing acceleration then constant acceleration",
                "D Increasing distance followed by constant speed"):
        y -= 6 * mm
        text(y, opt)
    y -= 7 * mm
    text(y, "Solution")
    y -= 6 * mm
    text(y, "B The gradient increases then becomes constant.")
    y -= 8 * mm
    rule(y)

    # --- a multi-part question with marks, running onto page 2 ---------------
    y -= 10 * mm
    text(y, "Question 14/ 11")
    y -= 6 * mm
    text(y, "[Adapted VCAA 2018 NHT SA Q8]")
    y -= 7 * mm
    text(y, "A 1.0 kg mass hangs 4.0 m above the ground on a massless string.")
    y -= 7 * mm
    text(y, "a. Calculate the magnetic flux through the coil.")
    y -= 6 * mm
    text(y, "(2 marks)")
    c.showPage()

    y = PAGE_H - 25 * mm
    text(y, "b. Determine the transformer turns ratio required.")
    y -= 6 * mm
    text(y, "(3 marks)")
    y -= 8 * mm
    text(y, "Solution")
    y -= 6 * mm
    text(y, "a 0.30 Wb, from the perpendicular area.")
    y -= 8 * mm
    rule(y)

    # --- a question whose maths is a stacked fraction -------------------------
    y -= 10 * mm
    text(y, "Question 5/ 14")
    y -= 7 * mm
    text(y, "Which expression gives the de Broglie wavelength of the photon?")
    y -= 9 * mm
    c.setFont("Helvetica", 10)
    c.drawString(LEFT + 14, y + 6, "h")        # numerator
    c.setLineWidth(0.5)
    c.line(LEFT + 12, y + 3, LEFT + 12 + 8, y + 3)   # the fraction bar
    c.drawString(LEFT + 14, y - 5, "p")        # denominator
    c.drawString(LEFT, y, "A")
    y -= 14 * mm
    text(y, "B E = hf")
    y -= 6 * mm
    text(y, "C E = pc")
    y -= 6 * mm
    text(y, "D E = mc")
    c.save()
    return path


def _questions(path):
    doc = pymupdf.open(path)
    try:
        return segment.segment_document(doc)
    finally:
        doc.close()


@pytest.fixture
def stimulus_book(tmp_path):
    """Reproduces how Checkpoints prints a shared stimulus and its figure.

    The lead-in sentence and the graph sit ABOVE the rule that fences the
    question, so they arrive attached to the previous question, and the figure
    is in the preceding fence rather than the question's own. Looking only
    inside the question's fence missed every graph question in the real sample.
    """
    path = tmp_path / "stimulus.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)

    def rule(y):
        c.setLineWidth(0.5)
        c.line(LEFT, y, PAGE_W - LEFT, y)

    def text(y, s, size=10):
        c.setFont("Helvetica", size)
        c.drawString(LEFT, y, s)

    y = PAGE_H - 25 * mm
    text(y, "Question 9/ 11")
    y -= 7 * mm
    text(y, "Calculate the impulse delivered during the collision.")
    y -= 8 * mm
    rule(y)

    # The stimulus block: its own "Question" header, a lead-in, and the figure.
    y -= 10 * mm
    text(y, "Question 10/ 11")
    y -= 7 * mm
    text(y, "The speed-time graph below describes the motion of an object.")
    y -= 6 * mm
    c.setLineWidth(1)
    for i in range(7):
        c.rect(LEFT + i * 8 * mm, y - 34 * mm, 7 * mm, 32 * mm)
    y -= 42 * mm
    rule(y)

    # The question that actually uses it, in the next fence.
    y -= 10 * mm
    text(y, "Question 11/ 11")
    y -= 7 * mm
    text(y, "Which one best describes the motion of the object at t = 5 s?")
    for opt in ("A Constant speed", "B Increasing speed",
                "C Constant acceleration", "D Increasing acceleration"):
        y -= 6 * mm
        text(y, opt)
    y -= 8 * mm
    rule(y)
    c.save()
    return path


@pytest.fixture
def fake_textbook(tmp_path):
    """A PDF shaped like a VCE textbook chapter.

    Teaching prose under section headings set in a larger font, a worked example
    with its solution, a numbered question block at the end of a section, and a
    chapter review. This is what the textbook extractor is written against, in
    the absence of a real textbook.
    """
    path = tmp_path / "fake-textbook.pdf"
    c = rl_canvas.Canvas(str(path), pagesize=A4)
    y = [PAGE_H - 25 * mm]

    def line(text, size=10, bold=False):
        if y[0] < 25 * mm:
            c.showPage()
            y[0] = PAGE_H - 25 * mm
        c.setFont("Helvetica-Bold" if bold else "Helvetica", size)
        c.drawString(LEFT, y[0], text)
        y[0] -= (size + 4)

    def para(*lines):
        for t in lines:
            line(t)
        y[0] -= 6

    line("Chapter 6  Light and matter", 18, bold=True)
    y[0] -= 8
    line("6.1  The photoelectric effect", 14, bold=True)
    para("When light of sufficiently high frequency falls on a clean metal surface,",
         "electrons are emitted. This is the photoelectric effect. Increasing the",
         "intensity of the light increases the number of photoelectrons but not their",
         "maximum kinetic energy; only raising the frequency does that. The work",
         "function of the metal is the minimum energy needed to free an electron,",
         "and the threshold frequency is the lowest frequency that causes emission.",
         "Einstein explained this by treating light as photons of energy E = hf.")
    line("Worked example 6.1", 12, bold=True)
    para("Light of frequency 8.0 x 10^14 Hz falls on a metal with work function",
         "2.1 eV. Calculate the maximum kinetic energy of the emitted electrons.")
    line("Solution", 10, bold=True)
    para("E = hf = 4.14 x 10^-15 x 8.0 x 10^14 = 3.3 eV.",
         "Ek max = E - W = 3.3 - 2.1 = 1.2 eV.")
    line("Questions", 12, bold=True)
    para("1. Explain why increasing the intensity of the light does not increase the",
         "   maximum kinetic energy of the photoelectrons. (2 marks)")
    para("2. A metal has a threshold frequency of 5.5 x 10^14 Hz. Determine its work",
         "   function in eV. (2 marks)")
    para("3. Which of the following best describes the photoelectric effect?",
         "A Light behaves only as a wave",
         "B Light delivers energy in discrete quanta",
         "C Electrons are emitted regardless of frequency",
         "D Intensity determines the energy of each photoelectron")
    y[0] -= 10
    line("6.2  The wave-like nature of matter", 14, bold=True)
    para("De Broglie proposed that matter has a wavelength given by lambda = h/p.",
         "Electron diffraction through a crystal lattice confirmed this: electrons",
         "produce the same ring patterns as X-rays of the same wavelength. The",
         "wavelength of everyday objects is far too small to observe, which is why",
         "the wave nature of matter only shows up for particles of very small mass.")
    line("Chapter review", 14, bold=True)
    para("1. Calculate the de Broglie wavelength of an electron travelling at",
         "   2.0 x 10^6 m/s. (3 marks)")
    para("2. Compare the diffraction patterns produced by electrons and photons of",
         "   the same wavelength. (2 marks)")
    c.save()
    return path


@pytest.fixture(autouse=True)
def _never_touch_a_real_folder():
    """Fail loudly if a test writes outside the throwaway root.

    Checked rather than assumed: the paths are spread across a dozen
    modules, and a new one that forgets is otherwise silent until someone
    finds strange files in their own Blitz folder.
    """
    from blitz import config

    assert str(config.ROOT) == str(_TEST_ROOT), (
        f"tests must run against {_TEST_ROOT}, not {config.ROOT}")
    yield
