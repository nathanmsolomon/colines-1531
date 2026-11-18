"""Give a mis-cut letter its real ink: replace an instance's crop with ink pieces chosen by eye.

Usage: python -I -X utf8 handcut.py <config.json> <copy>:<instance file>:<piece>[+<piece>...] ... [--dry]
  e.g.  handcut.py configs/ang_italic.json 2:0183.png:266 14:0220.png:649+631

Nov 13 2026. The aligner can only find a letter it has a template for, and a wrong first template
keeps itself alive (the italic T was the e after it in every build; the p-tilde never had its
tilde; the Y of "Yztal-" was cut from "vallee"). Where the real letter stands free on the page it
is one connected piece of ink (two with its accent), so it can simply be named:
  1. `scripts/region.py <config> <copy> <instance file> <out.png>` draws the page
     around the wrong instance with every ink piece boxed and numbered;
  2. this script replaces that instance's crop with the named pieces (their ink only, other ink
     whitened, in the format average.py reads) and moves its box. The label is unchanged.
Piece numbers come from cv2.connectedComponentsWithStats on the block at the folder's own
threshold (instances.json "otsu"), exactly as region.py numbers them; they change if the block
image changes, so the pieces' boxes are recorded in the instance ("handcut") and printed.
Nothing is drawn or composed: only which real ink belongs to the letter is decided by eye.
instances.json is backed up once as instances.json.before_handcut; each replaced crop is kept
as <file>.before_handcut. A full re-alignment overwrites the folder: run this again after one
(the commands used are in the working notes) and look at the sheet it writes.
"""
import os, sys, json, shutil
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]; dry = "--dry" in sys.argv
    C = json.load(open(args[0], encoding="utf-8")); nm = C["name"]; rows = []
    for spec in args[1:]:
        p, fn, pcs = spec.split(":"); pcs = [int(k) for k in pcs.split("+")]
        d = os.path.join(ROOT, "work", f"{nm}_al_p{p}"); jp = os.path.join(d, "instances.json")
        J = json.load(open(jp, encoding="utf-8")); it = next(i for i in J["instances"] if i["file"] == fn)
        bx = C["boxes"][p]
        g = cv2.imread(os.path.join(ROOT, C["images"][p]), 0)[bx[1]:bx[3], bx[0]:bx[2]]
        bw = (g < J["otsu"]).astype(np.uint8)
        n, lab, st, _ = cv2.connectedComponentsWithStats(bw, 8)
        paper = int(np.percentile(g, 90))
        x0 = min(int(st[k][0]) for k in pcs); x1 = max(int(st[k][0] + st[k][2]) for k in pcs)
        y0 = min(int(st[k][1]) for k in pcs); y1 = max(int(st[k][1] + st[k][3]) for k in pcs)
        gx0, gy0, gx1, gy1 = max(0, x0 - 6), max(0, y0 - 6), min(g.shape[1], x1 + 6), min(g.shape[0], y1 + 6)
        new = np.full((gy1 - gy0, gx1 - gx0), paper, np.uint8)
        m = cv2.dilate(np.isin(lab[gy0:gy1, gx0:gx1], pcs).astype(np.uint8), np.ones((5, 5), np.uint8)).astype(bool)
        # the dilated edge must not take in a neighbour's ink
        m &= ~((lab[gy0:gy1, gx0:gx1] > 0) & ~np.isin(lab[gy0:gy1, gx0:gx1], pcs))
        new[m] = g[gy0:gy1, gx0:gx1][m]
        old = cv2.imread(os.path.join(d, fn), 0)
        base = it["baseline"] + it.get("slope", 0.0) * ((x0 + x1) / 2 - (it["x0"] + it["x1"]) / 2)
        boxes = [[int(v) for v in st[k][:4]] for k in pcs]
        print(f"{nm} copy {p} {fn} '{it['ch']}': box {it['x0']},{it['y0']}-{it['x1']},{it['y1']} -> {x0},{y0}-{x1},{y1}; pieces {boxes}")
        H = 150
        fit = lambda a: cv2.resize(a, (max(1, int(a.shape[1] * H / a.shape[0])), H), interpolation=cv2.INTER_CUBIC)
        a_, b_ = fit(old), fit(new)
        rows.append(np.hstack([np.pad(a_, ((0, 0), (0, max(0, 260 - a_.shape[1]))), constant_values=255)[:, :260],
                               np.pad(b_, ((0, 0), (0, max(0, 260 - b_.shape[1]))), constant_values=255)[:, :260]]))
        if dry:
            continue
        if not os.path.exists(jp + ".before_handcut"):
            shutil.copy(jp, jp + ".before_handcut")
        if not os.path.exists(os.path.join(d, fn + ".before_handcut")):
            shutil.copy(os.path.join(d, fn), os.path.join(d, fn + ".before_handcut"))
        cv2.imwrite(os.path.join(d, fn), new)
        it.update(x0=x0, x1=x1, y0=y0, y1=y1, crop=[gx0, gy0], baseline=float(base), align=1.0,
                  handcut={"pieces": boxes, "note": "real ink chosen by eye (handcut.py)"})
        json.dump(J, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if rows:
        out = os.path.join(ROOT, "work", "review_thin", f"handcut_{nm}.png")
        os.makedirs(os.path.dirname(out), exist_ok=True)
        cv2.imwrite(out, np.vstack(rows)); print("sheet (before | after):", out, "(dry run)" if dry else "")


if __name__ == "__main__":
    main()
