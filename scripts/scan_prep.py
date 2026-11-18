"""Prepare a scanned Anghiera page for eye-checking: block box, block image, column draft, check sheets.

Usage: python -I scan_prep.py <page> [x0 x1]      e.g. p0026

1. The box: y from the longest run of baselines at the italic pitch (as find_block.py);
   x is the inkiest group of columns between blank gaps, so shoulder notes on either
   side are left out (give x0 x1 to override).
2. Adds/updates configs/blocks.json "ang_<page>" and runs prep_block.py.
3. From the page's ALTO draft (work/ocr_scan/ang_<page>_v6.xml) keeps the text lines whose
   centre lies inside the box, joins fragments sharing a baseline, and writes
   work/ocr_scan/ang_<page>_col.txt.
4. Writes check sheets work/ocr_scan/chk/ang_<page>_N.png (check_sheet.py).
"""
import sys, os, re, json, html, subprocess
import numpy as np
import cv2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from survey_pages import baselines
from ocr_draft import convert

PITCH = 116.0          # italic line pitch in page px (500 ppi scan; 139.2 at 600)
GAP = 12               # px of blank columns that separate the text column from shoulder notes
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def run_of(img):
    b = baselines(img)
    runs, cur = [], [b[0]]
    for c in b[1:]:
        a = cur[-1]
        if c - a < 0.85 * PITCH:                # spurious peak inside a line (p0103): skip it
            continue
        if abs((c - a) / PITCH - 1) < 0.08:       # baseline peaks jitter by up to ~7 px (p0085)
            cur.append(c)
        elif abs((c - a) / PITCH - 2) < 0.08:      # one baseline missed (p0028): fill it in
            cur += [(a + c) // 2, c]
        else:
            runs.append(cur); cur = [c]
    runs.append(cur)
    r = max(runs, key=len)
    return r, int(r[0] - 0.75 * PITCH), int(r[-1] + 0.45 * PITCH)


def box_for(img, x_fixed=None):
    r, y0, y1 = run_of(img)
    x0, x1 = x_fixed or column_x(img, y0, y1)
    # a short last line can be lost in the page-wide profile (p0030): extend the run
    # downward by baselines found within the column one pitch on (not upward: the
    # running head lies about a pitch above the first line)
    bc = baselines(img[:, x0:x1])
    r = list(r)
    while True:
        near = [c for c in bc if abs(c - r[-1] - PITCH) < 0.05 * PITCH]
        if not near:
            break
        r.append(near[0])
    # 0.95 pitch above the first baseline keeps its ascenders whole after the deslant
    y0, y1 = int(r[0] - 0.95 * PITCH), int(r[-1] + 0.45 * PITCH)
    return [x0, y0, x1, y1], len(r)


def column_x(img, y0, y1):
    # justified text leaves a clean vertical gap (often only ~20 px) between the column
    # and the shoulder notes: split the run's ink at gaps of GAP px and keep the
    # group with the most ink
    ink = (img[y0:y1] < 128).sum(0)
    xs = np.where(ink > (y1 - y0) * 0.002)[0]
    groups, g = [], [xs[0]]
    for a, c in zip(xs[:-1], xs[1:]):
        if c - a > GAP:
            groups.append(g); g = [c]
        else:
            g.append(c)
    groups.append(g)
    g = max(groups, key=lambda g: ink[g[0]:g[-1] + 1].sum())
    return max(0, int(g[0]) - 15), min(img.shape[1], int(g[-1]) + 15)


def column_draft(xml, box):
    x = open(xml, encoding="utf-8").read()
    x0, y0, x1, y1 = box
    frags = []
    for m in re.finditer(r"<TextLine([^>]*)>(.*?)</TextLine>", x, re.S):
        a = m.group(1)
        hp, vp, wd, ht = (float(re.search(k + r'="([\d.]+)"', a).group(1)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
        bl = [float(v) for v in re.search(r'BASELINE="([^"]*)"', a).group(1).split()]
        by = float(np.mean(bl[1::2]))
        if not (y0 < by < y1 + 0.3 * PITCH):
            continue
        # word by word: Kraken sometimes runs a column line on into a shoulder note
        words = []
        for s in re.finditer(r"<String([^>]*)/?>", m.group(2)):
            sh = float(re.search(r'HPOS="([\d.]+)"', s.group(1)).group(1))
            sw = float(re.search(r'WIDTH="([\d.]+)"', s.group(1)).group(1))
            if x0 < sh + sw / 2 < x1:
                words.append(html.unescape(re.search(r'CONTENT="([^"]*)"', s.group(1)).group(1)))
        if words:
            frags.append((by, hp, convert(" ".join(words))))
    frags.sort()
    lines = []
    for by, hp, t in frags:
        if lines and by - lines[-1][0] < 0.4 * PITCH:
            lines[-1][1].append((hp, t))
        else:
            lines.append([by, [(hp, t)]])
    return [" ".join(t for _, t in sorted(parts)) for _, parts in lines]


def main():
    page = sys.argv[1]
    xf = (int(sys.argv[2]), int(sys.argv[3])) if len(sys.argv) > 3 else None
    name = "ang_" + page
    src = f"source/books/anghiera1532/{page}.jpg"
    img = cv2.imread(os.path.join(ROOT, src), cv2.IMREAD_COLOR)[:, :, 2]
    box, n = box_for(img, xf)
    bj = os.path.join(ROOT, "configs", "blocks.json")
    blocks = json.load(open(bj, encoding="utf-8"))
    # a "blank" set by hand (woodcut initials, p0048) is kept on a rerun
    blank = blocks.get(name, {}).get("blank", [])
    blocks[name] = {"src": src, "ppi": 500, "box": box, "blank": blank, "slant": "auto", "rotate": "auto",
                    "channel": "red", "out": f"work/{name}.png"}
    s = json.dumps(blocks, ensure_ascii=False, indent=1)
    open(bj, "w", encoding="utf-8").write(s + "\n")
    py = [sys.executable, "-I", "-X", "utf8"]
    subprocess.run(py + ["scripts/prep_block.py", "configs/blocks.json", name], cwd=ROOT, check=True,
                   capture_output=True)
    lines = column_draft(os.path.join(ROOT, "work", "ocr_scan", name + "_v6.xml"), box)
    col = os.path.join(ROOT, "work", "ocr_scan", name + "_col.txt")
    open(col, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    os.makedirs(os.path.join(ROOT, "work", "ocr_scan", "chk"), exist_ok=True)
    r = subprocess.run(py + ["scripts/check_sheet.py", f"work/{name}.png", col, "139.2",
                             f"work/ocr_scan/chk/{name}", "9", "0.6"], cwd=ROOT, capture_output=True, text=True)
    print(name, "box", box, "run", n, "|", r.stdout.strip(), r.stderr.strip()[-300:])


if __name__ == "__main__":
    main()
