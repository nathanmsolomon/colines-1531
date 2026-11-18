"""Unattended book gathering from UB Frankfurt (Visual Library IIIF), for the
Garamont/Granjon harvest. Runs for hours; safe to stop and restart (it skips
what it already has).

Usage: python -I harvest_ufm.py <candidates.json> [--lib ufm|erara] [--cap-gb 120] [--min-free-gb 60]

candidates.json: {titleinfo_id: listing text} (collected from the library's search in
a browser; the search pages sit behind a browser check, IIIF does not).

For each candidate dated within the library's range (--lib, see LIBS; year read
from the listing text):
  1. fetch its IIIF manifest -> source/books/ufm/<id>/manifest.json (+ meta.json)
  2. download every page at full size -> source/books/ufm/<id>/p<NNNN>.jpg
  3. measure each page: dominant line pitch (px) by autocorrelation of the ink profile,
     and page size in px -> source/books/ufm/<id>/survey.json
Logs to work/harvest_ufm.log, progress to work/harvest_ufm_status.json.
Stops cleanly when the downloaded total passes --cap-gb or N: has < --min-free-gb free.
One request at a time with a pause between requests, to be polite to the library.
"""
import sys, os, json, re, time, shutil, urllib.request, io
import numpy as np
import cv2

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
# --lib picks the library (both run Visual Library, so manifests and images match):
#   ufm   UB Frankfurt, Frankfurt imprints 1555-1625 (the Egenolff-Berner foundry's city)
#   erara e-rara.ch, Paris imprints 1530-1561 (Estienne, Colines, Vascosan, Wechel:
#         Garamont's lifetime, his types at their freshest)
LIBS = {"ufm": ("https://sammlungen.ub.uni-frankfurt.de/i3f/v20", 1555, 1625),
        "erara": ("https://www.e-rara.ch/i3f/v20", 1530, 1561)}
LIB = sys.argv[sys.argv.index("--lib") + 1] if "--lib" in sys.argv else "ufm"
BASE, YMIN, YMAX = LIBS[LIB]
OUT = os.path.join(ROOT, "source", "books", LIB)
LOG = os.path.join(ROOT, "work", f"harvest_{LIB}.log")
STATUS = os.path.join(ROOT, "work", f"harvest_{LIB}_status.json")
UA = {"User-Agent": "Garamont-reconstruction research (single-threaded, polite)"}
PAUSE = 1.0


def log(*a):
    s = time.strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(s, flush=True)
    open(LOG, "a", encoding="utf-8").write(s + "\n")


def get(url, tries=4):
    for k in range(tries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120) as r:
                return r.read()
        except Exception as e:
            log("  retry", k + 1, url, e)
            time.sleep(10 * (k + 1))
    return None


def year_of(text):
    ys = [int(y) for y in re.findall(r"\b(1[5-6]\d\d)\b", text)]
    return min(ys) if ys else None


