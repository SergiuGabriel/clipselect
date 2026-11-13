"""Card offload (like Hailo's): every card at once, verified file by file, a report written next to the footage.

Safety rules: the card is only READ (never renamed, changed or deleted); a file already at the destination is never
overwritten (identical -> skipped as already there, different -> the copy gets " (2)"); a copy is first written as
.part and renamed only when it is complete; with "verify", the copy is read back from the destination and its checksum
compared with the card's. The file dates are kept (the app reads the day's order from them).
"""
import hashlib
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

CHUNK = 8 << 20
SKIP_DIRS = {".Spotlight-V100", ".Trashes", ".fseventsd", ".TemporaryItems", "System Volume Information", "$RECYCLE.BIN"}
PROXY = {".lrf", ".lrv", ".thm"}
SYSTEM_VOLUMES = {"Macintosh HD", "Macintosh HD - Data", "Recovery", "Preboot", "VM", "Update", "com.apple.TimeMachine.localsnapshots"}


def cards():
    """The cards / drives plugged in now (macOS: /Volumes; Windows: removable drive letters)."""
    out = []
    if sys.platform == "darwin" or os.environ.get("MMM_VOLUMES"):
        root = Path(os.environ.get("MMM_VOLUMES") or "/Volumes")
        for v in sorted(root.iterdir()) if root.exists() else []:
            if v.name in SYSTEM_VOLUMES or v.name.startswith(".") or not v.is_dir():
                continue
            try:
                if v.resolve() == Path("/"):
                    continue
            except OSError:
                continue
            out.append(v)
    elif os.name == "nt":
        import string
        for d in string.ascii_uppercase[3:]:
            p = Path(f"{d}:/")
            if p.exists():
                out.append(p)
    return out


def card_info(path):
    """What tells two cards apart: capacity, space used, the card's model and how it is plugged in (macOS: diskutil)."""
    info = dict(total=None, used=None, media="", protocol="", fs="")
    try:
        u = shutil.disk_usage(path)
        info.update(total=u.total, used=u.used)
    except OSError:
        pass
    if sys.platform == "darwin" and str(path).startswith("/Volumes/"):
        try:
            import plistlib
            out = subprocess.run(["diskutil", "info", "-plist", str(path)], capture_output=True, timeout=5).stdout
            d = plistlib.loads(out) if out else {}
            info.update(media=(d.get("MediaName") or d.get("IORegistryEntryName") or "").strip(),
                        protocol=d.get("BusProtocol") or "", fs=d.get("FilesystemName") or "")
        except Exception:
            pass
    return info


def fingerprint(source, limit=4000):
    """The cards of a camera that records on two slots hold the same files: names + sizes of the clips."""
    return frozenset((str(r), s) for r, s in scan(source)[:limit])


def scan(source, skip_proxies=False):
    """Every file to copy on a card / folder: (relative path, size)."""
    source = Path(source)
    files = []
    for dirpath, dirnames, filenames in os.walk(source):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith("."))
        for f in sorted(filenames):
            if f.startswith(".") or f in ("Thumbs.db", "desktop.ini"):
                continue
            if skip_proxies and Path(f).suffix.lower() in PROXY:
                continue
            p = Path(dirpath) / f
            try:
                files.append((p.relative_to(source), p.stat().st_size))
            except OSError:
                continue
    return files


def _hash(path, cancel=None, on_bytes=None):
    h = hashlib.blake2b(digest_size=16)
    with open(path, "rb") as f:
        while True:
            if cancel and cancel():
                raise InterruptedError("Cancelled")
            b = f.read(CHUNK)
            if not b:
                break
            h.update(b)
            if on_bytes:
                on_bytes(len(b))
    return h.hexdigest()


def _free_name(dest):
    k = 2
    while True:
        cand = dest.with_name(f"{dest.stem} ({k}){dest.suffix}")
        if not cand.exists():
            return cand
        k += 1


