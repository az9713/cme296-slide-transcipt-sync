"""Generate site/index.html and site/lectureN.html from alignment data."""
import html
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from meta import LECTURES, COURSE_TITLE

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"
(SITE / "assets").mkdir(parents=True, exist_ok=True)

PARA_SEGS = 4  # captions merged per paragraph


def fmt_t(sec):
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def yt_url(video_id, sec=None):
    url = f"https://www.youtube.com/watch?v={video_id}"
    return f"{url}&t={sec}s" if sec is not None else url


def esc(s):
    return html.escape(s, quote=True)


def paragraphs(seg_objs):
    """Group consecutive segments into paragraphs, breaking at chapter changes."""
    paras = []
    cur = []
    for seg in seg_objs:
        if cur and (len(cur) >= PARA_SEGS or seg["chapter"] != cur[-1]["chapter"]):
            paras.append(cur)
            cur = []
        cur.append(seg)
    if cur:
        paras.append(cur)
    return paras


def build_lecture(i):
    meta = LECTURES[i]
    vid = meta["video_id"]
    align = json.loads((ROOT / "data" / "align" / f"l{i}.json").read_text(encoding="utf-8"))
    tr = json.loads((ROOT / "data" / "transcripts" / f"l{i}.json").read_text(encoding="utf-8"))
    segs = tr["segments"]
    groups = align["groups"]

    pdf_url = f"https://cme296.stanford.edu/slides/spring26-cme296-lecture{i}.pdf"

    rows = []
    running_chapter = None
    last_t = 0
    for g in groups:
        seg_objs = [segs[s] for s in g["segments"]]

        # chapter banner when the slide starts a new transcript chapter
        if seg_objs and seg_objs[0]["chapter"] != running_chapter:
            running_chapter = seg_objs[0]["chapter"]
            if running_chapter:
                rows.append(
                    f'<div class="chapter" id="ch-{esc(running_chapter).replace(" ", "-")}">'
                    f'<span>{esc(running_chapter)}</span>'
                    f'<a class="tlink" href="{yt_url(vid, seg_objs[0]["t"])}" '
                    f'target="_blank" rel="noopener">{fmt_t(seg_objs[0]["t"])}</a></div>'
                )

        pages = (f'p. {g["pages"][0]}' if g["pages"][0] == g["pages"][1]
                 else f'pp. {g["pages"][0]}–{g["pages"][1]}')

        if seg_objs:
            t0 = seg_objs[0]["t"]
            last_t = seg_objs[-1]["t"]
            time_chip = (f'<a class="tlink chip" href="{yt_url(vid, t0)}" target="_blank" '
                         f'rel="noopener" title="Watch on YouTube from {fmt_t(t0)}">'
                         f'&#9658; {fmt_t(t0)}</a>')
            body = []
            for para in paragraphs(seg_objs):
                pt = para[0]["t"]
                text = " ".join(p["text"] for p in para)
                body.append(
                    f'<p><a class="tlink" href="{yt_url(vid, pt)}" target="_blank" '
                    f'rel="noopener">{fmt_t(pt)}</a> {esc(text)}</p>')
            transcript = "\n".join(body)
        else:
            time_chip = (f'<a class="tlink chip dim" href="{yt_url(vid, last_t)}" '
                         f'target="_blank" rel="noopener">&#8776; {fmt_t(last_t)}</a>')
            transcript = '<p class="dim">Shown briefly — discussed together with the adjacent slides.</p>'

        rows.append(f'''<section class="row" id="s{g["id"]}">
<figure>
<a href="slides/l{i}/{g["img"]}" target="_blank">
<img src="slides/l{i}/{g["img"]}" alt="Slide {esc(pages)}: {esc(g["title"])}" loading="lazy" width="1280" height="720">
</a>
<figcaption>{esc(pages)} {time_chip}</figcaption>
</figure>
<div class="transcript">
{transcript}
</div>
</section>''')

    nav_prev = (f'<a href="lecture{i - 1}.html">&larr; Lecture {i - 1}</a>'
                if i > 1 else '<span></span>')
    nav_next = (f'<a href="lecture{i + 1}.html">Lecture {i + 1} &rarr;</a>'
                if i < 8 else '<span></span>')

    chap_links = " &middot; ".join(
        f'<a href="#ch-{esc(c["name"]).replace(" ", "-")}">{esc(c["name"])}</a>'
        for c in tr["chapters"] if "t" in c)

    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Lecture {i}: {esc(meta["title"])} — {esc(COURSE_TITLE)}</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header>
