"""Synthetic pages in the shape of many publishers' question blocks.

Every real VCE book is licensed and none of them can live in this repo, so
these are written from the *shape* of real pages — the heading wording, the
numbering style, where the marks sit — with invented content. Each builder
returns a PDF and declares how many questions should come out of it.

They exist because counting questions is the only cheap way to catch a whole
class of regression: a pattern tightened for one publisher silently emptying
another one's book.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas as rl_canvas

PAGE_W, PAGE_H = A4
LEFT = 20 * mm


def _page(path):
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

    def newpage():
        c.showPage()
        y[0] = PAGE_H - 25 * mm

    return c, line, para, newpage


BUILDERS = {}


def page(name, expect):
    def deco(fn):
        BUILDERS[name] = (fn, expect)
        return fn
    return deco


# --- numbering and heading styles -------------------------------------------

@page("oxford-check-your-learning", 3)
def _(line, para, newpage):
    """Oxford: "Check your learning 3.2", numbered "1 Define ..." with no dot."""
    line("3.2  Enzymes", 14, bold=True)
    para("Enzymes are biological catalysts that lower activation energy.")
    line("Check your learning 3.2", 12, bold=True)
    para("1 Define the term activation energy. (2 marks)")
    para("2 Explain why an enzyme is described as a catalyst. (3 marks)")
    para("3 Compare competitive and non-competitive inhibition. (4 marks)")


@page("subparts-without-dots", 2)
def _(line, para, newpage):
    """Sub-parts written "a Calculate ..." rather than "a. Calculate ..."."""
    line("Chapter review", 14, bold=True)
    para("1 A trolley of mass 2.0 kg is pushed along a bench.",
         "a Calculate the net force if it accelerates at 1.5 m/s2. (2 marks)",
         "b State the direction of the net force. (1 mark)")
    para("2 A ball is dropped from a height of 5.0 m.",
         "a Determine the time taken to reach the ground. (2 marks)",
         "b Calculate its speed on impact. (2 marks)")


@page("exercise-4a", 3)
def _(line, para, newpage):
    line("Exercise 4A", 13, bold=True)
    para("1. Simplify the expression for kinetic energy. (2 marks)")
    para("2. A car travels 120 km in 1.5 hours. Find its average speed. (2 marks)")
    para("3. Explain the difference between speed and velocity. (3 marks)")


@page("bare-mc-no-block-heading", 3)
def _(line, para, newpage):
    """"Question 1" with no "Questions" heading anywhere above it."""
    line("Question 1")
    para("Which of the following is a vector quantity?",
         "A Speed", "B Distance", "C Velocity", "D Mass")
    line("Question 2")
    para("The SI unit of force is the:",
         "A joule", "B newton", "C watt", "D pascal")
    line("Question 3")
    para("Momentum is conserved in which type of collision?",
         "A Elastic only", "B Inelastic only", "C Both elastic and inelastic",
         "D Neither")


@page("exam-sections", 4)
def _(line, para, newpage):
    line("SECTION A - Multiple choice", 14, bold=True)
    line("Question 1")
    para("A resistor obeys Ohm's law. Doubling the voltage will:",
         "A halve the current", "B double the current",
         "C quadruple the current", "D leave the current unchanged")
    line("Question 2")
    para("The unit of capacitance is the:",
         "A ohm", "B henry", "C farad", "D tesla")
    line("SECTION B - Short answer", 14, bold=True)
    line("Question 3 (4 MARKS)")
    para("Describe how a transformer changes the voltage of an AC supply.")
    line("Question 4 (6 MARKS)")
    para("A generator produces 240 V at 5.0 A. Calculate the power output and",
         "explain one cause of energy loss in transmission.")


@page("marks-without-brackets", 2)
def _(line, para, newpage):
    line("Questions", 12, bold=True)
    para("1. State Newton's first law of motion.", "2 marks")
    para("2. Describe an example of Newton's third law.", "3 marks")


@page("restarting-numbers", 4)
def _(line, para, newpage):
    """Numbering restarts in the next section; both blocks must survive."""
    line("Check your learning 5.1", 12, bold=True)
    para("1. Define electric field strength. (2 marks)")
    para("2. State the unit of electric field strength. (1 mark)")
    line("5.2  Magnetic fields", 14, bold=True)
    para("A magnetic field is produced by a moving charge.")
    line("Check your learning 5.2", 12, bold=True)
    para("1. Define magnetic flux density. (2 marks)")
    para("2. State the right-hand rule. (2 marks)")


# --- things that must NOT become questions ----------------------------------

@page("glossary-and-index", 0)
def _(line, para, newpage):
    line("Glossary", 14, bold=True)
    para("acceleration the rate of change of velocity")
    para("displacement the change in position of an object")
    newpage()
    line("Index", 14, bold=True)
    para("acceleration 12, 45, 88")
    para("velocity 11, 44, 87")


@page("summary-dot-points", 0)
def _(line, para, newpage):
    """A numbered summary is not a numbered question block."""
    line("Chapter summary", 14, bold=True)
    para("1 Velocity is the rate of change of displacement.")
    para("2 Acceleration is the rate of change of velocity.")
    para("3 The area under a velocity-time graph gives displacement.")


@page("answers-at-the-back", 2)
def _(line, para, newpage):
    line("Questions", 12, bold=True)
    para("1. Calculate the momentum of a 2.0 kg trolley at 3.0 m/s. (2 marks)")
    para("2. Define the term impulse. (1 mark)")
    newpage()
    line("Answers", 14, bold=True)
    para("1. p = mv = 6.0 kg m/s")
    para("2. Impulse is the change in momentum.")


# --- layout hazards ----------------------------------------------------------

@page("across-page-break", 2)
def _(line, para, newpage):
    line("Review questions", 14, bold=True)
    para("1. A satellite orbits the Earth at an altitude of 400 km.")
    para("   Calculate its orbital period, given the radius of the Earth is",
         "   6.37 x 10^6 m and its mass is 5.97 x 10^24 kg. (4 marks)")
    newpage()
    para("2. Explain why a geostationary satellite must orbit above the",
         "   equator. (3 marks)")


@page("running-headers", 2)
def _(line, para, newpage):
    """A masthead repeated on every page must not join the question text."""
    line("VCE PHYSICS UNITS 3 & 4", 8)
    line("Questions", 12, bold=True)
    para("1. State the principle of conservation of energy. (2 marks)")
    line("Chapter 4", 8)
    line("112", 8)
    newpage()
    line("VCE PHYSICS UNITS 3 & 4", 8)
    para("2. Explain how energy is conserved in a pendulum. (3 marks)")
    line("113", 8)


@page("blank-page-between", 2)
def _(line, para, newpage):
    line("Questions", 12, bold=True)
    para("1. Define refractive index. (2 marks)")
    newpage()
    newpage()
    para("2. State Snell's law. (2 marks)")


@page("data-table", 1)
def _(line, para, newpage):
    line("Questions", 12, bold=True)
    para("1. The table below shows the results of an experiment.",
         "   Time (s)   0.0   1.0   2.0   3.0",
         "   Speed (m/s)   0.0   2.5   5.0   7.5",
         "   Calculate the acceleration of the object. (3 marks)")


@page("mixed-mc-and-short", 3)
def _(line, para, newpage):
    line("Chapter review", 14, bold=True)
    para("1. The unit of power is the:",
         "A joule", "B watt", "C newton", "D pascal")
    para("2. Calculate the power of a 60 W globe running for 2 hours. (2 marks)")
    para("3. Explain the difference between energy and power. (3 marks)")


@page("case-study-shared", 3)
def _(line, para, newpage):
    line("Case study", 12, bold=True)
    para("Harrow Retail employs 340 staff across 12 stores. Following a fall",
         "in sales, management is considering restructuring its operations.")
    line("Exam-style questions", 12, bold=True)
    line("Question 1 (2 MARKS)")
    para("Identify one driving force for change at Harrow Retail.")
    line("Question 2 (4 MARKS)")
    para("Explain one restraining force management may encounter.")
    line("Question 3 (6 MARKS)")
    para("Analyse how a lower cost strategy could improve performance.")


@page("worked-then-questions", 3)
def _(line, para, newpage):
    line("Worked example 7.3", 12, bold=True)
    para("A 3.0 kg block slides down a frictionless incline of 30 degrees.",
         "Calculate its acceleration.")
    line("Solution", 10, bold=True)
    para("a = g sin(theta) = 9.8 x 0.5 = 4.9 m/s2")
    line("Questions", 12, bold=True)
    para("1. Repeat the calculation for an incline of 45 degrees. (2 marks)")
    para("2. Explain the effect of adding friction to the incline. (3 marks)")


def build(name, tmp_path):
    """Write one named page set and return (path, expected question count)."""
    fn, expect = BUILDERS[name]
    path = tmp_path / f"{name}.pdf"
    c, line, para, newpage = _page(path)
    fn(line, para, newpage)
    c.save()
    return path, expect
