"""Structure test for the story XML (final spec, section 6).

Builds Premiere-like source sequences with 2 and 4 audio tracks (interview A = a WAV under a
Color Matte, interview B = a camera clip with its audio on every track), makes the same story
with the app (story.export_from_source) and with the reference script
(reference_make_story_xml.py, the proven one) and compares them element by element:
tracks, clip attributes, start / end / in / out, pproTicks, the first complete <file>,
source tracks and links. Then story.check_xml must find nothing.

    python tools/story_check.py        -> exit code 0 when everything matches
Needs no media files: the paths are only text inside the XML.
"""
import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import story  # noqa: E402

TK = 10160640000                      # pproTicks per frame at 25 fps
R = "<rate><timebase>25</timebase><ntsc>FALSE</ntsc></rate>"
WAV = "/Volumes/Nunta/recorder/ZOOM0001.WAV"
CAM = "/Volumes/Nunta/fx6/XDROOT/Clip/500_SERJFX60756.MXF"


def _link(ref, mt, ti, ci):
    return (f"<link><linkclipref>{ref}</linkclipref><mediatype>{mt}</mediatype>"
            f"<trackindex>{ti}</trackindex><clipindex>{ci}</clipindex></link>")


def source(n_audio):
    """A source sequence: A = WAV (frames 0-75) under a Color Matte, B = camera clip (100-175) on V1 + A1..An."""
    pairs = n_audio // 2
    wavfile = (f'<file id="file-1"><name>ZOOM0001.WAV</name><pathurl>file://localhost{WAV}</pathurl>{R}'
               '<duration>75</duration><media><audio><samplecharacteristics><depth>16</depth><samplerate>48000'
               '</samplerate></samplecharacteristics><channelcount>1</channelcount></audio></media></file>')
    camfile = (f'<file id="file-2"><name>500_SERJFX60756.MXF</name><pathurl>file://localhost{CAM}</pathurl>'
               '<rate><timebase>50</timebase><ntsc>FALSE</ntsc></rate><duration>150</duration><media><video>'
               '<samplecharacteristics><width>1920</width><height>1080</height></samplecharacteristics></video>'
               f'<pproOriginalAudio><channelcount>{n_audio}</channelcount></pproOriginalAudio>'
               + "<audio><channelcount>2</channelcount></audio>" * pairs + '</media></file>')
    gen = ('<generatoritem id="gen-1"><name>Color Matte</name><duration>1080000</duration>' + R +
           '<start>0</start><end>75</end><in>300</in><out>375</out><effect><name>Color</name>'
           '<effectid>Color</effectid></effect></generatoritem>')
    wav = (f'<clipitem id="clipitem-w"><name>ZOOM0001.WAV</name><duration>75</duration>{R}<start>0</start>'
           f'<end>75</end><in>0</in><out>75</out><pproTicksIn>0</pproTicksIn><pproTicksOut>{75 * TK}</pproTicksOut>'
           f'{wavfile}<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')
    lk = _link("clipitem-v", "video", 1, 2) + "".join(
        _link(f"clipitem-a{k}", "audio", k, 2 if k == 1 else 1) for k in range(1, n_audio + 1))
    mv = (f'<clipitem id="clipitem-v"><name>500_SERJFX60756.MXF</name><duration>75</duration>{R}<start>100</start>'
          f'<end>175</end><in>0</in><out>75</out><pproTicksIn>0</pproTicksIn><pproTicksOut>{75 * TK}</pproTicksOut>'
          f'{camfile}{lk}</clipitem>')

    def ma(k):
        return (f'<clipitem id="clipitem-a{k}" premiereChannelType="stereo"><name>500_SERJFX60756.MXF</name>'
                f'<duration>75</duration>{R}<start>100</start><end>175</end><in>0</in><out>75</out>'
                f'<pproTicksIn>0</pproTicksIn><pproTicksOut>{75 * TK}</pproTicksOut><file id="file-2"/>'
                f'<sourcetrack><mediatype>audio</mediatype><trackindex>{(k + 1) // 2}</trackindex></sourcetrack>'
                f'{lk}</clipitem>')

    def trk(items, extra=""):
        return f"<track{extra}>{items}<enabled>TRUE</enabled><locked>FALSE</locked></track>"

    audio = trk(wav + ma(1), ' currentExplodedTrackIndex="0" premiereTrackType="Stereo"')
    for k in range(2, n_audio + 1):
        audio += trk(ma(k), f' currentExplodedTrackIndex="{(k - 1) % 2}"')
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
            '<uuid>abc</uuid><duration>175</duration>' + R + '<name>interviuri miri</name>'
            '<media><video><format><samplecharacteristics>' + R + '<width>1920</width><height>1080</height>'
            '</samplecharacteristics></format>' + trk(gen + mv) + '</video><audio>' + audio +
            '</audio></media></sequence></xmeml>')


