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

API = "https://api.figma.com/v1"


def file_key(link):
    m = re.search(r"figma\.com/(?:file|design|proto|board)/([A-Za-z0-9]+)", link)
    return m.group(1) if m else link.strip()


def words(text):
    return len(re.findall(r"[A-Za-z0-9£$€%&@#'’\-]+(?:[.,][0-9]+)?", text or ""))


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


def walk(node, parents, out, page, section):
    if node.get("visible") is False: return
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
                "font_size": (node.get("style") or {}).get("fontSize"),
                "y": box.get("y", 0), "x": box.get("x", 0),
            })
        return
    for c in node.get("children", []) or []:
        walk(c, parents + [node], out, page, section)


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
    boxes.sort(key=lambda b: (b["page_order"], round(b["y"] / 8), b["x"]))  # Figma's page order, then top to bottom
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
