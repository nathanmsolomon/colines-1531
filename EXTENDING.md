# Extending Colines Gros-romain

How to rebuild the fonts, add a page, or fill a missing letter. Read DOCUMENTATION.md
first: its rules (section 4) decide what may go into a font.

## Setup

- Python 3.12+ and `pip install numpy opencv-python pillow fonttools potracer`.
  The `.sh` scripts need a POSIX shell (Git Bash on Windows).
- `python -I scripts/fetch_sources.py` downloads both books (about 700 pages) into
  `source/books/`; `python -I scripts/fetch_sources.py terentianus` (or `anghiera`) for one.
- `sh scripts/prep_all.sh` cuts the 52 blocks the configs use into `work/` (bit for bit the
  blocks the fonts were built from).
- Typst, for the catalogue and specimen.
- Only for OCR drafts of new pages: Kraken, with a segmentation model and a recognition
  model named by the environment variables `KRAKEN`, `KRAKEN_SEG_MODEL` and
  `KRAKEN_REC_MODEL` (see `scripts/ocr_draft.py`). The ligature-reading model used here is
  not published; any model that reads early-modern print works, since every draft is
  corrected by eye.

All intermediate data goes to `work/` (not in the repository): aligned letter crops
(`work/<face>_al_p<copy>/`), averages (`work/<face>_avg3/`: avg_/std_/inst_<glyph>.png,
glyphs.json, metrics.json) and run results (`work/<face>_result.json`).

## Rebuild

```sh
python -I -X utf8 scripts/run_size.py configs/ter_roman.json     # roman, a few hours
python -I -X utf8 scripts/run_size.py configs/ang_italic.json    # italic, about 4.5 h
python -I -X utf8 scripts/fix_v_spacing.py fonts/ColinesGros-romain-Italic.otf fonts/ColinesGros-romainImpression-Italic.otf
python -I -X utf8 scripts/make_ttf.py fonts/ttf fonts/*.otf
```

`COLINES_JOBS` sets how many copies are aligned side by side (default 4) and
`COLINES_AVG_JOBS` the averaging workers (default 3; the output is identical to a serial
run). Add `--reuse` to `run_size.py` to keep the alignment and redo only the averages'
spacing and the build (minutes).

**A full rebuild renumbers the crops.** The eye-checked choices name crops by number, so
after one, in this order:
1. `seed_glyphs.json`: find the new crop of each seeded letter and re-point it.
2. Roman ú: `python -I scripts/recut_accent.py configs/ter_roman.json "ú"` (use `--dry`
   first and look at the result: the tool can pull in ink from the line above).
3. The italic hand cuts (T, æ, p̃, Y): `scripts/handcut.py` with the new crop and piece
   numbers (DOCUMENTATION.md section 4).
4. Italic 4 and 9: their words may fail alignment; place them with `place_redo.py`.
5. `verified_thin.json`: every glyph on 1–2 impressions must be looked at and listed
   again (`scripts/review_thin.py <config>` makes the sheets), or `check_build.py` fails.
6. `run_size.py --reuse` on both, then `fix_v_spacing.py` and `make_ttf.py` as above.

Look at every changed glyph in context before releasing it.

## Add a page or a line

1. **Same fount and state.** Use 1531–32 pages for the roman (from 1533 it has new
   capitals). Check the body: the line pitch must match (`scripts/survey_pages.py`), and
   measure the x-height of any small block (57 px roman, 55 px italic at 600 ppi): a
   smaller fount on the same page looks alike.
2. **Cut the block.** Anghiera: `python -I scripts/scan_prep.py <page>`. A few lines around a
   rare letter: `python -I scripts/hit_block.py <ang|ter> <page> <lines>`. Both add the block
   to `configs/blocks.json`.
3. **Transcribe** into `transcriptions/<block>.txt`, one printed line per line, as printed:
   ligature sorts in braces (`{ſt}`, `{ct}`, `{ſſi}`), ſ where the page has it, accents and
   tildes as printed. An OCR draft (`ocr_draft.py`) must be checked line by line against
   the image (`check_sheet.py`): an OCR error becomes a wrong letter in the font.
4. **Add the copy** to `trans` and `images` in `configs/<face>.json` and rebuild.

## Fill a missing letter

- Find it first: OCR the whole book, then `scripts/hit_sheets.py` makes contact sheets of
  every word holding the letter. Many hits are another fount (running heads, marginalia,
  commentary), show-through, or numerals.
- One or two impressions are enough from a hand-checked transcription, but each must be
  looked at against its word on the page and listed in `scripts/verified_thin.json`.
- If every aligned crop of a rare letter is wrong but the letter stands free on the page,
  cut it with `scripts/handcut.py`: `scripts/region.py` draws the page around the crop with
  every ink piece numbered; name the pieces, run with `--dry` first, and look at the sheet.
- **Never** draw it, borrow it from another fount or size, or adapt another letter.

## Check

- `work/<face>_result.json`: fidelity (font vs print must beat print vs print), the
  build checks and the glyph checks.
- `python -I -X utf8 scripts/colines_catalogue.py`, then
  `typst compile --ignore-system-fonts --font-path fonts specimen/catalogue.typ specimen/Colines_catalogue.pdf`.
  (`--ignore-system-fonts` matters: an older installed build of the same family would be
  picked up instead.)
