#!/bin/sh
# Cut every text block the two configs use from the scans (configs/blocks.json -> work/*.png).
# Run once after `python -I scripts/fetch_sources.py`; existing blocks are kept.
#
# The small blocks around single lines (names ending _h<line>, cut by hit_block.py) had the ink
# of the neighbouring lines whitened, using the OCR line positions. configs/masks/<name>.png holds
# exactly the pixels whitened, so the blocks are rebuilt bit for bit without the OCR.
# Copy 11 of the roman (work/ter_p0055_h21k.png) is the left 705 px of the p. 55 line-21 block
# ("Refert nihili k"; the rest of that line upset the word spans), with the p of "prior" and
# the line above whitened by hand: masks/ter_p0055_h21k.png.
cd "$(dirname "$0")/.."
mkdir -p work
python -I -X utf8 - <<'EOF'
import json, os, subprocess, sys
import cv2
b = json.load(open("configs/blocks.json", encoding="utf-8"))
out = {v["out"]: k for k, v in b.items()}
need = set()
for c in ("ter_roman", "ang_italic"):
    for p in json.load(open(f"configs/{c}.json", encoding="utf-8"))["images"].values():
        need.add(out.get(p, "ter_p0055_h21" if p.endswith("h21k.png") else None))


def masked(im, name):
    m = f"configs/masks/{name}.png"
    if os.path.exists(m):
        im[cv2.imread(m, 0) > 0] = 255
    return im


for k in sorted(need):
    o = b[k]["out"]
    if os.path.exists(o):
        continue
    subprocess.run([sys.executable, "-I", "-X", "utf8", "scripts/prep_block.py", "configs/blocks.json", k],
                   check=True, stdout=subprocess.DEVNULL)
    cv2.imwrite(o, masked(cv2.imread(o, 0), k))
if not os.path.exists("work/ter_p0055_h21k.png"):
    raw = "work/_ter_p0055_h21_raw.png"
    spec = {"x": dict(b["ter_p0055_h21"], out=raw)}
    json.dump(spec, open("work/_spec.json", "w"))
    subprocess.run([sys.executable, "-I", "-X", "utf8", "scripts/prep_block.py", "work/_spec.json", "x"],
                   check=True, stdout=subprocess.DEVNULL)
    cv2.imwrite("work/ter_p0055_h21k.png", masked(cv2.imread(raw, 0)[:, :705].copy(), "ter_p0055_h21k"))
    os.remove(raw); os.remove("work/_spec.json")
print(len(need), "blocks ready")
EOF