<div class="wrap">
<p class="course"><a href="index.html">{esc(COURSE_TITLE)}</a></p>
<h1>Lecture {i}: {esc(meta["title"])}</h1>
<p class="meta">{esc(meta["date"])} &middot;
<a href="{pdf_url}" target="_blank" rel="noopener">Slides (PDF)</a> &middot;
<a href="{yt_url(vid)}" target="_blank" rel="noopener">Video on YouTube</a></p>
<nav class="lnav">{nav_prev}<a href="index.html">All lectures</a>{nav_next}</nav>
</div>
</header>
<details class="toc wrap"><summary>Chapters</summary><p>{chap_links}</p></details>
<main class="wrap">
{"".join(rows)}
</main>
<footer class="wrap">
<p>Slides &copy; CME 296 instructors (Afshine Amidi &amp; Shervine Amidi), Stanford University.
Transcript from the lecture video. Slide&ndash;transcript alignment is automatic
(content matching) and approximate; timestamps link to the video.</p>
<nav class="lnav">{nav_prev}<a href="index.html">All lectures</a>{nav_next}</nav>
</footer>
</body>
</html>'''
    (SITE / f"lecture{i}.html").write_text(page, encoding="utf-8")
    return len(groups)


def build_index():
    cards = []
    for i, m in LECTURES.items():
        align = json.loads((ROOT / "data" / "align" / f"l{i}.json").read_text(encoding="utf-8"))
        cover = align["groups"][0]["img"]
        cards.append(f'''<a class="card" href="lecture{i}.html">
<img src="slides/l{i}/{cover}" alt="Lecture {i} title slide" loading="lazy">
<div class="card-body">
<h2>Lecture {i}: {esc(m["title"])}</h2>
<p>{esc(m["date"])}</p>
</div>
</a>''')
    page = f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(COURSE_TITLE)} — Lectures</title>
<link rel="stylesheet" href="assets/style.css">
</head>
<body>
<header>
<div class="wrap">
<h1>{esc(COURSE_TITLE)}</h1>
<p class="meta">Spring 2026 &middot; Stanford University &middot; Afshine Amidi &amp; Shervine Amidi</p>
<p class="meta">Each lecture page shows every slide next to the transcript section
where it is discussed, with timestamps linking to the video.</p>
</div>
</header>
<main class="wrap cards">
{"".join(cards)}
</main>
<footer class="wrap">
<p>Built from <a href="https://cme296.stanford.edu/syllabus/" target="_blank" rel="noopener">cme296.stanford.edu</a>.
Slides &copy; the CME 296 instructors.</p>
</footer>
</body>
</html>'''
    (SITE / "index.html").write_text(page, encoding="utf-8")


