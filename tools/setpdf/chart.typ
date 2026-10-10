// Chord-chart layout for set-list PDFs. build.py passes the songs in as
// JSON through sys.inputs; see its header for the data it produces.

#let data = json(bytes(sys.inputs.data))

#let chord-col = rgb("#0a5fc2")
#let head-col = rgb("#a8322d")
#let meta-col = rgb("#666666")
#let base = 12pt

#set document(title: data.set)
#set page(paper: "a4", margin: (x: 16mm, top: 14mm, bottom: 14mm))
// Noto Sans has no ♭/♯; they fall back to DejaVu Sans, whose glyphs are
// small next to Noto's capitals, hence the size bump.
#set text(font: ("Noto Sans", "DejaVu Sans"), lang: "sv")
#show "♭": it => text(font: "DejaVu Sans", size: 1.12em, it)
#show "♯": it => text(font: "DejaVu Sans", size: 1.05em, it)
#set par(leading: 0.55em, spacing: 0.55em)

#let chord(c) = text(fill: chord-col, weight: "bold", size: 0.86em, c)

// A lyric line is a list of runs: a chord plus the words it covers up to
// the next chord. The chord hangs over the run from a zero-width box, and
// only if it's wider than the whole run does the text get pushed right --
// at the end of the run, or, when the next chord sits mid-word
// ("vil[Em]ja"), at the run's last space so the word stays whole, or with
// a dash bridging the split when the run has no space to give. Every word
// is its own box, with an invisible chord row when it has no chord, so a
// long line can wrap at any space and still share one baseline.
#let nbsp = "\u{00A0}"
#let run(r) = context {
  let c = if r.c == none { none } else { chord(r.c) + h(0.45em) }
  let span = r.words.map(w => w.t + if w.sp { nbsp } else { "" }).join()
  let extra = if c == none { 0pt } else { measure(c).width - measure(span).width }
  let n = r.words.len()
  let pad-at = if extra <= 0pt { none }
    else if not r.mid { n - 1 }
    else {
      let spaced = range(n - 1).filter(i => r.words.at(i).sp)
      if spaced.len() > 0 { spaced.last() } else { none }
    }
  for (i, w) in r.words.enumerate() {
    // The chord hangs out of a zero-width box; the inner box gets the
    // chord's own measured width, or a slash chord would wrap after its "/"
    // and print as "G/" over "B".
    let ch = if i == 0 and c != none { c } else { hide(chord("A")) }
    let top = box(width: 0pt, box(width: measure(ch).width, ch))
    // A chord over a space or over nothing ("the[C] Lord", "[Ab][(Db)]are")
    // gets an empty word: zero width, but it keeps the lyric row's height.
    let t = if w.t == "" { box(width: 0pt, hide("A")) } else { w.t }
    if i == pad-at { t = t + h(extra) }
    if i == n - 1 and extra > 0pt and r.mid and pad-at == none {
      t = t + box(width: extra, align(center, text(fill: luma(120), "–")))
    }
    box(stack(dir: ttb, spacing: 0.3em, top, t))
    if w.sp [ ]
  }
}

// hanging-indent: a lyric line too long for its column wraps indented, so
// the continuation reads as part of the line above.
#let lyric-line(runs) = par(hanging-indent: 1.2em, for r in runs { run(r) })

// Intro/turnaround lines: chords inline, bar lines and slashes in grey.
// Runs of spaces are kept (they're how bars get spaced out) except for the
// last space of each run, which stays breakable.
#let spaces(s) = s.replace(regex(" ( +)"), m => "\u{00A0}" * m.captures.at(0).len() + " ")
#let chords-line(toks) = par(hanging-indent: 1.2em, for t in toks {
  if "c" in t { chord(text(size: 1.08em, t.c)) } else { text(fill: meta-col, spaces(t.t)) }
})

#let section(s) = block(breakable: false, below: 0.95em, {
  if s.repeat != none {
    text(fill: head-col, weight: "bold", style: "italic", size: 0.9em, [↻ Repeat #s.repeat])
    return
  }
  if s.label != none {
    block(below: 0.5em, text(fill: head-col, weight: "bold", size: 0.9em, upper(s.label)))
  }
  for l in s.lines {
    if l.kind == "lyric" { lyric-line(l.runs) }
    else if l.kind == "chords" { chords-line(l.toks) }
    else if l.kind == "note" { par(text(fill: meta-col, style: "italic", l.text)) }
    else if l.kind == "tab" { block(spacing: 0.2em, text(font: "DejaVu Sans Mono", size: 0.8em, l.text)) }
    // "break" is the invisible "# ---" slide marker (tools/slides); a chart
    // is printed exactly as if it were not there.
    else if l.kind == "break" { none }
    else { par(l.text) }
  }
})

