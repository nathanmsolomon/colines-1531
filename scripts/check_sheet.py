"""Eye-check sheets: each printed line of a block with its draft transcription below it.

Usage: python -I check_sheet.py <block.png> <draft.txt> <pitch_px> <out_prefix> [lines_per_sheet] [scale]

Line i of the draft is set under the i-th baseline of the block, so a missing or
extra draft line shows at once as a mismatch from that line on.
"""
import sys
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, __file__.rsplit("\\", 1)[0].rsplit("/", 1)[0])
from survey_pages import baselines


def main():
    img, txt, pitch, pre = sys.argv[1], sys.argv[2], float(sys.argv[3]), sys.argv[4]
    per = int(sys.argv[5]) if len(sys.argv) > 5 else 6
    sc = float(sys.argv[6]) if len(sys.argv) > 6 else 0.7
    g = cv2.imread(img, 0)
    b = [int(x) for x in baselines(g)]
    keep = [b[0]]                      # drop spurious half-pitch peaks
    for x in b[1:]:
        if x - keep[-1] > 0.75 * pitch:
            keep.append(x)
    lines = open(txt, encoding="utf-8").read().splitlines()
    print(len(keep), "baselines,", len(lines), "draft lines")
    font = ImageFont.truetype("C:/Windows/Fonts/times.ttf", 34)
    W = int(g.shape[1] * sc)
    for s in range(0, len(keep), per):
        rows = []
        for i in range(s, min(s + per, len(keep))):
            y = keep[i]
            strip = g[max(0, int(y - 0.8 * pitch)):int(y + 0.35 * pitch)]
            strip = cv2.resize(strip, (W, int(strip.shape[0] * sc)), interpolation=cv2.INTER_AREA)
            lab = Image.new("L", (W, 44), 255)
            ImageDraw.Draw(lab).text((6, 2), f"{i + 1:2d}  " + (lines[i] if i < len(lines) else "<none>"), font=font, fill=0)
            rows += [cv2.cvtColor(strip, cv2.COLOR_GRAY2BGR)]
            l = cv2.cvtColor(np.array(lab), cv2.COLOR_GRAY2BGR); l[:, :, :2] = np.maximum(l[:, :, :2], 0)
            l[np.all(l < 128, axis=2)] = (0, 0, 200)
            rows += [l, np.full((6, W, 3), 230, np.uint8)]
        cv2.imwrite(f"{pre}_{s // per + 1}.png", np.vstack(rows))


if __name__ == "__main__":
    main()
