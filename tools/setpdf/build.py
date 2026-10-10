# /// script
# requires-python = ">=3.11"
# dependencies = ["typst==0.15.*"]
# ///
"""Render each set list to a printable chord-chart PDF.

    uv run tools/setpdf/build.py                    # every sets/*.txt -> dist/<name>.pdf
    uv run tools/setpdf/build.py sets/MEG26.txt     # just that one
    uv run tools/setpdf/build.py --song "Goodness of God | G"   # one song, for a quick look
    uv run tools/setpdf/build.py --check            # parse every chart, report oddities

A set-list line is a song title, optionally followed by "| <key>" to print
that song transposed, e.g. "Goodness of God | G" or "Oceans | Bm". Songs are
matched exactly the way build-sets.sh matches them (see its header), so a set
resolves to the same charts in the zip and in the PDF. The zip keeps the
charts in their own key on purpose: importing it into OnSong updates the
songs already there, and a transposed copy would overwrite their key.

Parsing is deliberately forgiving. The charts were written by hand over many
years and imported from several apps, so there are OnSong headers with and
without tags, ChordPro directives in a handful of files, whole sections pasted
onto a single line, and the odd "[Ab}" typo. Anything the parser can't place
is printed as plain lyric text rather than failing the build -- a set PDF
with one ugly line is still worth having on a music stand.

Layout lives in chart.typ (Typst). This script only turns charts into a JSON
description of each song and hands it over; fonts are bundled in fonts/ and
system fonts are ignored so a PDF built in CI matches one built locally.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
TEMPLATE = HERE / "chart.typ"
FONTS = HERE / "fonts"


def warn(msg: str) -> None:
    print(f"   warning: {msg}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Transposition
#
# Notes are moved by letter *and* semitone, so each chord keeps its musical
# spelling: a borrowed Bb in C becomes F in G (not E#), E/G# in C becomes
# B/D# in G. Only when that lands on something no chart should show (Cb, E#,
# a double sharp) does it fall back to the plain flat/sharp spelling of the
# target key. The chord's suffix is never parsed, just carried over, so
# sus2, (no3), add4, m7b5 and every hand-typed variant survive untouched.

LETTERS = "CDEFGAB"
NATURAL = [0, 2, 4, 5, 7, 9, 11]
SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
ACC = {"#": 1, "b": -1, "": 0}
# Pitch classes of the major keys written with flats: F Bb Eb Ab Db Gb.
FLAT_MAJORS = {5, 10, 3, 8, 1, 6}

NOTE_RE = re.compile(r"([A-G])([#b]?)")
CHORD_RE = re.compile(r"^([A-G][#b]?)(.*?)(?:/([A-G][#b]?))?$")
KEY_RE = re.compile(r"^([A-Ga-g])([#b♯♭]?)(m|min|-)?$")


@dataclass(frozen=True)
class Key:
    root: str  # "Ab", "F#"
    minor: bool

    def __str__(self) -> str:
        return self.root + ("m" if self.minor else "")


def pitch(note: str) -> int:
    m = NOTE_RE.fullmatch(note)
    return (NATURAL[LETTERS.index(m[1])] + ACC[m[2]]) % 12


def parse_key(text: str | None) -> Key | None:
    """Accept the spellings found in the charts: "[Ab]", "Bb", "A:", "Em"."""
    if not text:
        return None
    t = text.strip().strip("[]").strip().rstrip(":").strip()
    m = KEY_RE.fullmatch(t)
    if not m:
        return None
    acc = {"♯": "#", "♭": "b"}.get(m[2], m[2])
    return Key(m[1].upper() + acc, bool(m[3]))


def key_names(key: Key) -> list[str]:
    """Fallback spelling for a key: explicit accidentals win, else the
    circle of fifths (minor keys follow their relative major)."""
    if "#" in key.root:
        return SHARP_NAMES
    if "b" in key.root:
        return FLAT_NAMES
    major = (pitch(key.root) + (3 if key.minor else 0)) % 12
    return FLAT_NAMES if major in FLAT_MAJORS else SHARP_NAMES


@dataclass(frozen=True)
class Transposer:
    letters: int  # letter-name steps, 0..6
    semis: int  # semitones, 0..11
    names: tuple[str, ...]

    @classmethod
    def between(cls, src: Key, dst: Key) -> "Transposer":
        return cls(
            (LETTERS.index(dst.root[0]) - LETTERS.index(src.root[0])) % 7,
            (pitch(dst.root) - pitch(src.root)) % 12,
            tuple(key_names(dst)),
        )

    def note(self, note: str) -> str:
        target = (pitch(note) + self.semis) % 12
        letter = (LETTERS.index(note[0]) + self.letters) % 7
        diff = (target - NATURAL[letter] + 6) % 12 - 6
        if diff in (-1, 0, 1):
            name = LETTERS[letter] + {-1: "b", 0: "", 1: "#"}[diff]
            if name not in ("Cb", "Fb", "E#", "B#"):
                return name
        return self.names[target]

    def chord(self, token: str) -> str:
        """Transpose one chord; anything that isn't one passes through."""
        if token.startswith("(") and token.endswith(")") and len(token) > 2:
            # [(Db)]: an optional/alternate chord, parentheses on the chord line
            return "(" + self.chord(token[1:-1]) + ")"
        m = CHORD_RE.match(token)
        if not m:
            return token
        root, suffix, bass = m.groups()
        out = self.note(root) + suffix
        if bass:
            out += "/" + self.note(bass)
        return out

    def bracket(self, text: str) -> str:
        """A [bracket] may hold several space-separated chords or a note."""
        return re.sub(r"\S+", lambda m: self.chord(m[0]), text)


