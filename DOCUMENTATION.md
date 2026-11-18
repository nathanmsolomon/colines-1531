# Colines Gros-romain: processes and materials

## 1. Aim

Two fonts rebuilt from the printing of Simon de Colines (Paris, active 1518–1546): his
Great Primer (*Gros-romain*) roman of 1531 and the Great Primer chancery italic of 1532,
the two founts H. D. L. Vervliet numbers §14 and §24. They are measured, not drawn. Every
letter shape is the registered average of real impressions on Colines's own pages, and
every sidebearing is solved from the distances between printed neighbours.

Colines left no specimen sheet, so the method differs from that of a sheet revival such as
Caslon 1734 (the same pipeline, github.com/nathanmsolomon/caslon-1734). Clean book pages
stand in for the sheet, each hand-transcribed line by line, so every impression has a
known label. Vervliet's catalogue says which fount is which and gives the body (20-line
measure) that calibrates each scan.

**The rule: measure, never invent.** A letter is in a font only when real impressions of
that fount and state exist. Nothing is borrowed from another size or another face, and
nothing is drawn or completed by hand. A letter that is missing in print is missing here.

## 2. Materials

### 2.1 The founts (Vervliet 2003)

H. D. L. Vervliet, "Simon de Colines, punchcutter 1518–1546", *De Gulden Passer* 81 (2003),
115–167 (full text on DBNL), reprinted in *The Palaeotypography of the French Renaissance*
(Brill, 2008). For each of Colines's 28 founts it gives the 20-line measure, x-height and
capital height, the first book seen, and the letters that identify it.

| § | Fount | 20 lines | First seen | Here |
|---|---|---|---|---|
| 14 | 2nd Great Primer roman, the "Terentianus" roman | 119 mm | 1531 | Regular; measured 118.9 mm |
| 24 | Great Primer chancery italic (*cancellaresca formata*, later copied by Garamont) | 118 mm | 1532 | Italic; measured 117.9 mm |

**The state is pinned to 1531–32.** From 1533 the §14 roman was used with new, lighter
capitals (§17: a narrow E, a G without a beak, a steep R, a smaller g, a bulbous tail on
y). Only 1531–32 pages are used for the roman, so the fonts show the first state. The
italic was stable.

### 2.2 The books

| Font | Book | Copy and scan | Resolution |
|---|---|---|---|
| Regular | Terentianus Maurus, *De literis, syllabis, pedibus et metris* (Paris: Colines, 1531) | Bayerische Staatsbibliothek, Res/4 A.lat.a. 587; MDZ `bsb10198271` (IIIF, colour) | ~297 ppi, from the line pitch (69.5 px) and Vervliet's 119 mm |
| Italic | Pietro Martire d'Anghiera, *Extraict ou recueil des isles nouvellement trouvees en la grand mer Oceane* (Paris: Colines, 1532) | John Carter Brown Library, via the Internet Archive `extraictourecuei00angh` | 500 ppi, verified the same way (116.0 px) |

Every block is resampled to a 600 ppi working scale (`scripts/prep_block.py`), where the
body measures 140.5 px (roman, 16.9 pt) and 139.3 px (italic, 16.7 pt).

**Roman, 16 copies.** The preface, pp. 9–17 (whole pages); p. 100 (the only true K of 72
verse pages read); and small blocks of one or a few lines around rare letters found by
OCR over the whole book: p. 106 ll. 17–19 (K), p. 55 l. 21 (k), p. 75 l. 7 (K), p. 130
ll. 17 and 27 (X), p. 85 l. 4 (z).

**Italic, 36 copies.** Pages 25, 26, 30, 69, 70, 71, 77, 82, 90, 119, 132, 148, 160, 186
and 194, with their running heads (which give the figures 2 and 8); and 21 small blocks:
the chapter headings "Chap. XXVIII." of pp. 321–390 (X), the names Xaragua, Xamana and
Xagua (pp. 40, 78, 88, 239, 267), and p. 336 "Yztal-" (Y).

### 2.3 Searched and not used

- **Other Colines books of 1531–32** (Internet Archive and MDZ: 9 books of 1531–32 and 10 of 1533, 10 pages each,
  screened by line pitch and letter shape; `scripts/screen_colines.py`): none is in the
  §14 roman or the §24 italic at a usable size. Their text founts are English and Pica
  sizes. No 1533 book shows the italic as text.
