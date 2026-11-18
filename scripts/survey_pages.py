"""Rank a book's pages by how much of them is set in one fount, judged by line pitch.

Usage: python -I survey_pages.py <page_dir> <pitch_px> <out.json> [contact.png]

Baselines are found as the sharp fall in the row ink profile below each x-height band
(as in the probe). A gap between consecutive baselines within 6% of <pitch_px> counts
as a line of the wanted fount; any other gap (commentary in a smaller fount, headings,
figures) counts against the page. Writes per-page counts and the share of wanted
lines; the contact sheet shows the 24 best pages.
"""
import sys, os, glob, json
import numpy as np
import cv2
from scipy.signal import find_peaks


def baselines(gray):
    h, w = gray.shape
    band = gray[:, int(w * 0.15):int(w * 0.85)].astype(np.float32)
    p = (255 - band).mean(1)
    d = np.convolve(p, np.ones(5) / 5, "same")
    g = -np.diff(d)
    if g.max() <= 0:
        return np.array([], int)
    pk, _ = find_peaks(g, distance=25, prominence=g.max() * 0.25)
    return pk


def main():
    src, pitch, out = sys.argv[1], float(sys.argv[2]), sys.argv[3]
    rows = []
    for f in sorted(glob.glob(os.path.join(src, "p*.jpg"))):
        im = cv2.imread(f, cv2.IMREAD_COLOR)
        if im is None:
            continue
        gray = im[:, :, 2]
        b = baselines(gray)
        gaps = np.diff(b)
        good = int((np.abs(gaps / pitch - 1) < 0.06).sum())
        other = int(len(gaps) - good)
        rows.append(dict(page=os.path.basename(f)[:-4], lines=int(len(b)), good=good, other=other,
                         share=round(good / max(1, len(gaps)), 3)))
    rows.sort(key=lambda r: (-r["good"] * r["share"], r["page"]))
    json.dump(rows, open(out, "w"), indent=1)
    for r in rows[:30]:
        print(r)
    if len(sys.argv) > 4:
        thumbs = []
        for r in rows[:24]:
            im = cv2.imread(os.path.join(src, r["page"] + ".jpg"))
            t = cv2.resize(im, (300, int(300 * im.shape[0] / im.shape[1])))[:420]
            t = cv2.copyMakeBorder(t, 0, 420 - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(t, f"{r['page']} {r['good']}/{r['share']}", (5, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            thumbs.append(t)
        while len(thumbs) % 6:
            thumbs.append(np.full_like(thumbs[0], 255))
        grid = np.vstack([np.hstack(thumbs[i:i + 6]) for i in range(0, len(thumbs), 6)])
        cv2.imwrite(sys.argv[4], grid)


if __name__ == "__main__":
    main()
