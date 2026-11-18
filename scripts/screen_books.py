"""Screen downloaded book pages for the Cicero founts of the Berner specimen.

Usage: python -I screen_books.py [books_root] [--pages 30] [--out work/screen_ufm]

For each book under books_root (default source/books/ufm/<id>/p####.jpg, Latin books
only: those with survey.json) a sample of pages is measured:
  pitch_px   baseline-to-baseline distance (autocorrelation of the ink profile)
  xh_px      x-height (mode of the heights of x-height-sized components)
  roman, italic  letter-shape match: each x-height letter on the page is scaled to the
             box of each Cicero average (work/screen_tpl_roman, _italic: copies of the
             pilot averages) and the best IoU kept; the page score is the median.
             Controls (Oct 28): the sheet's own Cicero roman block scores 0.716 roman /
             0.485 italic, the italic block 0.479 / 0.726; German blackletter books
             about 0.48 / 0.55. A page above about 0.62 is a candidate.
  ppi_if_cicero  the scan resolution at which the page's line pitch would equal the
             Cicero body. UB Frankfurt scanned the Berner sheets at about 410-420 ppi,
             so a value near that, with a high roman or italic score, marks a candidate.
Writes <out>.csv (one row per page) and <out>_books.json (per-book medians, ranked).
Shape and line pitch only rank candidates: a source is confirmed by skeleton matching
(skel_match.py) and by eye, as in the Caslon project.
"""
import sys, os, json, glob, csv
import numpy as np
import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
LETTERS = list("aenomucrdtis")
CICERO_BODY_IN = 94.8 / 600          # measured body of the Cicero roman (work/cic_roman_result.json)
WORK_XH = 16.0                       # matching is done with the x-height scaled to this many px


