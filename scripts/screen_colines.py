"""Screen other Colines books (Internet Archive, MDZ) for the two pilot founts.

Usage: python -I -X utf8 scripts/screen_colines.py [--pages 10] [--no-fetch]

For each book in BOOKS, fetches --pages full-size page images spread through 15-85% of the
volume into source/probe/screen_nov17/<id>/p####.jpg (existing files are kept), then measures
each page with the shared screener's functions (_typelib/screen_books.py):
  pitch_px  line pitch (autocorrelation of the ink profile)
  xh_px     x-height
  roman / italic  median best IoU of the page's x-height letters against the pilot averages
            (work/ter_roman_avg3, work/ang_italic_avg3), shape only, scale-free
  ppi_if_14 / ppi_if_24  the scan resolution at which the pitch equals the Terentianus roman
            (119 mm / 20 lines) or the Great Primer italic (118 mm / 20) set solid
The book's stated scan resolution (IA metadata 'ppi', MDZ ~300) is printed beside it, so a
book in the pilot fount shows ppi_if close to its real ppi AND a high shape score.
Controls: the two pilot books themselves (terentianus1531, anghiera1532) from source/books.
Writes work/screen_nov17.csv and work/screen_nov17.md, and one contact image per book
(work/screen_nov17_<id>.jpg: the centre of its best page at 1:1).
Size and shape only rank candidates; a source is confirmed by eye and by the x-height check
(57 px roman / 55 px italic at the build scale) before any page becomes a copy.
"""
import sys, os, json, glob, csv, time, urllib.request
import numpy as np
import cv2

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
from screen_books import load_templates, page_measures, shape_score, letter_comps  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (type-history research script)"}
OUT = os.path.join(ROOT, "source", "probe", "screen_nov17")
L14 = 119 / 20 / 25.4      # Terentianus roman line, inches
L24 = 118 / 20 / 25.4      # Great Primer italic line, inches

# (id, source, year, note)
BOOKS = [
    ("b3355285x", "ia", 1531, "Wellcome: In librum Hippocratis de victus ratione (commentary)"),
    ("bub_gb_Pjtj-hHUC4EC", "ia", 1531, "BNC Roma (Google): Barthelemy, Christus Xylonicus"),
    ("bub_gb_Wj_BhOR6Xc4C", "ia", 1531, "BNC Roma (Google): Barthelemy, Ennoeae"),
    ("bub_gb_uDNhsOkMTqMC", "ia", 1531, "BNC Roma (Google): Aurelius Victor, Historia de vita imperatorum"),
    ("bsb10862434", "mdz", 1531, "BSB: Barthelemy, Christus Xylonicus"),
    ("bsb11199056", "mdz", 1531, "BSB: Sacrobosco, Textus de sphaera"),
    ("BIUSante_02054x01", "ia", 1532, "BIU Sante: Galen, Opera de pulsibus"),
    ("bub_gb_QSpbAsIzYkkC", "ia", 1532, "BNC Roma (Google): Livy, Conciones"),
    ("bub_gb_WTaXdNgItJ0C", "ia", 1532, "BNC Roma (Google): Breuis ad syllabarum quantitatem isagoge"),
    # 1533: the roman has the recut (§17) capitals, so these count for the ITALIC only
    ("ARes15508", "ia", 1533, "Sevilla: Apophthegmatum opus (italic only)"),
    ("BIUSante_33333x01", "ia", 1533, "BIU Sante: Caelius Aurelianus (italic only)"),
    ("BIUSante_71795x01", "ia", 1533, "BIU Sante: Serenus Sammonicus (italic only)"),
    ("blondiflaviiforl00bion", "ia", 1533, "Getty: Biondo, De Roma triumphante (italic only)"),
    ("hin-wel-all-00000883-001", "ia", 1533, "Wellcome: Galen, De semine (italic only)"),
    ("hin-wel-all-00001522-001", "ia", 1533, "Wellcome: Aristotle, De historia animalium (italic only)"),
    ("hin-wel-all-00002550-001", "ia", 1533, "Wellcome: Oribasius, Commentaria (italic only)"),
    ("bsb10172343", "mdz", 1533, "BSB: Nebrija, In Cosmographiae libros introductorium (italic only)"),
    ("bsb10186686", "mdz", 1533, "BSB: Bonae valetudinis conservandae praecepta (italic only)"),
    ("bsb11264754", "mdz", 1533, "BSB: Caelius Aurelianus, Liber celerum (italic only)"),
]
CONTROLS = [("terentianus1531", 297, "control: Terentianus 1531 (MDZ, pilot roman)"),
            ("anghiera1532", 500, "control: Anghiera 1532 (JCB, pilot italic)")]


def get_bytes(url, tries=5):
    for k in range(tries):
        try:
            return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=180).read()
        except Exception as e:
            print("  retry", url, e, flush=True); time.sleep(8 * (k + 1))
    return None


def pick(n_total, n):
    lo, hi = int(n_total * 0.15), max(int(n_total * 0.85), int(n_total * 0.15) + 1)
    return sorted(set(np.linspace(lo, hi - 1, n).astype(int).tolist()))


