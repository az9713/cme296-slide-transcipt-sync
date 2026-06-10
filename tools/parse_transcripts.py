"""Parse t1.txt..t8.txt (YouTube transcript copy-paste) into JSON segments.

Format: header lines, then "Search in video", then repeating
[optional chapter heading line] / timestamp line / text line.
"""
import json
import re
from pathlib import Path

TS_RE = re.compile(r"^(?:(\d+):)?(\d{1,2}):(\d{2})$")

# Spoken-language openers: a line starting with one of these in "chapter
# position" is a stray transcript line, not a chapter title.
SPOKEN_OPENERS = {
    "so", "and", "but", "yeah", "yes", "no", "ok", "okay", "hello", "now",
    "here", "this", "that", "these", "those", "i", "i'm", "we", "we're",
    "you", "let's", "it", "it's", "do", "don't", "of", "if", "the",
}


def is_chapter_title(line: str) -> bool:
    if len(line) > 60 or line[-1] in ".?!":
        return False
    first = line.split()[0].lower().strip(",")
    return first not in SPOKEN_OPENERS

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "transcripts"
OUT.mkdir(parents=True, exist_ok=True)


def ts_to_sec(m):
    h = int(m.group(1)) if m.group(1) else 0
    return h * 3600 + int(m.group(2)) * 60 + int(m.group(3))


def parse(path: Path):
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    # start after the "Search in video" marker (fall back to first timestamp)
    start = 0
    for i, ln in enumerate(lines):
        if ln == "Search in video":
            start = i + 1
            break

    segments = []
    chapters = []
    chapter = None
    pending_time = None
    pending_ts = None

    for ln in lines[start:]:
        if not ln:
            continue
        m = TS_RE.match(ln)
        if pending_time is None:
            if m:
                pending_time = ts_to_sec(m)
                pending_ts = ln
            elif is_chapter_title(ln):
                chapter = ln  # heading line appears where a timestamp is expected
                chapters.append({"name": chapter, "pending": True})
            elif segments:
                # stray continuation line that lost its timestamp in the paste
                segments[-1]["text"] += " " + ln
        else:
            segments.append({
                "t": pending_time,
                "ts": pending_ts,
                "text": ln,
                "chapter": chapter,
            })
            # resolve chapter start time on its first segment
            for ch in chapters:
                if ch.get("pending"):
                    ch["t"] = pending_time
                    del ch["pending"]
            pending_time = None
            pending_ts = None

    return segments, chapters


def main():
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from meta import LECTURES

    for i in range(1, 9):
        segs, chaps = parse(ROOT / f"t{i}.txt")
        data = {
            "lecture": i,
            "video_id": LECTURES[i]["video_id"],
            "segments": segs,
            "chapters": chaps,
        }
        out = OUT / f"l{i}.json"
        out.write_text(json.dumps(data, indent=1), encoding="utf-8")
        print(f"l{i}: {len(segs)} segments, {len(chaps)} chapters, "
              f"last ts {segs[-1]['ts']}, chapters: {[c['name'] for c in chaps][:12]}")


if __name__ == "__main__":
    main()
