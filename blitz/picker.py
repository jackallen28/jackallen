"""Choose the questions that go on a sheet.

The hard constraint is the page budget: a Blitz is two pages, so the picker
fills a weight budget rather than a question count. Within that budget it tries,
in order, to

  1. give every selected dot point at least one question (breadth first),
  2. spread across the question types the student asked for,
  3. honour the notes box by boosting questions that match its keywords,
  4. prefer questions that bring their own diagram when asked to, and
  5. avoid anything the student has already seen on a recent sheet.

Selection is deterministic for a given (spec, corpus, seed) so a sheet can be
regenerated identically — useful when you want the solutions later.
"""

from __future__ import annotations

import random
import re
import sqlite3
from collections import defaultdict

from .models import Question, SheetPlan, SheetSpec
from .render.layout import budget_mm, estimate_height_mm, image_height_mm
from .studydesign import StudyDesign, load_study_design

# A Blitz is two pages. The budget and every question "weight" below are in
# millimetres of column height — see render/layout.py for where the number
# comes from and why it is measured rather than guessed.
QUESTION_PAGES = 2

_WORD = re.compile(r"[A-Za-z][A-Za-z'-]{2,}")
_STOPWORDS = {
    "the", "and", "for", "with", "that", "this", "from", "have", "has", "are",
    "was", "were", "not", "but", "you", "your", "can", "how", "why", "what",
    "when", "which", "into", "about", "more", "than", "also", "them", "they",
    "get", "got", "need", "want", "really", "still", "just", "bit", "lot",
    "please", "help", "keep", "struggle", "struggling", "confused", "trouble",
    "revise", "revision", "question", "questions", "practice", "focus",
}


def _keywords(notes: str) -> list[str]:
    seen: list[str] = []
    for w in _WORD.findall(notes.lower()):
        if w in _STOPWORDS or w in seen:
            continue
        seen.append(w)
    return seen[:12]


