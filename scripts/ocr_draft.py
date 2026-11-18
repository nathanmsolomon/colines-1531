"""Draft a block transcription with Kraken (McCATMuS segmentation + ligocr_v6 reading).

Usage: python -I ocr_draft.py <block.png> <out.txt>

Writes one printed line per text line, top to bottom, in the transcription
convention: ligature sorts as {ſt}, {ſſ}, {ſi}, {ct} ... (from the model's ZWJ
sequences or private-use code points). The draft must be checked against the
image by eye before it is used: OCR errors become label errors.
"""
import sys, os, re, html, subprocess, unicodedata

K = os.environ.get("KRAKEN", "kraken")
MC = os.environ.get("KRAKEN_SEG_MODEL", "McCATMuS_nfd_nofix_V1.mlmodel")   # segmentation (McCATMuS, Zenodo)
LIG = os.environ.get("KRAKEN_REC_MODEL", "ligocr_v6.safetensors")   # recognition: a ligature-reading model (not published)
ENV = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
# ligocr_v6 writes these four sorts as private-use code points (checked on Terentianus 1531)
PUA = {"": "ct", "": "ſi", "": "ſſ", "": "ſſi", "ﬅ": "ſt", "ﬆ": "st",
       "\ufb00": "ff", "\ufb01": "fi", "\ufb02": "fl", "\ufb03": "ffi", "\ufb04": "ffl"}


def convert(t):
    t = unicodedata.normalize("NFC", t)
    t = re.sub(r"(\S(?:\u200d\S)+)", lambda m: "{" + m.group(1).replace("\u200d", "") + "}", t)
    out = []
    for ch in t:
        if ch in PUA:
            out.append("{" + PUA[ch] + "}")
        elif 0xE000 <= ord(ch) <= 0xF8FF:
            out.append("{?%04X}" % ord(ch))
        else:
            out.append(ch)
    return "".join(out).replace("⁹", "ꝰ")


def main():
    img, out = os.path.abspath(sys.argv[1]), os.path.abspath(sys.argv[2])
    d = os.path.dirname(out); b = os.path.splitext(out)[0]
    subprocess.run([K, "-a", "-i", img, b + "_mc.xml", "segment", "-bl", "ocr", "-m", MC], env=ENV, capture_output=True, cwd=d)
    subprocess.run([K, "-f", "alto", "-a", "-i", b + "_mc.xml", b + "_v6.xml", "ocr", "-m", LIG], env=ENV, capture_output=True, cwd=d)
    x = open(b + "_v6.xml", encoding="utf-8").read()
    lines = []
    for m in re.finditer(r"<TextLine([^>]*)>(.*?)</TextLine>", x, re.S):
        vpos = float(re.search(r'VPOS="([\d.]+)"', m.group(1)).group(1))
        words = [html.unescape(w) for w in re.findall(r'<String[^>]*CONTENT="([^"]*)"', m.group(2))]
        lines.append((vpos, convert(" ".join(words))))
    lines.sort()
    open(out, "w", encoding="utf-8").write("\n".join(t for _, t in lines) + "\n")
    print(open(out, encoding="utf-8").read())


if __name__ == "__main__":
    main()