def load_templates(avg):
    g = json.load(open(os.path.join(avg, "glyphs.json"), encoding="utf-8"))
    up = g["up"]; T = {}
    for gid, v in g["glyphs"].items():
        if v["ch"] in LETTERS:
            a = cv2.imread(os.path.join(avg, f"avg_{gid}.png"), -1)
            if a is None:
                continue
            a = cv2.resize(a.astype(np.float32) / 65535, None, fx=1 / up, fy=1 / up, interpolation=cv2.INTER_AREA)
            ys, xs = np.where(a > 0.3)
            if len(ys):
                T[v["ch"]] = a[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    xh = float(np.median([T[c].shape[0] for c in "nmuxr" if c in T]))
    return T, xh


def page_measures(gray):
    h, w = gray.shape
    _, bw = cv2.threshold(cv2.GaussianBlur(gray, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    core = bw[int(h * .1):int(h * .9), int(w * .12):int(w * .88)]
    if core.size == 0 or core.mean() < 2 or core.mean() > 80:   # empty crop, blank page or a picture
        return None
    p = core.sum(1).astype(np.float64); p -= p.mean()
    ac = np.correlate(p, p, "full")[len(p) - 1:]; ac /= ac[0] + 1e-9
    peaks = [k for k in range(25, min(len(ac) - 1, 400)) if ac[k] > ac[k - 1] and ac[k] >= ac[k + 1] and ac[k] > 0.1]
    if not peaks:
        return None
    pitch = max(peaks, key=lambda k: ac[k])
    n, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    hs = [s[3] for s in st[1:] if s[4] > 20 and 0.25 * pitch < s[3] < 0.6 * pitch and 0.3 < s[2] / s[3] < 2.2]
    if len(hs) < 60:
        return None
    hist = np.bincount(hs)
    xh = float(np.argmax(np.convolve(hist, np.ones(3), "same")))
    return dict(pitch_px=int(pitch), xh_px=xh, ac=float(ac[pitch]), bw=bw)


def shape_score(bw, xh_page, T, xh_tpl, comps):
    """Median, over the page's x-height letters, of the best IoU with any template
    letter after scaling the page letter to that template's box (shape only).
    Roman letters overlap the roman averages well; blackletter and italic do not."""
    masks = {c: (t > 0.5) for c, t in T.items() if c in "acemnorsuv"}
    best = []
    for (x, y, w, h) in comps:
        crop = bw[y:y + h, x:x + w] > 0
        b = 0.0
        for c, m in masks.items():
            r = cv2.resize(crop.astype(np.uint8), (m.shape[1], m.shape[0]), interpolation=cv2.INTER_NEAREST) > 0
            if abs(w / h - m.shape[1] / m.shape[0]) > 0.35 * m.shape[1] / m.shape[0]:
                continue                                   # proportions too far apart
            u = (r | m).sum()
            if u:
                b = max(b, (r & m).sum() / u)
        best.append(b)
    return float(np.median(best)) if best else 0.0


def letter_comps(bw, xh, limit=300):
    n, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
    c = [tuple(s[:4]) for s in st[1:] if 0.8 * xh <= s[3] <= 1.25 * xh and 0.4 * xh <= s[2] <= 2.0 * xh]
    step = max(1, len(c) // limit)
    return c[::step][:limit]


def main():
    av = sys.argv[1:]
    args = [a for k, a in enumerate(av) if not a.startswith("--") and not (k and av[k - 1] in ("--pages", "--out"))]
    books_root = args[0] if args else os.path.join(ROOT, "source", "books", "ufm")
    npages = int(sys.argv[sys.argv.index("--pages") + 1]) if "--pages" in sys.argv else 30
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else os.path.join(ROOT, "work", "screen_ufm")
    # stable copies of the pilot averages (the pilot folders are rebuilt on every run)
    R, xr = load_templates(os.path.join(ROOT, "work", "screen_tpl_roman"))
    I, xi = load_templates(os.path.join(ROOT, "work", "screen_tpl_italic"))
    rows = []; books = {}
    done = set()
    if os.path.exists(out + ".csv"):
        for r in csv.DictReader(open(out + ".csv", encoding="utf-8")):
            rows.append(r); done.add((r["book"], r["page"]))
    for d in sorted(glob.glob(os.path.join(books_root, "*"))):
        if not os.path.exists(os.path.join(d, "survey.json")):
            continue                                   # skipped (not Latin) or not yet downloaded
        bid = os.path.basename(d)
        pages = sorted(glob.glob(os.path.join(d, "p*.jpg")))
        pick = pages[::max(1, len(pages) // npages)][:npages]
        for fp in pick:
            pg = os.path.basename(fp)
            if (bid, pg) in done:
                continue
            g = cv2.imread(fp, cv2.IMREAD_COLOR)
            # MDZ serves tiny placeholders for some missing scans; they crop to nothing below
            if g is None or min(g.shape[:2]) < 200:
                continue
            m = page_measures(g[:, :, 2])                # red channel: foxing drops out
            if not m:
                continue
            cs = letter_comps(m["bw"], m["xh_px"])
            row = dict(book=bid, page=pg, pitch_px=m["pitch_px"], xh_px=round(m["xh_px"], 1),
                       roman=round(shape_score(m["bw"], m["xh_px"], R, xr, cs), 3),
                       italic=round(shape_score(m["bw"], m["xh_px"], I, xi, cs), 3),
                       ppi_if_cicero=round(m["pitch_px"] / CICERO_BODY_IN))
            rows.append(row)
            print(bid, pg, row["pitch_px"], row["xh_px"], row["roman"], row["italic"], row["ppi_if_cicero"], flush=True)
        with open(out + ".csv", "w", newline="", encoding="utf-8") as f:
            wr = csv.DictWriter(f, fieldnames=["book", "page", "pitch_px", "xh_px", "roman", "italic", "ppi_if_cicero"])
            wr.writeheader(); wr.writerows(rows)
    for r in rows:
        if os.path.exists(os.path.join(books_root, r["book"], "meta.json")):   # removed books drop out
            books.setdefault(r["book"], []).append(r)
    summ = []
    for bid, rs in books.items():
        meta = json.load(open(os.path.join(books_root, bid, "meta.json"), encoding="utf-8"))
        summ.append(dict(book=bid, year=meta.get("year"), title=str(meta.get("label"))[:100], pages=len(rs),
                         roman=float(np.median([float(r["roman"]) for r in rs])),
                         italic=float(np.median([float(r["italic"]) for r in rs])),
                         best_roman_pages=[r["page"] for r in sorted(rs, key=lambda r: -float(r["roman"]))[:5]],
                         ppi_if_cicero=float(np.median([float(r["ppi_if_cicero"]) for r in rs]))))
    summ.sort(key=lambda b: -max(b["roman"], b["italic"]))
    json.dump(summ, open(out + "_books.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(len(rows), "pages,", len(summ), "books ->", out + ".csv")


if __name__ == "__main__":
    main()
