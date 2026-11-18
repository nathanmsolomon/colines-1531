"""Cut a small block around OCR hit lines (from hit_sheets.py) for use as a copy.

Usage: python -I hit_block.py <ang|ter> <page> <line>[-<line>] ...     e.g. ter p0106 17-19

<line> numbers are the ALTO text lines as the hit sheets label them (L17 ...). The block is
the union of those lines' boxes, padded by a quarter of a line height, in the column the
lines share. Slant and rotation are measured on a larger box (the lines plus six lines'
height above and below) and then fixed, since one or two lines are too few to measure.

Writes configs/blocks.json "<ang|ter>_<page>_h<first line>", runs prep_block.py, writes the
OCR draft of those lines to transcriptions/<name>.txt (unless it exists: it is checked by
eye afterwards) and a check image work/sweep/chk/<name>.png (block above, draft below).
"""
import sys, os, re, json, html, subprocess, tempfile
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ocr_draft import convert

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = {"ang": ("anghiera1532", "work/ocr_scan", 500, "auto", 116.0),     # line pitch in page px
        "ter": ("terentianus1531", "work/ter_scan", 297, 0, 69.5)}
PY = [sys.executable, "-I", "-X", "utf8"]


def alto_lines(xml):
    x = open(xml, encoding="utf-8").read()
    out = []
    for m in re.finditer(r"<TextLine([^>]*)>(.*?)</TextLine>", x, re.S):
        a = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
        words = [html.unescape(w) for w in re.findall(r'<String[^>]*CONTENT="([^"]*)"', m.group(2))]
        bl = [float(v) for v in a.get("BASELINE", "").split()]
        base = float(np.mean(bl[1::2])) if bl else float(a["VPOS"]) + 0.75 * float(a["HEIGHT"])
        out.append(([int(float(a[k])) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")], convert(" ".join(words)), base))
    return out


def prep(spec, name):
    blocks_p = os.path.join(ROOT, "configs", "blocks.json")
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({name: spec}, f)
    r = subprocess.run(PY + [os.path.join(ROOT, "scripts", "prep_block.py"), f.name, name],
                       capture_output=True, text=True, encoding="utf-8", cwd=ROOT)
    os.unlink(f.name)
    if r.returncode:
        raise SystemExit(r.stdout + r.stderr)
    return json.loads(r.stdout.strip().splitlines()[-1])


def main():
    key, page = sys.argv[1], sys.argv[2]
    book, ocr, ppi, slant, P = BOOK[key]
    want, keep = [], (0.0, 1.0)
    for a in sys.argv[3:]:
        if a.startswith("keep="):        # keep=a,b: only this fraction of the block's width
            keep = tuple(map(float, a[5:].split(",")))   # (show-through, another fount beside)
            continue
        lo, _, hi = a.partition("-")
        want += range(int(lo), int(hi or lo) + 1)
    L = alto_lines(os.path.join(ROOT, ocr, f"{key}_{page}_v6.xml"))
    sel = [L[i - 1] for i in want]
    x0 = min(b[0] for b, _, _ in sel); x1 = max(b[0] + b[2] for b, _, _ in sel)
    # from just above the first line's capitals to below the last line's descenders
    b0, b1 = min(z for _, _, z in sel), max(z for _, _, z in sel)
    y0, y1 = int(b0 - 0.95 * P), int(b1 + 0.45 * P)
    h = int(P)
    src = f"source/books/{book}/{page}.jpg"
    W, H = Image.open(os.path.join(ROOT, src)).size
    name = f"{key}_{page}_h{want[0]}"
    # slant and rotation from a taller box in the same column
    ctx = dict(src=src, ppi=ppi, box=[x0, max(0, y0 - 6 * h), x1, min(H, y1 + 6 * h)], blank=[],
               slant=slant, rotate="auto", channel="red", out=f"work/sweep/chk/{name}_ctx.png")
    os.makedirs(os.path.join(ROOT, "work/sweep/chk"), exist_ok=True)
    m = prep(ctx, name)
    p = h // 4
    bx0, bx1 = max(0, x0 - p), min(W, x1 + p)
    bx0, bx1 = int(bx0 + keep[0] * (bx1 - bx0)), int(bx0 + keep[1] * (bx1 - bx0))
    spec = dict(src=src, ppi=ppi, box=[bx0, max(0, y0), bx1, min(H, y1)], blank=[],
                slant=m["slant"], rotate=m["rotate"], channel="red", out=f"work/{name}.png")
    out = prep(spec, name)
    # whiten ink pieces centred outside the lines' band (neighbouring lines' descenders and
    # ascenders), so the line finder sees only the transcribed lines
    op = os.path.join(ROOT, spec["out"])
    im = cv2.imread(op, cv2.IMREAD_GRAYSCALE)
    sc = im.shape[0] / (spec["box"][3] - spec["box"][1])
    lo, hi = (b0 - 0.8 * P - spec["box"][1]) * sc, (b1 + 0.38 * P - spec["box"][1]) * sc
    _, bw = cv2.threshold(im, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    n, lab, st, cen = cv2.connectedComponentsWithStats(bw)
    # (pieces cut by the top or bottom edge are always the neighbours': the lines' own
    # ascenders and descenders stop short of it)
    edge = lambda i: st[i][1] <= 1 or st[i][1] + st[i][3] >= im.shape[0] - 1
    drop = [i for i in range(1, n) if not lo <= cen[i][1] <= hi or edge(i)]
    im[np.isin(lab, drop)] = 255
    cv2.imwrite(op, im)
    blocks_p = os.path.join(ROOT, "configs", "blocks.json")
    B = json.load(open(blocks_p, encoding="utf-8"))
    B[name] = spec
    json.dump(B, open(blocks_p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    tp = os.path.join(ROOT, "transcriptions", f"{name}.txt")
    if not os.path.exists(tp):
        open(tp, "w", encoding="utf-8").write("\n".join(t for _, t, _ in sel) + "\n")
    text = open(tp, encoding="utf-8").read().splitlines()
    blk = Image.open(os.path.join(ROOT, spec["out"])).convert("L")
    try:
        font = ImageFont.truetype("seguisym.ttf", 34)
    except OSError:
        font = ImageFont.truetype("arial.ttf", 34)
    sheet = Image.new("L", (blk.width, blk.height + 50 * len(text) + 20), 255)
    sheet.paste(blk, (0, 0))
    d = ImageDraw.Draw(sheet)
    for i, t in enumerate(text):
        d.text((10, blk.height + 10 + 50 * i), f"{i + 1}: {t}", fill=0, font=font)
    sheet.save(os.path.join(ROOT, "work/sweep/chk", f"{name}.png"))
    print(name, out["size"], "slant", m["slant"], "rotate", m["rotate"])
    print("\n".join(text))


if __name__ == "__main__":
    main()
