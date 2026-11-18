"""Side-by-side proof for a Colines pilot: the printed block above, the same lines set
in the built font below, both at the scan's own scale (600 ppi working scale).

Usage: python -I -X utf8 proof_side.py <config.json> <copy> <out.png> [lines]

<copy> is the config's copy key ("0", "1", ...). Ligatures are set from the plain
letters by setline.render, as the transcription's braces only mark them.
"""
import sys, os, json
import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
import setline  # noqa: E402
from setline import render  # noqa: E402
from proof_size import label  # noqa: E402

# Colines sets ct and q̃ as sorts of their own; set them where the font has them
setline.LIGS[:0] = [("q̃", "q_tilde"), ("ct", "c_t")]


def main():
    cp, key, outp = sys.argv[1:4]
    n = int(sys.argv[4]) if len(sys.argv) > 4 else 10
    C = json.load(open(cp, encoding="utf-8"))
    R = json.load(open(f"work/{C['name']}_result.json", encoding="utf-8"))
    lines = [l.rstrip("\n") for l in open(C["trans"][key], encoding="utf-8") if l.strip()]
    pitch = R["pitch_px"]
    scan = cv2.imread(C["images"][key], 0)
    # the block's first n lines: the line pitch of the block, from its height and line count
    lp = scan.shape[0] / len(lines)
    scan = scan[: int(lp * (n + 0.35))]
    text = [l.replace("{", "").replace("}", "") for l in lines[:n]]
    img = render(R["fonts"][0], pitch, text)
    if img.ndim == 2:
        img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
    W = max(scan.shape[1], img.shape[1])
    pad = lambda a: np.pad(a, ((0, 0), (0, W - a.shape[1]), (0, 0)), constant_values=255)
    fid = R["fidelity"][0].split("median")[-1].strip() + " vs " + R["fidelity"][1].split("median")[-1].strip()
    src = os.path.basename(C["trans"][key]).replace(".txt", "")
    sheet = np.vstack([pad(label(scan, f"printed: {C['family']} {C['style']} ({src})")),
                       pad(label(img, f"font, same lines; fidelity {fid}"))])
    s = min(1.0, 1600 / sheet.shape[1])
    cv2.imwrite(outp, cv2.resize(sheet, None, fx=s, fy=s, interpolation=cv2.INTER_AREA))
    print(outp)


if __name__ == "__main__":
    main()
