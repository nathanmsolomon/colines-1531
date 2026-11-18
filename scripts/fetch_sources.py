"""Download the pilot's source books (full-size page images).

Usage: python -I fetch_sources.py [terentianus|anghiera|all]

terentianus  MDZ bsb10198271, Terentianus Maurus, De literis (Paris, Colines 1531),
             BSB Res/4 A.lat.a. 587; IIIF full size (~297 ppi measured on the type)
anghiera     IA extraictourecuei00angh, Anghiera, Extraict ou recueil des isles
             (Paris, Colines 1532), John Carter Brown Library; 500 ppi (verified)
Files go to source/books/<name>/p####.jpg; existing files are skipped, so a re-run
fills pages that failed (MDZ sometimes answers 502).
"""
import sys, os, json, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = {"User-Agent": "Colines-1531-fetch"}


def get(url, dest):
    if os.path.exists(dest) and os.path.getsize(dest) > 10000:
        return False
    for k in range(6):
        try:
            data = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=120).read()
            if len(data) < 10000:
                raise IOError("short response")
            open(dest + ".part", "wb").write(data); os.replace(dest + ".part", dest)
            return True
        except Exception as e:
            print("retry", url, e); time.sleep(10 * (k + 1))
    print("FAILED", url)
    return False


def terentianus():
    out = os.path.join(ROOT, "source", "books", "terentianus1531"); os.makedirs(out, exist_ok=True)
    m = json.load(urllib.request.urlopen(urllib.request.Request(
        "https://api.digitale-sammlungen.de/iiif/presentation/v2/bsb10198271/manifest", headers=UA)))
    json.dump(m, open(os.path.join(out, "manifest.json"), "w"), indent=0)
    for i, c in enumerate(m["sequences"][0]["canvases"], 1):
        sid = c["images"][0]["resource"]["service"]["@id"]
        get(sid + "/full/full/0/default.jpg", os.path.join(out, f"p{i:04d}.jpg"))


def anghiera():
    out = os.path.join(ROOT, "source", "books", "anghiera1532"); os.makedirs(out, exist_ok=True)
    meta = json.load(urllib.request.urlopen("https://archive.org/metadata/extraictourecuei00angh"))
    n = int(meta["metadata"]["imagecount"])
    json.dump(meta["metadata"], open(os.path.join(out, "meta.json"), "w"), indent=1)
    for i in range(n):
        get(f"https://archive.org/download/extraictourecuei00angh/page/n{i}.jpg", os.path.join(out, f"p{i:04d}.jpg"))


if __name__ == "__main__":
    w = sys.argv[1] if len(sys.argv) > 1 else "all"
    if w in ("terentianus", "all"): terentianus()
    if w in ("anghiera", "all"): anghiera()
    print("done")
