#!/usr/bin/env python3
"""Checks written site content against the Figma word counts and the owner's rules.

Usage: python3 scripts/check_content.py sites/<domain>/content.json

content.json shape (written by the agent):
  {"site": "...", "business_model": "...", "boxes": [
      {"id": "<figma node id>", "text": "the new content"}, ...]}
It reads sites/<domain>/figma.json for each box's target word count and role.

Rules (the owner's):
  - Headings, buttons and labels (and any box of 8 words or fewer): EXACTLY the Figma word count.
  - Paragraphs: within 10% of the Figma word count (rounded to whole words, at least 1 word either way).
  - Nothing copied from the Figma placeholder text (no shared run of 5+ words, no lorem ipsum).
  - Unique: no shared run of 6+ words with any other site's content in sites/*/content.json.
  - No [brackets], TBC, lorem ipsum or empty boxes.
Exit code 1 if anything fails, with a list of what to fix.
"""
import glob, json, math, os, re, sys

LOREM = re.compile(r"\b(lorem|ipsum|dolor sit|consectetur|adipiscing)\b", re.I)


def words(t):
    return re.findall(r"[A-Za-z0-9£$€%&@#'’\-]+(?:[.,][0-9]+)?", t or "")


def grams(t, n):
    w = [x.lower().strip("'’") for x in words(t)]
    return {" ".join(w[i:i + n]) for i in range(len(w) - n + 1)}


def allowed(box):
    t = box["target_words"]
    if box["role"] in ("heading", "button", "label") or t <= 8: return t, t, "exact"
    d = max(1, math.floor(t * 0.10))
    return t - d, t + d, "±10%"


def main():
    path = sys.argv[1]; site_dir = os.path.dirname(path)
    only_page = sys.argv[sys.argv.index("--page") + 1].lower() if "--page" in sys.argv else None
    content = json.load(open(path)); figma = json.load(open(os.path.join(site_dir, "figma.json")))
    boxes = {b["id"]: b for b in figma["boxes"] if not b.get("repeat_of") and (not only_page or b["page"].lower() == only_page)}
    alias = {b["id"]: b["repeat_of"] for b in figma["boxes"] if b.get("repeat_of")}
    written = {alias.get(c["id"], c["id"]): c["text"] for c in content["boxes"]}  # a repeat's id counts as its first copy
    keep = {alias.get(c["id"], c["id"]) for c in content["boxes"] if c.get("keep")}
    exact = {alias.get(c["id"], c["id"]) for c in content["boxes"] if c.get("exact")}  # boxes whose word count is printed on the page  # dev-only text, service names, prices: kept as designed
    others = []
    for f in glob.glob(os.path.join(os.path.dirname(site_dir), "*", "content.json")):
        if os.path.abspath(f) != os.path.abspath(path):
            o = json.load(open(f)); others.append((o.get("site", f), " ".join(c["text"] for c in o["boxes"])))
    problems, ok = [], 0
    for bid, b in boxes.items():
        label = f'{b["page"]} / {b["section"]} / {b["layer"]} ({b["role"]})'
        if bid not in written: problems.append(f"MISSING  {label}: no content written (needs {b['target_words']} words)"); continue
        t = written[bid].strip(); n = len(words(t)); lo, hi, kind = allowed(b)
        if bid in exact: lo = hi = b["target_words"]; kind = "exact, because the page shows this count"
        if bid in keep:
            if t != b["placeholder"].strip(): problems.append(f"CHANGED  {label}: marked 'keep as designed' but the text differs from the design")
            else: ok += 1
            continue
        if not t: problems.append(f"EMPTY    {label}"); continue
        if not (lo <= n <= hi):
            want = f"{lo}" if lo == hi else f"{lo}-{hi}"
            problems.append(f"COUNT    {label}: {n} words, needs {want} ({kind}, Figma has {b['target_words']})"); continue
        if b.get("role") == "heading" and bid not in keep:
            new_lines = [len(words(l)) for l in t.split("\n")]
            if len(b.get("lines", [1])) > 1 and new_lines != b["lines"]:
                problems.append(f"LINES    {label}: lines have {new_lines} words, the design has {b['lines']} (keep the same line split)"); continue
            acc = re.findall(r"\*([^*]+)\*", t)
            if b.get("accent"):
                want = [len(words(x)) for x in b["accent"]]
                if [len(words(x)) for x in acc] != want:
                    problems.append(f"ACCENT   {label}: mark the accent words with *…* ({want} words, like the design's '{' / '.join(b['accent'])}')"); continue
                if LOREM.search(t) or re.search(r"\[[^\]]+\]|\bTBC\b", t): problems.append(f"PLACEHOLDER {label}: {t[:60]!r}"); continue
        if b["target_words"] >= 5 and grams(t, 5) & grams(b["placeholder"], 5): problems.append(f"COPIED   {label}: reuses the Figma placeholder wording"); continue
        ok += 1
    extra = set() if only_page else set(written) - set(boxes)
    for e in extra: problems.append(f"UNKNOWN  box id {e} isn't in figma.json")
    mine = " ".join(v for k, v in written.items() if k not in keep)
    for site, text in others:
        shared = grams(mine, 6) & grams(text, 6)
        if shared: problems.append(f"NOT UNIQUE: shares {len(shared)} six-word phrase(s) with {site}, e.g. {sorted(shared)[:3]}")
    total_t = sum(b["target_words"] for b in boxes.values()); total_w = sum(len(words(written.get(i, ""))) for i in boxes)
    print(f"{ok}/{len(boxes)} boxes pass. Words: {total_w} written vs {total_t} in the Figma design.")
    if problems:
        print("\nFIX THESE:"); [print("  " + p) for p in problems]; sys.exit(1)
    print("All boxes match the word counts and rules, and the content is unique.")


if __name__ == "__main__":
    main()
