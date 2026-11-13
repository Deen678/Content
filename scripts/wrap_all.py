"""Prints {box id: [lines]} for wrapped headings in content.json, keeping *accent* marks (used by build_doc.js)."""
import json, os, sys
sys.path.insert(0, os.path.dirname(__file__))
from textfit import wrap
c = json.load(open(sys.argv[1])); f = {b["id"]: b for b in json.load(open(os.path.join(os.path.dirname(sys.argv[1]), "figma.json")))["boxes"]}
out = {}
for b in c["boxes"]:
    d = f.get(b["id"]); t = b["text"]
    if not d or not d.get("wrapped") or len(d["wrapped"]) <= len(d.get("lines", [1])): continue
    if b.get("keep"):
        for w in d.get("accent", []): t = t.replace(w, f"*{w}*", 1)
    lines = wrap(t, d["font_family"], d["font_size"], d["box_w"])  # wrap on plain words, then put the marks back
    words = t.replace("\xa0", " ").replace("\n", " ").split(" "); k = 0; res = []
    for l in lines or []:
        n = len(l.split()); res.append(" ".join(words[k:k + n])); k += n
    if lines: out[b["id"]] = res
print(json.dumps(out))
