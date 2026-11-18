"""Average the x-height letters of book pages without OCR, for skel_match.py.

Usage: python -I book_letters.py <out_avg_dir> <template_avg_dir> <page.jpg|png> [...]

Each x-height-sized component on the pages is scaled to the box of every template
letter (a c e m n o r s u) and given the label of the best IoU, if that IoU is at
least 0.6 and beats the runner-up by 0.05. Components of one label are scaled to
their median size and averaged. The result is written like an average.py folder
(glyphs.json + avg_XXXX.png), so skel_match.py and design_match.py read it.

The labels come from the templates' shapes, so the averages lean towards them; the
skeleton test still separates cuts, because each label's average keeps its own cut's
drawing (checked with controls; see the working notes).
"""
import sys, os, json
import numpy as np
import cv2

LETTERS = "acemnorsu"
UP = 3


def templates(avg):
    g = json.load(open(os.path.join(avg, "glyphs.json"), encoding="utf-8"))
    T = {}
    for gid, v in g["glyphs"].items():
        if v["ch"] in LETTERS:
            a = cv2.imread(os.path.join(avg, f"avg_{gid}.png"), -1)
            if a is None:
                continue
            m = a.astype(np.float32) / 65535 > 0.5
            ys, xs = np.where(m)
            if len(ys):
                T[v["ch"]] = m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return T


def page_bw(fp):
    im = cv2.imread(fp, cv2.IMREAD_COLOR)
    g = im[:, :, 2] if im.ndim == 3 else im          # red channel: foxing drops out
    _, bw = cv2.threshold(cv2.GaussianBlur(g, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    return bw


def xheight(bw):
    n, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    hs = [s[3] for s in st[1:] if s[4] > 20 and 8 <= s[3] <= 200 and 0.4 < s[2] / s[3] < 1.6]
    hist = np.bincount(hs) if hs else np.zeros(1)
    return float(np.argmax(np.convolve(hist, np.ones(3), "same"))), st


def main():
    out, tdir, pages = sys.argv[1], sys.argv[2], sys.argv[3:]
    T = templates(tdir)
    groups = {c: [] for c in T}
    for fp in pages:
        bw = page_bw(fp)
        xh, st = xheight(bw)
        for x, y, w, h, a in st[1:]:
            if not (0.85 * xh <= h <= 1.2 * xh and 0.4 * xh <= w <= 1.9 * xh and a > 20):
                continue
            crop = (bw[y:y + h, x:x + w] > 0).astype(np.uint8)
            sc = []
            for c, m in T.items():
                if abs(w / h - m.shape[1] / m.shape[0]) > 0.3 * m.shape[1] / m.shape[0]:
                    continue
                r = cv2.resize(crop, (m.shape[1], m.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
                sc.append(((r & m).sum() / max(1, (r | m).sum()), c))
            sc.sort(reverse=True)
            if sc and sc[0][0] >= 0.6 and (len(sc) == 1 or sc[0][0] - sc[1][0] >= 0.05):
                groups[sc[0][1]].append(crop)
    os.makedirs(out, exist_ok=True)
    glyphs = {}
    for c, crops in groups.items():
        if len(crops) < 3:
            continue
        H = int(np.median([k.shape[0] for k in crops])) * UP
        W = int(np.median([k.shape[1] for k in crops])) * UP
        acc = np.zeros((H, W), np.float32)
        for k in crops:
            acc += cv2.resize(k.astype(np.float32), (W, H), interpolation=cv2.INTER_LINEAR)
        avg = acc / len(crops)
        gid = f"{ord(c):04X}"
        cv2.imwrite(os.path.join(out, f"avg_{gid}.png"), (avg * 65535).astype(np.uint16))
        glyphs[gid] = dict(ch=c, n=len(crops))
    json.dump(dict(glyphs=glyphs, up=UP, base_row=0), open(os.path.join(out, "glyphs.json"), "w", encoding="utf-8"), indent=1)
    print(out, {v["ch"]: v["n"] for v in glyphs.values()})


if __name__ == "__main__":
    main()
