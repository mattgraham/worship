# /// script
# requires-python = ">=3.11"
# dependencies = ["pytest", "typst==0.15.*"]
# ///
"""Tests for the parts of build.py that are easy to get subtly wrong.

    uv run tools/setpdf/test_build.py
"""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))
from build import (Key, Transposer, build_song, layout_line, parse_chart, parse_key,  # noqa: E402
                   parse_set_line, pretty)


def xp(src, dst):
    return Transposer.between(parse_key(src), parse_key(dst))


@pytest.mark.parametrize("text, key", [
    ("[Ab]", Key("Ab", False)), ("Bb", Key("Bb", False)), ("A:", Key("A", False)),
    ("Em", Key("E", True)), ("[C#m]", Key("C#", True)), ("f#", Key("F#", False)),
    ("[]", None), ("", None), ("Ab/G#", None), ("H", None),
])
def test_parse_key(text, key):
    assert parse_key(text) == key


@pytest.mark.parametrize("src, dst, chords, want", [
    # Goodness of God, Ab -> G: sharps where G needs them
    ("Ab", "G", "Ab5 Dbsus2 Ab/C Eb/G Fm7 Ebsus4 Dbmaj7", "G5 Csus2 G/B D/F# Em7 Dsus4 Cmaj7"),
    # into a flat key: Bb not A#
    ("C", "F", "C F G Am E/G# Bb", "F Bb C Dm A/C# Eb"),
    # letter-wise spelling keeps borrowed chords sensible: bVII in C -> F in G
    ("C", "G", "Bb C/Bb Ab", "F G/F Eb"),
    # minor keys
    ("Em", "Dm", "Em C G D B7", "Dm Bb F C A7"),
    ("Am", "C#m", "Am F C G E", "C#m A E B G#"),
    # the suffix is carried through untouched, whatever it is
    ("G", "A", "G(no3) Cadd9 Dsus Em7b5 C6/9 Gmaj7#11", "A(no3) Dadd9 Esus F#m7b5 D6/9 Amaj7#11"),
    # optional chords keep their parentheses on the chord line
    ("Ab", "G", "(Db) (Fm)", "(C) (Em)"),
    # things in brackets that aren't chords pass through
    ("G", "A", "x2 N.C. Riff", "x2 N.C. Riff"),
])
def test_transpose(src, dst, chords, want):
    assert xp(src, dst).bracket(chords) == want


def test_never_prints_odd_names():
    """Letter-wise transposition can land on Cb, Fb, E#, B# or a double
    accidental; those fall back to the target key's plain spelling."""
    t = xp("C", "E")
    assert t.chord("E") == "G#"
    assert t.chord("E/G#") == "G#/C"  # not G#/B#
    for src in ("C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db", "Gb"):
        for dst in ("C", "G", "D", "A", "E", "B", "F#", "F", "Bb", "Eb", "Ab", "Db", "Gb"):
            t = xp(src, dst)
            for note in ("C", "C#", "Db", "D", "Eb", "E", "F", "F#", "Gb", "G", "Ab", "A", "Bb", "B"):
                out = t.note(note)
                assert out not in ("Cb", "Fb", "E#", "B#"), (src, dst, note, out)
                assert len(out) <= 2, (src, dst, note, out)


def test_round_trip_same_pitch():
    from build import pitch
    for src, dst in [("Ab", "G"), ("C", "F#"), ("E", "Eb"), ("Bm", "Gm")]:
        t, back = xp(src, dst), xp(dst, src)
        for note in ("C", "Db", "E", "F#", "Ab", "Bb"):
            assert pitch(back.note(t.note(note))) == pitch(note)


def test_pretty():
    assert pretty("Ab") == "A♭"
    assert pretty("C#m7b5/G#") == "C♯m7♭5/G♯"
    assert pretty("Ebsus4") == "E♭sus4"
    assert pretty("(Db)") == "(D♭)"
    assert pretty("Build") == "Build"  # not a chord, left alone
    assert pretty("x2") == "x2"


@pytest.mark.parametrize("line, title, key, bad", [
    ("Goodness of God | G", "Goodness of God ", Key("G", False), None),
    ("Oceans|Bm", "Oceans", Key("B", True), None),
    ("Holy Forever", "Holy Forever", None, None),
    ("Holy Forever | Q", "Holy Forever ", None, "Q"),
])
def test_set_line(line, title, key, bad):
    assert parse_set_line(line) == (title, key, bad)


def words(line):
    out = layout_line(line, lambda b: b)
    return [(r["c"], " ".join(w["t"] for w in r["words"]), r["mid"]) for r in out["runs"]]


def test_layout_runs():
    # a chord mid-word marks its predecessor run "mid"
    assert words("Här [G/B]är j[C]ag") == [(None, "Här", False), ("G/B", "är j", True), ("C", "ag", False)]
    # a chord sitting on a space keeps the space (as an empty word)
    assert words("Bless the[C] Lord") == [(None, "Bless the", False), ("C", " Lord", False)]
    # chord over nothing
    assert words("You [Ab][(Db)]are") == [(None, "You", False), ("A♭", "", False), ("(D♭)", "are", False)]


def test_chord_only_line():
    out = layout_line("| [Ab] / / / | [Db2] / / / |", lambda b: b)
    assert out["kind"] == "chords"
    assert [t.get("c") for t in out["toks"] if "c" in t] == ["A♭", "D♭2"]


CHART = """Title: Demo
Key: G
# a comment in the header
Artist: Someone

Verse 1:
# This is a heading note, not a lyric
[G]First line
#---
Second line
  # ---
Third line

Chorus:
{sot}
# not a comment: tab content
e|--0--|
{eot}
[C]Sing
"""


def test_hash_lines_are_comments_not_lyrics(tmp_path):
    """OnSong hides lines starting with "#" and the only ones in the repo
    (River of Life) are notes, so none may reach the printed chart; the
    "# ---" slide marker survives only as an inert {"kind": "break"}."""
    p = tmp_path / "Demo.onsong"
    p.write_text(CHART)
    chart = parse_chart(p)
    assert chart.meta["artist"] == "Someone"
    verse = chart.sections[0]
    assert [ln["kind"] for ln in verse.lines] == ["raw", "break", "raw", "break", "raw"]
    song = build_song(p, None)
    dumped = json.dumps(song, ensure_ascii=False)
    assert "---" not in dumped
    assert "heading note" not in dumped
    assert "comment in the header" not in dumped


def test_hash_inside_tab_block_is_kept(tmp_path):
    p = tmp_path / "Demo.onsong"
    p.write_text(CHART)
    tab = [ln for s in parse_chart(p).sections for ln in s.lines if ln["kind"] == "tab"]
    assert "# not a comment: tab content" in [t["text"] for t in tab]


def test_break_before_any_lyric_is_dropped(tmp_path):
    p = tmp_path / "Demo.onsong"
    p.write_text("Title: D\n\nVerse:\n# ---\nOnly line\n")
    assert [ln["kind"] for ln in parse_chart(p).sections[0].lines] == ["raw"]


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
