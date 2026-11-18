"""Harvest letters from a book page using Kraken OCR + variant-choosing alignment.

Usage: python -I ocr_harvest.py <page.jpg> <kraken_alto.xml> <template_avg_dir> <out_dir>
                                [--diplomatic] [--fill <avg_dir>,<avg_dir>...]

--diplomatic  the ALTO comes from the ligature model (Ligature OCR, ligocr_v3+), whose
              text already has ſ, æ and one code point per ligature sort: it is used
              as is (ligatures become {ſt} etc.), without trying spellings
--fill        letters missing from the size's own templates (capitals, rare sorts) are
              borrowed from these other sizes' averages, scaled by x-height, only to
              locate them; the harvested impressions are this book's own ink
--style       roman | italic: keep only letters from Kraken words of that style
              (measured slant; Kraken does not mark italics)
--slant       degrees: shear each line upright first (italic templates are upright)
--min-ncc     quality gate: drop letters whose template fit at placement is below this
              (default 0.5)

Kraken (McCATMuS) gives each text line's box and a normalized reading (ſ written s,
æ written "ae", no ligatures). Each line is cut out with room for ascenders and
descenders, scaled so its x-height matches the templates', and aligned with
segment_align.py --variants: every historical spelling of each OCR word is tried
and the one whose templates fit the ink best is kept, so ſ/s, æ and the ligature
sorts are decided by the type itself. Misread words align weakly and are dropped.

Writes <out_dir>/lineNNN/ (segment_align output), <out_dir>/instances.json (all
letters, with page and line), and prints a count per letter.
"""
import sys, os, re, json, html, subprocess, unicodedata
import numpy as np
import cv2

S = os.path.dirname(os.path.abspath(__file__))
PY = [sys.executable, "-I", "-X", "utf8"]