def is_chord(token: str) -> bool:
    token = token[1:-1] if token.startswith("(") and token.endswith(")") else token
    return bool(CHORD_RE.match(token))


def pretty(text: str) -> str:
    """Display form of a bracket: Ab -> A♭, C#m7b5 -> C♯m7♭5. Only tokens
    that parse as chords are touched, so "[Build]" or "[x2]" stay as typed."""

    def one(tok: str) -> str:
        if not is_chord(tok):
            return tok
        tok = re.sub(r"(?<=[A-G])b", "♭", tok)
        tok = re.sub(r"(?<=[A-G])#", "♯", tok)
        return re.sub(r"b(?=\d)", "♭", tok)

    return re.sub(r"\S+", lambda m: one(m[0]), text)


# ---------------------------------------------------------------------------
# Chart parsing

# Tags that are metadata even when empty ("Original Key:" with nothing after
# it is common), so they never get mistaken for a section heading.
META_KEYS = {
    "title", "artist", "author", "key", "original key", "tempo", "time", "ccli",
    "book", "notes", "copyright", "bpm", "cant key", "church key", "capo",
    "original capo", "album", "writer", "url", "topic", "scripture reference",
    "scripture refrence", "words", "words and music by", "arrangement", "temo",
    "waring", "flow", "duration", "keywords", "number", "year",
}
# First words that mark a section label, in English and Swedish. Used to
# recognise a label with content on the same line ("Verse 1:[A2]Can I...")
# and a bare label with no colon ("Intro").
SECTION_WORDS = (
    "intro|verse|vers|chorus|refrain|refräng|pre|prechorus|pre-chorus|bridge|brygga|"
    "tag|outro|ending|interlude|instrumental|instromental|turnaround|turn|vamp|rap|"
    "breakdown|slut|stick|tonartsbyte|final|alt|coda|solo|mellanspel|förspel|"
    "efterspel|post|refr|spontaneous|interlude"
)
SECTION_START = re.compile(rf"^(?:{SECTION_WORDS})\b", re.I)
TAG = re.compile(r"^([A-Za-zÅÄÖåäö][\w ()'’&/.#,-]{0,30}?)\s*:\s*(.*)$")
DIRECTIVE = re.compile(r"^\{\s*([\w-]+)\s*(?::\s*(.*?))?\s*\}$")
# "REPEAT CHORUS", "(Repeat Bridge)" -- the closing paren is only stripped
# when the line opened one, so "Repeat Pre-Chorus 2 (x2)" keeps its "(x2)".
REPEAT = re.compile(r"^(?:\(\s*repeat\s+(.+?)\s*\)|repeat\s+(.+?))\s*$", re.I)
# A bracket is only a chord when it closes before any other bracket or
# brace, so a "[Ab}" typo stays literal text instead of eating the line.
BRACKET = re.compile(r"\[([^\[\]{}]*)\]")
# What's left of a line once chords are removed, when it's really a chord
# line: bar lines, beat slashes, repeat counts.
CHORD_LINE_REST = re.compile(r"^[\s|/.\-–x×%()\d:]*$", re.I)
DIRECTIVE_META = {"title", "t", "artist", "subtitle", "st", "key", "original_key",
                  "tempo", "time", "ccli", "copyright"}
