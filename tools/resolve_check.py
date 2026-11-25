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
sys.exit(0 if ok else 1)
