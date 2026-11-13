"""Works out how text wraps inside a Figma text box, using the design's real font
(downloaded once from Google Fonts into fonts/) at the box's width and size.
So a heading the design shows on three lines must also fit on three lines."""
import os, re, requests
from PIL import ImageFont

FONT_DIR = os.path.join(os.path.dirname(__file__), "..", "fonts")


def font_file(family, italic=False):
    os.makedirs(FONT_DIR, exist_ok=True)
    path = os.path.join(FONT_DIR, f"{family.replace(' ', '')}-{'Italic' if italic else 'Regular'}.ttf")
    if os.path.exists(path): return path
    try:
        css = requests.get("https://fonts.googleapis.com/css2", params={"family": f"{family}:ital@{1 if italic else 0}"}, timeout=30).text
        url = re.search(r"url\((https://[^)]+\.ttf)\)", css)
        if not url: return None
        open(path, "wb").write(requests.get(url.group(1), timeout=30).content); return path
    except Exception:
        return None


def wrap(text, family, size, width):
    """Lines as the design would show them. '*accent*' words are measured in italics. None if the font isn't available."""
    reg, ita = font_file(family), font_file(family, True) or font_file(family)
    if not reg: return None
    R, I = ImageFont.truetype(reg, size), ImageFont.truetype(ita, size)
    out = []
    for para in text.replace(" ", "\n").split("\n"):
        tokens, ital = [], False  # (word, italic)
        for seg in re.split(r"(\*)", para):
            if seg == "*": ital = not ital; continue
            for w in seg.replace("\xa0", " ").split(" "):
                if w: tokens.append((w, ital))
        line, lw = [], 0.0
        for w, it in tokens:
            f = I if it else R
            add = f.getlength(w) + (R.getlength(" ") if line else 0)
            if line and lw + add > width + 1:
                out.append(" ".join(x for x, _ in line)); line, lw = [], 0.0; add = f.getlength(w)
            line.append((w, it)); lw += add
        out.append(" ".join(x for x, _ in line))
    return out
