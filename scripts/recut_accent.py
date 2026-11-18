"""Re-cut an accented letter's crops so they include the accent the aligner's box left out.

Usage: python -I -X utf8 recut_accent.py <config.json> <char> [--dry]
  rewrites the crops of <char> in work/<name>_al_p*/ (each instances.json is backed up once as
  instances.json.before_recut_accent) and writes work/review_thin/recut_<hex>.png (before | after)

Nov 12 2026: the roman u-acute averaged to a bare u (check_glyphs.py: "accented letter with no ink
above the x-height"). Colines' acute sits above and to the RIGHT of its vowel, over the next
letter's side, so the box the aligner cuts for the vowel stops short of it. For each crop the
accent is the ink piece that lies wholly above the letter's box, within one box-height of it, with
its centre between the box's left edge and 0.9 box-widths past its right edge, and that does not
touch the letter after it; the nearest such piece is taken. The crop then holds the letter and its
accent, other ink whitened, in the format average.py reads. A crop with no such piece is left as
it is and reported. Nothing is drawn or composed: only the box of real ink changes.
"""
import os, sys, json, shutil
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    C = json.load(open(sys.argv[1], encoding="utf-8")); ch = sys.argv[2]; dry = "--dry" in sys.argv
    nm = C["name"]; rows = []; done = left = 0
    for p in sorted(C["images"], key=int):
        d = os.path.join(ROOT, "work", f"{nm}_al_p{p}"); jp = os.path.join(d, "instances.json")
        if not os.path.exists(jp):
            continue
        J = json.load(open(jp, encoding="utf-8")); I = J["instances"]
        if not any(i["ch"] == ch for i in I):
            continue
        g = cv2.imread(os.path.join(ROOT, C["images"][p]), 0)
        bw = (g < J["otsu"]).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
        paper = int(np.percentile(g, 90)); changed = False
        for it in I:
            if it["ch"] != ch:
                continue
            x0, x1, y0, y1 = it["x0"], it["x1"], it["y0"], it["y1"]; w, h = x1 - x0, y1 - y0
            before = cv2.imread(os.path.join(d, it["file"]), 0)
            body = set(np.unique(lab[y0:y1, x0:x1])) - {0}
            cand = []
            for k in range(1, n):
                kx, ky, kw, kh, ka = st[k]
                # rises above the letter, ends no lower than half-way down it (the acute leans down
                # beside the u's right stem), and is a small mark, not the next letter's ascender
                if k in body or ka < 12 or ky > y0 - 0.15 * h or ky < y0 - h or ky + kh > y0 + 0.5 * h or kh > 0.8 * h:
                    continue
                cx = kx + kw / 2
                if x0 + 0.5 * w <= cx <= x1 + 0.9 * w and kh >= 0.15 * h:
                    cand.append((abs(cx - (x1 + 0.1 * w)) + (y0 - (ky + kh)), k))
            if not cand:
                left += 1; print(f"p{p}/{it['file']}: no accent piece found, left as it is"); continue
            k = min(cand)[1]; kx, ky, kw, kh, ka = st[k]
            # the letter is the aligner's own crop (it already cuts a touching neighbour away at the
            # box edge); the accent piece's ink is added to it on a canvas that holds both
            ox, oy = it["crop"]; bh, bw_ = before.shape
            gx0, gy0 = min(ox, max(0, int(kx) - 6)), min(oy, max(0, int(ky) - 6))
            gx1, gy1 = max(ox + bw_, int(kx + kw) + 6), max(oy + bh, int(ky + kh) + 6)
            new = np.full((gy1 - gy0, gx1 - gx0), paper, np.uint8)
            new[oy - gy0:oy - gy0 + bh, ox - gx0:ox - gx0 + bw_] = before
            m = cv2.dilate((lab[gy0:gy1, gx0:gx1] == k).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
            new[m] = g[gy0:gy1, gx0:gx1][m]
            nx0, nx1 = int(min(x0, kx)), int(max(x1, kx + kw)); ny0, ny1 = int(min(y0, ky)), int(max(y1, ky + kh))
            H = 150
            fit = lambda a: cv2.resize(a, (max(1, int(a.shape[1] * H / a.shape[0])), H), interpolation=cv2.INTER_CUBIC)
            a_, b_ = fit(before), fit(new)
            rows.append(np.hstack([np.pad(a_, ((0, 0), (0, 160 - min(160, a_.shape[1]))), constant_values=255)[:, :160],
                                   np.pad(b_, ((0, 0), (0, 200 - min(200, b_.shape[1]))), constant_values=255)[:, :200]]))
            done += 1
            if not dry:
                cv2.imwrite(os.path.join(d, it["file"]), new)
                it.update(x0=nx0, x1=nx1, y0=ny0, y1=ny1, crop=[int(gx0), int(gy0)], recut="accent added Nov 12 (recut_accent.py)")
                changed = True
        if changed:
            if not os.path.exists(jp + ".before_recut_accent"):
                shutil.copy(jp, jp + ".before_recut_accent")
            json.dump(J, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if rows:
        out = os.path.join(ROOT, "work", "review_thin", "recut_" + "_".join("%04X" % ord(c) for c in ch) + ".png")
        cv2.imwrite(out, np.vstack(rows)); print("sheet (before | after):", out)
    print(f"{ch}: {done} crops re-cut with their accent, {left} left" + (" (dry run)" if dry else ""))


if __name__ == "__main__":
    main()