def alto_lines(path):
    x = open(path, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"<TextLine([^>]*)>(.*?)</TextLine>", x, re.S):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        words = [html.unescape(w) for w in re.findall(r'<String[^>]*CONTENT="([^"]*)"', m.group(2))]
        text = unicodedata.normalize("NFC", " ".join(words)).strip()
        if all(k in a for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")) and text:
            bl = [float(v) for v in a.get("BASELINE", "").replace(",", " ").split()]
            by = float(np.median(bl[1::2])) if len(bl) >= 4 else int(float(a["VPOS"])) + int(float(a["HEIGHT"]))
            out.append(dict(x=int(float(a["HPOS"])), y=int(float(a["VPOS"])), w=int(float(a["WIDTH"])),
                            h=int(float(a["HEIGHT"])), base=by, text=text))
    return out


def page_xheight(gray):
    _, bw = cv2.threshold(cv2.GaussianBlur(gray, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    _, _, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    hs = [s[3] for s in st[1:] if s[4] > 20 and 8 <= s[3] <= 200 and 0.4 < s[2] / s[3] < 1.6]
    hist = np.bincount(hs)
    return float(np.argmax(np.convolve(hist, np.ones(3), "same")))


def template_xheight(avg):
    g = json.load(open(os.path.join(avg, "glyphs.json"), encoding="utf-8"))
    hs = []
    for gid, v in g["glyphs"].items():
        if v["ch"] in "nmux":
            a = cv2.imread(os.path.join(avg, f"avg_{gid}.png"), -1)
            if a is not None:
                ys = np.where((a.astype(np.float32) / 65535 > 0.5).any(1))[0]
                if len(ys):
                    hs.append((ys.max() - ys.min() + 1) / g["up"])
    return float(np.median(hs))


LIGTOK = {"ﬅ": "ſt", "ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl",
          "ﬆ": "st", "": "ct", "": "ſi", "": "ſſ", "": "ſſi", "": "ſh",
          "": "ſl", "": "ſk", "": "ſb", "": "Qu"}


def fill_spec(avg, dirs):
    own = {v["ch"] for v in json.load(open(os.path.join(avg, "glyphs.json"), encoding="utf-8"))["glyphs"].values()}
    xh = template_xheight(avg); spec = {}
    for d in dirs:
        k = round(xh / template_xheight(d), 3)
        for v in json.load(open(os.path.join(d, "glyphs.json"), encoding="utf-8"))["glyphs"].values():
            c = v["ch"]
            if c not in own and c not in spec and "," not in c and ":" not in c:
                spec[c] = f"{c}:{d}:{k}"
    return ",".join(spec.values())


def alto_words(path):
    """Every Kraken word box (page px): [x, y, w, h]."""
    x = open(path, encoding="utf-8").read()
    return [[float(v) for v in m.groups()] for m in
            re.finditer(r'<String[^>]*HPOS="([\d.]+)" VPOS="([\d.]+)" WIDTH="([\d.]+)" HEIGHT="([\d.]+)"', x)]


def word_style(gray, b):
    """roman / italic / unsure from the word's measured slant: the shear that makes its
    strokes most vertical (Garamont romans ~0 deg; Granjon italics 13.5-15 deg).
    Kraken does not mark italics, and italic words aligned with roman templates
    otherwise enter the roman harvest."""
    X, Y, W, H = (int(v) for v in b)
    c = gray[max(0, Y):Y + H, max(0, X):X + W]
    if c.size < 100:
        return "unsure"
    _, bw = cv2.threshold(c, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    f = (bw > 0).astype(np.float32); h, w = f.shape; best, A = -1.0, 0.0
    for ang in np.arange(-6, 28, 1.0):
        t = np.tan(np.radians(ang))
        p = cv2.warpAffine(f, np.float32([[1, t, -t * h], [0, 1, 0]]), (w + int(abs(t) * h) + 2, h)).sum(0)
        v = float((p ** 2).sum())
        if v > best:
            best, A = v, float(ang)
    return "italic" if A >= 8 else "roman" if A <= 4 else "unsure"


def main():
    page, alto, avg, out = sys.argv[1:5]
    dipl = "--diplomatic" in sys.argv
    extra = ["--variants"] if not dipl else []
    if "--fill" in sys.argv:
        sp = fill_spec(avg, sys.argv[sys.argv.index("--fill") + 1].split(","))
        if sp:
            extra.append("--borrow=" + sp)
    os.makedirs(out, exist_ok=True)
    im = cv2.imread(page, cv2.IMREAD_COLOR)
    gray = im[:, :, 2]                                   # red channel: foxing drops out
    k = template_xheight(avg) / page_xheight(gray)       # page px -> template px
    allinst, counts = [], {}
    global MIN_NCC, STYLE, WORDS, WSTYLE, SLANT
    SLANT = float(sys.argv[sys.argv.index("--slant") + 1]) if "--slant" in sys.argv else 0.0
    MIN_NCC = float(sys.argv[sys.argv.index("--min-ncc") + 1]) if "--min-ncc" in sys.argv else 0.5
    # band depth below the baseline, in line pitches. Default 0.28 as before; Garamont uses 0.45
    # (the g's lower loop was cut at 0.28 in solid-set books, Nov 13 2026)
    global BELOW
    BELOW = float(sys.argv[sys.argv.index("--below") + 1]) if "--below" in sys.argv else 0.28
    STYLE = sys.argv[sys.argv.index("--style") + 1] if "--style" in sys.argv else None
    WORDS = alto_words(alto); WSTYLE = {}
    dropped = {"weak": 0, "no word": 0, "other style": 0}
    LL = alto_lines(alto)
    gaps = np.diff(sorted(L["base"] for L in LL))
    pitch = float(np.median([g for g in gaps if g > 10])) if len(gaps) else 80.0
    for li, L in enumerate(LL):
        if len(L["text"].split()) < 2:
            continue                                     # signatures, catchwords, page numbers
        # a tight band around Kraken's baseline: Kraken's line boxes plus padding took in
        # the neighbouring lines, and the aligner then locked onto the wrong one
        y0 = max(0, int(L["base"] - 0.75 * pitch)); y1 = min(gray.shape[0], int(L["base"] + BELOW * pitch))
        x0, x1 = max(0, L["x"] - 10), min(gray.shape[1], L["x"] + L["w"] + 10)
        crop = cv2.resize(gray[y0:y1, x0:x1], None, fx=k, fy=k, interpolation=cv2.INTER_CUBIC)
        if SLANT:
            # italic templates were made from blocks sheared upright (prep_block.py), so
            # the book line is sheared the same way; letter x then maps back via shear
            hh, ww = crop.shape; tt = np.tan(np.radians(SLANT)); pap = int(np.percentile(crop, 80))
            crop = cv2.warpAffine(crop, np.float32([[1, tt, 0], [0, 1, 0]]), (ww + int(tt * hh) + 2, hh),
                                  flags=cv2.INTER_CUBIC, borderValue=pap)
        d = os.path.join(out, f"line{li:03d}")
        os.makedirs(d, exist_ok=True)
        cv2.imwrite(os.path.join(d, "line.png"), crop)
        # the ligature model's one-code-point sorts become the aligner's {ſt}-style names
        txt = "".join("{" + LIGTOK[c] + "}" if c in LIGTOK else c for c in L["text"]) if dipl else L["text"]
        open(os.path.join(d, "line.txt"), "w", encoding="utf-8").write(txt + "\n")
        r = subprocess.run(PY + [os.path.join(S, "segment_align.py"), os.path.join(d, "line.png"), "0", "0",
                                 str(crop.shape[1]), str(crop.shape[0]), os.path.join(d, "line.txt"), avg, d] + extra,
                           capture_output=True, text=True, encoding="utf-8")
        ip = os.path.join(d, "instances.json")
        if r.returncode or not os.path.exists(ip):
            print(f"line {li}: alignment failed: {L['text'][:50]}")
            continue
        for i in json.load(open(ip, encoding="utf-8"))["instances"]:
            if i.get("align", 1.0) < MIN_NCC:
                dropped["weak"] += 1; continue           # quality gate: template fit at placement
            if STYLE:
                # the Kraken word this letter lies in, and that word's measured slant
                cyi = (i["y0"] + i["y1"]) / 2
                cxi = (i["x0"] + i["x1"]) / 2 - (np.tan(np.radians(SLANT)) * cyi if SLANT else 0)
                px, py = x0 + cxi / k, y0 + cyi / k
                wb = next((b for b in WORDS if b[0] - 3 <= px <= b[0] + b[2] + 3 and b[1] - 3 <= py <= b[1] + b[3] + 3), None)
                if wb is None:
                    dropped["no word"] += 1; continue
                key = tuple(wb)
                if key not in WSTYLE:
                    WSTYLE[key] = word_style(gray, wb)
                if WSTYLE[key] != STYLE:
                    dropped["other style"] += 1; continue
            i.update(page=os.path.basename(page), ocr_line=li, dir=os.path.basename(d), scale=k)
            allinst.append(i)
            counts[i["ch"]] = counts.get(i["ch"], 0) + 1
    json.dump(dict(instances=allinst, scale=k), open(os.path.join(out, "instances.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"scale {k:.3f}; {len(allinst)} letters:", " ".join(f"{c}:{n}" for c, n in sorted(counts.items())))
    print("dropped:", dict(dropped))


if __name__ == "__main__":
    main()
