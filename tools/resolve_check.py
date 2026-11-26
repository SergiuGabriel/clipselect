"""CI: the DaVinci Resolve conversion (resolve.py) keeps the edit and drops only what Resolve cannot use."""
import os
import sys
import tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import resolve  # noqa: E402

F = ('<file id="f1"><name>C0001.MP4</name><pathurl>file://localhost/x/C0001.MP4</pathurl><rate><timebase>25</timebase></rate>'
     '<duration>250</duration><media><video/></media></file>')
LUM = '<filter><effect><name></name><effectid>Lumetri</effectid></effect></filter>'
MOT = '<filter><effect><name>Basic Motion</name><effectid>basic</effectid></effect></filter>'
CROP = '<filter><effect><name>Crop</name><effectid>crop</effectid></effect></filter>'
X = ('<?xml version="1.0"?><xmeml version="5"><project><name>P</name><children><bin><name>Camera A</name><children>'
     '<clip id="masterclip-1"><name>C0001.MP4</name><media><video><track><clipitem id="m1"><name>C0001.MP4</name>' + F +
     '</clipitem></track></video></media></clip></children></bin>'
     '<sequence id="s"><name>select</name><rate><timebase>25</timebase></rate><media><video><track>'
     '<clipitem id="c1"><name>C0001.MP4</name><masterclipid>masterclip-1</masterclipid><start>0</start><end>100</end>'
     '<in>0</in><out>100</out><file id="f1"/>' + LUM + MOT + CROP + '</clipitem></track></video></media></sequence>'
     '</children></project></xmeml>')
d = tempfile.mkdtemp()
src, out = os.path.join(d, "a.xml"), os.path.join(d, "a (DaVinci).xml")
open(src, "w").write(X)
r = resolve.convert(src, out)
y = open(out).read()
ok = (r["project_unwrapped"] and r["filters_removed"] == 3 and "<bin>" not in y and "masterclipid" not in y and
      "Lumetri" not in y and "<effectid>basic" not in y and "<effectid>crop" not in y and "<pathurl>" in y and
      y.count("<clipitem") == 1 and "<start>0</start><end>100</end>" in y and resolve.name_for(src, "davinci") == out)
v = resolve.verify(out)
ok = ok and not v["errors"] and v["clips"] == 1 and v["missing"] == ["C0001.MP4"]
print("resolve conversion + check", "OK" if ok else "FAILED", r, v)
if not ok:
    sys.exit(1)

# v4.2.0: the DaVinci file written from scratch (rewrite) out of a Premiere-shaped export with exploded stereo tracks,
# pproTicks, premiere attributes, a generator item, labels, links and a marker
F2 = ('<file id="file-1"><name>C0002.MXF</name><pathurl>file://localhost/x/C0002.MXF</pathurl><rate><timebase>50</timebase>'
      '<ntsc>FALSE</ntsc></rate><duration>500</duration><media><video><samplecharacteristics><width>3840</width><height>2160'
      '</height></samplecharacteristics></video><pproOriginalAudio><channelcount>4</channelcount></pproOriginalAudio>'
      '<audio><channelcount>2</channelcount></audio><audio><channelcount>2</channelcount></audio></media></file>')
A = lambda i, ch, ex: (f'<clipitem id="a{i}" premiereChannelType="stereo"><name>C0002.MXF</name><duration>250</duration>'
                       f'<rate><timebase>25</timebase></rate><start>10</start><end>60</end><in>0</in><out>50</out>'
                       f'<pproTicksIn>0</pproTicksIn><file id="file-1"/><sourcetrack><mediatype>audio</mediatype>'
                       f'<trackindex>{ch}</trackindex></sourcetrack><link><linkclipref>v1</linkclipref><mediatype>video'
                       f'</mediatype><trackindex>1</trackindex><clipindex>2</clipindex></link></clipitem>')
X2 = ('<?xml version="1.0"?><xmeml version="5"><sequence id="s"><name>Long</name><duration>60</duration><rate><timebase>25'
      '</timebase><ntsc>FALSE</ntsc></rate><media><video><format><samplecharacteristics><width>1920</width><height>1080'
      '</height></samplecharacteristics></format><track><generatoritem id="g1"><name>Color Matte</name><start>0</start>'
      '<end>10</end></generatoritem><clipitem id="v1"><name>C0002.MXF</name><duration>250</duration><rate><timebase>25'
      '</timebase></rate><start>10</start><end>60</end><in>0</in><out>50</out>' + F2 + MOT + LUM +
      '<link><linkclipref>v1</linkclipref><mediatype>video</mediatype><trackindex>1</trackindex><clipindex>2</clipindex>'
      '</link><link><linkclipref>a1</linkclipref><mediatype>audio</mediatype><trackindex>1</trackindex><clipindex>1'
      '</clipindex><groupindex>1</groupindex></link><labels><label2>Rose</label2></labels></clipitem></track></video>'
      '<audio><track currentExplodedTrackIndex="0" totalExplodedTrackCount="2" premiereTrackType="Mono">' + A(1, 1, 0) +
      '</track><track currentExplodedTrackIndex="1" totalExplodedTrackCount="2" premiereTrackType="Mono">' + A(2, 2, 1) +
      '</track></audio></media><marker><name>Church</name><comment/><in>10</in><out>-1</out></marker></sequence></xmeml>')
src2, out2 = os.path.join(d, "b.xml"), os.path.join(d, "b (DaVinci).xml")
open(src2, "w").write(X2)
r2 = resolve.rewrite(src2, out2, tc=False)
y2 = open(out2).read()
import xml.etree.ElementTree as ET  # noqa: E402
t2 = ET.parse(out2).getroot()
vs = t2.findall("sequence/media/video/track/clipitem")
bad = [w for w in ("premiere", "ppro", "Exploded", "generatoritem", "Lumetri", "<effectid>basic", "<filter") if w in y2]
ok2 = (not bad and len(vs) == 1 and vs[0].get("id") == "C0002.MXF 0" and vs[0].findtext("labels/label2") == "Rose"
       and len(t2.findall("sequence/media/audio/track")) == 2
       and [c.findtext("sourcetrack/trackindex") for c in t2.iter("clipitem") if c.find("sourcetrack") is not None] == ["1", "2"]
       and t2.find("sequence/media/video/track/clipitem/file/timecode/string") is not None
       and t2.findtext("sequence/media/video/track/clipitem/file/media/audio/channelcount") == "4"
       and {(ln.findtext("linkclipref"), ln.findtext("clipindex")) for ln in vs[0].findall("link")}
       == {("C0002.MXF 0", "1"), ("C0002.MXF 1", "1")}
       and t2.findtext("sequence/marker/name") == "Church")
v2 = resolve.verify(out2)
ok2 = ok2 and not v2["errors"]
print("resolve rewrite (from scratch) + check", "OK" if ok2 else "FAILED", bad, r2, v2["errors"])
sys.exit(0 if ok2 else 1)
