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
GAP = 1200.0                  # 20 min of empty timeline between two cameras (owner: you must see where one starts)
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


def all_folders(root):
    """Every folder of the wedding: the camera folders (find_cameras) and the sound folders (lavaliere, recorder:
    sound=True), owner: "everything that is in the wedding folder goes into the project"."""
    return find_cameras(root) + [dict(c, sound=True) for c in sound_files(root)]


def groups(ach):
    """The sound of a file the way Premiere lays it out (measured on his Premiere exports and his reference sequence
    "cum trebuie sa arate cadrele ca si sunet si setari"): the channels in STEREO PAIRS, one track per pair
    (FX6 4 channels = A1 stereo 1+2, A2 stereo 3+4; FX3 / A7 / osmo 2 channels = ONE stereo track), an odd last
    channel = a mono track (a mono lavalier = one mono track). -> [("stereo", [1, 2]), ("mono", [3])...]"""
    out = [("stereo", [k, k + 1]) for k in range(1, ach, 2)]
    if ach % 2:
        out.append(("mono", [ach]))
    return out


def _file_xml(f, i, files):
    """The <file> of a clip, written whole the first time, then <file id/>. The sound described like Premiere does:
    more than 2 channels -> pproOriginalAudio with all of them, then one <audio> per stereo pair / mono channel."""
    if f in files:
        return f'<file id="{files[f]}"/>'
    files[f] = f"file-{len(files) + 1}"
    frate, ffps = core._rate(i["fps"] if i.get("video") else SEQ_FPS)
    sc = f'<samplecharacteristics><depth>16</depth><samplerate>{i.get("arate", 48000)}</samplerate></samplecharacteristics>'
    aud = ""
    if i.get("ach"):
        if i["ach"] > 2:
            aud += f'<pproOriginalAudio>{sc}<channelcount>{i["ach"]}</channelcount></pproOriginalAudio>'
        aud += "".join(f'<audio>{sc}<channelcount>{len(chs)}</channelcount></audio>' for _k, chs in groups(i["ach"]))
    vid = f'<video>{core._sc(frate, i["w"], i["h"], "none")}</video>' if i.get("video") else ""
    return (f'<file id="{files[f]}"><name>{escape(Path(f).name)}</name><pathurl>{escape(core._url(f))}</pathurl>'
            f'{frate}<duration>{int(i["dur"] * ffps)}</duration><media>{vid}{aud}</media></file>')


def _track_attrs(kind, ex):
    """Premiere's exploded-track attributes: a stereo track = two xmeml tracks (index 0 and 1 of 2)."""
    n = 2 if kind == "stereo" else 1
    return f' currentExplodedTrackIndex="{ex}" totalExplodedTrackCount="{n}" premiereTrackType="Mono"'


def _master(f, i, mid, files):
    """A bin clip (master clip): picture + its sound in stereo pairs / mono, exactly like the timeline."""
    frate, ffps = core._rate(i["fps"] if i.get("video") else SEQ_FPS)
    nm = escape(Path(f).name)
    fx = _file_xml(f, i, files)
    vid = ""
    if i.get("video"):
        vid = (f'<video><track><clipitem id="{mid}-v"><masterclipid>{mid}</masterclipid><name>{nm}</name>{frate}'
               f'<alphatype>none</alphatype>{fx}</clipitem></track></video>')
        fx = f'<file id="{files[f]}"/>'
    aud = []
    for g, (kind, chs) in enumerate(groups(i.get("ach", 0))):
        for ex, ch in enumerate(chs):
            aud.append(f'<track{_track_attrs(kind, ex)}><clipitem id="{mid}-a{ch}" premiereChannelType="{kind}">'
                       f'<masterclipid>{mid}</masterclipid><name>{nm}</name>{frate}{fx}<sourcetrack><mediatype>audio'
                       f'</mediatype><trackindex>{ch}</trackindex></sourcetrack></clipitem></track>')
            fx = f'<file id="{files[f]}"/>'
    return (f'<clip id="{mid}" explodedTracks="true"><masterclipid>{mid}</masterclipid><ismasterclip>TRUE</ismasterclip>'
            f'<duration>{int(i["dur"] * ffps)}</duration>{frate}<name>{nm}</name><media>{vid}'
            f'<audio>{"".join(aud)}</audio></media></clip>')


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
        ok = [f for f in c["files"] if (infos.get(f, {}).get("video") or infos.get(f, {}).get("ach"))
              and int(infos[f]["dur"] * sf) >= 1]
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


