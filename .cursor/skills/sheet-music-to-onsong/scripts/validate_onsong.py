#!/usr/bin/env python3
"""Validate native OnSong (.onsong) chord charts.

Usage:
    python3 validate_onsong.py [--strict] FILE [FILE ...]

Exit code is 1 if any file has errors (or warnings, with --strict), else 0.
Review flags (`# REVIEW: ...` comment lines) are listed so they can be
reported back to the user.
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ACCIDENTAL = r"(?:#|b|\u266f|\u266d)"
CHORD_SUFFIX_TOKENS = (
    r"(?:Maj|maj|ma|min|mi|m|M|dim|aug|sus|add|alt|no|omit|\d{1,2}|[#b\u266f\u266d+\u00b0\u00f8()\-])*"
)
CHORD_RE = re.compile(
    rf"^[A-H]{ACCIDENTAL}?{CHORD_SUFFIX_TOKENS}(?:/[A-H]{ACCIDENTAL}?)?$"
)
KEY_RE = re.compile(rf"^\[?[A-G]{ACCIDENTAL}?m?\]?$")
TIME_RE = re.compile(r"^\d{1,2}/\d{1,2}$")
TEMPO_RE = re.compile(r"^\d{2,3}(?:\.\d+)?$")
METATAG_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 ()\-]*?)\s*:\s*(.*)$")
HEADER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 '\-]*?):\s*$")
BRACKET_TOKEN_RE = re.compile(r"\[([^\[\]]*)\]")
CHORDPRO_RE = re.compile(r"\{\s*[A-Za-z_]+\s*(?::[^}]*)?\}")
REVIEW_RE = re.compile(r"^#\s*REVIEW\b:?\s*(.*)$")

KNOWN_SECTION_WORDS = {
    "intro", "verse", "pre-chorus", "pre chorus", "prechorus", "chorus",
    "post-chorus", "post chorus", "refrain", "bridge", "interlude",
    "instrumental", "solo", "turnaround", "turn", "tag", "vamp", "breakdown",
    "outro", "ending", "coda", "final chorus", "channel", "hook", "rap",
}
SECTION_LIKE_BRACKET_RE = re.compile(
    r"^(?:" + "|".join(sorted((re.escape(w) for w in KNOWN_SECTION_WORDS), key=len, reverse=True))
    + r")(?:\s*\d+)?$",
    re.IGNORECASE,
)
INLINE_TAGS = {"key", "capo", "transpose", "midi", "scene"}
ILLEGAL_FILENAME_CHARS = re.compile(r'[\\/:*?"<>|]')


@dataclass
class Report:
    path: Path
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    flags: list[str] = field(default_factory=list)

    def error(self, line: int | None, msg: str) -> None:
        self.errors.append(f"line {line}: {msg}" if line else msg)

    def warn(self, line: int | None, msg: str) -> None:
        self.warnings.append(f"line {line}: {msg}" if line else msg)


def clean_filename(title: str) -> str:
    name = ILLEGAL_FILENAME_CHARS.sub("", title)
    name = re.sub(r"\s+", " ", name).strip().rstrip(".")
    return f"{name}.onsong"


def is_chord_only_line(line: str) -> bool:
    tokens = line.split()
    return bool(tokens) and all(CHORD_RE.match(t) or t in {"/", "|", "-"} for t in tokens) and any(
        CHORD_RE.match(t) for t in tokens
    )


def split_sections(lines: list[str]) -> list[list[tuple[int, str]]]:
    sections: list[list[tuple[int, str]]] = []
    current: list[tuple[int, str]] = []
    for number, line in enumerate(lines, start=1):
        if line.strip() == "":
            if current:
                sections.append(current)
                current = []
        else:
            current.append((number, line))
    if current:
        sections.append(current)
    return sections


def check_metadata(section: list[tuple[int, str]], report: Report) -> dict[str, str]:
    meta: dict[str, str] = {}
    positional: list[str] = []
    for number, line in section:
        if line.lstrip().startswith("#"):
            continue
        match = METATAG_RE.match(line)
        if match and not BRACKET_TOKEN_RE.search(match.group(1)):
            name, value = match.group(1).strip().lower(), match.group(2).strip()
            meta[name] = value
            if not value:
                report.warn(number, f"Metadata '{match.group(1).strip()}:' has no value; remove it or fill it from the source")
        elif len(positional) < 2 and not meta:
            positional.append(line.strip())
        else:
            report.warn(number, f"Unrecognized line in metadata section: {line.strip()!r}")
        if BRACKET_TOKEN_RE.search(line) and not (match and match.group(1).strip().lower() == "key"):
            report.warn(number, "Chords found in the metadata section; add a blank line before the song body")

    if "title" not in meta and positional:
        meta["title"] = positional[0]
    if "artist" not in meta and len(positional) > 1:
        meta["artist"] = positional[1]

    if not meta.get("title"):
        report.error(None, "Missing title (Title: or first line)")
    if not meta.get("artist"):
        report.warn(None, "Missing artist (Artist: or second line); list it in the review summary if absent from the source")

    key = meta.get("key")
    if not key:
        report.warn(None, "Missing Key:")
    elif not KEY_RE.match(key):
        report.error(None, f"Key value {key!r} is not a valid key (e.g. G, Bb, F#m, [G])")
    if meta.get("original key") and not KEY_RE.match(meta["original key"]):
        report.error(None, f"Original Key value {meta['original key']!r} is not a valid key")

    time = meta.get("time")
    if not time:
        report.warn(None, "Missing Time: (time signature)")
    elif not TIME_RE.match(time):
        report.error(None, f"Time value {time!r} should look like 4/4 or 6/8")

    tempo = meta.get("tempo")
    if not tempo:
        report.warn(None, "Missing Tempo: (only include it if the source gives a BPM)")
    elif not TEMPO_RE.match(tempo):
        report.error(None, f"Tempo value {tempo!r} must be a number of BPM only")

    return meta


def check_body_line(number: int, line: str, report: Report) -> None:
    stripped = line.strip()

    if line.count("[") != line.count("]"):
        report.error(number, "Unbalanced square brackets")

    for token in BRACKET_TOKEN_RE.findall(line):
        chord = token.strip()
        if SECTION_LIKE_BRACKET_RE.match(chord):
            report.error(number, f"Bracketed section label [{chord}]; use '{chord}:' on its own line")
        elif chord.upper() in {"N.C.", "NC", "N.C"}:
            report.warn(number, "N.C. is not a recognized OnSong chord; prefer a (N.C.) instruction")
        elif not CHORD_RE.match(chord):
            report.error(number, f"Invalid chord [{chord}]; flag unreadable chords with a '# REVIEW:' line instead")

    lyric = BRACKET_TOKEN_RE.sub("", stripped)
    if stripped.startswith("(") and stripped.endswith(")"):
        return
    if (
        re.search(r"[A-Za-z]\s+-\s*[a-z]", lyric)
        or re.search(r"[A-Za-z]-\s+[a-z]", lyric)
        or re.search(r"\b[a-z]+-[a-z]+-[a-z]+\b", lyric)
    ):
        report.warn(number, "Possible un-joined syllable split from sheet music (e.g. 'A - maz - ing')")
    if "_" in lyric:
        report.warn(number, "Underscore found; remove melisma/extender lines from lyrics")
    if is_chord_only_line(stripped) and "[" not in stripped:
        report.warn(number, "Chords-over-lyrics line; convert to inline [bracketed] chords")


def validate(path: Path) -> Report:
    report = Report(path)
    raw = path.read_bytes()
    if raw.startswith(b"\xef\xbb\xbf"):
        report.warn(None, "File starts with a UTF-8 BOM; save as UTF-8 without BOM")
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        report.error(None, f"File is not valid UTF-8: {exc}")
        return report

    if path.suffix != ".onsong":
        report.error(None, "File extension must be .onsong")

    lines = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")

    for number, line in enumerate(lines, start=1):
        review = REVIEW_RE.match(line.strip())
        if review:
            report.flags.append(f"line {number}: {review.group(1).strip()}")
        if line.lstrip().startswith("#"):
            continue
        if "(?)" in line and (number < 2 or not REVIEW_RE.match(lines[number - 2].strip())):
            report.error(number, "'(?)' marker without a '# REVIEW:' comment on the line directly above")
        if CHORDPRO_RE.search(line):
            report.error(number, "ChordPro directive found; use native OnSong metadata/section headers")
        if re.match(r"^\s*flow\s*:", line, re.IGNORECASE):
            report.error(number, "Flow: must never be generated")
        if "\t" in line:
            report.warn(number, "Tab character found; use spaces")

    sections = split_sections(lines)
    if not sections:
        report.error(None, "File is empty")
        return report

    meta = check_metadata(sections[0], report)
    title = meta.get("title")
    if title:
        expected = clean_filename(title)
        if path.name != expected:
            report.warn(None, f"Filename {path.name!r} does not match title; expected {expected!r}")

    body = sections[1:]
    if not body:
        report.error(None, "No song body after the metadata section")

    has_lyrics = False
    has_chords = False
    for section in body:
        content = [(n, l) for n, l in section if not l.lstrip().startswith("#")]
        if not content:
            continue
        first_number, first_line = content[0]
        header = HEADER_RE.match(first_line.strip())
        if header:
            label = header.group(1).strip()
            base = re.sub(r"\s*\d+[a-z]?$", "", label).strip().lower()
            if label.lower() in INLINE_TAGS:
                pass
            elif base not in KNOWN_SECTION_WORDS:
                report.warn(first_number, f"Unusual section label {label!r}")
            content = content[1:]
            if not content:
                report.error(first_number, f"Section {label!r} has a label but no content")
        for number, line in content:
            check_body_line(number, line, report)
            if BRACKET_TOKEN_RE.search(line):
                has_chords = True
            lyric = BRACKET_TOKEN_RE.sub("", line).strip()
            if re.search(r"[A-Za-z]{2,}", lyric) and not (lyric.startswith("(") and lyric.endswith(")")):
                has_lyrics = True

    if body and not has_lyrics:
        report.warn(None, "No lyric lines found")
    if body and not has_chords:
        report.warn(None, "No chords found")

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("files", nargs="+", type=Path)
    parser.add_argument("--strict", action="store_true", help="treat warnings as errors")
    args = parser.parse_args()

    failed = False
    for path in args.files:
        if not path.is_file():
            print(f"{path}: not found", file=sys.stderr)
            failed = True
            continue
        report = validate(path)
        status = "FAIL" if report.errors or (args.strict and report.warnings) else "OK"
        print(f"{status}  {path}  ({len(report.errors)} errors, {len(report.warnings)} warnings, {len(report.flags)} review flags)")
        for msg in report.errors:
            print(f"  ERROR    {msg}")
        for msg in report.warnings:
            print(f"  WARNING  {msg}")
        for msg in report.flags:
            print(f"  REVIEW   {msg}")
        failed = failed or status == "FAIL"
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
