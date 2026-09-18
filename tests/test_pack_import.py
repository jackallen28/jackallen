"""Importer details that only show up on a real book: marks printed in the
stem, and crop widths derived from image files."""

import pytest


def test_trailing_marks_are_stripped_from_stems_and_parts():
    """The book prints "(3 marks)" after the question; the sheet prints marks
    itself, so a stem that keeps them shows them twice."""
    from blitz.ingest.pack import _split_marks, _marks, _text_of

    assert _split_marks("Explain why. (3 marks)") == ("Explain why.", 3)
    assert _split_marks("Explain why.\n(1 mark)") == ("Explain why.", 1)
    assert _split_marks("Find (3 marks) of x") == ("Find (3 marks) of x", None)
    assert _split_marks(None) == (None, None)

    q = {"stem": "Find the speed. (2 marks)", "parts": [
        {"label": "a", "text": "First part. (1 mark)"}]}
    assert _text_of(q) == "Find the speed. a. First part."
    # Marks fall back to the stem's own count when nothing else states them.
    assert _marks({"stem": "Explain why. (3 marks)"}) == 3
    assert _marks({"stem": "Explain why. (3 marks)", "marks": 5}) == 5


def test_file_figure_width_is_pixels_over_zoom(tmp_path):
    """A 1596px crop rendered at 3x is a 532pt region. PyMuPDF would have
    called it 1197pt (an assumed 96 dpi), which is how the width was wrong
    by a quarter before."""
    from PIL import Image
    from blitz.ingest.pack import _pt_width
    from blitz.render.layout import image_px_size

    png = tmp_path / "crop.png"
    Image.new("L", (1596, 300), 255).save(png)
    assert image_px_size(str(png)) == (1596, 300)
    assert _pt_width({"file": "crop.png"}, str(png), zoom=3.0) == pytest.approx(532.0)
    assert _pt_width({"file": "crop.png"}, str(png)) == pytest.approx(1596.0)
    assert _pt_width({"file": "crop.png", "pt_width": 400}, str(png), zoom=3.0) == 400.0
    assert _pt_width({"page": 3, "bbox": [10, 10, 210, 60]}, str(png), zoom=3.0) == 200.0


def _q(qid, stem, kk_ids, **kw):
    return {"id": qid, "stem": stem, "kk_ids": kk_ids, **kw}


def test_refiner_narrows_chapter_tags_to_the_dot_point_the_text_names():
    from blitz.ingest.pack import TagRefiner
    from blitz.studydesign import load_study_design

    design = load_study_design("physics")
    energy = "physics-u3-aos1-kk08"          # work done by a force
    transform = "physics-u3-aos1-kk09"       # transformations of energy
    q = _q("Q1", "A spring launcher projects a ball vertically upwards. "
                 "Find the elastic potential energy stored in the spring.",
           [energy, transform])
    r = TagRefiner(design, [q])
    kk, what = r.refine(q, q["stem"])
    assert what == "narrowed"
    assert kk == [transform]


def test_refiner_keeps_pack_tags_when_the_text_names_none_of_them():
    from blitz.ingest.pack import TagRefiner
    from blitz.studydesign import load_study_design

    design = load_study_design("physics")
    tags = ["physics-u3-aos1-kk08", "physics-u3-aos1-kk09"]
    q = _q("Q1", "Which one of the following is closest to the value of x?", tags)
    r = TagRefiner(design, [q])
    assert r.refine(q, q["stem"]) == (tags, "kept")


def test_refiner_extends_only_to_dot_points_the_pack_left_empty():
    from blitz.ingest.pack import TagRefiner
    from blitz.studydesign import load_study_design

    design = load_study_design("physics")
    postulates = "physics-u4-aos1-kk20"
    examples = "physics-u4-aos1-kk26"        # examples of special relativity (muons)
    muons = _q("Q1", "Muons created in the upper atmosphere have a proper lifetime "
                     "of 2.2 μs. Explain, using time dilation, why muons reach "
                     "the ground.", [postulates])
    r = TagRefiner(design, [muons])
    kk, what = r.refine(muons, muons["stem"])
    assert "extended" in what
    assert examples in kk and postulates in kk

    # The same question, in a pack that already uses that dot point elsewhere,
    # is not extended: the pack's own mapping is trusted for what it covers.
    other = _q("Q2", "Something else entirely.", [examples])
    r2 = TagRefiner(design, [muons, other])
    kk2, what2 = r2.refine(muons, muons["stem"])
    assert "extended" not in what2


def test_refiner_never_leaves_the_area_of_study():
    from blitz.ingest.pack import TagRefiner
    from blitz.studydesign import load_study_design

    design = load_study_design("physics")
    # A motion tag on a question whose text screams photoelectric effect.
    q = _q("Q1", "Light of frequency above the threshold frequency ejects "
                 "photoelectrons; the work function of the metal is 2.1 eV.",
           ["physics-u3-aos1-kk01"])
    r = TagRefiner(design, [q])
    kk, _ = r.refine(q, q["stem"])
    assert all(k.startswith("physics-u3-aos1") for k in kk)


def test_figures_are_found_in_a_folder_of_any_name_beside_the_pack(tmp_path):
    """The pack says figures/x.png; the person unzipped them into
    checkpointscodexfigures/. Same file, found anyway, once and unambiguously."""
    from PIL import Image
    from blitz.ingest.pack import _FIGURE_INDEX, _locate_figure

    (tmp_path / "checkpointscodexfigures").mkdir()
    Image.new("L", (30, 30), 255).save(tmp_path / "checkpointscodexfigures" / "p0001-abc.png")
    _FIGURE_INDEX.pop(tmp_path, None)
    found = _locate_figure(tmp_path, "figures/p0001-abc.png")
    assert found == tmp_path / "checkpointscodexfigures" / "p0001-abc.png"
    assert _locate_figure(tmp_path, "figures/missing.png") is None
    # Two files of the same name in different folders is ambiguous: refuse.
    (tmp_path / "other").mkdir()
    Image.new("L", (30, 30), 255).save(tmp_path / "other" / "p0001-abc.png")
    _FIGURE_INDEX.pop(tmp_path, None)
    assert _locate_figure(tmp_path, "figures/p0001-abc.png") is None