DIRECTIVE_SECTIONS = {
    "start_of_verse": "Verse", "sov": "Verse", "start_of_chorus": "Chorus",
    "soc": "Chorus", "start_of_bridge": "Bridge", "sob": "Bridge",
    "start_of_part": "", "start_of_grid": "", "sog": "",
}


# A "# ---" (or "#---", any run of 2+ dashes) comment is the one comment that
# means something: an invisible slide-break marker for tools/slides/build.py.
BREAK_MARK = re.compile(r"^#\s*-{2,}\s*$")


@dataclass
class Section:
    label: str | None = None
    repeat: str | None = None
    lines: list[dict] = field(default_factory=list)


@dataclass
class Chart:
    path: Path
    meta: dict[str, str] = field(default_factory=dict)
    sections: list[Section] = field(default_factory=list)
    untagged: list[str] = field(default_factory=list)


def is_label(line: str) -> str | None:
    """'Verse 1:' / 'Tonartsbyte (D):' / bare 'Intro' -> the label."""
    s = line.strip()
    if "[" in s or "{" in s:
        return None
    m = TAG.match(s)
    if m and not m[2] and m[1].strip().lower() not in META_KEYS:
        return m[1].strip()
    if not s.endswith(":") and len(s) <= 20 and SECTION_START.match(s) and re.fullmatch(
        r"[\w ()'’-]+", s
    ):
        return s
    return None


