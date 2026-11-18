"""Put a re-averaged glyph into an averages folder whose canvas differs from the re-run's.

Usage: python -I -X utf8 place_redo.py <avg dir> <redo dir> <char>

redo_chars.py refuses when the temporary run's canvas (width, height, base_row) is not the
existing one (it happens when only a few characters are averaged: the canvas is sized from the
letters present). The images are the same scale, so each is copied onto the existing canvas with
its baseline row on the existing baseline row, centred sideways (spacing.py measures from the
ink, so the sideways position does not matter). Nothing is resampled. Run spacing/build after.
"""
import sys, os, json
import numpy as np, cv2


def main():
    avg, redo, ch = sys.argv[1:4]
    g = json.load(open(f"{avg}/glyphs.json", encoding="utf-8")); t = json.load(open(f"{redo}/glyphs.json", encoding="utf-8"))
    assert g["up"] == t["up"], "upsampling differs"
    gid = next(k for k, v in t["glyphs"].items() if v["ch"] == ch)
    dy = g["base_row"] - t["base_row"]   # base_row is already in canvas (upsampled) rows
    for pre in ("avg_", "std_", "inst_"):
        im = cv2.imread(f"{redo}/{pre}{gid}.png", -1)
        if im is None:
            continue
        H, W = cv2.imread(f"{avg}/{pre}{next(iter(g['glyphs']))}.png", -1).shape[:2]
        out = np.zeros((H, W) + im.shape[2:], im.dtype)
        dx = (W - im.shape[1]) // 2
        ys, xs = max(dy, 0), max(dx, 0); sy, sx = ys - dy, xs - dx
        h = min(im.shape[0] - sy, H - ys); w = min(im.shape[1] - sx, W - xs)
        out[ys:ys + h, xs:xs + w] = im[sy:sy + h, sx:sx + w]
        lost = float(im.astype(np.float64).sum() - out.astype(np.float64).sum())
        if pre == "avg_" and lost > 0.001 * float(im.sum()):
            sys.exit(f"{ch}: ink falls outside the existing canvas")
        cv2.imwrite(f"{avg}/{pre}{gid}.png", out)
    old = g["glyphs"].get(gid, {})
    g["glyphs"][gid] = t["glyphs"][gid]
    json.dump(g, open(f"{avg}/glyphs.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{ch}: placed (dy {dy} px at x{g['up']}), n {old.get('n')} -> {t['glyphs'][gid]['n']}; canvas {t['width']}x{t['height']} base {t['base_row']} -> {g['width']}x{g['height']} base {g['base_row']}")


if __name__ == "__main__":
    main()
