"""The Premiere bridge: a small CEP extension (premiere_bridge/) installed into Premiere Pro that picks up jobs the app
leaves in a folder: import an XML into the open project, open its sequence, put an adjustment layer with Crop on top
(File > New > Adjustment Layer through the menu, then the WarpAutomation steps). An XML cannot carry an adjustment layer
(it imports as Black Video), so this is the only way to get the same result as his WarpAutomation button.
Two copies run in Premiere (the visible panel Window > Extensions > MoneyMakingMachine and an invisible worker that
starts with Premiere); a job is claimed by renaming it."""
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

VERSION = "1.0.0"
BUNDLE = "MoneyMakingMachine"


def _src():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    return base / "premiere_bridge"


def base():
    if os.environ.get("MMM_BRIDGE"):
        return Path(os.environ["MMM_BRIDGE"])
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "MoneyMakingMachine Bridge"
    return Path.home() / "Library" / "Application Support" / "MoneyMakingMachine Bridge"


def ext_dir():
    if os.environ.get("MMM_CEP"):
        return Path(os.environ["MMM_CEP"]) / BUNDLE
    if sys.platform == "win32":
        return Path(os.environ.get("APPDATA", Path.home())) / "Adobe" / "CEP" / "extensions" / BUNDLE
    return Path.home() / "Library" / "Application Support" / "Adobe" / "CEP" / "extensions" / BUNDLE


def installed_version():
    try:
        m = (ext_dir() / "CSXS" / "manifest.xml").read_text("utf-8")
        i = m.index('ExtensionBundleVersion="') + 24
        return m[i:m.index('"', i)]
    except Exception:
        return ""


def install(force=False):
    """Copy the extension into Premiere's CEP folder and allow unsigned extensions (PlayerDebugMode, like his
    WarpAutomation installer). Returns True when something was (re)installed; Premiere must be restarted then."""
    src = _src()
    if not src.is_dir():
        raise RuntimeError("the Premiere bridge files are missing from this app")
    if not force and installed_version() == VERSION:
        return False
    d = ext_dir()
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)
    shutil.copytree(src, d)
    if sys.platform == "darwin" and not os.environ.get("MMM_CEP"):
        for v in range(9, 15):
            subprocess.run(["defaults", "write", f"com.adobe.CSXS.{v}", "PlayerDebugMode", "1"],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        subprocess.run(["xattr", "-cr", str(d)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    elif sys.platform == "win32" and not os.environ.get("MMM_CEP"):
        for v in range(9, 15):
            subprocess.run(["reg", "add", rf"HKCU\Software\Adobe\CSXS.{v}", "/v", "PlayerDebugMode", "/t", "REG_SZ",
                            "/d", "1", "/f"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return True


def alive(within=30):
    """True when the bridge ran inside Premiere in the last `within` seconds."""
    try:
        return time.time() - int((base() / "alive").read_text()) / 1000 < within
    except Exception:
        return False


def send(xml=None, name="", crop=None):
    """Leave a job for Premiere. Returns its id (result() reads the answer)."""
    jid = time.strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:6]
    job = {"xml": str(xml) if xml else "", "name": name}
    if crop is not None:                    # an adjustment layer on top with Crop crop % top / bottom
        job["adjust"] = {"crop": float(crop)}
    d = base() / "jobs"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (jid + ".tmp")
    tmp.write_text(json.dumps(job), "utf-8")
    os.replace(tmp, d / (jid + ".json"))
    return jid


def result(jid):
    """The bridge's answer {ok, msg}, or None while it is not done."""
    f = base() / "done" / (jid + ".json")
    try:
        return json.loads(f.read_text("utf-8"))
    except Exception:
        return None


def pending(jid):
    d = base() / "jobs"
    return (d / (jid + ".json")).exists() or (d / (jid + ".run")).exists()


def cancel(jid):
    try:
        (base() / "jobs" / (jid + ".json")).unlink()
    except Exception:
        pass
