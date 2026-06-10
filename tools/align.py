"""Align transcript segments to slide groups with TF-IDF + monotone DP.

Score for assigning segment s to slide group g:
  cosine(tfidf(seg), tfidf(slide))        lexical match (title tokens boosted)
  + CHAPTER_BONUS if the segment's chapter title matches the slide title
  - PACE_W * |segment position - slide position|   pacing prior

The DP enforces a monotone (chronological) assignment: every segment is
assigned to exactly one group, groups may be empty, group index never
decreases as time advances.
"""
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "align"
OUT.mkdir(parents=True, exist_ok=True)

TITLE_BOOST = 3.0
CHAPTER_BONUS = 0.35
PACE_W = 0.5
SKIP_W = 0.10   # cost per slide group skipped in one transition
WINDOW = 1      # segments on each side pooled into the similarity query
ANCHOR_PEN = 2.0    # penalty for violating a chapter->slide anchor
ANCHOR_SLACK = 45   # seconds of tolerance around a chapter start
ANCHOR_MIN_SIM = 0.6

STOP = set("""a an and are as at be by for from has have if in is it its of on or
that the this to was we will with you your i so what how can our they them then
there going just very really actually kind sort thing things want know see say
said like lets let going go do does did done not no yes here now also one two
""".split())

TOKEN_RE = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")


def tokens(text):
    return [t for t in TOKEN_RE.findall(text.lower()) if len(t) >= 2 and t not in STOP]


def align_lecture_full(i):
    """Same as align_lecture but stores all DP rows for exact backtracking."""
    global dp_rows
    tr = json.loads((ROOT / "data" / "transcripts" / f"l{i}.json").read_text(encoding="utf-8"))
    sl = json.loads((ROOT / "data" / "slides" / f"l{i}.json").read_text(encoding="utf-8"))
    segs, groups = tr["segments"], sl["groups"]
    S, G = len(segs), len(groups)
    n_pages = sl["n_pages"]

    seg_toks = [tokens(s["text"]) for s in segs]
    grp_toks = [tokens(g["text"]) + tokens(g["title"]) * int(TITLE_BOOST - 1) for g in groups]
    docs = seg_toks + grp_toks
    df = Counter()
    for d in docs:
        df.update(set(d))
    N = len(docs)
    idf = {w: math.log(N / (1 + c)) for w, c in df.items()}

    def vec(toks):
        tf = Counter(toks)
        v = {w: (1 + math.log(c)) * idf[w] for w, c in tf.items()}
        nrm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {w: x / nrm for w, x in v.items()}

    # pool each segment with its neighbors: words about a slide spill across
    # adjacent caption segments
    pooled = [sum((seg_toks[j] for j in range(max(0, s - WINDOW),
                                              min(S, s + WINDOW + 1))), [])
              for s in range(S)]
    seg_vecs = [vec(t) for t in pooled]
    grp_vecs = [vec(t) for t in grp_toks]
    grp_pos = [((g["page_first"] + g["page_last"]) / 2 - 1) / max(1, n_pages - 1) for g in groups]
    grp_title_toks = [set(tokens(g["title"])) for g in groups]

    def cos(a, b):
        if len(a) > len(b):
            a, b = b, a
        return sum(x * b.get(w, 0.0) for w, x in a.items())

    # --- chapter -> slide anchors: a chapter whose name closely and
    # unambiguously matches slide titles pins the alignment at its start time
    chapters = [c for c in tr.get("chapters", []) if "t" in c]
    anchors = []  # (time, group_id)
    for ch in chapters:
        ch_t = set(tokens(ch["name"]))
        if not ch_t:
            continue
        cands = []
        for g in range(G):
            tt = grp_title_toks[g]
            if tt and len(ch_t & tt) / len(ch_t | tt) >= ANCHOR_MIN_SIM:
                cands.append(g)
        if cands and (max(cands) - min(cands)) <= 0.25 * G:
            anchors.append((ch["t"], min(cands)))
    anchors.sort()
    monotone = []
    for t, g in anchors:  # keep only group-increasing anchors
        if not monotone or g > monotone[-1][1]:
            monotone.append((t, g))
    anchors = monotone

    score = [[0.0] * G for _ in range(S)]
    for s in range(S):
        sv, spos = seg_vecs[s], s / max(1, S - 1)
        ch_toks = set(tokens(segs[s]["chapter"] or ""))
        t = segs[s]["t"]
        for g in range(G):
            sc = cos(sv, grp_vecs[g]) - PACE_W * abs(spos - grp_pos[g])
            if ch_toks and grp_title_toks[g]:
                ov = len(ch_toks & grp_title_toks[g]) / len(ch_toks | grp_title_toks[g])
                if ov >= 0.5:
                    sc += CHAPTER_BONUS * ov
            for at, ag in anchors:
                if t >= at + ANCHOR_SLACK and g < ag:
                    sc -= ANCHOR_PEN
                elif t <= at - ANCHOR_SLACK and g >= ag:
                    sc -= ANCHOR_PEN
            score[s][g] = sc

    # dp[s][g]: best total score with segment s shown on group g.
    # Transition g' -> g (g' <= g) costs SKIP_W per group skipped in between.
    NEG = float("-inf")
    dp = [[0.0] * G for _ in range(S)]
    dp[0] = [score[0][g] - SKIP_W * g for g in range(G)]  # skipping leading slides
    for s in range(1, S):
        # prefix max of dp[s-1][g'] + SKIP_W * g'  over g' < g
        pref = [NEG] * G
        best = NEG
        for g in range(G):
            pref[g] = best
            best = max(best, dp[s - 1][g] + SKIP_W * g)
        for g in range(G):
            jump = pref[g] - SKIP_W * (g - 1) if g > 0 else NEG
            dp[s][g] = score[s][g] + max(dp[s - 1][g], jump)

    assign = [0] * S
    # skipping trailing slides also costs
    g = max(range(G), key=lambda x: dp[S - 1][x] - SKIP_W * (G - 1 - x))
    assign[S - 1] = g
    for s in range(S - 1, 0, -1):
        stay = dp[s - 1][g]
        if g > 0:
            best_earlier = max(range(g), key=lambda x: dp[s - 1][x] + SKIP_W * x)
            jump = dp[s - 1][best_earlier] - SKIP_W * (g - 1 - best_earlier)
            if jump > stay:
                g = best_earlier
        assign[s - 1] = g
    return assign, segs, groups