def parse_chart(path: Path) -> Chart:
    chart = Chart(path)
    text = path.read_text(encoding="utf-8", errors="replace").lstrip("﻿")
    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    cur: Section | None = None
    in_tab = False
    header = True  # OnSong: tagged or untagged lines up to the first blank line

    def section(label=None, repeat=None) -> Section:
        s = Section(label, repeat)
        chart.sections.append(s)
        return s

    for raw in lines:
        line = raw.rstrip().replace("\t", "    ")
        stripped = line.strip()

        if in_tab:
            if re.fullmatch(r"\{\s*(eot|end_of_tab)\s*\}", stripped):
                in_tab = False
            else:
                cur.lines.append({"kind": "tab", "text": line})
            continue

        # OnSong never shows a line starting with "#", and ChordPro drops them
        # too, so they are comments here as well (checked 2026-10-10: the only
        # such lines in the repo are three "# Heading" notes in "River of Life
        # - This is the Day", which the app already hides). This sits after the
        # tab block above on purpose: inside {sot}..{eot} a "#" is tab content.
        # The "# ---" marker is kept as a {"kind": "break"} entry, which
        # build_song passes through untouched and chart.typ draws as nothing,
        # so the printed chart is unchanged; only the slide builder reads it.
        # A break before any lyric of a section has nothing to separate, so
        # it is dropped.
        if stripped.startswith("#"):
            if BREAK_MARK.match(stripped) and cur is not None and cur.lines:
                cur.lines.append({"kind": "break"})
            continue

        d = DIRECTIVE.match(stripped)
        if d:
            name, val = d[1].lower(), (d[2] or "").strip()
            if name in DIRECTIVE_META:
                key = {"t": "title", "st": "artist", "subtitle": "artist",
                       "original_key": "original key"}.get(name, name)
                chart.meta.setdefault(key, val)
            elif name in DIRECTIVE_SECTIONS:
                header = False
                cur = section(val or DIRECTIVE_SECTIONS[name] or None)
            elif name in ("sot", "start_of_tab"):
                header = False
                if cur is None:
                    cur = section()
                in_tab = True
            elif name.startswith("end_of_") or name in ("eoc", "eov", "eob", "eog"):
                cur = None
            elif name in ("c", "comment", "ci", "comment_italic", "cb", "comment_box"):
                header = False
                if cur is None:
                    cur = section()
                cur.lines.append({"kind": "note", "text": val})
            elif name == "chorus":
                section(repeat=val or "Chorus")
                cur = None
            continue  # unknown directives (define, capo, ...) carry no text

        if header:
            if not stripped:
                if chart.meta or chart.untagged:
                    header = False
                continue
            m = TAG.match(stripped)
            if m and "[" not in m[1]:
                name = m[1].strip().lower()
                if name in META_KEYS or (m[2] and not SECTION_START.match(name)):
                    chart.meta.setdefault(name, m[2].strip())
                    continue
            if "[" not in stripped and not is_label(stripped) and len(chart.untagged) < 2:
                chart.untagged.append(stripped)
                continue
            header = False  # first real body line; fall through

        if not stripped:
            if cur is not None and cur.lines:
                cur = None
            continue

        label = is_label(stripped)
        if label:
            cur = section(label)
            continue

        m = TAG.match(stripped)
        if m:
            name = m[1].strip()
            if name.lower() in META_KEYS and "[" not in m[2]:
                chart.meta.setdefault(name.lower(), m[2].strip())
                continue
            if SECTION_START.match(name) and m[2]:
                cur = section(name)
                stripped = line = m[2]

        r = REPEAT.match(stripped)
        what = r and (r[1] or r[2])
        if what and SECTION_START.match(what) and "[" not in stripped:
            section(repeat=what.title())
            cur = None
            continue

        if cur is None:
            cur = section()
        cur.lines.append({"kind": "raw", "text": line})

    # OnSong's own convention for untagged headers: title, then artist.
    if chart.untagged:
        chart.meta.setdefault("title", chart.untagged[0])
        if len(chart.untagged) > 1:
            chart.meta.setdefault("artist", chart.untagged[1])
    # A section label with nothing under it ("CHORUS" between the bridge
    # and the ending, "CHORUS (X2)") is a cue to play that section again.
    for s in chart.sections:
        if s.label and not s.lines and not s.repeat:
            s.repeat, s.label = s.label.title(), None
    chart.sections = [s for s in chart.sections if s.lines or s.repeat]
    return chart


def layout_line(text: str, xpose) -> dict:
    """Turn one raw chart line into what chart.typ draws.

    A lyric line becomes a list of runs: a chord and the words it covers up
    to the next chord. Each word carries its text ("t") and whether a space
    follows ("sp"); "mid" marks a run whose last word the next chord splits
    ("vil[Em]ja"). The template measures the chord against the whole run, so
    room is only added when the run really is too short for its chord, and
    words stay separate boxes so a long line can wrap at any space -- about a
    dozen imported charts have whole sections pasted onto one line.
    """
    parts = BRACKET.split(text)
    lyric = "".join(parts[0::2])
    chords = parts[1::2]
    if not chords:
        return {"kind": "text", "text": text.strip()}

    if CHORD_LINE_REST.match(lyric):
        # Intro/turnaround lines: "| [Ab] / / / | [Db2] / / / |"
        toks = []
        for i, t in enumerate(parts):
            if i % 2:
                toks.append({"c": pretty(xpose(t.strip()))})
            elif t:
                toks.append({"t": t})
        return {"kind": "chords", "toks": toks}

    runs: list[dict] = [{"c": None, "words": []}]
    for i, t in enumerate(parts):
        if i % 2:
            runs.append({"c": pretty(xpose(t.strip())), "words": []})
            continue
        words = runs[-1]["words"]
        for ch in t:
            if ch == " ":
                if words:
                    words[-1]["sp"] = True
                elif runs[-1]["c"] is not None:
                    # "Bless the[C] Lord": the chord sits on the space itself.
                    # Keep the space as an empty word under the chord, or
                    # "the" and "Lord" run together.
                    words.append({"t": "", "sp": True})
            else:
                if not words or words[-1]["sp"]:
                    words.append({"t": "", "sp": False})
                words[-1]["t"] += ch
    runs = [r for r in runs if r["c"] is not None or r["words"]]
    for r, nxt in zip(runs, runs[1:] + [None]):
        if not r["words"]:  # chord over nothing: "[Eb] [Ab]me", "[Ab][(Db)]are"
            r["words"].append({"t": "", "sp": True})
        last = r["words"][-1]
        r["mid"] = bool(not last["sp"] and last["t"] and nxt and nxt["words"]
                        and nxt["words"][0]["t"])
    return {"kind": "lyric", "runs": runs}


