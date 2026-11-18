"""Review sheet for the glyphs that rest on only 1 or 2 impressions (for checking by eye).

Usage: python -I -X utf8 review_thin.py <config.json> [max_n=2]
  -> work/review_thin/<name>_<k>.png (a few rows each) and a numbered list on stdout

One row per labelled crop of each thin glyph: the averaged glyph as the font traces it | the
crop | the crop's place on the page (the crop boxed) | glyph, copy, crop file, the transcribed
word. Verdicts go in scripts/verified_thin.json (see check_build.py).
"""
import os, sys, json, glob
import numpy as np, cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def fit(a, h, w):
    s = min(h / a.shape[0], w / a.shape[1])
    a = cv2.resize(a, (max(1, int(a.shape[1] * s)), max(1, int(a.shape[0] * s))), interpolation=cv2.INTER_CUBIC if s > 1 else cv2.INTER_AREA)
    t = np.full((h, w), 255, np.uint8); t[:a.shape[0], :a.shape[1]] = a
    return t


def main():
    C = json.load(open(sys.argv[1], encoding="utf-8")); nm = C["name"]
    maxn = int(sys.argv[2]) if len(sys.argv) > 2 else 2
    avg = os.path.join(ROOT, "work", f"{nm}_avg3")
    G = json.load(open(os.path.join(avg, "glyphs.json"), encoding="utf-8"))["glyphs"]
    rows = []; listing = []
    for gid, v in sorted(G.items(), key=lambda t: (t[1]["n"], t[1]["ch"])):
        if v.get("n", 0) > maxn:
            continue
        a = cv2.imread(os.path.join(avg, f"avg_{gid}.png"), -1)
        a = 255 - (a.astype(np.float32) / 65535 * 255).astype(np.uint8)
        ys, xs = np.where(a < 128)
        a = a[max(0, ys.min() - 20):ys.max() + 20, max(0, xs.min() - 20):xs.max() + 20] if len(ys) else a
        found = 0
        for p in sorted(C["images"], key=int):
            d = os.path.join(ROOT, "work", f"{nm}_al_p{p}")
            jp = os.path.join(d, "instances.json")
            if not os.path.exists(jp):
                continue
            tr = [ln.split() for ln in open(os.path.join(ROOT, C["trans"][p]), encoding="utf-8").read().splitlines()]
            page = None
            for it in json.load(open(jp, encoding="utf-8"))["instances"]:
                if it["ch"] != v["ch"]:
                    continue
                found += 1
                crop = cv2.imread(os.path.join(d, it["file"]), 0)
                if page is None:
                    page = cv2.imread(os.path.join(ROOT, C["images"][p]), 0)
                ctx = np.full((10, 10), 255, np.uint8)
                if page is not None:
                    x0, x1, y0, y1 = it["x0"], it["x1"], it["y0"], it["y1"]
                    cx0, cy0 = max(0, x0 - 260), max(0, y0 - 45)
                    ctx = page[cy0:y1 + 45, cx0:x1 + 260].copy()
                    cv2.rectangle(ctx, (x0 - cx0 - 3, y0 - cy0 - 3), (x1 - cx0 + 3, y1 - cy0 + 3), 0, 1)
                try:
                    word = tr[it["line"]][it["word"]]
                except Exception:
                    word = "?"
                used = f"{nm}_al_p{p}" in v.get("copies", [])
                H = 130
                lab = np.full((H, 520), 255, np.uint8)
                txt = f"#{len(listing)}  U+{' U+'.join('%04X' % ord(c) for c in v['ch'])}  n={v['n']}  p{p}/{it['file']}"
                cv2.putText(lab, txt, (6, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.55, 0, 1)
                cv2.putText(lab, f"line {it['line'] + 1} word {it['word'] + 1}  align {it.get('align', 0):.2f}  {'in a used copy' if used else 'copy not used'}",
                            (6, 80), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
                rows.append(np.hstack([np.pad(fit(a, H, 130), 3, constant_values=120), np.pad(fit(crop, H, 130), 3, constant_values=120),
                                       np.pad(fit(ctx, H, 760), 3, constant_values=120), np.pad(lab, 3, constant_values=120)]))
                listing.append(f"#{len(listing)} {v['ch']} n={v['n']} {nm}_al_p{p}/{it['file']} word={word} line={it['line'] + 1} used={used}")
        if not found:
            H = 130; lab = np.full((H, 520), 255, np.uint8)
            cv2.putText(lab, f"#{len(listing)} U+{' U+'.join('%04X' % ord(c) for c in v['ch'])} n={v['n']} NO CROP in al dirs", (6, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.5, 0, 1)
            rows.append(np.hstack([np.pad(fit(a, H, 130), 3, constant_values=120), np.pad(np.full((H, 130), 255, np.uint8), 3, constant_values=120),
                                   np.pad(np.full((H, 760), 255, np.uint8), 3, constant_values=120), np.pad(lab, 3, constant_values=120)]))
            listing.append(f"#{len(listing)} {v['ch']} n={v['n']} NO CROP FOUND (copied in by hand?) copies={v.get('copies')}")
    out = os.path.join(ROOT, "work", "review_thin"); os.makedirs(out, exist_ok=True)
    for k in range(0, len(rows), 8):
        cv2.imwrite(os.path.join(out, f"{nm}_{k // 8}.png"), np.vstack(rows[k:k + 8]))
    open(os.path.join(out, f"{nm}.txt"), "w", encoding="utf-8").write("\n".join(listing))
    print("\n".join(listing)); print(len(rows), "rows ->", out)


if __name__ == "__main__":
    main()
