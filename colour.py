"""Colour for the exported sequences: the owner's LUT (Lumetri Creative > Look, intensity 0-200) and the 10 % crop at
the top and bottom, written on EVERY picture clip, exactly the way Premiere itself writes a Lumetri effect in xmeml
(copied from his own export: effect "Lumetri", the settings in a base64 "Blob", the LUT path also as a UTF-16 base64
parameter).

Tested in his Premiere 2026 (24 Nov 2026): an ADJUSTMENT LAYER cannot travel in an XML: Premiere imports it as an
opaque "Black Video" clip (even written exactly as Premiere exports it). The same Lumetri + crop on the clips imports
correctly (crop bars and the look visible). So the look goes on every clip; two LUTs = two Lumetri effects.
Intensity is Premiere's Look intensity: 0-200, 100 = the LUT as it is.
"""
import base64
import re
import sys
from pathlib import Path
from xml.sax.saxutils import escape

_ASSETS = Path(getattr(sys, "_MEIPASS", Path(__file__).parent)) / "assets"   # packed app: next to the code
LUT_EXT = (".cube", ".look", ".3dl")


def _num(x):
    x = float(x)
    return str(int(x)) if x == int(x) else f"{x:.2f}"


def _blob(lut, intensity):
    """Premiere's own Lumetri settings (the XML inside the Blob) with this LUT and intensity, everything else neutral."""
    raw = (_ASSETS / "lumetri_look.xml").read_text(encoding="utf-8")
    # two <LUT> tags: the Input LUT (empty in his look) and the Creative Look (his LUT): only the look changes
    old = re.search(r'<LUT>"([^"]+)"</LUT>', raw).group(1)
    raw = raw.replace(f'<LUT>"{old}"</LUT>', '<LUT>"' + escape(lut or "", {'"': "&quot;"}) + '"</LUT>')
    raw = re.sub(r'<__Intensity>"[^"]*"</__Intensity>', f'<__Intensity>"{_num(intensity)}"</__Intensity>', raw)
    # the embedded copy belongs to his old LUT file: Premiere reads the new file from its path
    raw = re.sub(r"\s*<embeddedlut>.*?</embeddedlut>", "", raw, flags=re.S)
    return base64.b64encode(raw.encode("utf-8")).decode("ascii")


def lumetri_filter(lut, intensity=100):
    """One Lumetri effect with the LUT as the Creative Look at this intensity (0-200)."""
    t = (_ASSETS / "lumetri_filter.xml").read_text(encoding="utf-8")
    i = t.find("<name>Blob</name>")
    j = t.find("<value>", i) + len("<value>")
    k = t.find("</value>", j)
    t = t[:j] + _blob(lut, intensity) + t[k:]
    path16 = base64.b64encode((lut or "").encode("utf-16-le")).decode("ascii")
    t = re.sub(r"(<parameterid>24</parameterid>.*?<value>)[^<]*(</value>)", rf"\g<1>{path16}\g<2>", t, count=1, flags=re.S)
    t = re.sub(r"(<name>Intensity</name>.*?<value>)-91445760000000000,[^,]*,",
               rf"\g<1>-91445760000000000,{float(intensity):.1f},", t, count=1, flags=re.S)
    t = re.sub(r"(<name>Highlights</name>.*?<value>)-91445760000000000,[^,]*,",   # his template had -36 there
               r"\g<1>-91445760000000000,0.,", t, count=1, flags=re.S)
    return re.sub(r">\s+<", "><", t.strip())


def crop_filter(top, bottom):
    p = lambda pid, name, v: (f'<parameter authoringApp="PremierePro"><parameterid>{pid}</parameterid><name>{name}</name>'
                              f'<valuemin>0.0</valuemin><valuemax>100.0</valuemax><value>{_num(v)}</value></parameter>')
    return ('<filter><effect><name>Crop</name><effectid>crop</effectid><effectcategory>motion</effectcategory>'
            '<effecttype>motion</effecttype><mediatype>video</mediatype><pproBypass>false</pproBypass>'
            + p("left", "Left", 0) + p("top", "Top", top) + p("right", "Right", 0) + p("bottom", "Bottom", bottom)
            + '</effect></filter>')


CROP = 10.0                     # % at the top and at the bottom (owner)


def clip_filters(settings):
    """The filters to put on every picture clip for these colour settings ("" = no colour).
    settings = dict(on, crop, lut1, int1, lut2, int2)."""
    s = settings or {}
    if not s.get("on"):
        return ""
    out = []
    for k in ("1", "2"):
        lut = s.get("lut" + k)
        if lut:
            out.append(lumetri_filter(lut, s.get("int" + k, 100)))
    if s.get("crop"):
        out.append(crop_filter(CROP, CROP))
    return "".join(out)


def describe(settings):
    """A short line for the page: what will be put on the clips."""
    s = settings or {}
    if not s.get("on"):
        return "No colour"
    bits = [f"{Path(s[k]).stem} {_num(s.get('int' + k[-1], 100))}" for k in ("lut1", "lut2") if s.get(k)]
    if s.get("crop"):
        bits.append(f"crop {_num(CROP)} % top / bottom")
    return " + ".join(bits) if bits else "No colour"
