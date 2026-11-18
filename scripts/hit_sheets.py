"""Contact sheets of OCR hits for letters a font still lacks, for one look by eye.

Usage: python -I hit_sheets.py <book dir> <ocr dir> <prefix> <out dir> <targets>

<book dir>  source/books/<book>, with pNNNN.jpg pages
<ocr dir>   where ocr_draft.py left <prefix>_pNNNN_v6.xml (ALTO on the whole page)
<targets>   characters to look for, e.g. "KXY"; "0-9" stands for the figures;
            a {..} group names a ligature or accented sort spelt out in the ALTO
            ("ff", "é")

For each target, every ALTO word whose text contains it is cut from the page
image (word box plus a margin of half a line) and pasted into
<out dir>/<prefix>_<name>.png, labelled with page, line and the OCR word, so
misreads (metrical marks, marginal letters, another fount) are told apart at a
glance. Pages with the most hits come first; at most MAX crops per sheet.
<out dir>/<prefix>_summary.md lists the counts and the pages for each target.
"""
import sys, os, re, html, glob, unicodedata
from PIL import Image, ImageDraw, ImageFont

MAX = 120
CELL_W, CELL_H, COLS = 420, 170, 6


def targets(spec):
    out = []
    for m in re.finditer(r"\{([^}]*)\}|0-9|.", spec):
        t = m.group(1) or m.group(0)
        out.append(list("0123456789") if t == "0-9" else [t])
    # figures share one sheet; everything else one sheet per target
    return [("figures" if len(t) > 1 else t[0], t) for t in out]


def words(xml):
    x = open(xml, encoding="utf-8").read()
    for li, m in enumerate(re.finditer(r"<TextLine[^>]*>(.*?)</TextLine>", x, re.S)):
        for s in re.finditer(r"<String([^>]*)>", m.group(1)):
            a = dict(re.findall(r'(\w+)="([^"]*)"', s.group(1)))
            if "CONTENT" in a and "HPOS" in a:
                # ligatures come as ZWJ sequences or presentation forms: spell them out
                w = unicodedata.normalize("NFC", html.unescape(a["CONTENT"])).replace("‍", "")
                w = w.replace("ﬀ", "ff").replace("ﬃ", "ffi").replace("ﬄ", "ffl")
                yield li, w,[int(float(a[k])) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]


def main():
    book, ocr, prefix, out, spec = sys.argv[1:6]
    os.makedirs(out, exist_ok=True)
    try:
        font = ImageFont.truetype("arial.ttf", 15)
    except OSError:
        font = ImageFont.load_default()
    hits = {name: [] for name, _ in targets(spec)}
    for xml in sorted(glob.glob(os.path.join(ocr, f"{prefix}_p*_v6.xml"))):
        page = re.search(r"_(p\d{4})_v6", xml).group(1)
        for li, w, box in words(xml):
            for name, chars in targets(spec):
                if any(c in w for c in chars):
                    hits[name].append((page, li, w, box))
    summary = [f"# OCR hits ({prefix})", ""]
    for name, hs in hits.items():
        pages = {}
        for h in hs:
            pages[h[0]] = pages.get(h[0], 0) + 1
        summary.append(f"- **{name}**: {len(hs)} words on {len(pages)} pages: "
                       + ", ".join(f"{p} ({n})" for p, n in sorted(pages.items())))
        if not hs:
            continue
        hs.sort(key=lambda h: (-pages[h[0]], h[0], h[1]))
        hs = hs[:MAX]
        rows = (len(hs) + COLS - 1) // COLS
        sheet = Image.new("L", (COLS * CELL_W, rows * CELL_H), 255)
        dr = ImageDraw.Draw(sheet)
        cache = {}
        for k, (page, li, w, (x, y, ww, hh)) in enumerate(hs):
            if page not in cache:
                cache = {page: Image.open(os.path.join(book, page + ".jpg")).convert("L")}
            im = cache[page]
            m = hh // 2
            crop = im.crop((max(0, x - m), max(0, y - m), min(im.width, x + ww + m), min(im.height, y + hh + m)))
            crop.thumbnail((CELL_W - 10, CELL_H - 30))
            cx, cy = (k % COLS) * CELL_W, (k // COLS) * CELL_H
            sheet.paste(crop, (cx + 5, cy + 25))
            dr.text((cx + 5, cy + 4), f"{page} L{li + 1}  {w}"[:48], fill=0, font=font)
            dr.rectangle((cx, cy, cx + CELL_W - 1, cy + CELL_H - 1), outline=180)
        safe = name if name.isascii() and name.isalnum() else "u" + "_".join("%04X" % ord(c) for c in name)
        if name.islower() and len(name) == 1:
            safe = "lc_" + safe        # Windows filenames ignore case: k would overwrite K
        sheet.save(os.path.join(out, f"{prefix}_{safe}.png"))
    open(os.path.join(out, f"{prefix}_summary.md"), "w", encoding="utf-8").write("\n".join(summary) + "\n")
    print("\n".join(summary))


if __name__ == "__main__":
    main()