def fetch_ia(bid, n):
    md = json.loads(get_bytes(f"https://archive.org/metadata/{bid}") or b"{}")
    m = md.get("metadata", {})
    ppi = m.get("ppi")
    imgcount = int(m.get("imagecount") or 0)
    if not imgcount:                        # count from the jp2 zip listing if no imagecount
        imgcount = sum(1 for f in md.get("files", []) if f.get("name", "").endswith(".jp2")) or 100
    d = os.path.join(OUT, bid); os.makedirs(d, exist_ok=True)
    json.dump({"ppi": ppi, "imagecount": imgcount, "title": m.get("title"), "date": m.get("date"),
               "contributor": m.get("contributor")}, open(os.path.join(d, "meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for i in pick(imgcount, n):
        dest = os.path.join(d, f"p{i:04d}.jpg")
        if os.path.exists(dest):
            continue
        b = get_bytes(f"https://archive.org/download/{bid}/page/n{i}.jpg")
        if b and len(b) > 20000:
            open(dest, "wb").write(b)
        time.sleep(1)
    return ppi


def fetch_mdz(bid, n):
    man = json.loads(get_bytes(f"https://api.digitale-sammlungen.de/iiif/presentation/v2/{bid}/manifest") or b"{}")
    cv = man.get("sequences", [{}])[0].get("canvases", [])
    d = os.path.join(OUT, bid); os.makedirs(d, exist_ok=True)
    json.dump({"ppi": "~300 (MDZ, calibrated on Garamont books; some 400)", "imagecount": len(cv),
               "title": man.get("label")}, open(os.path.join(d, "meta.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for i in pick(len(cv), n):
        dest = os.path.join(d, f"p{i:04d}.jpg")
        if os.path.exists(dest):
            continue
        sid = cv[i]["images"][0]["resource"]["service"]["@id"]
        b = get_bytes(f"{sid}/full/full/0/default.jpg")
        if b and len(b) > 20000:
            open(dest, "wb").write(b)
        time.sleep(1)
    return 300


def measure_book(pages, R, xr, I, xi):
    rows = []
    for fp in pages:
        g = cv2.imread(fp, cv2.IMREAD_COLOR)
        if g is None or min(g.shape[:2]) < 400:
            continue
        m = page_measures(g[:, :, 2])
        if not m:
            continue
        cs = letter_comps(m["bw"], m["xh_px"])
        rows.append(dict(page=os.path.basename(fp), h=g.shape[0], w=g.shape[1], pitch_px=m["pitch_px"],
                         xh_px=round(m["xh_px"], 1),
                         roman=round(shape_score(m["bw"], m["xh_px"], R, xr, cs), 3),
                         italic=round(shape_score(m["bw"], m["xh_px"], I, xi, cs), 3),
                         ppi_if_14=round(m["pitch_px"] / L14), ppi_if_24=round(m["pitch_px"] / L24)))
    return rows


def contact(fp, out):
    g = cv2.imread(fp)
    h, w = g.shape[:2]
    c = g[int(h * .3):int(h * .3) + min(900, h), int(w * .15):int(w * .15) + min(1400, w)]
    cv2.imwrite(out, c, [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    n = int(sys.argv[sys.argv.index("--pages") + 1]) if "--pages" in sys.argv else 10
    R, xr = load_templates(os.path.join(ROOT, "work", "ter_roman_avg3"))
    I, xi = load_templates(os.path.join(ROOT, "work", "ang_italic_avg3"))
    allrows, summ = [], []
    jobs = [(b, src, yr, note) for b, src, yr, note in BOOKS] + [(b, "ctl", None, note) for b, _, note in CONTROLS]
    for bid, src, yr, note in jobs:
        print("==", bid, note, flush=True)
        if src == "ctl":
            ppi = dict((c[0], c[1]) for c in CONTROLS)[bid]
            pages = sorted(glob.glob(os.path.join(ROOT, "source", "books", bid, "p*.jpg")))
            pages = [pages[i] for i in pick(len(pages), n)]
        else:
            if "--no-fetch" not in sys.argv:
                ppi = fetch_ia(bid, n) if src == "ia" else fetch_mdz(bid, n)
            else:
                ppi = json.load(open(os.path.join(OUT, bid, "meta.json"), encoding="utf-8")).get("ppi")
            pages = sorted(glob.glob(os.path.join(OUT, bid, "p*.jpg")))
        rows = measure_book(pages, R, xr, I, xi)
        for r in rows:
            r.update(book=bid); allrows.append(r)
            print(" ", r["page"], r["w"], "x", r["h"], "pitch", r["pitch_px"], "xh", r["xh_px"],
                  "R", r["roman"], "I", r["italic"], "ppi_if14", r["ppi_if_14"], flush=True)
        if not rows:
            summ.append(dict(book=bid, year=yr, note=note, stated_ppi=ppi, pages=len(pages), measured=0))
            continue
        best = max(rows, key=lambda r: max(r["roman"], r["italic"]))
        contact(os.path.join(OUT if src != "ctl" else os.path.join(ROOT, "source", "books"),
                             bid, best["page"]), os.path.join(ROOT, "work", f"screen_nov17_{bid}.jpg"))
        med = lambda k: float(np.median([r[k] for r in rows]))
        summ.append(dict(book=bid, year=yr, note=note, stated_ppi=ppi, pages=len(pages), measured=len(rows),
                         px=f"{int(med('w'))}x{int(med('h'))}", pitch=med("pitch_px"), xh=med("xh_px"),
                         roman=med("roman"), italic=med("italic"),
                         roman_max=max(r["roman"] for r in rows), italic_max=max(r["italic"] for r in rows),
                         ppi_if_14=med("ppi_if_14"), ppi_if_24=med("ppi_if_24"), best_page=best["page"]))
    with open(os.path.join(ROOT, "work", "screen_nov17.csv"), "w", newline="", encoding="utf-8") as f:
        wr = csv.DictWriter(f, fieldnames=list(allrows[0].keys())); wr.writeheader(); wr.writerows(allrows)
    json.dump(summ, open(os.path.join(ROOT, "work", "screen_nov17.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    for s in summ:
        print(json.dumps(s, ensure_ascii=False))


if __name__ == "__main__":
    main()
