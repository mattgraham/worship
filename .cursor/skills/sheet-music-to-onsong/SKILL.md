---
name: sheet-music-to-onsong
description: Convert sheet music (PDF, image, photo, or screenshot of a lead sheet, chord chart, hymnal page, or piano/vocal score) into a native OnSong `.onsong` text file with inline bracketed chords, native metadata and section headers, flagged ambiguities, and a validation pass. Use when the user asks to transcribe, convert, import, or add a song from sheet music or a chart image into OnSong or this song library.
---

# Sheet Music to OnSong

Turn a sheet-music source into one UTF-8 `.onsong` file in **native OnSong format** (not ChordPro), then validate it and report a review summary.

Format reference (verified against the OnSong manual):
[file format](https://onsongapp.com/docs/features/formats/onsong/),
[metadata](https://onsongapp.com/docs/features/formats/onsong/metadata/),
[sections](https://onsongapp.com/docs/features/formats/onsong/section/),
[chords and lyrics](https://onsongapp.com/docs/features/formats/onsong/chords/).

## Hard rules

1. **Never invent.** Every lyric word and chord must come from the source. If something is missing, illegible, or cut off, flag it (see [Flagging](#flagging-convention)); never fill it from memory, the internet, or "the usual" version of the song.
2. **Exact lyrics.** Keep the source's wording, spelling, punctuation, capitalization, and archaic forms ("Thou hast", "attendeth"). Only undo sheet-music typesetting (see [Lyrics](#lyrics)).
3. **Native OnSong only.** Use `Name: value` metadata and `Label:` section headers. No ChordPro directives (`{title:}`, `{t:}`, `{key:}`, `{start_of_chorus}`, `{soc}`, `{c:}` ...), and no bracketed labels like `[Verse 1]`.
4. **Never write a `Flow:` line**, even if the source lists an arrangement order.
5. **Keep the original key.** Transpose only if the user asks.
6. **Inline bracketed chords** (`[G]`, `[D/F#]`, `[Cmaj7]`), not chords-over-lyrics lines.

## Workflow

Copy this checklist and work through it:

```
- [ ] 1. Read every page/image; note quality problems (crop, blur, glare, page breaks)
- [ ] 2. Extract metadata
- [ ] 3. Map the song structure (sections, repeats, endings, D.S./D.C./Coda)
- [ ] 4. Transcribe lyrics exactly; split stacked stanzas into separate verses
- [ ] 5. Place chords on the correct syllables (derive from staff only if harmony is clear)
- [ ] 6. Add # REVIEW flags for anything uncertain
- [ ] 7. Write the file with a clean title-based filename
- [ ] 8. Run the validator, fix errors, re-run until it passes
- [ ] 9. Send the review summary to the user
```

### 1. Read the source

- Look at every page. Multi-page PDFs often continue a section across a page break or put later verses at the bottom of the last page.
- If a page is too blurry or cropped to read at all, say so and ask for a better copy rather than transcribing a guess.

### 2. Metadata

Write metadata as the first block of the file, one tag per line, followed by one blank line. OnSong treats everything before the first blank line as metadata.

| Tag | Source | Format |
|---|---|---|
| `Title:` | Song title as printed (drop "Lead Sheet", arranger notes, page numbers) | Text. Always write the explicit `Title:` tag. |
| `Artist:` | Credited artist, or writers ("Words: X / Music: Y") if no artist is credited | Separate several names with `; ` |
| `Key:` | Key signature plus the final/tonic chord (a key signature alone can't distinguish a major key from its relative minor) | `[G]`, `[Bb]`, `[F#m]` (see note) |
| `Original Key:` | Same as the source key; stays the same if you transpose | `G`, `Bb`, `F#m` |
| `Time:` | Time signature at the start | `4/4`, `3/4`, `6/8` |
| `Tempo:` | Metronome mark (e.g. "♩ = 72") | Number only: `72` |
| `Copyright:` | Copyright line, if printed | Text as printed |
| `CCLI:` | CCLI song number, if printed | Number |

- **Key style:** this library writes `Key: [G]` (bracketed so OnSong transposes the key label along with the chords) plus `Original Key: G`. OnSong also accepts plain `Key: G`. Match the existing library.
- If a field is not in the source, **leave the tag out** and list it in the review summary. Don't write empty tags.
- Tempo written only as text ("Moderately", "Slow rock") isn't a BPM. Leave out `Tempo:` and mention the text in the summary.
- Tempo or meter changes partway through go on a separate instruction line where they happen, e.g. `(Tempo 84)` or `(3/4)`.
- Never write `Flow:`.

### 3. Sections

Each section is a label line ending in a colon, then its lines. Separate sections with one blank line.

- Use the source's section names in title case: `Intro:`, `Verse 1:`, `Verse 2:`, `Pre-Chorus:`, `Chorus:`, `Refrain:`, `Bridge:`, `Interlude:`, `Instrumental:`, `Turnaround:`, `Tag:`, `Vamp:`, `Outro:`, `Ending:`, `Coda:`.
- If the source has no labels, use `Verse 1:`, `Chorus:`, and so on only where the structure is obvious (for example, a repeated block of lyrics is the chorus). Otherwise use `Verse 1:`, `Verse 2:` and flag it.
- Number repeated section types (`Verse 1:`, `Verse 2:`, `Bridge 2:`). A single chorus is just `Chorus:`.
- Keep sections in the order the source prints them. **Don't copy out a section the source prints only once.** Write the source's repeat instruction as a musical-instruction line instead.

**Repeats and navigation.** OnSong shows a line that is fully wrapped in parentheses as a musician-only instruction (it is hidden from lyric projection). Use these lines for:

| Source notation | OnSong |
|---|---|
| Repeat bars `𝄆 … 𝄇` around a section | `(x2)` at the end of the last line, or `(Repeat 2x)` on its own line |
| Repeated lyric line | Write the line once, ending in ` (x2)` |
| 1st / 2nd endings | `(1st ending)` and `(2nd ending)` lines before each ending's lines |
| D.S. al Coda / D.C. al Fine / To Coda / Fine | `(D.S. al Coda)` etc. where it appears; label the coda `Coda:` |
| "Repeat Chorus" / "Refrain after each verse" | `(Repeat Chorus)` / `(Sing after each verse)` |
| Fermata, rit., a tempo, key change | `(Hold)`, `(rit.)`, `(a tempo)`, `(Key change to D)` |

**Instrumental sections** (intro, interlude, solo, ending without lyrics): one bar per `|` cell with slash beats, matching the library:

```
Intro:
| [G] / / / | [Em] / / / | [C] / / / | [D] / / / |
```

### 4. Lyrics

- Rejoin the syllables that sheet music splits with hyphens: `A - maz - ing` becomes `Amazing`, `for-ev-er` becomes `forever`. Keep hyphens that are really part of a word (`Joy-Giver`).
- Remove melisma/extender underscores and dashes.
- **Stacked stanzas** (verse 1, 2, 3 printed under the same staff): make each stanza its own `Verse N:` section and repeat the shared chords on the matching syllables of each stanza. This counts as transcription, not invention, because the score applies the same chords to every stanza.
- Echo or response lyrics stay in the line in parentheses, as printed: `It is [C]well (it is [F]well)`.
- Break lines where the source's phrases or systems break, normally one sung phrase per line.

### 5. Chords

- **Spelling:** copy the chord symbol exactly (`Cmaj7` stays `Cmaj7`, `C2` stays `C2`, `Bb/D` stays `Bb/D`). Use `#`/`b` for sharps and flats with no spaces (`[D/F#]`, not `[D / F#]`). Write N.C. as the instruction `(N.C.)`.
- **Placement:** put the chord directly before the first letter of the syllable sung when the chord changes, even in the middle of a word: `at[C]tendeth`, `What[C]ever`, `as[F]surance`.
  - A chord on a pickup or rest before the lyric goes at the start of the line: `[G]When I survey`.
  - Chords on held notes with no new syllable go after the word with spaces between: `soul. [Gsus4]   [G]`.
- **Chords per stanza:** match by syllable count, not character position. Count the syllables in each stanza against the one the chords are printed over.

**Staff notation without chord symbols.** Work out chords only when the harmony is clear in that bar: a complete or nearly complete triad or seventh chord in the accompaniment, or bass plus a clear melody/harmony, with no reasonable second reading.

- Use plain triads or sevenths (`C`, `Am`, `G7`); don't add extensions you can't see.
- Use a slash chord only when the bass note is clearly not the root (`[C/E]`).
- If a bar's harmony is unclear (passing tones, single melody line, competing readings), **don't add a chord**. Put `(?)` in that bar or syllable position and add a `# REVIEW:` line.
- Say in the review summary which sections had chords worked out from notation rather than printed.

**Transposition** (only if requested): move every chord by the same interval, using the target key's sharp/flat spelling. Set `Key:` to the new key and keep `Original Key:` as the source key.

### 6. Flagging convention

Every uncertainty gets **both** of these:

1. A **`# REVIEW:` comment line** directly above the affected line. OnSong shows `#` lines only in the editor, never on stage or in projection. Format:
   ```
   # REVIEW: <section>, <line N | bar N> - <what the source shows> - <what was done>
   ```
   Put metadata problems in the metadata block, and put section-wide problems directly under the section label.
2. A **`(?)` marker** at the exact spot where content is missing or unreadable, so it's visible on stage until someone fixes it. Never put `(?)` inside brackets; `[?]` is not a valid chord.

| Situation | What to write |
|---|---|
| Chord unreadable | Leave the chord out, put `(?)` at that position, add `# REVIEW:` |
| Chord readable but one detail is unclear (e.g. F vs F/A) | Write the most likely reading, add `# REVIEW:` giving the alternatives (no `(?)`) |
| Lyric word or syllable missing/cropped/illegible | `(?)` in its place, add `# REVIEW:`. Never guess the word |
| Staff-only bar with unclear harmony | `(?)` in the bar, add `# REVIEW:` |
| Section label or structure unclear | Best label, `# REVIEW:` under the label |
| Metadata missing | Leave the tag out; mention it in the summary (no flag needed) |

### 7. Filename and encoding

- Filename = title + `.onsong`, e.g. `It Is Well with My Soul.onsong`. Keep the title's capitalization, spaces, apostrophes, and parentheses. Remove `\ / : * ? " < > |`, collapse repeated spaces, and drop trailing dots.
- Save in the repository root alongside the other songs, unless the user says otherwise.
- **Check for an existing file for the same song first** (e.g. `It Is Well.onsong`). Never overwrite one. Tell the user and let them decide.
- UTF-8 without BOM, LF line endings, spaces not tabs, one blank line between sections, ending with a newline.

### 8. Validate

Run the bundled validator and fix every error:

```bash
python3 .cursor/skills/sheet-music-to-onsong/scripts/validate_onsong.py "It Is Well with My Soul.onsong"
```

It checks UTF-8 encoding, title and metadata formats, ChordPro directives, `Flow:`, bracketed section labels, bracket balance, chord spelling (using OnSong's chord rules), empty sections, chords-over-lyrics lines, leftover syllable hyphens and underscores, `(?)` markers without a `# REVIEW:` line, and whether the filename matches the title. It lists every `# REVIEW:` flag. Errors make it exit with code 1. Warnings point to things to check (for example, a missing `Time:` that isn't in the source is fine if the summary mentions it). Use `--strict` to make warnings fail too.

Then go through the [validation checklist](#validation-checklist) by hand. The script can't compare the file against the source.

### 9. Review summary (always report to the user)

```
Review summary - <filename>
Source: <file(s), pages>
Metadata: Title <..> | Artist <..> | Key <..> | Time <..> | Tempo <..> | <other tags>
Not in source (left out): <tags>
Sections: <in order>
Chords derived from staff notation: <sections/bars, or "none">
Flags (<count>):
  1. <section, line/bar> - <issue> - <what was done>
Other notes: <existing-file conflicts, transposition, source-quality problems>
Validator: <OK/FAIL> (<errors> errors, <warnings> warnings)
```

If there are no flags, write `Flags (0): none`.

## Validation checklist

- [ ] File starts with a metadata block: `Title:` present, then `Artist:`, `Key:`, `Original Key:`, plus `Time:`, `Tempo:`, `Copyright:`, `CCLI:` if they're in the source. No empty tags.
- [ ] One blank line after the metadata. No chords in the metadata block.
- [ ] No `Flow:` line. No `{...}` ChordPro directives. No `[Verse]`-style labels.
- [ ] Every section from the source is present, in source order, with a `Label:` header and content.
- [ ] Repeats, endings, D.S./D.C./Coda, and repeat instructions are kept as `( … )` instruction lines or `(xN)`.
- [ ] Lyrics match the source word for word, including punctuation. Syllable hyphens and extenders are removed. Every stanza is present.
- [ ] Every chord in the source is present, in brackets, on the correct syllable, spelled exactly as printed (or transposed consistently if requested).
- [ ] Key matches the source (or the requested transposition, with `Original Key:` kept).
- [ ] Every uncertainty has a `# REVIEW:` line, and every missing item also has `(?)`. Nothing is guessed.
- [ ] The filename is the clean title plus `.onsong`, and no existing song file was overwritten.
- [ ] UTF-8 without BOM, LF line endings, no tabs.
- [ ] The validator exits 0, and the review summary has been sent to the user.

## Worked example

### Input (described source)

A two-page screenshot of a hypothetical public-domain lead sheet:

- Header: **"It Is Well with My Soul"**, "Words: Horatio G. Spafford", "Music: Philip P. Bliss", "Public Domain". Metronome mark ♩ = 72, time signature 4/4, no sharps or flats in the key signature, final chord C, so the key is **C major**.
- **Intro:** 4 bars of piano staff with no chord symbols, inside repeat bars. Bar 1 is a clear C–E–G triad, bar 2 a clear F–A–C triad, bar 4 G–B–D–F (G7). Bar 3 has D–F–A in the right hand over passing tones G–A–B in the left hand, which could be Dm or G7.
- **Verse:** one melody staff with chord symbols C, F, C, G / C, F, G / C, Am, Dm, C / G, G7, C, with **four stanzas stacked** under it, printed with hyphenated syllables ("at - tend - eth"). The last line of stanza 4 is cut off at the screenshot edge after "Lord shall de-".
- **Refrain** marked "sing after each verse", with echo lyrics in parentheses. The chord over the first echo is faint and reads either F or F/A.
- **Ending** box marked "Last time only" with the final line and "rit.".

### Expected output: `It Is Well with My Soul.onsong`

```
Title: It Is Well with My Soul
Artist: Horatio G. Spafford; Philip P. Bliss
Key: [C]
Original Key: C
Time: 4/4
Tempo: 72
Copyright: Public Domain

Intro:
# REVIEW: Intro, bar 3 - staff notation only (no chord symbol); right hand D-F-A over left-hand passing tones G-A-B, could be Dm or G7 - left as (?)
| [C] / / / | [F] / / / | (?) | [G7] / / / | (x2)

Verse 1:
When [C]peace like a [F]river at[C]tendeth my [G]way,
When [C]sorrows like [F]sea billows [G]roll;
What[C]ever my [Am]lot, Thou hast [Dm]taught me to [C]say,
It is [G]well, it is [G7]well with my [C]soul.

Verse 2:
Though [C]Satan should [F]buffet, though [C]trials should [G]come,
Let [C]this blest as[F]surance con[G]trol,
That [C]Christ hath re[Am]garded my [Dm]helpless es[C]tate,
And hath [G]shed His own [G7]blood for my [C]soul.

Verse 3:
My [C]sin, oh, the [F]bliss of this [C]glorious [G]thought!
My [C]sin, not in [F]part but the [G]whole,
Is [C]nailed to the [Am]cross, and I [Dm]bear it no [C]more,
Praise the [G]Lord, praise the [G7]Lord, O my [C]soul!

Verse 4:
And [C]Lord, haste the [F]day when my [C]faith shall be [G]sight,
The [C]clouds be rolled [F]back as a [G]scroll;
# REVIEW: Verse 4, line 3 - final syllable after "de-" is cropped off the screenshot - left as (?)
The [C]trump shall re[Am]sound, and the [Dm]Lord shall de[C](?),
Even [G]so, it is [G7]well with my [C]soul.

Refrain:
(Sing after each verse)
# REVIEW: Refrain, line 1 - chord over the echo "(it is well)" reads F or F/A (bass letter faint) - transcribed as F
It is [C]well (it is [F]well)
With my [C]soul (with my [G]soul),
It is [F]well, it is [C]well [G7]with my [C]soul.

Ending:
(Last time only)
It is [F]well, it is [C]well [G7]with my [C]soul.
(rit.)
```

Things to notice:

- The Refrain is printed once with its instruction, not copied out after every verse, and there's no `Flow:`.
- The stacked stanzas became `Verse 1` to `Verse 4`, each with chords matched by syllable count.
- The cropped word "descend" was not filled in, even though it's familiar.

### Expected review summary

```
Review summary - It Is Well with My Soul.onsong
Source: 2-page screenshot (lead sheet)
Metadata: Title It Is Well with My Soul | Artist Horatio G. Spafford; Philip P. Bliss | Key C | Time 4/4 | Tempo 72 | Copyright Public Domain
Not in source (left out): CCLI
Sections: Intro, Verse 1, Verse 2, Verse 3, Verse 4, Refrain, Ending
Chords derived from staff notation: Intro bars 1, 2, 4 (C, F, G7)
Flags (3):
  1. Intro, bar 3 - harmony unclear (Dm or G7) - left as (?)
  2. Verse 4, line 3 - last syllable after "de-" cropped - left as (?)
  3. Refrain, line 1 - F vs F/A over "(it is well)" - transcribed as F
Other notes: Library already has "It Is Well.onsong" (not overwritten; separate file created)
Validator: OK (0 errors, 0 warnings)
```
