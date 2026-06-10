"""Render each PDF page to JPEG and extract per-page text.

Consecutive 'build' pages (incremental reveals, where the previous page's
text is a prefix of the next page's text, or identical) are collapsed into
one logical slide group; the group's representative image is its final,
most complete page.
"""
import json
import re
from pathlib import Path

import fitz

ROOT = Path(__file__).resolve().parent.parent
IMG_OUT = ROOT / "site" / "slides"
DATA_OUT = ROOT / "data" / "slides"
DATA_OUT.mkdir(parents=True, exist_ok=True)

TARGET_WIDTH = 1280
JPG_QUALITY = 78


def norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def main():
    for i in range(1, 9):
        doc = fitz.open(ROOT / "slides" / f"lecture{i}.pdf")
        out_dir = IMG_OUT / f"l{i}"
        out_dir.mkdir(parents=True, exist_ok=True)

        pages = []
        for p in range(doc.page_count):
            page = doc[p]
            zoom = TARGET_WIDTH / page.rect.width
            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            img_name = f"p{p + 1:03d}.jpg"
            pix.save(out_dir / img_name, jpg_quality=JPG_QUALITY)
            raw = page.get_text()
            lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
            pages.append({
                "page": p + 1,
                "img": img_name,
                "title": lines[0] if lines else "",
                "text": " ".join(lines),
            })

        # group consecutive build pages: prev text is prefix of (or equal to) next
        groups = []
        for pg in pages:
            n = norm(pg["text"])
            if groups:
                prev_n = norm(groups[-1]["pages"][-1]["text"])
                if n.startswith(prev_n) or prev_n.startswith(n):
                    groups[-1]["pages"].append(pg)
                    continue
            groups.append({"pages": [pg]})

        for g_idx, g in enumerate(groups):
            final = max(g["pages"], key=lambda p: len(p["text"]))
            g["id"] = g_idx
            g["img"] = final["img"]
            g["page_first"] = g["pages"][0]["page"]
            g["page_last"] = g["pages"][-1]["page"]
            g["title"] = final["title"]
            g["text"] = final["text"]
            g["pages"] = [p["page"] for p in g["pages"]]

        (DATA_OUT / f"l{i}.json").write_text(
            json.dumps({"lecture": i, "n_pages": doc.page_count, "groups": groups},
                       indent=1), encoding="utf-8")
        print(f"l{i}: {doc.page_count} pages -> {len(groups)} slide groups")


if __name__ == "__main__":
    main()