SLOTS = ["A", "B", "C", "D", "E", "F", "G", "H"]


def default_slots(cams):
    """Every folder -> its place: 'A', 'B'... in his order, 'drone' for the drone, 'sound' for the sound folders
    (lavaliere, recorder), 'out' for trash / gunoi."""
    out, k = [], 0
    for c in cams:
        r = rank(c["name"])[0]
        if c.get("sound"):
            out.append("sound")
        elif r == 4:
            out.append("out")
        elif r == 2:
            out.append("drone")
        else:
            out.append(SLOTS[min(k, len(SLOTS) - 1)])
            k += 1
    return out


def by_slot(cams, slots):
    """The cameras that go into the project, in the order of their places (A, B, ... then the drone)."""
    key = {s: i for i, s in enumerate(SLOTS + ["drone", "sound"])}
    picked = [(key[s], i, c, s) for i, (c, s) in enumerate(zip(cams, slots)) if s in key]
    return [(c, s) for _, _, c, s in sorted(picked)]


def export_xml(lay, infos, out_path, name, project=None):
    """One 25 fps sequence: every camera whole, one after the other (20 min between cameras), picture on V1, sound in
    STEREO PAIRS like Premiere (groups(): FX6 = A1 stereo 1+2 + A2 stereo 3+4, 2-channel cameras = A1 stereo, a mono
    file = a mono track), every pair written as Premiere writes it (two exploded tracks, premiereChannelType="stereo",
    sourcetrack = the channel), all of a clip LINKED (link = track + position in that track, sound in one group).
    Sound folders (lavaliere, recorder) go on the timeline as sound only.
    With project: one BIN per folder holding its clips as master clips, and the sequence next to them (masterclipid)."""
    rate_xml, sf = core._rate(SEQ_FPS)
    clips = [(f, st, n) for _, row in lay for f, st, n in row]
    if not clips:
        raise ValueError("No clips to put on the timeline.")
    vids = [f for f, _, _ in clips if infos[f].get("video")]
    sizes = {}
    for f in vids[:200]:
        k = (infos[f]["w"], infos[f]["h"])
        sizes[k] = sizes.get(k, 0) + 1
    sw, sh = max(sizes, key=sizes.get) if sizes else (1920, 1080)
    # the audio slots: (pair / mono group number, kind) -> xmeml tracks (2 for stereo)
    slots = sorted({(g, kind) for f, _, _ in clips for g, (kind, _c) in enumerate(groups(infos[f].get("ach", 0)))},
                   key=lambda t: (t[1] != "stereo", t[0]))   # stereo tracks first (A1, A2), mono after
    tracks, tix = [], {}
    for sl in slots:
        for ex in range(2 if sl[1] == "stereo" else 1):
            tix[(sl, ex)] = len(tracks) + 1
            tracks.append((sl, ex))
    ids, n, vpos = {}, 0, 0
    tpos = {t: 0 for t in tix.values()}
    for ci, (f, st, ln) in enumerate(clips, 1):
        if infos[f].get("video"):
            n += 1
            vpos += 1
            ids[("v", ci)] = (f"clipitem-{n}", 1, vpos)
    for ci, (f, st, ln) in enumerate(clips, 1):
        for g, (kind, chs) in enumerate(groups(infos[f].get("ach", 0))):
            for ex, ch in enumerate(chs):
                t = tix[((g, kind), ex)]
                n += 1
                tpos[t] += 1
                ids[("a", ci, ch)] = (f"clipitem-{n}", t, tpos[t], kind)
    files, master, bins_xml = {}, {}, []
    if project is not None:                       # the bins first: every file is written whole the first time here
        for cam, row in lay:
            items = []
            for f, _st, _ln in row:
                if f not in master:
                    master[f] = f"masterclip-{len(master) + 1}"
                    items.append(_master(f, infos[f], master[f], files))
            bins_xml.append(f'<bin><name>{escape(cam)}</name><children>{"".join(items)}</children></bin>')

    def links(ci, f):
        out = []
        if ("v", ci) in ids:
            v = ids[("v", ci)]
            out.append(f'<link><linkclipref>{v[0]}</linkclipref><mediatype>video</mediatype><trackindex>1</trackindex>'
                       f'<clipindex>{v[2]}</clipindex></link>')
        for _g, (_kind, chs) in enumerate(groups(infos[f].get("ach", 0))):
            for ch in chs:
                a = ids[("a", ci, ch)]
                out.append(f'<link><linkclipref>{a[0]}</linkclipref><mediatype>audio</mediatype><trackindex>{a[1]}'
                           f'</trackindex><clipindex>{a[2]}</clipindex><groupindex>1</groupindex></link>')
        return "".join(out) if len(out) > 1 else ""

    def head(cid, f, st, ln, attr=""):
        mc = f"<masterclipid>{master[f]}</masterclipid>" if f in master else ""
        return (f'<clipitem id="{cid}"{attr}>{mc}<name>{escape(Path(f).name)}</name><enabled>TRUE</enabled>'
                f'<duration>{ln}</duration>{rate_xml}<start>{st}</start><end>{st + ln}</end><in>0</in><out>{ln}</out>')

    vx = [head(ids[("v", ci)][0], f, st, ln) + _file_xml(f, infos[f], files) + links(ci, f) + "</clipitem>"
          for ci, (f, st, ln) in enumerate(clips, 1) if ("v", ci) in ids]
    ax = {t: [] for t in tix.values()}
    for ci, (f, st, ln) in enumerate(clips, 1):
        for _g, (kind, chs) in enumerate(groups(infos[f].get("ach", 0))):
            for ch in chs:
                cid, t, _pos, _k = ids[("a", ci, ch)]
                ax[t].append(head(cid, f, st, ln, f' premiereChannelType="{kind}"') + _file_xml(f, infos[f], files) +
                             f'<sourcetrack><mediatype>audio</mediatype><trackindex>{ch}</trackindex></sourcetrack>' +
                             links(ci, f) + "</clipitem>")
    total = clips[-1][1] + clips[-1][2]
    arate = next((infos[f]["arate"] for f, _, _ in clips if infos[f].get("ach")), 48000)
    trk = lambda its, attrs="": f'<track{attrs}>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    audio = (f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
             f'<samplerate>{arate}</samplerate></samplecharacteristics></format>'
             f'{"".join(trk(ax[tix[(sl, ex)]], _track_attrs(sl[1], ex)) for sl, ex in tracks)}</audio>')
    seq = (f'<sequence id="sequence-1"><name>{escape(name)}</name><duration>{total}</duration>{rate_xml}'
           f'<media><video><format>{core._sc(rate_xml, sw, sh, "none")}</format>{trk(vx)}</video>{audio}</media>'
           f'</sequence>')
    if project is not None:
        seq = f'<project><name>{escape(project)}</name><children>{"".join(bins_xml)}{seq}</children></project>'
    xml = f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">{seq}</xmeml>'
    Path(out_path).write_text(xml, encoding="utf-8")
    return dict(clips=len(clips), cameras=[(c, len(r)) for c, r in lay], seconds=total / sf)