CSS = '''
:root {
  --ink: #1c2125;
  --muted: #69757d;
  --paper: #f7f6f3;
  --card: #ffffff;
  --accent: #16695c;      /* deck's teal */
  --accent-ink: #0e4a41;
  --rule: #e3e0da;
  --chip: #eaf2f0;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--paper);
  color: var(--ink);
  font: 16px/1.6 Georgia, "Times New Roman", serif;
}
.wrap { max-width: 1200px; margin: 0 auto; padding: 0 24px; }
header {
  background: var(--accent);
  color: #fff;
  padding: 28px 0 22px;
}
header a { color: #d6e8e4; text-decoration: none; }
header a:hover { text-decoration: underline; }
header h1 {
  margin: 4px 0 6px;
  font-family: "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: 1.9rem;
  letter-spacing: -0.01em;
}
.course { margin: 0; font-family: "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: .85rem; text-transform: uppercase; letter-spacing: .12em; opacity: .9; }
.meta { margin: 2px 0; color: #d6e8e4; font-family: "Segoe UI", Helvetica, Arial, sans-serif; font-size: .95rem; }
.meta a { text-decoration: underline; }
.lnav { display: flex; justify-content: space-between; gap: 16px; margin-top: 14px;
  font-family: "Segoe UI", Helvetica, Arial, sans-serif; font-size: .95rem; }
footer .lnav a { color: var(--accent-ink); }
.toc { margin: 18px auto 0; font-family: "Segoe UI", Helvetica, Arial, sans-serif; }
.toc summary { cursor: pointer; color: var(--accent-ink); font-weight: 600; }
.toc a { color: var(--accent-ink); text-decoration: none; white-space: nowrap; }
.toc a:hover { text-decoration: underline; }

.chapter {
  display: flex; align-items: baseline; gap: 14px;
  margin: 44px 0 6px;
  padding-bottom: 6px;
  border-bottom: 2px solid var(--accent);
  font-family: "Segoe UI", Helvetica, Arial, sans-serif;
}
.chapter span { font-size: 1.25rem; font-weight: 700; color: var(--accent-ink); }

.row {
  display: grid;
  grid-template-columns: minmax(0, 58fr) minmax(0, 42fr);
  gap: 22px;
  padding: 18px 0;
  border-bottom: 1px solid var(--rule);
  align-items: start;
}
.row figure { margin: 0; position: sticky; top: 12px; }
.row img {
  width: 100%; height: auto;
  border: 1px solid var(--rule);
  border-radius: 6px;
  background: #fff;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
figcaption {
  margin-top: 6px;
  color: var(--muted);
  font-family: "Segoe UI", Helvetica, Arial, sans-serif;
  font-size: .85rem;
  display: flex; align-items: center; gap: 10px;
}
.transcript p { margin: 0 0 .9em; }
.tlink {
  font-family: Consolas, "SF Mono", Menlo, monospace;
  font-size: .8rem;
  color: var(--accent-ink);
  background: var(--chip);
  border-radius: 4px;
  padding: 1px 6px;
  text-decoration: none;
  white-space: nowrap;
}
.tlink:hover { background: var(--accent); color: #fff; }
.chip { font-size: .85rem; }
.dim { color: var(--muted); font-style: italic; }

.cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(330px, 1fr));
  gap: 22px;
  padding-top: 26px; padding-bottom: 26px;
}
.card {
  background: var(--card);
  border: 1px solid var(--rule);
  border-radius: 8px;
  overflow: hidden;
  text-decoration: none;
  color: var(--ink);
  box-shadow: 0 1px 4px rgba(0,0,0,.05);
  transition: box-shadow .15s ease, transform .15s ease;
}
.card:hover { box-shadow: 0 4px 14px rgba(0,0,0,.12); transform: translateY(-2px); }
.card img { width: 100%; height: auto; display: block; }
.card-body { padding: 12px 16px 14px; font-family: "Segoe UI", Helvetica, Arial, sans-serif; }
.card-body h2 { margin: 0 0 4px; font-size: 1.05rem; color: var(--accent-ink); }
.card-body p { margin: 0; color: var(--muted); font-size: .9rem; }

footer { padding: 26px 24px 40px; color: var(--muted);
  font-family: "Segoe UI", Helvetica, Arial, sans-serif; font-size: .85rem; }
footer a { color: var(--accent-ink); }

@media (max-width: 860px) {
  .row { grid-template-columns: 1fr; }
  .row figure { position: static; }
}
'''


def main():
    (SITE / "assets" / "style.css").write_text(CSS, encoding="utf-8")
    for i in range(1, 9):
        n = build_lecture(i)
        print(f"lecture{i}.html: {n} slide rows")
    build_index()
    print("index.html written")


if __name__ == "__main__":
    main()
