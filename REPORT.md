# Project Report — CME 296 Slides × Transcript Browser

**Goal:** For each of the 8 lectures of Stanford's *CME 296: Diffusion & Large
Vision Models* (Spring 2026), retrieve the slide PDF and the transcript, then
build a web page that matches each slide to the transcript section where it is
discussed, keyed by timestamps.

**Result:** A static website (`site/`) — one landing page plus 8 lecture pages —
where every slide is rendered next to the exact stretch of transcript that
accompanies it, with each paragraph timestamped and linked to the moment in the
lecture video on YouTube.

---

## 1. Sources and how they were retrieved

| Input | Source | Notes |
|---|---|---|
| Slide decks | `https://cme296.stanford.edu/slides/spring26-cme296-lecture{1..8}.pdf` | Downloaded directly (≈ 64 MB of PDF total) |
| Transcripts | `t1.txt … t8.txt` (provided in the working directory) | YouTube "copy transcript" format |
| Video IDs / titles / dates | Scraped from the syllabus page | Used to build YouTube deep-links |

The syllabus itself exposes **no transcript files and no slide timestamps** —
only a slide PDF and a YouTube link per lecture. That shaped the whole approach:
the transcripts (which you supplied) carry the timing, the PDFs carry the
visuals, and the core technical problem is **aligning the two**.

A small metadata table (`tools/meta.py`) records each lecture's title, date and
YouTube video ID, e.g. Lecture 1 "Diffusion" (Apr 3) → `tr-CUpw--ck`.

---

## 2. The clarifying decisions

Before building, I confirmed three design choices with you:

1. **Transcript source** — you provided the transcript files (`t*.txt`), so no
   caption scraping was needed.
2. **Alignment method** — *content matching*: infer each slide's time range from
   where the lecturer discusses its content, rather than splitting the video
   duration evenly (which would be inaccurate, since some slides take seconds
   and others minutes).
3. **Page layout** — *slide + transcript rows*: each slide image side-by-side
   with its transcript section, timestamps linking into the video.

---

## 3. Pipeline overview

Four deterministic Python stages, each writing intermediate JSON so any stage
can be inspected or re-run independently:

```
t*.txt ─► parse_transcripts.py ─► data/transcripts/lN.json   (timed segments + chapters)
PDFs   ─► extract_slides.py    ─► site/slides/lN/*.jpg        (slide images)
                                  data/slides/lN.json         (slide groups + text)
both   ─► align.py             ─► data/align/lN.json          (slide → segment assignment)
        ─► build_site.py       ─► site/*.html + assets/style.css
```

### Stage 1 — Parsing transcripts (`parse_transcripts.py`)

The `t*.txt` files are pasted YouTube transcripts: a header, then a stream of
chapter headings interleaved with alternating `m:ss` timestamp lines and text
lines. The parser:

- Skips the header up to the `Search in video` marker.
- Reads the stream as `[optional chapter heading] / timestamp / text` triples,
  converting `h:mm:ss` / `m:ss` to absolute seconds.
- **Distinguishes chapter titles from stray transcript lines.** A line sitting
  where a timestamp is expected is treated as a chapter title only if it is
  short, isn't a full sentence, and doesn't begin with a spoken-language opener
  ("So", "And", "Yeah", "Hello", …). This removed ~8–13 false "chapters" per
  lecture (e.g. *"Hello, everyone, and welcome to lecture 2…"* was being read as
  a chapter name). Lines that fail both tests are folded back into the previous
  segment's text.

Output per lecture: an array of `{t, ts, text, chapter}` segments plus a clean
chapter list with start times.

### Stage 2 — Rendering & de-duplicating slides (`extract_slides.py`)

Using **PyMuPDF**, each PDF page is:

- Rendered to a 1280-px-wide JPEG (`site/slides/lN/pNNN.jpg`).
- Text-extracted for the alignment stage.

The key transformation here is **build-page collapsing.** Lecture decks animate:
a single conceptual slide is stored as several PDF pages that reveal content
incrementally. Consecutive pages where one page's normalized text is a *prefix*
of (or identical to) the next are merged into one **slide group**, represented
by its most complete page. This collapsed **1,041 raw pages → 847 logical
slides**, so the site shows one row per idea rather than a dozen near-identical
frames.

### Stage 3 — Alignment (`align.py`) — the heart of the project

The task: assign each transcript segment to a slide group, in time order. The
method combines lexical similarity, a pacing prior, and chapter anchors, resolved
by a monotone dynamic program.

**a. TF-IDF similarity.** Every segment and every slide group is tokenized
(stopwords removed) and turned into a TF-IDF vector over the combined corpus.
Slide-**title** tokens are boosted (×3), and each segment is pooled with its
immediate neighbors, because the words describing a slide spill across adjacent
caption lines. The base score is the cosine similarity between segment and slide.

**b. Pacing prior.** A slide's position in the deck (page midpoint as a fraction)
is compared to the segment's position in the transcript; large mismatches are
penalized. This keeps lexically-ambiguous segments flowing roughly linearly
through the deck.

**c. Chapter anchors.** When a transcript chapter name unambiguously matches a
slide title (high token overlap, and the matching slides are clustered in the
deck), that chapter's start time is used to **pin** the alignment: any segment
more than a 45-second slack away from the anchor is penalized for landing on the
wrong side of it. This is what fixed a real misalignment I found in Lecture 4,
where lexical coincidence had pulled the CLIP "contrastive learning" slides ~3
minutes off; after anchoring they snapped to the 1:18–1:19 discussion.

