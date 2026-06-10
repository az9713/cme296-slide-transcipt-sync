# CME 296 — Slides × Transcript Sync

A static website that pairs **every slide** of Stanford's *CME 296: Diffusion &
Large Vision Models* (Spring 2026) with the **transcript section where it is
discussed**, with timestamps that link straight to the moment in the lecture
video on YouTube.

The slide decks carry the visuals, the transcripts carry the timing — the core
of this project is automatically **aligning the two**, slide-by-slide, across all
8 lectures (≈14 hours of video, 1,041 slides, ~6,900 transcript segments).

**🔗 Live site:** <https://az9713.github.io/cme296-slide-transcript-sync/>

[![Index of all 8 lectures](front.jpg)](https://az9713.github.io/cme296-slide-transcript-sync/)

> **Models used.**
> - The **website** — the slide↔transcript lecture pages, the alignment
>   pipeline, the layout, and the styling — was generated with Anthropic's
>   **Fable 5**.
> - The **reports and documentation** ([`README.md`](README.md) and
>   [`REPORT.md`](REPORT.md)) were authored with **Claude Opus 4.8**.
>
> The lecture **transcripts were provided directly to Fable 5** as input
> (`t1.txt … t8.txt`), so it did **not** need to scrape or fetch transcripts —
> only the slide PDFs were downloaded. The transcript files themselves are not
> committed to this repository.

---

## Quick start

Browse the **[live site](https://az9713.github.io/cme296-slide-transcript-sync/)**,
or clone the repo and open **`site/index.html`** in a browser.

> **Note:** the rendered slide images are committed under `site/slides/` so the
> site works out of the box. The source slide PDFs (`slides/*.pdf`) and the raw
> transcripts (`t*.txt`) are **not** committed — they are regenerable inputs
> (the PDFs from the public slide URLs). Run the pipeline below to rebuild
> everything from scratch.

---

## What each page shows

- **Index** — a card grid of all 8 lectures.
- **Lecture page** — one row per slide: the slide image on the left, the
  transcript section that accompanies it on the right, split into short
  timestamped paragraphs. Each timestamp links to `youtube.com/watch?v=…&t=Ns`.
  Transcript chapter banners divide the page, with a collapsible chapter index at
  the top, plus prev/next navigation and links to the original PDF and video.

![A slide matched to its transcript section, with timestamps](sample.jpg)

*Each slide (left) is aligned to the transcript passage where it is discussed
(right); the timestamps link into the lecture video.*

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
data/         intermediate JSON (transcripts, slides, alignment)
site/         generated website (index + 8 lecture pages + CSS + slide images)
.github/      GitHub Pages deployment workflow
README.md     this file
REPORT.md     full methodology report
```

> `t1.txt … t8.txt` (the raw transcripts) are required inputs to rebuild the
> site but are intentionally not tracked in this repository.

---

## Attribution & license

Slide content and lecture transcripts are © the **CME 296** instructors
(Afshine Amidi & Shervine Amidi), Stanford University, and are used here for
educational purposes. This repository's **code** (the alignment pipeline and site
generator) is the original contribution; treat the course material it processes
according to the instructors' terms.

Source course materials: <https://cme296.stanford.edu/syllabus/>