def offload(source, dest_dir, verify=True, keep_folders=True, skip_proxies=False, report=True,
            progress=None, cancel=None, on_file=None):
    """Copy one card into dest_dir. progress(done_bytes, total_bytes, current file); on_file(rel, status) with status
    'copied', 'verified', 'already there', 'renamed', 'FAILED: ...'. Returns the summary."""
    source, dest_dir = Path(source), Path(dest_dir)
    files = scan(source, skip_proxies)
    total = sum(s for _, s in files) * (2 if verify else 1)
    done = [0]
    t0 = time.time()

    def tick(n, name=""):
        done[0] += n
        if progress:
            progress(done[0], total, name)
    rows, counts = [], dict(copied=0, verified=0, already=0, renamed=0, failed=0)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for rel, size in files:
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        src = source / rel
        dst = dest_dir / (rel if keep_folders else rel.name)
        status, digest, part = "", "", None
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            if dst.exists():
                if dst.stat().st_size == size and _hash(dst, cancel) == _hash(src, cancel):
                    status = "already there"
                    counts["already"] += 1
                    tick(size * (2 if verify else 1), rel.name)
                    rows.append((str(rel), size, "", status))
                    if on_file:
                        on_file(str(rel), status)
                    continue
                dst = _free_name(dst)                     # never overwrite: a different file of the same name
                counts["renamed"] += 1
            part = dst.with_name(dst.name + ".part")
            h = hashlib.blake2b(digest_size=16)
            with open(src, "rb") as fi, open(part, "wb") as fo:     # the card is only read
                while True:
                    if cancel and cancel():
                        raise InterruptedError("Cancelled")
                    b = fi.read(CHUNK)
                    if not b:
                        break
                    fo.write(b)
                    h.update(b)
                    tick(len(b), rel.name)
                fo.flush()
                os.fsync(fo.fileno())
            digest = h.hexdigest()
            shutil.copystat(src, part)                    # the file dates stay (the day's order is read from them)
            part.replace(dst)
            counts["copied"] += 1
            status = "copied"
            if verify:
                if _hash(dst, cancel, lambda n: tick(n, rel.name)) != digest:
                    raise IOError("the copy differs from the card")
                counts["verified"] += 1
                status = "verified"
        except InterruptedError:
            if part is not None and part.exists():
                part.unlink()                             # no half copy is left behind
            raise
        except Exception as e:
            counts["failed"] += 1
            status = f"FAILED: {e}"
        rows.append((str(dst.relative_to(dest_dir)) if dst else str(rel), size, digest, status))
        if on_file:
            on_file(str(rel), status)
    took = time.time() - t0
    summary = dict(source=str(source), dest=str(dest_dir), files=len(files), bytes=sum(s for _, s in files),
                   seconds=round(took, 1), **counts)
    if report:
        lines = ["Card offload report - MoneyMakingMachine", f"Card:        {source}", f"Destination: {dest_dir}",
                 f"Date:        {time.strftime('%Y-%m-%d %H:%M')}",
                 f"Files: {len(files)}, {summary['bytes'] / 1e9:.2f} GB in {took / 60:.1f} min",
                 f"Copied {counts['copied']}, verified {counts['verified']}, already there {counts['already']}, "
                 f"renamed (a different file had the name) {counts['renamed']}, FAILED {counts['failed']}",
                 "", "file\tbytes\tchecksum (blake2b)\tstatus"]
        lines += [f"{r}\t{s}\t{d}\t{st}" for r, s, d, st in rows]
        (dest_dir / "_offload_report.txt").write_text("\n".join(lines), encoding="utf-8")
    return summary


def eject(volume):
    """Eject a card when everything on it is copied (macOS)."""
    if sys.platform == "darwin":
        subprocess.run(["diskutil", "eject", str(volume)], capture_output=True)


# ---------------------------------------------------------------- which card is which
MONTHS = ["IANUARIE", "FEBRUARIE", "MARTIE", "APRILIE", "MAI", "IUNIE", "IULIE", "AUGUST", "SEPTEMBRIE", "OCTOMBRIE",
          "NOIEMBRIE", "DECEMBRIE"]
FOLDERS = ["fx6", "fx3", "a74", "osmo", "recorder", "lavaliere/lav 1", "lavaliere/lav 2", "drona"]
SONY = {"ILME-FX6": "fx6", "ILME-FX6V": "fx6", "ILME-FX6T": "fx6", "ILME-FX3": "fx3", "ILME-FX30": "fx30", "ILCE-7M4": "a74",
        "ILCE-7SM3": "a7s3", "ILCE-7M3": "a73", "ILCE-1": "a1", "ILCE-7RM5": "a7r5", "ILCE-7CM2": "a7c2", "ILME-FR7": "fr7"}


def wedding_name(day, month, bride, groom, year):
    """His folder name: NUNTA 4 IULIE Alexandra si Vlad 2026."""
    return f"NUNTA {int(day)} {MONTHS[int(month) - 1]} {bride.strip()} si {groom.strip()} {int(year)}"


def _files(vol, limit=4000):
    out = []
    for dirpath, dirnames, filenames in os.walk(vol):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        for f in filenames:
            if not f.startswith("."):
                out.append(Path(dirpath) / f)
                if len(out) >= limit:
                    return out
    return out


def identify(vol):
    """(what it is, the folder it goes to) from the files on the card."""
    files = _files(vol)
    names = [p.name for p in files]
    for p in files:                                   # Sony writes the exact model next to every clip
        if p.suffix.upper() == ".XML" and p.stat().st_size < 200000:
            try:
                t = p.read_text("utf-8", errors="ignore")
            except OSError:
                continue
            for model, folder in SONY.items():
                if f'modelName="{model}"' in t:
                    return f"Sony {model}", folder
            if "modelName=" in t and "Sony" in t:
                m = t.split('modelName="', 1)[1].split('"', 1)[0]
                return f"Sony {m}", m.lower()
    if any("Wireless_PRO" in n or "WIRELESS_PRO" in n.upper() for n in names):
        return "RODE Wireless PRO", "lavaliere"
    if any(n.upper().startswith("REC") and n.upper().endswith(".WAV") for n in names):
        return "lavalier", "lavaliere"
    if any(n.upper().startswith(("ZOOM", "TASCAM", "STE-", "DR-")) for n in names) or \
            (names and sum(n.upper().endswith(".WAV") for n in names) > 0.8 * len(names)):
        return "recorder", "recorder"
    dji = [p for p in files if p.name.upper().startswith("DJI_") and p.suffix.upper() in (".MP4", ".MOV")]
    if dji:
        try:
            out = subprocess.run([core_ffprobe(), "-v", "error", "-show_entries", "format_tags", "-of", "default=nw=1",
                                  str(dji[0])], capture_output=True, text=True, timeout=10).stdout.lower()
        except Exception:
            out = ""
        if any(k in out for k in ("osmo", "pocket", "action")):
            return "DJI Osmo", "osmo"
        return "DJI drone", "drona"
    return "", ""


