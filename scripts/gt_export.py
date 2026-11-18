"""Export aligned specimen lines as Kraken training data (PageXML), keeping ſ, æ/œ and
ligature sorts, so a recognition model can learn to read them.

Usage: python -I gt_export.py <project_root> <out_dir> <config.json> [<config.json> ...]

For each copy of each config (run_size.py format: images/boxes, trans, name), the
line baselines come from the aligned letters (work/<name>_al_p<p>/instances.json):
median baseline and slope per line. Each line's horizontal extent is the ink in
its band, so words the aligner dropped are still inside the line image. Writes
<out_dir>/<name>_p<p>.xml (PageXML with Coords, Baseline and Unicode per line) and
lists them in <out_dir>/files.txt.

Text convention (shared by every model trained on it):
  ſ æ œ Æ Œ are their own letters;
  a ligature sort is ONE code point (LIGCP: Unicode ligatures, else private use);
  Ligature OCR/lig_text.py turns model output into the ZWJ convention;
  swash capitals, tailed finals (m.alt ...) and the second ampersand are written
  as the plain letter; lines with small capitals are skipped.
"""
import sys, os, json, re
import numpy as np
import cv2

ZWJ = "‍"
# One code point per ligature sort for TRAINING (Kraken's compile strips ZWJ, a
# format character, so v1/v2 never saw ligatures). Unicode presentation forms where
# they exist (NFD leaves them alone), else private-use points listed here; the model's
# output is turned back into the ZWJ convention by Ligature OCR/lig_text.py.
LIGCP = {"ſt": "ﬅ", "ff": "ﬀ", "fi": "ﬁ", "fl": "ﬂ", "ffi": "ﬃ", "ffl": "ﬄ",
         "st": "ﬆ", "ct": "", "ſi": "", "ſſ": "", "ſſi": "", "ſh": "",
         "ſl": "", "ſk": "", "ſb": "", "Qu": ""}


def tokens(line):
    return [re.findall(r"\{[^}]+\}|.", w) for w in line.split()]


def to_unicode(tok):
    t = tok.strip("{}")
    if "." in t and len(t) > 1 and t not in (".",):
        base, suf = t.split(".", 1)
        if suf == "sc":
            return None
        return base or t                     # M.sw, m.alt, &.alt -> plain letter
    if len(t) > 1:
        return LIGCP.get(t, ZWJ.join(t))     # ligature sort: its own code point
    return t


def line_text(line):
    words = []
    for w in tokens(line):
        u = [to_unicode(t) for t in w]
        if any(x is None for x in u):
            return None
        words.append("".join(u))
    return " ".join(words)


def main():
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    listing = []
    for cfg in sys.argv[3:]:
        C = json.load(open(cfg, encoding="utf-8"))
        nm = C["name"]
        TR = C["trans"] if isinstance(C["trans"], dict) else {p: C["trans"] for p in C["boxes"]}
        for p in sorted(C["boxes"]):
            img = (C.get("images") or {}).get(p) or f"work/page{p}.png"
            alj = os.path.join(root, "work", f"{nm}_al_p{p}", "instances.json")
            if not os.path.exists(alj):
                continue
            I = json.load(open(alj, encoding="utf-8"))["instances"]
            lines = [l.rstrip("\n") for l in open(os.path.join(root, TR[p]), encoding="utf-8") if l.strip()]
            gray = cv2.imread(os.path.join(root, img), cv2.IMREAD_GRAYSCALE)
            if gray is None:
                continue
            H, W = gray.shape
            _, bw = cv2.threshold(cv2.GaussianBlur(gray, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
            bx0, by0, bx1, by1 = C["boxes"][p]
            hs = [i["y1"] - i["y0"] for i in I if i["ch"] in "xunmo"]
            xh = float(np.median(hs)) if hs else 30.0
            tl = []
            for li, txt in enumerate(lines):
                u = line_text(txt)
                L = [i for i in I if i["line"] == li]
                if not u or len(L) < 3:
                    continue
                bl = np.array([i["baseline"] for i in L]); cx = np.array([(i["x0"] + i["x1"]) / 2 for i in L])
                coef = np.polyfit(cx, bl, 1) if len(set(cx.round())) > 1 else np.array([0.0, float(np.median(bl))])
                top = int(np.polyval(coef, (bx0 + bx1) / 2) - 2.4 * xh); bot = int(np.polyval(coef, (bx0 + bx1) / 2) + 1.1 * xh)
                band = bw[max(0, top):min(H, bot), max(0, bx0):min(W, bx1)]
                cols = np.where(band.sum(0) > 0)[0]
                if not len(cols):
                    continue
                x0 = max(1, max(0, bx0) + int(cols.min()) - 4)
                x1 = min(W - 2, max(0, bx0) + int(cols.max()) + 4)   # Kraken rejects baselines outside the image
                y0a, y0b = np.polyval(coef, x0), np.polyval(coef, x1)
                pts = [(x0, y0a - 2.3 * xh), (x1, y0b - 2.3 * xh), (x1, y0b + 1.0 * xh), (x0, y0a + 1.0 * xh)]
                pts = [(int(max(0, min(W - 1, a))), int(max(0, min(H - 1, b)))) for a, b in pts]
                if not (1 <= y0a <= H - 2 and 1 <= y0b <= H - 2):
                    continue
                tl.append((pts, [(x0, int(y0a)), (x1, int(y0b))], u))
            if not tl:
                continue
            fn = os.path.join(out, f"{nm}_p{p}.xml")
            imgabs = os.path.abspath(os.path.join(root, img)).replace("\\", "/")
            esc = lambda s: s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            body = "".join(
                f'<TextLine id="l{k}"><Coords points="{" ".join(f"{a},{b}" for a, b in pts)}"/>'
                f'<Baseline points="{" ".join(f"{a},{b}" for a, b in bas)}"/>'
                f'<TextEquiv><Unicode>{esc(u)}</Unicode></TextEquiv></TextLine>' for k, (pts, bas, u) in enumerate(tl))
            xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
                   '<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">'
                   f'<Metadata><Creator>gt_export.py</Creator><Created>2026-10-29T00:00:00</Created>'
                   f'<LastChange>2026-10-29T00:00:00</LastChange></Metadata>'
                   f'<Page imageFilename="{imgabs}" imageWidth="{W}" imageHeight="{H}">'
                   f'<TextRegion id="r0"><Coords points="0,0 {W-1},0 {W-1},{H-1} 0,{H-1}"/>{body}</TextRegion>'
                   '</Page></PcGts>\n')
            open(fn, "w", encoding="utf-8").write(xml)
            listing.append(os.path.abspath(fn).replace("\\", "/"))
            print(f"{nm} p{p}: {len(tl)} lines")
    open(os.path.join(out, "files.txt"), "a", encoding="utf-8").write("\n".join(listing) + ("\n" if listing else ""))


if __name__ == "__main__":
    main()
