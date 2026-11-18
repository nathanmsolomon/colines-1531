"""Cut a specimen block from a Berner sheet, blank what must not be read, and
resample it to the 600 ppi working scale the Caslon pipeline was tuned for.

Usage: python -I prep_block.py <spec.json> <name>

spec.json: {name: {"src": sheet jpg, "box": [x0,y0,x1,y1] (sheet px),
                   "ppi": scan ppi, "blank": [[x0,y0,x1,y1], ...] (sheet px),
                   "slant": degrees to shear upright, or "auto", or 0,
                   "rotate": degrees (deskew, after resampling; "auto" or omitted),
                   "blank_out": [[x0,y0,x1,y1], ...] (output px, applied last),
                   "blank_post": [[x0,y0,x1,y1], ...] (final output px, after everything),
                   "channel": "red" to read the red channel only (suppresses foxing),
                   "out": png path}}
'ppi' is a per-copy working scale (410 for the 1592 sheet, 420 for 1622), chosen so
that both copies end at the same body in px (see configs). The true scan resolution
is 400 ppi (UB Frankfurt, Nov 4 2026), so the output is really 585 ppi in the 1592
sheet's frame; absolute sizes in pt must use that (the working notes).
Prints the slant used and the output size.
"""
import sys, json
import cv2
import numpy as np


def auto_slant(bw):
    # the shear that makes vertical ink projections sharpest (as prepare_italic.py)
    h, w = bw.shape; best, A = -1, 0
    for a in np.arange(8, 26, 0.25):
        t = np.tan(np.radians(a))
        p = cv2.warpAffine(bw, np.float32([[1, t, 0], [0, 1, 0]]), (w + int(t * h) + 2, h)).sum(0)
        s = float((p ** 2).sum())
        if s > best:
            best, A = s, float(a)
    return A


def main():
    spec = json.load(open(sys.argv[1], encoding="utf-8"))[sys.argv[2]]
    # "channel": "red" reads only the red channel: foxing is orange-brown, so it
    # almost vanishes there, while the (neutral) ink stays dark
    ch = spec.get("channel")
    im = cv2.imread(spec["src"], cv2.IMREAD_COLOR)[:, :, 2] if ch == "red" else cv2.imread(spec["src"], cv2.IMREAD_GRAYSCALE)
    x0, y0, x1, y1 = spec["box"]
    blk = im[y0:y1, x0:x1].copy()
    paper = int(np.percentile(blk, 80))
    for a, b, c, d in spec.get("blank", []):
        blk[max(0, b - y0):max(0, d - y0), max(0, a - x0):max(0, c - x0)] = paper
    s = 600.0 / spec["ppi"]
    blk = cv2.resize(blk, None, fx=s, fy=s, interpolation=cv2.INTER_CUBIC)
    if spec.get("blank_out") and "blank_ref" in spec:
        # blank_out rectangles were drawn on an earlier output made with rotation
        # blank_ref["rotate"] and shear blank_ref["slant"]: map their corners back
        # to this resampled image and blank them here, so a changed rotation keeps
        # them on the same ink
        h, w = blk.shape
        R0, A0 = spec["blank_ref"].get("rotate", 0), spec["blank_ref"].get("slant", 0)
        t0 = np.tan(np.radians(A0))
        Minv = cv2.invertAffineTransform(cv2.getRotationMatrix2D((w / 2, h / 2), R0, 1))
        for a, b, c, d in spec.pop("blank_out"):
            pts = np.float32([[x - t0 * y, y] for x, y in ((a, b), (c, b), (c, d), (a, d))])
            pts = cv2.transform(pts[None], Minv)[0]
            cv2.fillPoly(blk, [np.round(pts).astype(np.int32)], paper)
    R = spec.get("rotate", 0)
    if R == "auto":
        # the rotation that makes the horizontal ink profile sharpest (baselines level)
        _, bw = cv2.threshold(cv2.GaussianBlur(blk, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        h, w = bw.shape; best = -1
        for r in np.arange(-3.5, 3.51, 0.05):   # the 1622 strips tilt up to ~3 degrees
            M = cv2.getRotationMatrix2D((w / 2, h / 2), r, 1)
            p = cv2.warpAffine(bw, M, (w, h)).astype(np.float32).sum(1)
            if (p ** 2).sum() > best:
                best, R = float((p ** 2).sum()), round(float(r), 2)
    if R:
        h, w = blk.shape
        blk = cv2.warpAffine(blk, cv2.getRotationMatrix2D((w / 2, h / 2), R, 1), (w, h),
                             flags=cv2.INTER_CUBIC, borderValue=paper)
    A = spec.get("slant", 0)
    if A == "auto":
        _, bw = cv2.threshold(cv2.GaussianBlur(blk, (3, 3), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        A = auto_slant(bw.astype(np.float32) / 255)
    if A:
        h, w = blk.shape; t = np.tan(np.radians(A))
        blk = cv2.warpAffine(blk, np.float32([[1, t, 0], [0, 1, 0]]), (w + int(t * h) + 2, h),
                             flags=cv2.INTER_CUBIC, borderValue=paper)
    for a, b, c, d in spec.get("blank_out", []):
        blk[b:d, a:c] = paper
    for a, b, c, d in spec.get("blank_post", []):     # final-output px, never remapped
        blk[b:d, a:c] = paper
    cv2.imwrite(spec["out"], blk)
    print(json.dumps(dict(name=sys.argv[2], rotate=R, slant=A, scale=round(s, 4), size=list(blk.shape[::-1]))))


if __name__ == "__main__":
    main()