def line_pitch(gray):
    """Dominant baseline-to-baseline distance on the page (px), from the
    autocorrelation of the horizontal ink profile of the central text area."""
    h, w = gray.shape
    c = gray[int(h * .12):int(h * .88), int(w * .15):int(w * .85)]
    _, bw = cv2.threshold(cv2.GaussianBlur(c, (5, 5), 0), 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    p = bw.sum(1).astype(np.float64)
    if p.max() == 0:
        return None, 0.0
    p -= p.mean()
    ac = np.correlate(p, p, "full")[len(p) - 1:]
    ac /= ac[0] + 1e-9
    lo = 15; hi = min(len(ac) - 1, 400)
    if hi <= lo:
        return None, 0.0
    k = lo + int(np.argmax(ac[lo:hi]))
    return k, float(ac[k])


def dir_gb(path):
    t = 0
    for dp, _, fs in os.walk(path):
        for f in fs:
            t += os.path.getsize(os.path.join(dp, f))
    return t / 1e9


def main():
    cand = json.load(open(sys.argv[1], encoding="utf-8"))
    cap = float(sys.argv[sys.argv.index("--cap-gb") + 1]) if "--cap-gb" in sys.argv else 120.0
    min_free = float(sys.argv[sys.argv.index("--min-free-gb") + 1]) if "--min-free-gb" in sys.argv else 60.0
    os.makedirs(OUT, exist_ok=True)
    todo = sorted(((year_of(t), i, t) for i, t in cand.items() if year_of(t) and YMIN <= year_of(t) <= YMAX))
    log(f"start ({LIB}): {len(cand)} candidates, {len(todo)} dated {YMIN}-{YMAX}; cap {cap} GB, keep {min_free} GB free")
    used = dir_gb(OUT)
    st = dict(started=time.strftime("%Y-%m-%d %H:%M"), books_total=len(todo), books_done=0, pages=0, gb=round(used, 2), stopped=None)
    for y, tid, text in todo:
        d = os.path.join(OUT, tid)
        if os.path.exists(os.path.join(d, "done")) or os.path.exists(os.path.join(d, "skipped")):
            st["books_done"] += 1
            continue
        os.makedirs(d, exist_ok=True)
        raw = get(f"{BASE}/{tid}/manifest")
        if not raw:
            log("no manifest", tid); continue
        open(os.path.join(d, "manifest.json"), "wb").write(raw)
        m = json.loads(raw)
        meta = {str(x.get("label")): str(x.get("value"))[:300] for x in m.get("metadata", [])}
        json.dump(dict(id=tid, year=y, listing=text, label=m.get("label"), metadata=meta),
                  open(os.path.join(d, "meta.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        # roman and italic were used for Latin (and French); German books of the
        # period are set in blackletter, and manuscripts have no type at all
        lang = " ".join(v for k, v in meta.items() if "Sprache" in k or "anguage" in k)
        # e-rara manifests carry no language field: there an unknown language is kept
        # (the candidates are Paris imprints, nearly all Latin or French)
        known_ok = re.search(r"Latein|Latin|\blat\b|Franz|French|\bfre\b|Griech|Greek|\bgrc\b", lang)
        if (not known_ok and not (LIB == "erara" and not lang.strip())) or str(m.get("label", "")).startswith("Ms."):
            open(os.path.join(d, "skipped"), "w").write(f"language: {lang or 'none'}")
            log(f"skip {tid} ({y}): language {lang or 'none'}: {str(m.get('label'))[:70]}")
            continue
        canv = m["sequences"][0]["canvases"]
        sp = os.path.join(d, "survey.json")
        survey = json.load(open(sp, encoding="utf-8")) if os.path.exists(sp) else {}
        log(f"book {tid} ({y}) {len(canv)} pages: {str(m.get('label'))[:90]}")
        for n, c in enumerate(canv):
            fn = f"p{n:04d}.jpg"; fp = os.path.join(d, fn)
            if not os.path.exists(fp):
                if used > cap or shutil.disk_usage(OUT).free / 1e9 < min_free:
                    st["stopped"] = f"disk limit reached ({used:.1f} GB downloaded)"
                    json.dump(st, open(STATUS, "w"), indent=1); log("STOP:", st["stopped"]); return
                svc = c["images"][0]["resource"]["service"]["@id"]
                img = get(f"{svc}/full/full/0/default.jpg")
                time.sleep(PAUSE)
                if not img:
                    continue
                open(fp, "wb").write(img); used += len(img) / 1e9; st["pages"] += 1
            if fn not in survey:
                g = cv2.imdecode(np.frombuffer(open(fp, "rb").read(), np.uint8), cv2.IMREAD_GRAYSCALE)
                if g is not None:
                    k, s = line_pitch(g)
                    survey[fn] = dict(w=int(g.shape[1]), h=int(g.shape[0]), pitch_px=k, strength=round(s, 3))
            if n % 25 == 0:
                json.dump(survey, open(sp, "w"), indent=0)
                st["gb"] = round(used, 2); json.dump(st, open(STATUS, "w"), indent=1)
        json.dump(survey, open(sp, "w"), indent=0)
        open(os.path.join(d, "done"), "w").write("ok")
        st["books_done"] += 1; st["gb"] = round(used, 2)
        json.dump(st, open(STATUS, "w"), indent=1)
    st["stopped"] = "finished all candidates"
    json.dump(st, open(STATUS, "w"), indent=1); log("finished")


if __name__ == "__main__":
    main()
