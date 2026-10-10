# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "python-pptx>=1.0"]
# ///
"""Tests for the slide splitting, which needs no pptx.

    uv run tools/slides/test_build.py
"""

import importlib.util
import sys
from pathlib import Path

import pytest

# By path and under a unique name: setpdf's tests import their own "build".
_spec = importlib.util.spec_from_file_location("slides_build", Path(__file__).parent / "build.py")
sb = importlib.util.module_from_spec(_spec)
sys.modules["slides_build"] = sb
_spec.loader.exec_module(sb)
Section = sb.setpdf.Section
B = sb.BREAK


def sec(label, *raws, repeat=None):
    lines = [{"kind": "break"} if r is B else {"kind": "raw", "text": r} for r in raws]
    return Section(label, repeat, lines)


@pytest.mark.parametrize("raw, want", [
    ("[G]This is the [D]day", "This is the day"),
    ("Bless the[C] Lord", "Bless the Lord"),
    ("vil[Em]ja  mer", "vilja mer"),
    ("| [Ab] / / / | [Db2] / / / |", None),
    ("[G] [C]", None),
    ("   ", None),
    ("when the even--ing comes", "when the evening comes"),
    ("fore----[G]vermore!", "forevermore!"),
    ("a-[D]bundant-ly", "a-bundant-ly"),
    ("Sing it (x2)", "Sing it (x2)"),
])
def test_lyric_of(raw, want):
    assert sb.lyric_of(raw) == want


@pytest.mark.parametrize("n, sizes", [
    (1, [1]), (4, [4]), (5, [3, 2]), (6, [3, 3]), (8, [4, 4]), (9, [3, 3, 3]), (10, [4, 3, 3]), (0, []),
])
def test_balanced_chunks(n, sizes):
    lines = [str(i) for i in range(n)]
    chunks = sb.balanced_chunks(lines)
    assert [len(c) for c in chunks] == sizes
    assert [l for c in chunks for l in c] == lines  # order kept, nothing lost


def test_markers_split_and_short_section_is_one_slide():
    assert sb.split_section(["a", "b"]) == [["a", "b"]]
    assert sb.split_section(["a", "b", B, "c", "d"]) == [["a", "b"], ["c", "d"]]
    # stray markers never yield an empty slide
    assert sb.split_section([B, "a", B, B, "b", B]) == [["a"], ["b"]]


def test_marker_groups_still_capped():
    got = sb.split_section(["1", "2", B, "3", "4", "5", "6", "7"])
    assert got == [["1", "2"], ["3", "4", "5"], ["6", "7"]]


def test_song_slides_repeat_reuses_referenced_section():
    sections = [
        sec("Verse 1", "[G]one", "two"),
        sec("Chorus", "[C]sing", "loud"),
        sec("Verse 2", "three"),
        sec(None, repeat="Chorus"),
    ]
    got = sb.song_slides(sections)
    assert [lab for lab, _ in got] == ["Verse 1", "Chorus", "Verse 2", "Chorus"]
    assert got[-1][1] == ["sing", "loud"]


def test_unresolvable_repeat_is_skipped():
    sections = [sec("Verse 1", "one"), sec(None, repeat="Bridge")]
    assert sb.song_slides(sections) == [("Verse 1", ["one"])]


def test_repeat_finds_numbered_section_and_prefers_nearest():
    sections = [sec("Chorus 1", "a"), sec("Chorus 2", "b"), sec(None, repeat="Chorus")]
    assert sb.song_slides(sections)[-1] == ("Chorus 2", ["b"])


def test_chord_only_and_note_lines_are_not_projected():
    s = Section("Intro", None, [
        {"kind": "raw", "text": "| [G] / / / |"},
        {"kind": "note", "text": "slowly"},
        {"kind": "raw", "text": "[G]words"},
    ])
    assert sb.song_slides([s]) == [("Intro", ["words"])]


def test_real_chart_end_to_end(tmp_path):
    chart = tmp_path / "x.onsong"
    chart.write_text("Title: X\nKey: G\n\nVerse 1:\n[G]one\ntwo\n# ---\nthree\n\nChorus\n")
    songs = sb.song_data(chart)
    assert songs["slides"] == [("Verse 1", ["one", "two"]), ("Verse 1", ["three"])]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