def _stem(word: str) -> str:
    """Crude suffix stripping so 'relativity' matches 'relativistic'.

    Proper stemming would need a dependency for very little gain here — the
    notes box is a nudge, not a query language, and over-matching a little is
    much better than a student typing 'momentum' and getting nothing because the
    book says 'momenta'.
    """
    for suffix in ("ically", "ation", "ivity", "istic", "ness", "ing", "ies",
                   "ied", "ive", "ity", "al", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 5:
            return word[: -len(suffix)]
    return word


def _matches(keyword: str, haystack: str) -> bool:
    if keyword in haystack:
        return True
    stem = _stem(keyword)
    return len(stem) >= 5 and stem in haystack


def _fetch_candidates(
    conn: sqlite3.Connection, spec: SheetSpec
) -> tuple[list[Question], dict[str, list[str]]]:
    """Every question matching the subject, dot points and types the student chose."""
    if not spec.kk_ids:
        return [], {}

    kk_marks = ", ".join("?" for _ in spec.kk_ids)
    params: list = [spec.subject_id, *spec.kk_ids]
    sql = (
        "SELECT DISTINCT q.*, s.kind AS source_kind FROM question q "
        "JOIN question_kk qk ON qk.question_id = q.id "
        "LEFT JOIN source s ON s.id = q.source_id "
        f"WHERE q.subject_id = ? AND qk.kk_id IN ({kk_marks})"
    )
    if spec.question_type_ids:
        qt_marks = ", ".join("?" for _ in spec.question_type_ids)
        sql += f" AND q.question_type IN ({qt_marks})"
        params.extend(spec.question_type_ids)
    if not spec.allow_generated:
        sql += " AND q.generated = 0"
    if spec.exclude_question_ids:
        ex_marks = ", ".join("?" for _ in spec.exclude_question_ids)
        sql += f" AND q.id NOT IN ({ex_marks})"
        params.extend(spec.exclude_question_ids)

    rows = conn.execute(sql, params).fetchall()

    links = defaultdict(list)
    if rows:
        id_marks = ", ".join("?" for _ in rows)
        for link in conn.execute(
            f"SELECT question_id, kk_id FROM question_kk WHERE question_id IN ({id_marks})",
            [r["id"] for r in rows],
        ):
            links[link["question_id"]].append(link["kk_id"])

    questions = [Question.from_row(r, links.get(r["id"], [])) for r in rows]
    return questions, links


def _difficulty_fit(spec: SheetSpec, q: Question) -> float:
    if spec.difficulty == "mixed" or q.difficulty is None:
        return 0.0
    if spec.difficulty == "easy":
        return 1.0 - abs(q.difficulty - 2) * 0.35
    if spec.difficulty == "hard":
        return 1.0 - abs(q.difficulty - 4) * 0.35
    return 0.0


def _score(spec: SheetSpec, q: Question, keywords: list[str], rng: random.Random) -> float:
    """Higher is better. Everything here is a nudge, not a filter."""
    score = 0.0
    haystack = f"{q.body} {q.answer or ''} {q.figure_caption or ''}".lower()
    hits = sum(1 for kw in keywords if _matches(kw, haystack))
    score += hits * 1.4
    if spec.prefer_figures and q.has_figure:
        score += 0.9
    if q.answer:
        score += 0.6                      # a question without a solution is half a question
    if not q.generated:
        score += 1.2                      # real questions from the books win ties
    if q.verified:
        score += 0.3
    score += _difficulty_fit(spec, q)
    score += rng.uniform(0.0, 0.5)        # break ties differently each seed
    return score


def build_plan(
    conn: sqlite3.Connection,
    spec: SheetSpec,
    design: StudyDesign | None = None,
    pages: int = QUESTION_PAGES,
) -> SheetPlan:
    design = design or load_study_design(spec.subject_id)
    rng = random.Random(spec.seed if spec.seed is not None else 0xB117)
    keywords = _keywords(spec.notes)

    candidates, _ = _fetch_candidates(conn, spec)
    plan = SheetPlan(spec=spec)

    if not candidates:
        plan.uncovered_kk_ids = list(spec.kk_ids)
        plan.warnings.append(
            "No questions in the index match that selection. Ingest your sources "
            "first, or widen the question types."
        )
        return plan

    def weight(q: Question) -> float:
        """Estimated column millimetres this question will occupy."""
        try:
            fallback = design.question_type(q.question_type).default_weight * 45.0
        except KeyError:
            fallback = 45.0
        if q.is_cropped:
            # The images ARE the question — continuation pages, shared context
            # and required earlier questions included — so the whole stack is
            # the cost, not just the first one.
            return sum(
                image_height_mm(spec["path"], columns=columns,
                                pt_width=spec.get("pt_width"))
                for spec in q.figures_for("question")
            ) + 12
        return estimate_height_mm(
            q.body,
            marks=q.marks,
            options=q.options,
            has_figure=q.has_figure and spec.prefer_figures,
            fallback=fallback,
        )

    ranked = sorted(candidates, key=lambda q: -_score(spec, q, keywords, rng))
    by_kk: dict[str, list[Question]] = defaultdict(list)
    for q in ranked:
        for kk in q.kk_ids:
            if kk in spec.kk_ids:
                by_kk[kk].append(q)

    # A crop-heavy sheet goes single column so the page images stay readable,
    # which halves the millimetres available. Decide before spending them.
    from .render.sheet import choose_columns

    columns = spec.columns or choose_columns(candidates)
    budget = budget_mm(pages, columns=columns)
    remaining = budget
    chosen: list[Question] = []
    chosen_ids: set[str] = set()
    type_counts: dict[str, int] = defaultdict(int)

    # Pass 1 — breadth. One question per selected dot point.
    #
    # The order matters: when more dot points are selected than will fit on two
    # pages, whichever comes last gets nothing. Walking them in menu order would
    # silently drop Unit 4 every time, and would ignore the notes box entirely.
    # So dot points are ordered by how well their best question answers what the
    # student actually asked for.
    for kk in _kk_priority(spec, design, by_kk, keywords):
        pool = [q for q in by_kk.get(kk, []) if q.id not in chosen_ids]
        if not pool:
            continue
        # Prefer a lighter question when the budget is tight, but stay near the top
        # of the ranking: consider only the best few.
        shortlist = pool[:4]
        # When the budget is nearly spent, take the cheapest of the best few so
        # a wide dot-point selection still gets broad coverage.
        pick = min(shortlist, key=weight) if remaining < 120 else shortlist[0]
        w = weight(pick)
        if w > remaining:
            continue
        chosen.append(pick)
        chosen_ids.add(pick.id)
        type_counts[pick.question_type] += 1
        remaining -= w

    # Pass 2 — depth. Spend what's left on the highest-scoring questions, keeping
    # the mix of question types roughly even.
    wanted_types = spec.question_type_ids or sorted({q.question_type for q in ranked})
    for q in ranked:
        if remaining <= 20:
            break
        if q.id in chosen_ids:
            continue
        w = weight(q)
        if w > remaining:
            continue
        # Don't let one type eat the sheet while another asked-for type is absent.
        missing = [t for t in wanted_types if type_counts[t] == 0]
        if missing and q.question_type not in missing:
            continue
        chosen.append(q)
        chosen_ids.add(q.id)
        type_counts[q.question_type] += 1
        remaining -= w

    # Pass 3 — top up with anything that still fits, now ignoring the type balance.
    for q in ranked:
        if remaining <= 20:
            break
        if q.id in chosen_ids:
            continue
        w = weight(q)
        if w <= remaining:
            chosen.append(q)
            chosen_ids.add(q.id)
            type_counts[q.question_type] += 1
            remaining -= w

    chosen = _pull_in_dependencies(conn, spec, chosen, design, columns)
    covered = {kk for q in chosen for kk in q.kk_ids}
    plan.questions = _order_for_sheet(chosen, spec, design)
    plan.uncovered_kk_ids = [kk for kk in spec.kk_ids if kk not in covered]
    plan.estimated_pages = round((budget - remaining) / budget * pages, 2)

    if plan.uncovered_kk_ids:
        names = ", ".join(
            design.key_knowledge(kk).display for kk in plan.uncovered_kk_ids[:4]
        )
        plan.warnings.append(
            f"{len(plan.uncovered_kk_ids)} selected dot point(s) got no question "
            f"— not enough room or not enough coverage in the index ({names})."
        )
    missing_types = [t for t in wanted_types if type_counts[t] == 0]
    if missing_types:
        labels = []
        for t in missing_types:
            try:
                labels.append(design.question_type(t).label)
            except KeyError:
                labels.append(t)
        plan.warnings.append(
            "No room (or no matching questions) for: " + ", ".join(labels) + "."
        )
    if any(q.generated for q in chosen):
        n = sum(1 for q in chosen if q.generated)
        plan.warnings.append(
            f"{n} question(s) were generated to fill coverage gaps and are marked "
            "with a ° on the sheet."
        )
    return plan


def _pull_in_dependencies(
    conn: sqlite3.Connection,
    spec: SheetSpec,
    chosen: list[Question],
    design: StudyDesign,
    columns: int,
) -> list[Question]:
    """Bring in any question a chosen one cannot be answered without.

    Checkpoints sets runs where a later question reads "using your answer from
    part a" or refers to the scenario two questions earlier. Putting the second
    on a sheet without the first gives the student something they cannot answer
    and no way to know why.
    """
    have = {q.id for q in chosen}
    wanted = [d for q in chosen for d in q.depends_on if d not in have]
    if not wanted:
        return chosen

    marks = ", ".join("?" for _ in wanted)
    rows = conn.execute(
        f"SELECT q.*, s.kind AS source_kind FROM question q "
        f"LEFT JOIN source s ON s.id = q.source_id WHERE q.id IN ({marks})",
        wanted,
    ).fetchall()
    links: dict[str, list[str]] = {}
    for row in rows:
        links[row["id"]] = [
            r["kk_id"] for r in conn.execute(
                "SELECT kk_id FROM question_kk WHERE question_id = ?", (row["id"],))
        ]

    out = list(chosen)
    for row in rows:
        prerequisite = Question.from_row(row, links.get(row["id"], []))
        # Insert immediately before the first question that needs it, so the
        # pair reads in the order the book prints them.
        at = next((i for i, q in enumerate(out) if row["id"] in q.depends_on),
                  len(out))
        out.insert(at, prerequisite)
    return out


def _kk_hits(design: StudyDesign, kk_id: str, pool: list[Question],
             keywords: list[str]) -> int:
    """How many notes keywords this dot point answers to.

    Counts both the dot point's own wording and the questions filed under it, so
    "motivation theories" matches the dot point directly while "Maslow" matches
    through the questions.
    """
    if not keywords:
        return 0
    try:
        kk = design.key_knowledge(kk_id)
        hay = f"{kk.text} {kk.label or ''}".lower()
    except KeyError:
        hay = ""
    for q in pool[:8]:
        hay += f" {q.body} {q.figure_caption or ''}".lower()
    return sum(1 for kw in keywords if _matches(kw, hay))


def _kk_priority(
    spec: SheetSpec,
    design: StudyDesign,
    by_kk: dict[str, list[Question]],
    keywords: list[str],
) -> list[str]:
    """Selected dot points, most-wanted first.

    When more dot points are selected than will fit on two pages, whichever
    comes last gets nothing. Walking them in menu order would silently drop
    Unit 4 every time and ignore the notes box entirely; ordering by score alone
    would let the picker's random tie-break shuffle a selection the student made
    deliberately. So: dot points the notes actually name come first, ranked by
    how many keywords they answer, and everything else keeps the student's own
    order.
    """
    if not keywords:
        return list(spec.kk_ids)

    order = {kk: i for i, kk in enumerate(spec.kk_ids)}
    hits = {kk: _kk_hits(design, kk, by_kk.get(kk, []), keywords)
            for kk in spec.kk_ids}
    return sorted(spec.kk_ids, key=lambda kk: (-hits[kk], order[kk]))


def _order_for_sheet(
    questions: list[Question], spec: SheetSpec, design: StudyDesign
) -> list[Question]:
    """Group by area of study, then run easy-to-hard within each group.

    Multiple choice always leads — it's the warm-up, and it keeps the short items
    from being stranded at the bottom of page two.
    """
    aos_order = {a.id: i for i, a in enumerate(design.all_areas())}

    def key(q: Question):
        aos_rank = min(
            (aos_order.get(design.area_of(kk).id, 99) for kk in q.kk_ids
             if _safe_area(design, kk)),
            default=99,
        )
        is_mc = 0 if q.question_type.endswith("-mc") else 1
        return (aos_rank, is_mc, q.difficulty or 3, q.marks or 0)

    return sorted(questions, key=key)


def _safe_area(design: StudyDesign, kk_id: str) -> bool:
    try:
        design.area_of(kk_id)
        return True
    except KeyError:
        return False