- **Wellcome Collection, Oribasius (Colines, 1533)**, 600 ppi: a large Colines roman at
  about 112 mm per 20 lines, probably the §17 state. Not used: it is the later state.
- **Gallica** (the largest Colines holding) could not be reached by script.
- Not Colines books, though sometimes listed as such: Sylvius, *In linguam Gallicam
  isagoge* (1531, Robert Estienne) and Finé, *Protomathesis* (1532, Gérard Morrhy).
- Smaller founts on the same pages are kept out: Terentianus p. 103 l. 29 and the errata
  figures of p. 24 are a smaller fount (x-height 48 px against 57); p. 65's Z and p. 111's
  K are in the italic commentary and a red marginal letter.

## 3. Pipeline (scripts/)

1. **Fetch and cut.** `fetch_sources.py` downloads both books. `prep_all.sh` cuts every
   block in `configs/blocks.json` (crop, deskew, deslant the italic, red channel to
   suppress foxing, resample to 600 ppi). The small single-line blocks had the ink of
   their neighbouring lines whitened when they were cut; `configs/masks/` holds exactly
   those pixels, so every block is rebuilt bit for bit.
2. **Transcribe.** `transcriptions/<block>.txt`: one printed line per line, as printed,
   with ligature sorts in braces (`{ſt}`, `{ct}`, `{ſſi}`). Drafts came from Kraken OCR
   (`ocr_draft.py`) and were corrected by eye against the image, line by line.
3. **Segment and align** (`segment.py`, `segment_align.py`, `align_core.py`): find the
   text lines, cut words at the gaps, and force-align each word's letters to its
   transcription, cutting each letter's crop.
4. **Average** (`average.py`): register every crop of a letter to a reference and average
   them, at 600 ppi. For letters with 6 or more crops the reference is built from the crops
   that agree with the most typical one (the medoid), and a crop must agree with it to be
   used. Three rounds: each round's averages are the templates for the next alignment.
5. **Space** (`spacing.py`): sidebearings solved by least squares from the measured gaps
   between neighbouring letters (roman 9,802 pairs, rms 1.6 px; italic 9,564, 1.4 px).
6. **Build** (`build.py`): trace (potrace) and write CFF OpenType, 1000 units = the measured
   body; ligatures (liga, hlig for ct), long s, p̃ and q̃. `make_ttf.py` makes TrueType
   copies (every curve within 1 unit) for Word.
7. **Check** (`check_build.py`, `check_glyphs.py`, `fidelity.py`): see section 5.

`run_size.py configs/<face>.json` runs 3–7 for one font. Each project setting of the shared
library is in `scripts/typelib.json`.

## 4. Rules and decisions

- **How a glyph may be attested.** From hand-checked transcription, any number of
  impressions, but a glyph on 1 or 2 impressions must be looked at by eye against its word
  on the page and listed in `scripts/verified_thin.json` (`check_build.py` fails a build
  otherwise). Letters labelled by OCR alone would need 3 agreeing impressions.
- **Eye-checked overrides.** `scripts/seed_glyphs.json` names an eye-checked crop as the
  reference of a letter whose crops are often mis-cut (italic v, fl, 6; roman í, ó, ú, k);
  under 6 crops, the seed stands alone. `scripts/reject_glyphs.json` drops a glyph whose
  only crops were wrong, so it is composed from its letters (italic fi = f + i).