def core_ffprobe():
    import core
    ff = core.ffmpeg_exe()
    probe = Path(ff).with_name(Path(ff).name.replace("ffmpeg", "ffprobe"))
    return str(probe) if probe.exists() else "ffprobe"


def media_info(vol):
    """Card type as macOS reports it (CFexpress / SD ...), and its size."""
    total = used = 0
    try:
        u = shutil.disk_usage(vol)
        total, used = u.total, u.used
    except OSError:
        pass
    kind = ""
    if sys.platform == "darwin":
        try:
            import plistlib
            r = subprocess.run(["diskutil", "info", "-plist", str(vol)], capture_output=True, timeout=10)
            d = plistlib.loads(r.stdout)
            kind = " · ".join(x for x in (d.get("MediaName") or "", d.get("BusProtocol") or "") if x)
            total = d.get("TotalSize") or total
        except Exception:
            pass
    return dict(total=total, used=used, kind=kind)


def _sample(p):
    """A fingerprint of a file's CONTENT (its start, middle and end): names and sizes alone are not enough (two
    lavaliers started together write files with the same names and lengths)."""
    h = hashlib.blake2b(digest_size=12)
    n = p.stat().st_size
    with open(p, "rb") as f:
        for at in (0, n // 2, max(0, n - 65536)):
            f.seek(at)
            h.update(f.read(65536))
    return h.hexdigest()


def signature(vol, sampled=6):
    """What is on a card: names, sizes and the content fingerprint of a few of its biggest files. Two cards with the
    same signature hold the same clips (a backup pair recorded on two slots)."""
    files = [p for p in _files(vol, 20000) if p.suffix.lower() not in PROXY]
    big = {p for p in sorted(files, key=lambda p: -p.stat().st_size)[:sampled]}
    out = set()
    for p in files:
        try:
            out.add((str(p.relative_to(vol)), p.stat().st_size, _sample(p) if p in big else ""))
        except OSError:
            continue
    return out


def same_clips(a, b):
    """The same clips: 90 % of the files match by name and size AND every sampled file matches by content."""
    if not a or not b:
        return False
    plain = lambda sig: {(r, n) for r, n, _ in sig}
    if len(plain(a) & plain(b)) < 0.9 * max(len(a), len(b)):
        return False
    fa = {(r, n): h for r, n, h in a if h}
    fb = {(r, n): h for r, n, h in b if h}
    common = set(fa) & set(fb)
    return bool(common) and all(fa[k] == fb[k] for k in common)


def read_speed(vol, mb=96):
    """How fast the card reads (MB/s), from its biggest file: tells which of two backup cards is the fast one."""
    files = [p for p in _files(vol, 2000) if p.suffix.lower() not in PROXY]
    if not files:
        return 0.0
    big = max(files, key=lambda p: p.stat().st_size)
    want = min(big.stat().st_size, mb << 20)
    if want < (4 << 20):
        return 0.0
    t = time.time()
    got = 0
    with open(big, "rb", buffering=0) as f:
        f.seek(max(0, big.stat().st_size // 3))
        while got < want:
            b = f.read(4 << 20)
            if not b:
                break
            got += len(b)
    return got / 1e6 / max(1e-3, time.time() - t)


def verify_only(source, dest_dir, progress=None, cancel=None):
    """A backup card: nothing is copied, every file on it is compared with the copy already at the destination."""
    source, dest_dir = Path(source), Path(dest_dir)
    files = scan(source, skip_proxies=True)
    total = sum(s for _, s in files) * 2
    done = [0]
    ok = bad = missing = 0
    rows = []
    for rel, size in files:
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        dst = dest_dir / rel
        if not dst.exists():
            dst = dest_dir / rel.name
        if not dst.exists():
            missing += 1
            rows.append((str(rel), size, "MISSING at the destination"))
            done[0] += 2 * size
            continue
        same = dst.stat().st_size == size and _hash(source / rel, cancel) == _hash(dst, cancel)
        done[0] += 2 * size
        if progress:
            progress(done[0], total, rel.name)
        if same:
            ok += 1
            rows.append((str(rel), size, "same as the copy"))
        else:
            bad += 1
            rows.append((str(rel), size, "DIFFERENT from the copy"))
    return dict(source=str(source), dest=str(dest_dir), files=len(files), bytes=sum(s for _, s in files), same=ok,
                different=bad, missing=missing, rows=rows)
