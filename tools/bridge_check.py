"""The Premiere bridge: installs into a test CEP folder, a job goes in, a fake answer comes back; the extension files
parse (manifest XML, the panel's JavaScript)."""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
tmp = Path(tempfile.mkdtemp())
os.environ["MMM_CEP"] = str(tmp / "cep")
os.environ["MMM_BRIDGE"] = str(tmp / "bridge")
import bridge  # noqa: E402

ET.parse(ROOT / "premiere_bridge" / "CSXS" / "manifest.xml")
m = (ROOT / "premiere_bridge" / "CSXS" / "manifest.xml").read_text()
assert f'ExtensionBundleVersion="{bridge.VERSION}"' in m, "manifest version != bridge.VERSION"
if shutil.which("node"):
    for f in ("js/main.js",):
        subprocess.run(["node", "-e", f"new Function(require('fs').readFileSync('{ROOT / 'premiere_bridge' / f}','utf8'))"],
                       check=True)
assert bridge.installed_version() == ""
assert bridge.install() is True
assert bridge.installed_version() == bridge.VERSION
assert bridge.install() is False                     # already there
assert (tmp / "cep" / "MoneyMakingMachine" / "jsx" / "host.jsx").exists()
jid = bridge.send("/x/film.xml", "Film", 10.0)
job = json.loads((tmp / "bridge" / "jobs" / (jid + ".json")).read_text())
assert job == {"xml": "/x/film.xml", "name": "Film", "adjust": {"crop": 10.0}}, job
assert bridge.pending(jid) and bridge.result(jid) is None
(tmp / "bridge" / "done").mkdir(parents=True)
(tmp / "bridge" / "done" / (jid + ".json")).write_text(json.dumps({"ok": True, "msg": "x"}))
assert bridge.result(jid)["ok"]
j2 = bridge.send("/x/a.xml", "A")
assert "adjust" not in json.loads((tmp / "bridge" / "jobs" / (j2 + ".json")).read_text())
bridge.cancel(j2)
assert not bridge.pending(j2)
print("bridge check ok")