def main():
    for i in range(1, 9):
        assign, segs, groups = align_lecture_full(i)
        G = len(groups)
        out_groups = []
        for g_idx, g in enumerate(groups):
            seg_idx = [s for s, a in enumerate(assign) if a == g_idx]
            entry = {
                "id": g_idx,
                "img": g["img"],
                "pages": [g["page_first"], g["page_last"]],
                "title": g["title"],
                "segments": seg_idx,
            }
            if seg_idx:
                entry["t_start"] = segs[seg_idx[0]]["t"]
                entry["ts_start"] = segs[seg_idx[0]]["ts"]
                entry["t_end"] = segs[seg_idx[-1]]["t"]
            out_groups.append(entry)

        empty = sum(1 for g in out_groups if not g["segments"])
        (OUT / f"l{i}.json").write_text(json.dumps({"lecture": i, "groups": out_groups},
                                                   indent=1), encoding="utf-8")
        used = G - empty

        # quality check: transcript chapter start vs aligned slide start for
        # slides whose title closely matches the chapter name
        tr = json.loads((ROOT / "data" / "transcripts" / f"l{i}.json").read_text(encoding="utf-8"))
        diffs = []
        for ch in tr["chapters"]:
            ch_t = set(tokens(ch["name"]))
            if not ch_t or "t" not in ch:
                continue
            cands = [g for g in out_groups if g["segments"] and set(tokens(g["title"]))
                     and len(ch_t & set(tokens(g["title"]))) / len(ch_t | set(tokens(g["title"]))) >= 0.6]
            if cands:
                best = min(cands, key=lambda g: abs(g["t_start"] - ch["t"]))
                diffs.append(abs(best["t_start"] - ch["t"]))
        diffs.sort()
        med = diffs[len(diffs) // 2] if diffs else -1
        print(f"l{i}: {used}/{G} groups got segments ({empty} empty), "
              f"avg {len(segs) / max(1, used):.1f} segs/group, "
              f"chapter-anchor median diff {med}s over {len(diffs)} anchors")


if __name__ == "__main__":
    main()
