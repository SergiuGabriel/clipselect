"""Create Project: the wedding folder -> one timeline the way the owner lays out his footage before the selection.

Measured on his selects (4 July Alexandra & Vlad, 25 July Madalina & Radu): ONE camera after the other on V1 (fx6, fx3,
a74, then the drone), every camera's clips in the order they were filmed, back to back, whole, each with all its sound
channels (FX6 MXF: 4 mono channels on A1-A4, the MP4 cameras: A1-A2, the drone: none), 25 fps 1080p sequence.
The XML (xmeml) is imported into the project he has open in Premiere (drag it into the Project panel) or in DaVinci
Resolve (File > Import > Timeline).
"""
import datetime as _dt
import os
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from xml.sax.saxutils import escape

import core

SEQ_FPS = 25.0
GAP = 10.0                    # seconds of empty timeline between two cameras (you see where a camera starts)
SKIP_DIRS = {".Spotlight-V100", ".Trashes", ".fseventsd", ".TemporaryItems", "System Volume Information", "$RECYCLE.BIN"}
# his folder names (Card Offload makes them) in the order he places them; unknown folders after these, the drone after
# them and folders called trash / gunoi at the very end
ORDER = ["fx6", "fx3", "fx30", "a74", "a7iv", "a7s3", "a7siii", "a7iii", "osmo", "pocket", "gopro"]
DRONE = ("drona", "drone", "mavic", "dji", "avata")
TRASH = ("trash", "gunoi")


def _skip(p):
    """Proxies and previews never go on the timeline."""
    if p.name.startswith(".") or p.suffix.lower() not in core.VIDEO_EXT:
        return True
    if p.parent.name.upper() == "SUB" and p.stem.upper().endswith("S03"):     # Sony proxy (SUB/C0001S03.MP4)
        return True
    return False


def _videos(folder):
    out = []
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")
                             and d.upper() not in ("PROXY", "PROXIES"))
        for f in filenames:
            p = Path(dirpath) / f
            if not _skip(p):
                out.append(str(p))
    return out


def rank(name):
    n = name.lower().strip()
    if any(t in n for t in TRASH):
        return (4, 0, n)
    if n in ORDER:
        return (0, ORDER.index(n), n)
    if "osmo" in n:
        return (0, ORDER.index("osmo"), n)
    if any(n == d or n.startswith(d) for d in DRONE):
        return (2, 0, n)
    return (1, 0, n)


def find_cameras(root):
    """[dict(name, folder, files)] in his order. A camera = a first-level folder of the wedding folder holding video
    (lavaliere / recorder hold only sound and are left out, like in his selects). Video lying directly in the chosen
    folder is one camera named after the folder."""
    root = Path(root)
    cams = []
    try:
        subs = sorted(d for d in root.iterdir() if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith("."))
    except OSError:
        return []
    for d in subs:
        fs = _videos(d)
        if fs:
            cams.append(dict(name=d.name, folder=str(d), files=fs))
    loose = [str(p) for p in root.iterdir() if p.is_file() and not _skip(p)]
    if loose:
        cams.append(dict(name=root.name, folder=str(root), files=sorted(loose)))
    # one folder holding the camera folders (e.g. "Video/fx6", "Video/fx3"): use its camera folders
    if len(cams) == 1 and cams[0]["folder"] != str(root):
        inner = find_cameras(cams[0]["folder"])
        if len(inner) > 1:
            cams = inner
    cams.sort(key=lambda c: rank(c["name"]))
    return cams


AUDIO = {".wav", ".bwf", ".mp3", ".m4a", ".aif", ".aiff", ".flac"}


def sound_folders(root):
    """First-level folders with sound but no video (recorder, lavaliere): shown, not put on the timeline."""
    out = []
    try:
        subs = sorted(d for d in Path(root).iterdir() if d.is_dir() and not d.name.startswith("."))
    except OSError:
        return out
    for d in subs:
        has_a = has_v = False
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = [x for x in dirnames if not x.startswith(".")]
            for f in filenames:
                ext = Path(f).suffix.lower()
                has_a |= ext in AUDIO
                has_v |= ext in core.VIDEO_EXT and not f.startswith(".")
            if has_v:
                break
        if has_a and not has_v:
            out.append(d.name)
    return out