#let header(song, idx, total) = block(below: 1.1em, {
  grid(columns: (1fr, auto), column-gutter: 1em,
    text(size: 1.9em, weight: "bold", song.title),
    text(fill: meta-col, size: 0.8em, [#data.set · #idx/#total]))
  v(0.2em)
  let bits = ()
  if song.artist != none { bits.push(song.artist) }
  if song.key != none { bits.push([Key *#song.key*]) }
  if song.tempo != none { bits.push(song.tempo) }
  if song.time != none { bits.push(song.time) }
  if song.ccli != none { bits.push([CCLI #song.ccli]) }
  text(fill: meta-col, size: 0.9em, bits.join("  ·  "))
  v(0.3em)
  line(length: 100%, stroke: 0.5pt + luma(200))
})

// Fit each song to one page. One column is preferred while the text stays
// near full size; then two columns, balanced by splitting between sections
// (never inside one); then smaller single-column sizes. The first pass
// also insists that no lyric line wraps, since a wrapped line drags a blank
// chord row along and reads badly -- but only down to 80% text size: Great
// I Am's long bridge lines otherwise landed it at 68%, and small text on a
// music stand is worse than a wrapped line. The second pass takes the first
// layout that fits at all (the imported charts with a whole section on one
// line always end up there). The fit is judged by measuring the
// assembled page, not by summing section heights: block spacing between
// joined sections doesn't add up the way separately measured parts do, and
// summing let a song spill onto a second page. If nothing fits, the song
// runs over at full size rather than becoming unreadably small.
#let song-page(song, idx, total) = layout(size => {
  let gutter = 8mm
  let attempts = (
    (1, 1.0), (1, 0.93), (1, 0.86), (2, 1.0), (2, 0.93), (2, 0.86),
    (2, 0.8), (2, 0.74), (2, 0.68), (2, 0.62), (1, 0.8), (1, 0.74), (1, 0.68),
  )
  let body(cols, scale) = {
    let sz = base * scale
    let wrap(c) = { set text(size: sz); c }
    let hdr = wrap(header(song, idx, total))
    let secs = song.sections.map(s => wrap(section(s)))
    let colw = if cols == 1 { size.width } else { (size.width - gutter) / 2 }
    // natural width: how wide each section is when no line wraps
    let widest = calc.max(0pt, ..secs.map(s => measure(s).width))
    let content = if cols == 1 { hdr; secs.join() } else {
      let hs = secs.map(s => measure(block(width: colw, s)).height)
      let total-h = hs.sum(default: 0pt)
      let best = (k: secs.len(), h: total-h)
      let acc = 0pt
      for k in range(1, secs.len()) {
        acc += hs.at(k - 1)
        let h = calc.max(acc, total-h - acc)
        if h < best.h { best = (k: k, h: h) }
      }
      hdr
      grid(columns: (1fr, 1fr), column-gutter: gutter,
        secs.slice(0, best.k).join(), secs.slice(best.k).join())
    }
    (
      fits: measure(block(width: size.width, content)).height <= size.height,
      wraps: widest > colw,
      content: content,
    )
  }
  // Attempts are laid out one at a time and the loop stops at the first
  // one the first pass accepts; the second pass's pick is remembered on
  // the way. This used to lay out all 13 up front, and Typst keeps every
  // measure() result memoised for the whole compile, so memory grew by
  // ~65 MB per song: a 15-song set took 1.4 GB, and on 2026-09-27 two
  // "every chart in one PDF" test runs (685 songs) got OOM-killed at
  // 10.6 GB and then froze the whole dev container.
  let fallback = none
  for (cols, scale) in attempts {
    let r = body(cols, scale)
    if r.fits and not r.wraps and scale >= 0.8 { return r.content }
    if r.fits and fallback == none { fallback = r.content }
  }
  if fallback != none { return fallback }
  body(1, 1.0).content
})

#for (i, song) in data.songs.enumerate() {
  if i > 0 { pagebreak() }
  song-page(song, i + 1, data.songs.len())
}