**d. Monotone DP.** A dynamic program assigns segments to groups so that the
group index never decreases over time (slides advance, never rewind). Skipping
ahead over a slide costs a small penalty, which both discourages wild jumps and
naturally leaves quickly-flipped slides unassigned. Complexity is O(segments ×
slides) per lecture, made linear in the transition step with a prefix-max.

**Quality metric.** As an automatic check, the script measures the gap between
each transcript chapter's start time and the start time of the slide it aligned
to. The **median difference is 0 seconds** for 5 of 8 lectures and 6 s / 18 s
for two others — i.e. chapter boundaries land on the right slide.

### Stage 4 — Site generation (`build_site.py`)

Generates plain, dependency-free HTML + one CSS file:

- **Lecture pages** — one `<section>` per slide group: the slide image (links to
  full size) on the left, the transcript on the right, broken into short
  timestamped paragraphs. Chapter banners from the transcript divide the page; a
  collapsible chapter index sits at the top. Each timestamp is a chip linking to
  `youtube.com/watch?v=ID&t=Ns`. Slides with no assigned segments render a muted
  "shown briefly" note with an approximate time.
- **Index page** — a card grid of all 8 lectures using each deck's title slide as
  the cover.
- **Styling** — the deck's Stanford/ICME teal palette, a serif transcript column
  for readability against a sans-serif UI, sticky slide images so the slide stays
  in view while you read its transcript, and a responsive single-column layout on
  narrow screens.

---

## 4. Verification

- **Visual** — rendered the index and lecture pages in a headless Chrome
  (DevTools MCP) and screenshotted them; confirmed layout, chapter banners,
  sticky slides, and the "shown briefly" fallback all render correctly.
- **Link correctness** — confirmed a timestamp chip's `href` resolves to the
  right second (11:47 → `&t=707s`) and opens in a new tab.
- **Spot-checked alignments** across the start, middle and end of several
  lectures: e.g. Lecture 1's "Important note on conventions" slide ↔ the 11:47
  discussion of those exact three conventions; Lecture 4's CLIP slides ↔ the
  contrastive-learning discussion. The Lecture 4 drift was found *during*
  verification and fixed by adding chapter anchors (Stage 3c), then re-verified.

---

## 5. Results at a glance

| Lecture | Title | Pages → groups | Segments | Chapters | Slides w/ transcript | Length |
|---|---|---|---|---|---|---|
| 1 | Diffusion | 117 → 95 | 853 | 15 | 70 | 1:46:18 |
| 2 | Score matching | 121 → 98 | 870 | 18 | 73 | 1:48:39 |
| 3 | Flow matching | 96 → 80 | 869 | 21 | 61 | 1:47:28 |
| 4 | Latent space and guidance | 148 → 122 | 833 | 18 | 102 | 1:40:54 |
| 5 | Image generation architectures | 171 → 133 | 890 | 18 | 100 | 1:46:17 |
| 6 | Model training | 139 → 110 | 833 | 22 | 80 | 1:40:48 |
| 7 | Evaluation | 137 → 113 | 835 | 18 | 102 | 1:41:03 |
| 8 | Trending topics | 112 → 96 | 909 | 13 | 92 | 1:49:21 |
| **Total** | | **1,041 → 847** | **6,892** | — | **680** | ≈ 14 h |

Plus 1,041 rendered slide JPEGs (≈ 61 MB).

---

## 6. Deliverables

```
site/
  index.html              ← open this
  lecture1.html … lecture8.html
  assets/style.css
  slides/l1 … l8/*.jpg     (rendered slide images)
data/
  transcripts/lN.json      (parsed, timed segments + chapters)
  slides/lN.json           (slide groups + extracted text)
  align/lN.json            (slide → segment assignment, with timestamps)
slides/lectureN.pdf        (downloaded source decks)
tools/
  meta.py, parse_transcripts.py, extract_slides.py, align.py, build_site.py
README.md                  (how to re-run the pipeline)
REPORT.md                  (this file)
```

---

## 7. Limitations & honest caveats

- **Alignment is automatic and approximate.** It rests on word overlap between
  speech and slide text; boundaries can be off by a few seconds, and slides with
  little text (pure diagrams) are the hardest to place.
- **680 of 847 slides** got their own transcript section; the rest were flipped
  through quickly and are shown with an approximate timestamp and a "shown
  briefly" note rather than fabricated text.
- **Timestamps are the transcript's**, which for YouTube auto-captions are
  generally accurate to a second or two.
- The slide–text similarity assumes the lecturer's words echo the slide's words;
  where a slide is discussed in very different language, the pacing prior and
  chapter anchors carry the alignment instead of lexical match.

## 8. Reproducibility

The whole site rebuilds from the two raw inputs (`t*.txt` and the PDFs) by
running the four `tools/` scripts in order (documented in `README.md`). Each
stage is deterministic and writes inspectable JSON, so the alignment can be
tuned (the weights `TITLE_BOOST`, `PACE_W`, `SKIP_W`, `ANCHOR_*` are constants at
the top of `align.py`) and the site regenerated without re-downloading or
re-rendering anything.
