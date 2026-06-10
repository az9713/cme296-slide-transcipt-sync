import fitz

for i in range(1, 9):
    doc = fitz.open(f"slides/lecture{i}.pdf")
    n = doc.page_count
    # check for consecutive duplicate text (animation build steps)
    texts = [doc[p].get_text().strip() for p in range(n)]
    dupes = sum(1 for a, b in zip(texts, texts[1:]) if a == b and a)
    empty = sum(1 for t in texts if not t)
    t0 = texts[0].replace("\n", " | ")[:70]
    print(f"L{i}: {n} pages, {dupes} consecutive-dupe texts, {empty} empty-text pages | p1: {t0!r}")
