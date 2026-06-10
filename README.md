# CME 296 — Slides × Transcript Sync

A static website that pairs **every slide** of Stanford's *CME 296: Diffusion &
Large Vision Models* (Spring 2026) with the **transcript section where it is
discussed**, with timestamps that link straight to the moment in the lecture
video on YouTube.

The slide decks carry the visuals, the transcripts carry the timing — the core
of this project is automatically **aligning the two**, slide-by-slide, across all
8 lectures (≈14 hours of video, 1,041 slides, ~6,900 transcript segments).

> **Built with Fable 5.** The content of this project — the alignment pipeline,
> the page generation, the styling, and this documentation — was generated using
> Anthropic's **Fable 5** model.

---

## Quick start

Open **`site/index.html`** in a browser.

> **Note:** the rendered slide images (`site/slides/`) and source PDFs
> (`slides/*.pdf`) are **not committed** — they are Stanford course material and
> are regenerable from the public slide URLs. Run the pipeline below to populate
> them, then open the site.

---

## What each page shows

- **Index** — a card grid of all 8 lectures.
- **Lecture page** — one row per slide: the slide image on the left, the
  transcript section that accompanies it on the right, split into short
  timestamped paragraphs. Each timestamp links to `youtube.com/watch?v=…&t=Ns`.
  Transcript chapter banners divide the page, with a collapsible chapter index at
  the top, plus prev/next navigation and links to the original PDF and video.

---

## How it works

Four deterministic Python stages, each writing inspectable JSON:

```
t*.txt ─► tools/parse_transcripts.py ─► data/transcripts/lN.json   (timed segments + chapters)
PDFs   ─► tools/extract_slides.py    ─► site/slides/lN/*.jpg        (slide images)
                                        data/slides/lN.json         (slide groups + text)
both   ─► tools/align.py             ─► data/align/lN.json          (slide → segment match)
        ─► tools/build_site.py       ─► site/*.html + assets/style.css
```

1. **Parse transcripts** — converts the YouTube copy-transcript format into
   timed `{t, ts, text, chapter}` segments, separating real chapter titles from
   stray spoken lines.
2. **Render & de-duplicate slides** — PyMuPDF renders each PDF page to a JPEG and
   extracts its text. Consecutive *build* pages (incremental reveals, where one
   page's text is a prefix of the next) are collapsed into one logical slide
   (**1,041 pages → 847 slides**).
3. **Align** — each transcript segment is scored against each slide with
   **TF-IDF cosine similarity** (slide-title tokens boosted), a **pacing prior**,
   and **chapter anchors** (a chapter whose name matches a slide title pins the
   alignment at its start time). A **monotone dynamic program** then assigns
   segments to slides in chronological order.
4. **Build site** — emits dependency-free HTML + one CSS file.

Alignment quality (chapter-start vs. aligned-slide-start) has a **0-second median
difference** for most lectures. See [`REPORT.md`](REPORT.md) for the full
methodology and per-lecture statistics.

---

## Reproduce from scratch

Requires Python 3.x with `pymupdf`.

```bash
pip install pymupdf

# 1. download the 8 slide decks (or fetch manually into slides/lectureN.pdf)
#    from https://cme296.stanford.edu/slides/spring26-cme296-lectureN.pdf
# 2. place transcripts as t1.txt … t8.txt in the project root, then:

python tools/parse_transcripts.py
python tools/extract_slides.py
python tools/align.py
python tools/build_site.py
```

Alignment weights are tunable constants at the top of `tools/align.py`
(`TITLE_BOOST`, `PACE_W`, `SKIP_W`, `ANCHOR_*`).

---

## Repository layout

```
tools/        pipeline scripts (parse, extract, align, build) + meta.py
t1.txt…t8.txt lecture transcripts (inputs)
data/         intermediate JSON (transcripts, slides, alignment)
site/         generated website (index + 8 lecture pages + CSS)
README.md     this file
REPORT.md     full methodology report
```

---

## Attribution & license

Slide content and lecture transcripts are © the **CME 296** instructors
(Afshine Amidi & Shervine Amidi), Stanford University, and are used here for
educational purposes. This repository's **code** (the alignment pipeline and site
generator) is the original contribution; treat the course material it processes
according to the instructors' terms.

Source course materials: <https://cme296.stanford.edu/syllabus/>
