"""Give the italic v the side bearings of the nine-page build (Nov 6).

Usage: python -I -X utf8 fix_v_spacing.py fonts/ColinesGros-romain-Italic.otf [...]

The 15-copy build kept only 3 spacing pairs for v (most v crops are cut short of the
hooked arm), so its fitted advance came out far too wide ("v ne", "v ie" in the proofs).
The v outline itself was restored from the nine-page averages, whose spacing (8 pairs)
was right: lsb 79, rsb 33 font units. Run after every build of the italic until v has
enough good crops of its own. Idempotent.
"""
import sys
from fontTools.ttLib import TTFont
from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.t2CharStringPen import T2CharStringPen
from fontTools.pens.transformPen import TransformPen

LSB, RSB = 79, 33


def main():
    for path in sys.argv[1:]:
        f = TTFont(path)
        gs = f.getGlyphSet()
        bp = BoundsPen(gs); gs["v"].draw(bp)
        x0, _, x1, _ = bp.bounds
        dx = LSB - x0
        adv = round(x1 - x0 + LSB + RSB)
        cff = f["CFF "].cff; top = cff[cff.fontNames[0]]
        pen = T2CharStringPen(adv, gs)
        gs["v"].draw(TransformPen(pen, (1, 0, 0, 1, dx, 0)))
        cs = pen.getCharString(private=top.Private, globalSubrs=top.GlobalSubrs)
        top.CharStrings["v"] = cs
        f["hmtx"].metrics["v"] = (adv, LSB)
        f.save(path)
        print(path, "v: shifted", round(dx), "advance", adv)


if __name__ == "__main__":
    main()