def stray_brackets(line: str) -> bool:
    return bool(re.search(r"[\[\]]", BRACKET.sub("", line)))


def build_song(path: Path, target: Key | None) -> dict:
    chart = parse_chart(path)
    meta = chart.meta
    orig = parse_key(meta.get("key")) or parse_key(meta.get("original key"))
    shown = orig
    xp: Transposer | None = None
    if target:
        if not orig:
            warn(f"{path.name}: no Key: to transpose from; printing as written")
        else:
            if target.minor != orig.minor:
                warn(f"{path.name}: chart is in {orig}, set asks for {target}; "
                     f"moving the tonic to {target.root}")
                target = Key(target.root, orig.minor)
            if target != orig:
                xp = Transposer.between(orig, target)
                shown = target

    def xpose(bracket: str) -> str:
        return xp.bracket(bracket) if xp else bracket

    sections = []
    for s in chart.sections:
        lines = []
        for ln in s.lines:
            if ln["kind"] != "raw":
                lines.append(ln)
                continue
            if stray_brackets(ln["text"]):
                warn(f"{path.name}: unbalanced bracket, printed as text: {ln['text'].strip()}")
            lines.append(layout_line(ln["text"], xpose))
        sections.append({"label": s.label, "repeat": s.repeat, "lines": lines})

    key = None
    if shown:
        key = pretty(str(shown))
        if xp:
            key += f"  (orig. {pretty(str(orig))})"
    tempo = meta.get("tempo") or meta.get("bpm") or meta.get("temo")
    if tempo and re.fullmatch(r"\d+(\.\d+)?", tempo):
        tempo += " BPM"
    return {
        "title": meta.get("title") or path.stem,
        "artist": meta.get("artist") or meta.get("author") or meta.get("writer") or None,
        "key": key,
        "tempo": tempo or None,
        "time": meta.get("time") or None,
        "ccli": meta.get("ccli") or None,
        "sections": sections,
    }


# ---------------------------------------------------------------------------
# Set lists -- same matching rules as build-sets.sh


def norm(s: str) -> str:
    return re.sub(r"[\W_]+", " ", s.lower()).strip()


def swedish_dir() -> Path:
    if env := os.environ.get("SWEDISH_DIR"):
        return Path(env)
    return REPO / "worship-swedish" if (REPO / "worship-swedish").is_dir() else REPO.parent / "worship-swedish"


def index_charts() -> list[tuple[Path, str, str]]:
    paths = sorted(p for d in (REPO, swedish_dir()) if d.is_dir()
                   for p in d.glob("*.onsong") if p.stat().st_size > 0)
    out = []
    for p in paths:
        text = p.read_text(encoding="utf-8", errors="replace").splitlines()
        title = text[0] if text else ""
        for ln in text:
            if re.match(r"^[Tt]itle:", ln):
                title = re.sub(r"^[Tt]itle:[ \t]*", "", ln)
                break
        out.append((p, norm(p.stem), norm(title)))
    return out


def resolve(q: str, charts) -> list[Path]:
    hits = [p for p, stem, title in charts if q in (stem, title)]
    if not hits:
        hits = [p for p, stem, title in charts
                if stem.startswith(q + " ") or title.startswith(q + " ")]
    return hits