def probe(path):
    """Duration, picture, frame rate, sound channels and the camera's recording time of one file (one FFmpeg call)."""
    import subprocess
    r = subprocess.run([core.ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace",
                       **core._NOWIN)
    t = r.stderr
    vline = next((l for l in t.splitlines() if " Video:" in l and "attached pic" not in l), None)
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", t)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    info = dict(video=vline is not None, dur=dur, fps=25.0, w=1920, h=1080, arate=48000, ach=0, ctime=None)
    if vline:
        body = vline.split("Video:", 1)[1]
        mm = re.search(r",\s*(\d{2,5})x(\d{2,5})", body)
        if mm:
            info["w"], info["h"] = int(mm.group(1)), int(mm.group(2))
        mm = re.search(r"([\d.]+)\s*fps", body) or re.search(r"([\d.]+)\s*tbr", body)
        if mm:
            info["fps"] = float(mm.group(1))
    ch = 0
    for mm in re.finditer(r"Stream #\d+:\d+.*?: Audio:.*?(\d+) Hz, ([^,\n]+)", t):
        if ch == 0:
            info["arate"] = int(mm.group(1))
        lay = mm.group(2).strip()
        n = re.match(r"(\d+) channels?", lay)
        ch += 1 if lay == "mono" else 2 if lay == "stereo" else int(n.group(1)) if n else 6 if lay.startswith("5.1") else 2
    info["ach"] = min(ch, 8)
    mm = re.search(r"^\s*creation_time\s*:\s*(\d{4})-(\d\d)-(\d\d)[T ](\d\d):(\d\d):(\d\d)", t, re.M)
    if mm and int(mm.group(1)) >= 2005:
        try:
            info["ctime"] = _dt.datetime(*map(int, mm.groups())).timestamp()
        except ValueError:
            pass
    try:
        info["mtime"] = os.path.getmtime(path)
    except OSError:
        info["mtime"] = 0.0
    return info


def _natural(path):
    return [int(x) if x.isdigit() else x.lower() for x in re.split(r"(\d+)", Path(path).name)]


def chrono(files, infos):
    """The order the camera filmed them: its own recording time when EVERY clip has it (one camera = one clock), else
    the file date (copies keep it), the file name (C9378, C9379...) when two are equal."""
    if files and all(infos[f].get("ctime") for f in files):
        key = lambda f: (infos[f]["ctime"], _natural(f))
    else:
        key = lambda f: (infos[f].get("mtime", 0.0), _natural(f))
    return sorted(files, key=key)


def read_all(cams, progress=None, cancel=None, jobs=6):
    """Reads every clip once (several at a time: on a disk this is mostly waiting)."""
    allf = [f for c in cams for f in c["files"]]
    infos, done = {}, 0
    with ThreadPoolExecutor(max_workers=jobs) as ex:
        futs = {f: ex.submit(probe, f) for f in allf}
        for f in allf:
            if cancel and cancel():
                for x in futs.values():
                    x.cancel()
                raise InterruptedError("Cancelled")
            try:
                infos[f] = futs[f].result()
            except Exception:
                infos[f] = dict(video=False, dur=0.0)
            done += 1
            if progress and (done % 5 == 0 or done == len(allf)):
                progress(f"Reading the clips: {done} of {len(allf)}", done / max(1, len(allf)))
    return infos


def layout(cams, infos, gap=GAP):
    """[(camera name, [(path, start frame, length in frames)])] at 25 fps, plus the clips that could not be read."""
    sf, pos, out, bad = SEQ_FPS, 0, [], []
    for c in cams:
        ok = [f for f in c["files"] if infos.get(f, {}).get("video") and int(infos[f]["dur"] * sf) >= 1]
        bad += [f for f in c["files"] if f not in ok]
        row = []
        for f in chrono(ok, infos):
            n = int(infos[f]["dur"] * sf + 1e-6)          # never past the end of the file
            row.append((f, pos, n))
            pos += n
        if row:
            out.append((c["name"], row))
            pos += round(gap * sf)
    return out, bad


def export_xml(lay, infos, out_path, name):
    """One 25 fps sequence: every clip whole on V1, its sound channel k on track Ak (source channel k), LINKED to the
    picture (link = clip's track + its position in that track, the sound in one group)."""
    rate_xml, sf = core._rate(SEQ_FPS)
    clips = [(f, st, n) for _, row in lay for f, st, n in row]
    if not clips:
        raise ValueError("No video clips to put on the timeline.")
    first = lay[0][1]
    sizes = {}
    for f, _, _ in first:
        k = (infos[f]["w"], infos[f]["h"])
        sizes[k] = sizes.get(k, 0) + 1
    sw, sh = max(sizes, key=sizes.get)                   # the main camera's picture size (his: 1920x1080)
    nach = max([infos[f]["ach"] for f, _, _ in clips] + [0])
    ids, n = {}, 0
    for ci, (f, st, ln) in enumerate(clips, 1):
        n += 1
        ids[("v", ci)] = (f"clipitem-{n}", 1, ci)
    for k in range(1, nach + 1):
        pos = 0
        for ci, (f, st, ln) in enumerate(clips, 1):
            if infos[f]["ach"] >= k:
                pos += 1
                n += 1
                ids[("a", k, ci)] = (f"clipitem-{n}", k, pos)
    files = {}

    def file_xml(f):
        if f in files:
            return f'<file id="{files[f]}"/>'
        files[f] = f"file-{len(files) + 1}"
        i = infos[f]
        frate, ffps = core._rate(i["fps"])
        aud = (f'<audio><samplecharacteristics><depth>16</depth><samplerate>{i["arate"]}</samplerate></samplecharacteristics>'
               f'<channelcount>{i["ach"]}</channelcount></audio>') if i["ach"] else ""
        return (f'<file id="{files[f]}"><name>{escape(Path(f).name)}</name><pathurl>{escape(core._url(f))}</pathurl>'
                f'{frate}<duration>{int(i["dur"] * ffps)}</duration><media><video>{core._sc(frate, i["w"], i["h"], "none")}'
                f'</video>{aud}</media></file>')

    def links(ci, f):
        if not infos[f]["ach"]:
            return ""
        v = ids[("v", ci)]
        out = [f'<link><linkclipref>{v[0]}</linkclipref><mediatype>video</mediatype><trackindex>1</trackindex>'
               f'<clipindex>{v[2]}</clipindex></link>']
        for k in range(1, infos[f]["ach"] + 1):
            a = ids[("a", k, ci)]
            out.append(f'<link><linkclipref>{a[0]}</linkclipref><mediatype>audio</mediatype><trackindex>{k}</trackindex>'
                       f'<clipindex>{a[2]}</clipindex><groupindex>1</groupindex></link>')
        return "".join(out)

    def head(cid, f, st, ln):
        return (f'<clipitem id="{cid}"><name>{escape(Path(f).name)}</name><duration>{ln}</duration>{rate_xml}'
                f'<start>{st}</start><end>{st + ln}</end><in>0</in><out>{ln}</out>')

    vx = [head(ids[("v", ci)][0], f, st, ln) + file_xml(f) + links(ci, f) + "</clipitem>"
          for ci, (f, st, ln) in enumerate(clips, 1)]
    ax = []
    for k in range(1, nach + 1):
        items = [head(ids[("a", k, ci)][0], f, st, ln) + file_xml(f) +
                 f'<sourcetrack><mediatype>audio</mediatype><trackindex>{k}</trackindex></sourcetrack>' + links(ci, f) +
                 "</clipitem>" for ci, (f, st, ln) in enumerate(clips, 1) if infos[f]["ach"] >= k]
        ax.append(items)
    total = clips[-1][1] + clips[-1][2]
    arate = next((infos[f]["arate"] for f, _, _ in clips if infos[f]["ach"]), 48000)
    trk = lambda its: f'<track>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    audio = (f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
             f'<samplerate>{arate}</samplerate></samplecharacteristics></format>{"".join(trk(a) for a in ax)}</audio>')
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}'
           f'<media><video><format>{core._sc(rate_xml, sw, sh, "none")}</format>{trk(vx)}</video>{audio}</media>'
           f'</sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return dict(clips=len(clips), cameras=[(c, len(r)) for c, r in lay], seconds=total / sf)


def free_path(p):
    p = Path(p)
    if not p.exists():
        return p
    i = 2
    while True:
        q = p.with_name(f"{p.stem} ({i}){p.suffix}")
        if not q.exists():
            return q
        i += 1