- **Hand cuts.** Where every aligned crop of a rare letter was wrong but the real letter
  stands free on the page as one piece of ink, `handcut.py` takes that piece instead
  (italic T, æ, p̃, Y). `recut_accent.py` adds a free-standing accent that the aligner's
  box missed (roman ú: Colines's acute sits above and to the right of the vowel).
- **The italic's hooked v.** Colines's word-initial v has a hooked arm that overhangs the
  space. Most crops are cut short of it, so v is averaged around a seed that keeps the arm
  (`ang_italic_al_p1/0592`), and `fix_v_spacing.py` sets its sidebearings.
- **One borrowing, for finding only.** The roman's first alignment round has no X template,
  so the italic's upright X is used to find the letter; the roman's X is its own (3
  impressions, rounds 2–3).
- **Capitals in the italic are upright**, as Colines printed them.
- **J, U, W, w** were not cut in these founts (i, V and vv serve). They are absent, not
  missing.

## 5. Quality checks

**Fidelity** is the median IoU between each letter in the font and its printed
impressions. The test of success: the font must be closer to the impressions than they
are to each other.

| Font | Font vs print | Print vs print | Lowest |
|---|---|---|---|
| Regular | **0.880** | 0.838 | Q 0.67 (its long tail varies), á 0.70, ú 0.74, í 0.76 |
| Italic | **0.844** | 0.783 | v and fl (scored against all their crops, most of them mis-cut; the glyphs themselves are right), 6 0.63, g 0.63 |

`check_build.py` runs at the end of every build: stale seed crops, glyphs lost against
the previous build, spacing with nothing to fit, and unverified thin glyphs.
`check_glyphs.py` asks whether each averaged glyph is the letter its label says. In the
final fonts every flag was looked at and is a design difference, not an error (roman j, à;
italic & A F Q V Y ct y z).

**Errors found by checking, and fixed** (all in the released fonts):
- Italic T, æ and p̃ were wrong in an earlier build (the e after T; the fragment "bigar";
  a plain p with its tilde cut off). Removed, then replaced by hand cuts of the real
  letters.
- Roman ú had lost its accent; roman ó's accent had become a dot; roman k was the fragment
  "ihil" of *nihili*. Each was re-cut or re-seeded from an eye-checked crop.
- One added line (p. 103) turned out to be a smaller fount and was removed, with every
  letter it touched re-averaged.
- The italic fl ligature was set too tight on the right; re-measured from three agreeing
  pairs.

## 6. What each font contains, and what is missing

The catalogue (`specimen/Colines_catalogue.pdf`) shows every glyph with its number of
impressions.

**Regular** (80 glyphs): `A–I K–T V X a–v x–z` (no w), `& ( ) , - . : ; ?`, ꝰ; à á ã í ó ò õ ú ę ẽ ī ũ
æ œ ſ; ligatures ct ſi ſſ ſſi ſt fi fl ffi, q̃.
- On 1–2 impressions (each eye-checked): G k q̃ z í ó ú ī ꝰ. On 3–4: B K L R X fl.
- **Missing:** Y, Z and the figures (in this book they appear only in the running heads
  and folios, which may be another fount, so they were not taken); `!`, `'`.

**Italic** (77 glyphs): `A–I L–T V X Y Z a–i l–v x–z` (no j, k), figures `0–9` (old style),
`& ( ) , - . :`; ã ẽ ĩ õ ũ æ ſ; ligatures ct ff fl ſi ſſ ſt, p̃ q̃.
- On 1–2 impressions (each eye-checked): ( ) 1 2 4 6 8 9 O Q T Y Z p̃ æ. On 3–4: 0 3 5 7
  F H N fl ĩ ũ.
- **Missing:** K (very rare), j, k; `;` `?` `!` `'`; œ. Word substitutes another font for
  a missing character.

The **Impression** fonts have the same characters; each glyph is the single most typical
real impression, with its ink spread and grain.

## 7. Reproducing

See EXTENDING.md. In short: `fetch_sources.py`, `prep_all.sh`, then
`run_size.py configs/ter_roman.json` and `configs/ang_italic.json` (about 4.5 hours for
the italic). A full rebuild re-aligns every crop, so the crop numbers named in
`seed_glyphs.json`, `verified_thin.json` and the hand cuts change; they must be found
again and checked by eye (EXTENDING.md, "Rebuild").

## 8. Credits

Scans: **Bayerische Staatsbibliothek / Münchener DigitalisierungsZentrum** (Terentianus
Maurus, 1531) and the **John Carter Brown Library** via the **Internet Archive** (Anghiera,
1532). The scans are not redistributed; `fetch_sources.py` downloads them from their
holders.

Scholarship: H. D. L. Vervliet's catalogue of Colines's types (2003, 2008), which
identifies the founts and gives the measures used to calibrate every scan. Also K. Amert,
"Origins of the French old-style" (*Printing History* 26/27, 1991–92) and F. Schreiber,
*Simon de Colines: an annotated catalogue* (1995), for context.

OCR drafts: Kraken, with the McCATMuS segmentation model.