def norm(path):
    seq = ET.parse(path).getroot().find("sequence")
    out = []
    for kind in ("video", "audio"):
        for ti, t in enumerate(seq.find("media").find(kind).findall("track"), 1):
            out.append((kind, ti, dict(t.attrib)))
            for c in t:
                if c.tag not in ("clipitem", "generatoritem"):
                    continue
                f = c.find("file")
                links = [(lk.findtext("mediatype"), lk.findtext("trackindex"), lk.findtext("clipindex"))
                         for lk in c.findall("link")]
                out.append((c.tag, dict(c.attrib, id=None),
                            [c.findtext(x) for x in ("start", "end", "in", "out", "pproTicksIn", "pproTicksOut")],
                            (f.get("id"), len(f)) if f is not None else None,
                            c.findtext("sourcetrack/trackindex"), links))
    return out, seq.findtext("duration")


def run(n_audio, tmp):
    src = os.path.join(tmp, f"src{n_audio}.xml")
    open(src, "w").write(source(n_audio))
    cuts = [(0, 0.40, 1.20, "el 1"), (1, 0.52, 2.00, "ea 1"), (0, 1.52, 2.60, "el 2"), (1, 2.08, 2.92, "ea 2")]
    cj = os.path.join(tmp, "cuts.json")
    json.dump({"fps": 25, "segments": {"MIRE": 1, "MIREASA": 2},
               "cuts": [{"seg": ["MIRE", "MIREASA"][fi], "in": a, "out": b, "text": t} for fi, a, b, t in cuts]},
              open(cj, "w"))
    ref, mine = os.path.join(tmp, f"ref{n_audio}.xml"), os.path.join(tmp, f"mine{n_audio}.xml")
    p = subprocess.run([sys.executable, os.path.join(HERE, "reference_make_story_xml.py"), src, cj, ref, "POVESTE"],
                       capture_output=True, text=True)
    if p.returncode or not os.path.exists(ref):
        return [f"{n_audio} tracks: the reference script failed: {p.stderr.strip()[-300:]}"]
    story.export_from_source(cuts, [dict(path=WAV), dict(path=CAM)], src, mine, "POVESTE", {0: "Mirele", 1: "Mireasa"})
    a, da = norm(ref)
    b, db = norm(mine)
    probs = []
    if da != db:
        probs.append(f"{n_audio} tracks: duration {db}, the reference has {da}")
    if len(a) != len(b):
        probs.append(f"{n_audio} tracks: {len(b)} elements, the reference has {len(a)}")
    probs += [f"{n_audio} tracks: {y}  ≠ reference {x}" for x, y in zip(a, b) if x != y][:10]
    errs = story.check_xml(mine)
    probs += [f"{n_audio} tracks, check_xml: {e}" for e in (errs[0] if isinstance(errs, tuple) else errs)]
    n_a = len(ET.parse(mine).getroot().find("sequence/media/audio").findall("track"))
    if n_a != n_audio:
        probs.append(f"{n_audio} tracks: the story has {n_a} audio tracks")
    print(f"{n_audio} audio tracks: {len(b)} elements, {'OK' if not probs else 'DIFFERENT'}")
    return probs


def main():
    with tempfile.TemporaryDirectory() as tmp:
        probs = run(2, tmp) + run(4, tmp)
    for p in probs:
        print("  ✗", p)
    print("story XML structure:", "OK" if not probs else f"{len(probs)} problem(s)")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