def sound_files(root):
    """[dict(name, folder, files)] of the first-level folders with sound only (recorder, lavaliere): the Custom
    project imports them too, like dragging the folders into Premiere."""
    out = []
    for name in sound_folders(root):
        d = Path(root) / name
        fs = []
        for dirpath, dirnames, filenames in os.walk(d):
            dirnames[:] = sorted(x for x in dirnames if not x.startswith("."))
            fs += [str(Path(dirpath) / f) for f in sorted(filenames)
                   if not f.startswith(".") and Path(f).suffix.lower() in AUDIO]
        if fs:
            out.append(dict(name=name, folder=str(d), files=fs))
    return out


def export_bins(folders, infos, out_path, project):
    """CUSTOM project (the workflow of a videographer who labels the cameras and makes the sequence himself): only
    bins, one per folder (cameras AND sound folders), every clip whole as a master clip with its sound in stereo pairs
    / mono like Premiere (groups()), NO sequence. folders = [(bin name, [files])]."""
    files, bins, n_clips, bad = {}, [], 0, []
    for name, fs in folders:
        items = []
        for f in fs:
            i = infos.get(f) or {}
            if not i.get("dur") or not (i.get("video") or i.get("ach")):
                bad.append(f)
                continue
            n_clips += 1
            items.append(_master(f, i, f"masterclip-{n_clips}", files))
        if items:
            bins.append((name, len(items), f'<bin><name>{escape(name)}</name><children>{"".join(items)}</children></bin>'))
    if not bins:
        raise ValueError("No clips could be read.")
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><project><name>'
           f'{escape(project)}</name><children>{"".join(b for _, _, b in bins)}</children></project></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return dict(clips=n_clips, bins=[(nm, k) for nm, k, _ in bins], bad=bad)


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
