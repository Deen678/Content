#!/usr/bin/env python3
"""Reads a Figma file and lists every text box the site needs content for,
with its page, section, type (heading / paragraph / button / label) and the
word count of the placeholder text in the design.

Usage:
  python3 scripts/figma_extract.py <figma link or file key> --site <domain> [--page "Home"] [--out sites/<domain>/figma.json]
  python3 scripts/figma_extract.py --from-json saved-figma-response.json --site <domain>   # work from a saved API response

The Figma token is added by this environment's network settings (saved via the
secure credential form), so it is never written in this file or in chat.
"""
import argparse, json, os, re, sys
import requests
sys.path.insert(0, os.path.dirname(__file__))
from textfit import wrap

API = "https://api.figma.com/v1"


def file_key(link):
    m = re.search(r"figma\.com/(?:file|design|proto|board)/([A-Za-z0-9]+)", link)
    return m.group(1) if m else link.strip()


def words(text):
    return len(re.findall(r"[A-Za-z0-9£$€%&@#'’\-]+(?:[.,][0-9]+)?", text or ""))


def accents(node):
    """Words the design sets apart in italic/colour (e.g. 'before and after' in red italics)."""
    ch = node.get("characters") or ""; ov = node.get("characterStyleOverrides") or []; tbl = node.get("styleOverrideTable") or {}
    parts, cur, buf = [], None, ""
    for k, c in enumerate(ch):
        sid = str(ov[k]) if k < len(ov) else "0"
        st = tbl.get(sid, {}); acc = bool(st.get("italic") or "Italic" in str(st.get("fontStyle", "")))
        if acc != cur:
            if cur and buf.strip(): parts.append(buf.strip())
            cur, buf = acc, c
        else: buf += c
    if cur and buf.strip(): parts.append(buf.strip())
    base = (node.get("style") or {}); 
    if not parts and (base.get("italic") or "Italic" in str(base.get("fontStyle", ""))): return []  # whole box italic: not an accent
    return parts


def marked(node):
    """The design's text with its styling marked: ~~struck-through words~~ and *accent words* (italic or a different font, e.g. handwritten inserts)."""
    ch = node.get("characters") or ""; ov = node.get("characterStyleOverrides") or []; tbl = node.get("styleOverrideTable") or {}
    base = node.get("style") or {}
    def kind(k):
        st = tbl.get(str(ov[k]) if k < len(ov) else "0", {})
        if st.get("textDecoration") == "STRIKETHROUGH": return "~~"
        if st.get("italic") or "Italic" in str(st.get("fontStyle", "")) or (st.get("fontFamily") and st.get("fontFamily") != base.get("fontFamily")): return "*"
        return ""
    out, cur, buf = [], None, ""
    def flush():
        if not buf: return
        core = buf.strip(); lead = buf[:len(buf) - len(buf.lstrip())]; trail = buf[len(buf.rstrip()):]
        out.append(lead + (f"{cur}{core}{cur}" if cur and core else core) + trail)
    for k, c in enumerate(ch):
        kd = kind(k)
        if kd != cur: flush(); cur, buf = kd, c
        else: buf += c
    flush()
    return "".join(out)


def role_of(node, parents):
    name = (node.get("name") or "").lower()
    chain = " / ".join(p.get("name", "") for p in parents).lower()
    size = (node.get("style") or {}).get("fontSize") or 0
    text = node.get("characters") or ""
    n = words(text)
    if re.search(r"\b(button|btn|cta)\b", name + " " + chain[-80:]): return "button"
    if re.search(r"\b(nav|menu|header link|breadcrumb|tab|badge|tag|chip|label|eyebrow|caption)\b", name): return "label"
    if re.search(r"sub-?title|subheading|sub-?head|description|body|paragraph|copy|intro|lead", name) and n > 8: return "paragraph"
    if re.search(r"\bh[1-6]\b|heading|\btitle\b|headline", name) or size >= 24: return "heading"
    if n <= 4 and size and size < 18: return "label"
    if n <= 8 and size >= 18: return "heading"
    return "paragraph"


PAGE_ORDER = {}


