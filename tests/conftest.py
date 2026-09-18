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


def _book_page(path):
    """A canvas plus a `line` helper, shared by the publisher-shaped fixtures."""
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

    return c, line, para


@pytest.fixture
def fake_physics_textbook(tmp_path):
    """A PDF in the Jacaranda-style Physics vocabulary.

    The real book heads its worked examples "Sample problem 1.6" and drops
    single questions into the teaching prose as "Revision question 1.5", with
    no numbered list anywhere. Written from the shape of the real pages, not
    from their content.
    """
    path = tmp_path / "fake-physics-textbook.pdf"
    c, line, para = _book_page(path)

    line("Chapter 1  Motion", 18, bold=True)
    line("1.1  Describing motion", 14, bold=True)
    para("Velocity is the rate of change of displacement. A velocity-time graph",
         "describes how that velocity changes, and the area under it gives the",
         "displacement travelled over the interval shown.")
    line("Sample problem 1.6", 12, bold=True)
    para("A car accelerates uniformly from rest to 25 m/s in 8.0 s. Calculate the",
         "acceleration of the car and the distance it travels in that time.")
    line("Solution", 10, bold=True)
    para("a = (v - u)/t = 25/8.0 = 3.1 m/s^2, and s = (u + v)t/2 = 100 m.")
    line("Revision question 1.5", 12, bold=True)
    para("A tram slows uniformly from 14 m/s to rest over 7.0 s. Determine the",
         "magnitude of its acceleration and the distance it covers while stopping.")
    line("1.2  Forces", 14, bold=True)
    para("A force is a push or a pull, measured in newtons. The net force on a",
         "body determines its acceleration through Newton's second law.")
    line("Revision question 1.12", 12, bold=True)
    para("A crate of mass 45 kg is pushed across a floor by a horizontal force of",
         "180 N against a friction force of 55 N. Calculate its acceleration.")
    c.save()
    return path


@pytest.fixture
def fake_busman_textbook(tmp_path):
    """A PDF in the Edrolo-style Business Management vocabulary.

    "Case study" above a block of "Exam-style questions", each question headed
    "Question 1" on its own line with "(2 MARKS)" under it and the exam it came
    from cited bare underneath. The scenario is invented for the test.
    """
    path = tmp_path / "fake-busman-textbook.pdf"
    c, line, para = _book_page(path)

    line("Chapter 3  Managing employees", 18, bold=True)
    line("3.1  Motivation strategies", 14, bold=True)
    para("Motivation is the willingness of an employee to exert effort towards",
         "the objectives of the business. Financial and non-financial strategies",
         "are used together, because each addresses a different need.")
    line("Case study", 12, bold=True)
    para("Northbrook Cartons is a family-owned packaging manufacturer employing",
         "120 staff across two sites. Absenteeism has risen sharply and the",
         "operations manager has proposed a new performance-related pay scheme.")
    line("Exam-style questions", 12, bold=True)
    line("Question 1")
    para("Outline one financial motivation strategy Northbrook Cartons could use.",
         "(2 MARKS)",
         "Adapted from VCAA 2020 exam Section A Q1a")
    line("Question 2")
    para("Analyse how investment in training could reduce absenteeism at",
         "Northbrook Cartons over the longer term.",
         "(6 MARKS)")
    c.save()
    return path


@pytest.fixture
def fake_learnon_textbook(tmp_path):
    """A Physics page with online-resource callouts among the questions.

    Jacaranda's learnON titles print these in the question block and in the
    same style, so they were being filed as questions and printed on sheets
    telling the student to go and watch a video.
    """
    path = tmp_path / "fake-learnon.pdf"
    c, line, para = _book_page(path)

    line("Chapter 5  Fields", 18, bold=True)
    line("5.1  Gravitational fields", 14, bold=True)
    para("The field around a mass is the region in which another mass feels a",
         "force. Its strength is the force per unit mass at that point.")
    line("Resources", 12, bold=True)
    para("Watch this eLesson: Gravitational fields (ele-0031)",
         "Try out this Interactivity: Field strength explorer (int-6799)",
         "Complete this digital document: Investigation 5.1 (doc-1821)")
    line("Questions", 12, bold=True)
    para("1. Calculate the gravitational field strength 2.0 Earth radii from the",
         "   centre of the Earth. (3 marks)")
    para("2. Try out this Interactivity: Orbital motion (int-6801) and describe",
         "   what happens to the period as the radius increases.")
    para("3. Explain why the field strength inside a uniform shell is zero.",
         "   (2 marks)")
    para("Find all this and more in your learnON title.")
    c.save()
    return path


@pytest.fixture
def fake_marks_inline_textbook(tmp_path):
    """Question number and marks on one line, as several publishers print it."""
    path = tmp_path / "fake-marks-inline.pdf"
    c, line, para = _book_page(path)

    line("Chapter 2  Managing employees", 18, bold=True)
    line("Exam-style questions", 12, bold=True)
    line("Question 1 (2 MARKS)")
    para("Outline one financial motivation strategy a business could use.")
    line("Question 2 (6 MARKS)")
    para("Analyse how investment in training could reduce staff absenteeism",
         "over the longer term.")
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
