"""Suggest a text-block box for a page: the longest run of baselines at the wanted pitch.

Usage: python -I find_block.py <page.jpg> <pitch_px> [x-margin-frac]

Prints the baselines of the run and a box [x0, y0, x1, y1] in page px: y0 0.75 pitch
above the first baseline, y1 0.45 pitch below the last; x from the ink extent of
the run's rows (shoulder notes beyond a wide gap are left out).
"""
import sys
import numpy as np
import cv2
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from survey_pages import baselines


def main():
    im = cv2.imread(sys.argv[1], cv2.IMREAD_COLOR)[:, :, 2]
    pitch = float(sys.argv[2])
    b = baselines(im)
    runs, cur = [], [b[0]]
    for a, c in zip(b[:-1], b[1:]):
        if abs((c - a) / pitch - 1) < 0.05:
            cur.append(c)
        else:
            runs.append(cur); cur = [c]
    runs.append(cur)
    r = max(runs, key=len)
    y0, y1 = int(r[0] - 0.75 * pitch), int(r[-1] + 0.45 * pitch)
    ink = (im[y0:y1] < 128).sum(0) > (y1 - y0) * 0.01
    xs = np.where(ink)[0]
    # largest block of columns with no gap wider than one pitch
    groups, g = [], [xs[0]]
    for a, c in zip(xs[:-1], xs[1:]):
        if c - a > pitch:
            groups.append(g); g = [c]
        else:
            g.append(c)
    groups.append(g)
    g = max(groups, key=lambda g: g[-1] - g[0])
    print("lines", len(r), "baselines", list(map(int, r)))
    print("box", [int(g[0]) - 15, y0, int(g[-1]) + 15, y1])


if __name__ == "__main__":
    main()
