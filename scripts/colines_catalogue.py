"""Write specimen/catalogue.typ: every glyph of the four Colines fonts, with the number of
printed impressions each clean glyph was averaged from, and what each font lacks.

Usage: python -I -X utf8 scripts/colines_catalogue.py
then:  typst compile --font-path fonts specimen/catalogue.typ specimen/Colines_catalogue.pdf

Reads fonts/*.otf (cmap and GSUB ligatures) and work/<face>_avg3/glyphs.json (impression
counts). Nothing is set in a fallback font: a character the font lacks is listed, not drawn.
"""
import os, json, unicodedata
from fontTools.ttLib import TTFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FACES = [  # (heading, font file, typst family, style, avg dir, body pt, source)
    ("Roman, 1531", "ColinesGros-romain-Roman.otf", "Colines Gros-romain", "normal", "work/ter_roman_avg3", 16.9,
     "Terentianus Maurus, De literis, syllabis, pedibus et metris (Paris: Colines, 1531). BSB Munich, bsb10198271. Figures, Z, z and the double hyphen from Paulus Aegineta (Colines, 1532)."),
    ("Italic, 1532", "ColinesGros-romain-Italic.otf", "Colines Gros-romain", "italic", "work/ang_italic_avg3", 16.7,
     "Anghiera, Extraict ou recueil des isles nouvellement trouvees (Paris: Colines, 1532). John Carter Brown Library, via the Internet Archive. Figures also from the Annotationes of Paulus Aegineta (Colines, 1532)."),
    ("Impression Roman, 1531", "ColinesGros-romainImpression-Roman.otf", "Colines Gros-romain Impression", "normal", None, 16.9,
     "As the Roman, but each glyph is the single most typical real impression."),
    ("Impression Italic, 1532", "ColinesGros-romainImpression-Italic.otf", "Colines Gros-romain Impression", "italic", None, 16.7,
     "As the Italic, but each glyph is the single most typical real impression."),
]
# what a 1530s Latin/French text could call for; anything here a font lacks is listed as missing
EXPECTED = (list("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789")
            + list(".,;:?!()&-'") + ["ſ", "æ", "œ"])
NEVER = set("JUWw")  # not yet cut in these founts (i, V and vv serve)
FEATS = '("liga", "hlig", "ccmp")'
PRES = {"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬅ": "ſt"}  # presentation forms


def esc(s):
    return "".join("\\" + c if c in '\\#*_[]$@<>`"~=/+-' else c for c in s)


def inventory(path):
    t = TTFont(path)
    cmap = t.getBestCmap()
    rev = {g: chr(u) for u, g in cmap.items()}
    items = {}
    for u, g in sorted(cmap.items()):
        if u in (0x20, 0x0303) or g == ".notdef":
            continue
        items[g] = chr(u)
    for L in t["GSUB"].table.LookupList.Lookup:
        for st in L.SubTable:
            st = getattr(st, "ExtSubTable", st)
            for first, ligs in getattr(st, "ligatures", {}).items():
                for l in ligs:
                    s = rev.get(first, "") + "".join("\u0303" if c == "uni0303" else rev.get(c, "") for c in l.Component)
                    items.setdefault(l.LigGlyph, unicodedata.normalize("NFC", s))
    return items


def counts(avg):
    if not avg:
        return {}
    g = json.load(open(os.path.join(ROOT, avg, "glyphs.json"), encoding="utf-8"))["glyphs"]
    return {unicodedata.normalize("NFC", v["ch"]): v["n"] for v in g.values()}


def sort_key(s):
    c = s[0]
    grp = 0 if c.isupper() else 1 if c.islower() or c == "ſ" else 2 if c.isdigit() else 3
    return (grp, unicodedata.normalize("NFD", s)[0].lower(), len(s), s)


def main():
    out = ['#set page(paper: "a4", margin: (x: 16mm, y: 15mm), footer: context align(center, text(size: 8pt, fill: luma(110), counter(page).display())))',
           '#set text(font: "Libertinus Serif", size: 9pt)',
           '#let lab(t) = text(size: 6.5pt, fill: luma(90), t)',
           '#align(center)[#text(size: 20pt)[Colines Gros-romain] #linebreak() #text(size: 10pt)[Catalogue of the four fonts: every glyph, and what each lacks]]',
           '#v(4mm)',
           '#text(size: 8.5pt)[Each cell shows a glyph at 24 pt. Under the clean fonts, the number is how many printed impressions the glyph was averaged from (1 or 2: a single eye-checked impression). Ligatures are reached by typing their letters (ct needs the historical-ligature feature; p̃ and q̃ are p or q followed by U+0303). Nothing is set in a fallback font.]',
           '#v(3mm)']
    summary = []
    for head, fn, fam, style, avg, body, src in FACES:
        items = inventory(os.path.join(ROOT, "fonts", fn))
        n = counts(avg)
        chars = set(items.values())
        missing = [c for c in EXPECTED if c not in chars]
        summary.append((head, len(items), missing))
        out.append(f'#block(breakable: false)[#heading(level: 2)[{esc(head)}: {len(items)} glyphs] #text(size: 8pt)[{esc(src)} Body {body} pt.]]')
        cells = []
        for s in sorted(set(items.values()), key=sort_key):
            c = PRES.get(s, s)
            k = f" · {n[c]}" if c in n else ""
            name = "U+" + "+".join(f"{ord(c):04X}" for c in s) if len(s) == 1 else esc(s)
            cells.append(f'box(width: 100%)[#align(center)[#text(font: "{fam}", style: "{style}", size: 24pt, features: {FEATS}, top-edge: "ascender", bottom-edge: "descender", "{s.replace(chr(92), chr(92)*2).replace(chr(34), chr(92)+chr(34))}") #linebreak() #lab[{name}{k}]]]')
        out.append("#grid(columns: 10, row-gutter: 2.5mm, column-gutter: 1mm,\n  " + ",\n  ".join(cells) + ")")
        ms = ", ".join(("*" + esc(c) + "*" if c in NEVER else esc(c)) for c in missing)
        out.append(f'#v(2mm) #text(size: 8.5pt)[*Not in this font:* {ms or "nothing"}. (Bold: not yet cut in these founts in 1531–32.)]')
        out.append("#v(6mm)")
    open(os.path.join(ROOT, "specimen", "catalogue.typ"), "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    for head, k, m in summary:
        print(f"{head}: {k} glyphs; missing {' '.join(m)}")


if __name__ == "__main__":
    main()