def walk(node, parents, out, page, section, group=None):
    if node.get("visible") is False: return
    if len(parents) >= 2 and node.get("type") in ("FRAME", "INSTANCE", "COMPONENT", "GROUP") and node.get("type") != "TEXT":
        bb = node.get("absoluteBoundingBox") or {}
        kids_text = [c for c in node.get("children", []) or [] if c.get("type") == "TEXT"]
        if len(kids_text) >= 2: group = (node.get("name"), bb.get("y", 0), bb.get("x", 0))  # a card/step holding a title + text
    t = node.get("type")
    if t in ("FRAME", "SECTION", "COMPONENT", "INSTANCE", "GROUP") and len(parents) == 1: section = node.get("name")  # top-level frame on the page = section / screen
    if t == "TEXT":
        text = (node.get("characters") or "").strip()
        if text:
            box = node.get("absoluteBoundingBox") or {}
            out.append({
                "id": node.get("id"), "page": page, "page_order": PAGE_ORDER.get(page, 0), "section": section or "(no frame)",
                "layer": node.get("name"), "path": " / ".join(p.get("name", "") for p in parents[1:]),
                "role": role_of(node, parents), "placeholder": text, "target_words": words(text),
                "lines": [words(l) for l in text.split("\n")], "accent": accents(node), "marked": marked(node).strip(),
                "group": group[0] if group else None, "group_y": group[1] if group else box.get("y", 0), "group_x": group[2] if group else box.get("x", 0),
                "font_size": (node.get("style") or {}).get("fontSize"), "font_family": (node.get("style") or {}).get("fontFamily"),
                "box_w": box.get("width") if (node.get("style") or {}).get("textAutoResize") != "WIDTH_AND_HEIGHT" else None,
                "y": box.get("y", 0), "x": box.get("x", 0),
            })
        return
    for c in node.get("children", []) or []:
        walk(c, parents + [node], out, page, section, group)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("link", nargs="?"); ap.add_argument("--site", required=True)
    ap.add_argument("--page", help="Only this Figma page (e.g. Home)"); ap.add_argument("--from-json"); ap.add_argument("--out")
    a = ap.parse_args()
    if a.from_json:
        data = json.load(open(a.from_json))
    else:
        if not a.link: sys.exit("Give the Figma link or file key.")
        r = requests.get(f"{API}/files/{file_key(a.link)}", headers={"X-Figma-Token": os.environ.get("FIGMA_TOKEN", "set-by-proxy")}, timeout=120)
        if r.status_code in (401, 403): sys.exit(f"Figma refused access ({r.status_code}). The token is missing, expired, or can't open this file.")
        if r.status_code == 404: sys.exit("Figma file not found. Check the link, and that the token's account can open it.")
        r.raise_for_status(); data = r.json()
    boxes = []
    for i, page in enumerate(data["document"].get("children", [])):
        PAGE_ORDER[page.get("name")] = i
        if a.page and page.get("name", "").strip().lower() != a.page.strip().lower(): continue
        walk(page, [], boxes, page.get("name"), None)
    # Figma's page order, then top to bottom; text inside the same card stays together (title, then its description).
    boxes.sort(key=lambda b: (b["page_order"], round(b["group_y"] / 8), b["group_x"], round(b["y"] / 8), b["x"]))
    # How each heading wraps in its box (same font, size and width), so new text can be held to the same shape.
    for b in boxes:
        b["wrapped"] = None
        if b["role"] == "heading" and b["box_w"] and b["font_family"] and b["font_size"]:
            marked = b["placeholder"]
            for w in b["accent"]: marked = marked.replace(w, f"*{w}*", 1)
            b["wrapped"] = wrap(marked, b["font_family"], b["font_size"], b["box_w"])
    # Text repeated on several frames (menus, footers, buttons) is written once.
    seen = {}
    for b in boxes:
        key = (b["layer"], b["placeholder"])
        b["repeat_of"] = seen.get(key)
        seen.setdefault(key, b["id"])
    out = a.out or f"sites/{a.site}/figma.json"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump({"site": a.site, "figma_file": data.get("name"), "boxes": boxes}, open(out, "w"), indent=1, ensure_ascii=False)
    uniq = [b for b in boxes if not b["repeat_of"]]
    by = {}
    for b in uniq: by.setdefault(b["role"], []).append(b["target_words"])
    print(f'Figma file "{data.get("name")}": {len(boxes)} text boxes, {len(uniq)} to write ({len(boxes) - len(uniq)} repeats written once).')
    for r_, ns in sorted(by.items()): print(f"  {r_:10} {len(ns):3} boxes, {sum(ns)} words")
    print(f"Saved {out}")
    last = None
    for b in uniq:
        if (b["page"], b["section"]) != last: print(f'\n[{b["page"]} / {b["section"]}]'); last = (b["page"], b["section"])
        print(f'  {b["role"]:9} {b["target_words"]:3}w  {b["layer"][:30]:30} {b["placeholder"][:70]!r}')


if __name__ == "__main__":
    main()
