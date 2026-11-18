"""Sanity checks on a size's averages after a build, so slips show without proofing.

Usage: python -I check_build.py <avg dir> [<previous avg dir>]

- seeds: each seed_glyphs.json crop for this avg dir must still be labelled with its
  glyph (crop numbers shift when a transcription gains or loses lines)
- spacing: advance below half the ink width, or a sidebearing beyond half the ink
  width either way, means the spacing fit had nothing to go on
- glyphs lost or gained against the previous build
- glyphs averaged from a single impression
Prints one line per problem and "OK" if there are none; exits 1 on problems.
"""
import sys, os, json

S = os.path.dirname(os.path.abspath(__file__))


def main():
    avg = os.path.normpath(sys.argv[1])
    key = os.path.basename(avg)
    work = os.path.dirname(avg)
    g = json.load(open(os.path.join(avg, "glyphs.json"), encoding="utf-8"))["glyphs"]
    m = json.load(open(os.path.join(avg, "metrics.json"), encoding="utf-8"))["glyphs"]
    bad = []
    seeds = json.load(open(os.path.join(S, "seed_glyphs.json"), encoding="utf-8")).get(key, {})
    for ch, crop in seeds.items():
        d, f = crop.replace("\\", "/").split("/")
        I = json.load(open(os.path.join(work, d, "instances.json"), encoding="utf-8"))["instances"]
        lab = next((i["ch"] for i in I if i["file"] == f), None)
        if lab != ch:
            bad.append(f"seed {ch}: {crop} is now labelled {lab!r}")
    for ch, o in sorted(m.items()):
        w = o["inkw"]
        # italic overhangs (fl) run to about -w/3; narrow marks (. :) have wide sides
        if o["adv"] < 0.4 * w or min(o["lsb"], o["rsb"]) < -0.5 * w or max(o["lsb"], o["rsb"]) > 0.5 * w + 6:
            bad.append(f"spacing {ch}: adv {o['adv']:.1f} lsb {o['lsb']:.1f} rsb {o['rsb']:.1f} (ink {w:.1f})")
    if len(sys.argv) > 2:
        p = json.load(open(os.path.join(sys.argv[2], "glyphs.json"), encoding="utf-8"))["glyphs"]
        name = lambda k, d: d[k]["ch"]
        lost = sorted(name(k, p) for k in set(p) - set(g))
        if lost:
            bad.append("lost since previous build: " + " ".join(lost))
        gained = sorted(name(k, g) for k in set(g) - set(p))
        if gained:
            print("gained: " + " ".join(gained))
    singles = sorted(v["ch"] for v in g.values() if v.get("n", 0) <= 1)
    if singles:
        print("single impression: " + " ".join(singles))
    # glyphs on 1-2 impressions must have been checked by eye (verified_thin.json, Nov 11): a
    # trusted transcription does not make the CUT right (italic T was an e, ae was "bigar")
    vp = os.path.join(S, "verified_thin.json")
    ver = json.load(open(vp, encoding="utf-8")).get(key, {}) if os.path.exists(vp) else {}
    thin = sorted(v["ch"] for v in g.values() if v.get("n", 0) <= 2)
    unchecked = [c for c in thin if c not in ver]
    wrong = [c for c in thin if isinstance(ver.get(c), dict) and ver[c].get("verdict") not in ("ok", None) and "ok" not in ver[c].get("verdict", "")]
    if unchecked:
        bad.append("on 1-2 impressions, not checked by eye (review_thin.py, then verified_thin.json): " + " ".join(unchecked))
    if wrong:
        bad.append("on 1-2 impressions and judged wrong or to fix by eye, still in the averages: " + " ".join(wrong))
    print("\n".join(bad) if bad else "OK")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
