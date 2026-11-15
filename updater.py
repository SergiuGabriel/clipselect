"""Check for updates + download inside the app (owner's wish: people never see where the app comes from, no browser,
no address shown). The address is kept encoded so it does not show up as plain text in the packed app.

Check: the releases API; if it refuses (rate limit, network filter), the public 'latest release' page, whose redirect
names the newest tag. Download: the file for THIS computer (Apple Silicon / Intel DMG, Windows zip) into Downloads,
streamed with progress, then opened (the DMG mounts and shows its window with the Applications link)."""
import base64
import json
import os
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

_S = "dGNlbGVzcGlsYy9sZWlyYmFHdWlncmVT"
UA = {"User-Agent": "MoneyMakingMachine"}
ASSETS = {"arm": "MoneyMakingMachine-Apple-Silicon-M1-M2-M3-M4.dmg", "intel": "MoneyMakingMachine-Mac-Intel.dmg",
          "win": "MoneyMakingMachine-Windows.zip"}


def _src():
    return base64.b64decode(_S).decode()[::-1]


def _ctx():
    try:                                  # the packed app has no system certificates: bring our own (certifi)
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def kind():
    """Which file this computer needs."""
    if sys.platform == "darwin":
        try:
            arm = subprocess.run(["sysctl", "-n", "hw.optional.arm64"], capture_output=True, text=True,
                                 timeout=5).stdout.strip() == "1"     # true on Apple Silicon even under Rosetta
        except Exception:
            import platform
            arm = platform.machine() == "arm64"
        return "arm" if arm else "intel"
    return "win"


def _clean(e):
    """An error message that never names the server."""
    if isinstance(e, urllib.error.HTTPError):
        return f"HTTP {e.code}"
    if isinstance(e, urllib.error.URLError):
        r = str(getattr(e, "reason", e))
        return "certificate" if "CERTIFICATE" in r.upper() or "SSL" in r.upper() else "no connection"
    return type(e).__name__


def latest():
    """dict(tag, url of the file for this computer). Raises RuntimeError(short reason) when both ways fail."""
    src, want = _src(), ASSETS[kind()]
    errs = []
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{src}/releases/latest",
                                     headers={**UA, "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=12, context=_ctx()) as r:
            d = json.loads(r.read().decode("utf-8"))
        tag = d.get("tag_name", "")
        url = next((a.get("browser_download_url") for a in d.get("assets", []) if a.get("name") == want), None)
        if tag:
            return dict(tag=tag, url=url or f"https://github.com/{src}/releases/download/{tag}/{want}")
    except Exception as e:
        errs.append(_clean(e))
    try:                                  # no API: the 'latest' page redirects to .../releases/tag/vX.Y.Z
        req = urllib.request.Request(f"https://github.com/{src}/releases/latest", headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=12, context=_ctx()) as r:
            final = r.geturl()
        m = re.search(r"/releases/tag/(v[\d.]+)", final)
        if m:
            return dict(tag=m.group(1), url=f"https://github.com/{src}/releases/download/{m.group(1)}/{want}")
        errs.append("no version published yet")
    except Exception as e:
        errs.append(_clean(e))
    raise RuntimeError(" / ".join(dict.fromkeys(errs)))


def download(url, tag, progress=None, cancel=None):
    """Streams the file into Downloads (.part, renamed when complete). Returns the path."""
    name = ASSETS[kind()].replace("MoneyMakingMachine-", f"MoneyMakingMachine-{tag}-")
    folder = Path.home() / "Downloads"
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        import tempfile
        folder = Path(tempfile.gettempdir())
    out = folder / name
    part = out.with_name(out.name + ".part")
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ctx()) as r, open(part, "wb") as f:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                if cancel and cancel():
                    raise InterruptedError("Cancelled")
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
                got += len(b)
                if progress:
                    progress(got, total)
        if total and got < total:
            raise RuntimeError("the download was cut off")
        os.replace(part, out)
        return str(out)
    except (urllib.error.URLError, urllib.error.HTTPError) as e:
        part.unlink(missing_ok=True)
        raise RuntimeError(_clean(e)) from None
    except OSError:
        part.unlink(missing_ok=True)
        raise RuntimeError("could not write the file (is the disk full?)") from None
    except BaseException:
        part.unlink(missing_ok=True)
        raise


def open_installer(path):
    if sys.platform == "darwin":
        subprocess.Popen(["open", path])                       # mounts the DMG and shows its window
    elif os.name == "nt":
        subprocess.Popen(["explorer", "/select,", path])
    else:
        subprocess.Popen(["xdg-open", str(Path(path).parent)])