def parse_set_line(line: str) -> tuple[str, Key | None, str | None]:
    """'Goodness of God | G' -> ('Goodness of God', Key(G), None)."""
    title, bar, key_text = line.partition("|")
    key = parse_key(key_text) if bar else None
    bad = key_text.strip() if bar and not key else None
    return title, key, bad


def build_set(name: str, lines: list[str], charts, out_dir: Path) -> Path | None:
    import typst

    print(f"== {name}")
    songs, skipped = [], 0
    for line in lines:
        if re.match(r"^\s*#", line):
            continue
        title, key, bad = parse_set_line(line)
        q = norm(title)
        if not q:
            continue
        if bad:
            warn(f"'{bad}' is not a key, printing '{title.strip()}' as written")
        hits = resolve(q, charts)
        if len(hits) == 1:
            print(f"   ok       {line.strip()} -> {hits[0].name}")
            songs.append(build_song(hits[0], key))
        elif not hits:
            print(f"   MISSING  {line.strip()}", file=sys.stderr)
            skipped += 1
        else:
            names = " ".join(f'"{p.name}"' for p in hits)
            print(f"   AMBIGUOUS {line.strip()} -> {names}", file=sys.stderr)
            skipped += 1

    if not songs:
        print("   no songs, no PDF")
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    pdf = out_dir / f"{name}.pdf"
    typst.compile(
        str(TEMPLATE),
        output=str(pdf),
        font_paths=[str(FONTS)],
        ignore_system_fonts=True,
        sys_inputs={"data": json.dumps({"set": name, "songs": songs}, ensure_ascii=False)},
    )
    print(f"   {len(songs)} songs -> {pdf}" + (f", {skipped} skipped" if skipped else ""))
    return pdf


def check(charts) -> int:
    """Parse every chart and push every chord through every key, listing
    what didn't parse -- the safety net for the transposer and parser."""
    odd: dict[str, set[str]] = {}
    empty = 0
    for p, _, _ in charts:
        chart = parse_chart(p)
        if not any(s.lines for s in chart.sections):
            empty += 1
            print(f"   no body: {p.name}")
        for s in chart.sections:
            for ln in s.lines:
                if ln["kind"] != "raw":
                    continue
                for b in BRACKET.findall(ln["text"]):
                    for tok in b.split():
                        if not is_chord(tok):
                            odd.setdefault(tok, set()).add(p.name)
                if stray_brackets(ln["text"]):
                    print(f"   unbalanced: {p.name}: {ln['text'].strip()}")
        src = parse_key(chart.meta.get("key")) or parse_key(chart.meta.get("original key"))
        if not src:
            print(f"   no key: {p.name} (Key: {chart.meta.get('key')!r})")
            continue
        for dst in SHARP_NAMES:
            xp = Transposer.between(src, Key(dst, src.minor))
            for s in chart.sections:
                for ln in s.lines:
                    if ln["kind"] == "raw":
                        layout_line(ln["text"], xp.bracket)
    print(f"{len(charts)} charts parsed, {empty} without a body")
    print(f"{len(odd)} bracket tokens that aren't chords (printed as typed, never transposed):")
    for tok, files in sorted(odd.items(), key=lambda kv: -len(kv[1])):
        print(f"   [{tok}]  {len(files)}x  e.g. {sorted(files)[0]}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("sets", nargs="*", type=Path, help="set files (default: sets/*.txt)")
    ap.add_argument("--song", action="append", help='render one set line, e.g. "Oceans | D"')
    ap.add_argument("--check", action="store_true", help="parse every chart and report oddities")
    ap.add_argument("--out", type=Path, default=Path(os.environ.get("OUT_DIR", REPO / "dist")))
    args = ap.parse_args()

    charts = index_charts()
    if not charts:
        print("no .onsong charts found", file=sys.stderr)
        return 1
    if args.check:
        return check(charts)
    if args.song:
        build_set("song", args.song, charts, args.out)
        return 0
    for s in args.sets or sorted((REPO / "sets").glob("*.txt")):
        build_set(s.stem, s.read_text(encoding="utf-8").splitlines(), charts, args.out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
