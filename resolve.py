"""The same XML, made for DaVinci Resolve (File > Import > Timeline).

v4.2.0: rewrite() writes a NEW file from scratch in the way DaVinci Resolve itself writes its FCP7 XML (measured on an
export of Resolve Studio 20 on his Mac): only the sequence, clipitems with id "<file name> <n>", the file's own
timecode (Resolve places media by its timecode: without it a clip whose camera timecode is 23:08:00 does "not
overlap" the XML's 00:00:00:00 and goes offline), one plain mono audio track per source channel, the links, the clip
colours and markers. NOTHING of Premiere stays: no exploded stereo tracks, no premiereChannelType / premiereTrackType,
no pproTicks / pproOriginalAudio, no Basic Motion / Lumetri / Crop, no master clips or bins, no generator items.
Two friends' Resolve 21.2 crashed at import on the old (Premiere-shaped) file.

The older converter below (convert) only took effects out of the Premiere file:
- Basic Motion "scale to fill" is removed: Resolve already fits every clip to the timeline (Project Settings > Image
  Scaling, default "Scale entire image to fit"); with the Premiere scale on top a 4K clip came out at a quarter size.
- Lumetri (Premiere's colour effect) is removed: Resolve cannot read it (apply the LUT in Resolve's Color page).
- A Premiere PROJECT (bins + master clips, Create Project) becomes its sequence alone: Resolve's Import Timeline wants
  a sequence; every <file> is written in full where the sequence first uses it, master clip references are dropped
  (Resolve puts every clip in the Media Pool by itself).
Nothing else changes: clip names = file names (Resolve links media by name), times, tracks, links, markers, the
sound channels, disabled clips and the label colours stay exactly as in the Premiere file.
"""
import copy
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'


def _drop_filters(root):
    n = dict(scale=0, colour=0)
    for parent in root.iter():
        for f in list(parent.findall("filter")):
            eff = f.find("effect")
            eid = (eff.findtext("effectid") or "") if eff is not None else ""
            name = (eff.findtext("name") or "") if eff is not None else ""
            # the colour of the Long Film v2 card (LUT + crop) is Premiere only: in Resolve it goes on the Color page
            if eid in ("basic", "crop") or "lumetri" in eid.lower() or "lumetri" in name.lower():
                parent.remove(f)
                n["scale" if eid == "basic" else "colour"] += 1
    return n


def _unwrap(root):
    """<xmeml><project>... bins ... <sequence>  ->  <xmeml><sequence> with every file complete at its first use."""
    if root.find("project") is None:
        return root
    full = {}
    for f in root.iter("file"):
        if f.get("id") and len(f) and f.get("id") not in full:
            full[f.get("id")] = f
    seqs = [s for s in root.iter("sequence")]
    new = ET.Element("xmeml", root.attrib)
    for s in seqs:
        s = copy.deepcopy(s)
        seen = set()
        for parent in s.iter():
            for m in list(parent.findall("masterclipid")):
                parent.remove(m)
        for f in s.iter("file"):
            i = f.get("id")
            if not i:
                continue
            if i not in seen:
                seen.add(i)
                if not len(f) and i in full:
                    for c in full[i]:
                        f.append(copy.deepcopy(c))
        new.append(s)
    return new


def _path(url):
    p = urllib.parse.unquote(url or "")
    for pre in ("file://localhost", "file://"):
        if p.startswith(pre):
            p = p[len(pre):]
            break
    if len(p) > 2 and p[0] == "/" and p[2] == ":":          # file://localhost/C:/... on Windows
        p = p[1:]
    return p


def _fix_names(root):
    """Resolve links a timeline clip to its media by NAME: every clipitem is named exactly like its file."""
    names, n = {}, 0
    for f in root.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            names[f.get("id")] = Path(_path(f.findtext("pathurl"))).name
    for c in root.iter("clipitem"):
        f = c.find("file")
        want = names.get(f.get("id")) if f is not None else None
        nm = c.find("name")
        if want and nm is not None and nm.text != want:
            nm.text = want
            n += 1
    return n


def verify(path, progress=None, cancel=lambda: False):
    """Everything Resolve needs, checked on the written file. -> dict(errors, warnings, clips, files, missing)."""
    import story
    say = progress or (lambda t, f: None)
    errors, warnings = [], []
    say("Reading the XML…", 0.02)
    root = ET.parse(path).getroot()
    seqs = root.findall("sequence")
    if len(seqs) != 1:
        errors.append("The file must hold exactly one sequence (it has {}).".format(len(seqs)))
        return dict(errors=errors, warnings=warnings, clips=0, files=0, missing=[])
    seq = seqs[0]
    if not seq.findtext("rate/timebase"):
        errors.append("The sequence has no frame rate.")
    say("Checking links and clips…", 0.08)
    errors += story.check_xml(path)
    files = {}
    for f in seq.iter("file"):
        i = f.get("id")
        if i and len(f) and i not in files:
            files[i] = dict(path=_path(f.findtext("pathurl")), dur=int(f.findtext("duration") or 0),
                            name=Path(_path(f.findtext("pathurl"))).name)
    clips = list(seq.iter("clipitem"))
    left = sum(1 for p in seq.iter() for f in p.findall("filter")
               if (f.findtext("effect/effectid") or "") in ("basic", "crop") or "umetri" in (f.findtext("effect/effectid") or ""))
    if left:
        errors.append(f"{left} Premiere-only effects are still in the file.")
    bad_name = bad_range = 0
    for k, c in enumerate(clips):
        if cancel():
            raise RuntimeError("Cancelled")
        if k % 200 == 0:
            say("Checking clips: {} of {}".format(k, len(clips)), 0.1 + 0.4 * k / max(1, len(clips)))
        f = c.find("file")
        fi = files.get(f.get("id")) if f is not None else None
        if fi is None:
            continue
        if c.findtext("name") != fi["name"]:
            bad_name += 1
        try:
            i0, i1 = int(c.findtext("in")), int(c.findtext("out"))
            st, en = int(c.findtext("start")), int(c.findtext("end"))
        except (TypeError, ValueError):
            continue
        if i1 <= i0 or (st >= 0 and en >= 0 and en - st != i1 - i0):
            bad_range += 1
        sfps = float(c.findtext("rate/timebase") or 25)
        ffps = float(f.findtext("rate/timebase") or 0) if f is not None and len(f) else 0
        if fi["dur"] and ffps:
            if i1 > fi["dur"] * sfps / ffps + 2:
                bad_range += 1
    if bad_name:
        errors.append(f"{bad_name} clips are not named like their file (Resolve would show them offline).")
    if bad_range:
        errors.append(f"{bad_range} clips have a wrong in / out (outside the file or a length that does not match).")
    missing = []
    for k, fi in enumerate(files.values()):
        if cancel():
            raise RuntimeError("Cancelled")
        if k % 50 == 0:
            say("Looking for the files on this computer: {} of {}".format(k, len(files)), 0.5 + 0.45 * k / max(1, len(files)))
        if fi["path"] and not Path(fi["path"]).exists():
            missing.append(fi["name"])
    if missing:
        warnings.append("{} files are not on this computer right now (connect the disk before importing): {}".format(
            len(missing), ", ".join(missing[:5]) + (" …" if len(missing) > 5 else "")))
    say("Done", 1.0)
    return dict(errors=errors, warnings=warnings, clips=len(clips), files=len(files), missing=missing)


def convert(src, out=None):
    """Writes the DaVinci Resolve version of the xmeml `src` to `out` (default: in place). Returns a short summary."""
    out = out or src
    tree = ET.parse(src)
    root = tree.getroot()
    was_project = root.find("project") is not None
    root = _unwrap(root)
    n = _drop_filters(root)
    renamed = _fix_names(root)
    body = ET.tostring(root, encoding="unicode")
    Path(out).write_text(HEAD + body, encoding="utf-8")
    return dict(filters_removed=n["scale"] + n["colour"], scale_removed=n["scale"], colour_removed=n["colour"],
                project_unwrapped=was_project, renamed=renamed)


TC_CACHE = {}


def file_tc(path, fps):
    """The camera timecode of a file as (string, frame count, nominal rate) or None (no / zero timecode)."""
    if path in TC_CACHE:
        return TC_CACHE[path]
    out = None
    try:
        import re
        import subprocess
        import core
        r = subprocess.run([core.ffmpeg_exe(), "-hide_banner", "-nostdin", "-i", path], capture_output=True, text=True,
                           errors="replace", timeout=60, **core._NOWIN)
        m = re.search(r"^\s*timecode\s*:\s*(\d\d):(\d\d):(\d\d)([:;.])(\d\d)", r.stderr, re.M)
        if m and any(int(x) for x in (m.group(1), m.group(2), m.group(3), m.group(5))):
            nom = int(round(fps or 25))
            h, mi, se, fr = int(m.group(1)), int(m.group(2)), int(m.group(3)), int(m.group(5))
            out = (f"{h:02d}:{mi:02d}:{se:02d}{m.group(4) if m.group(4) == ';' else ':'}{fr:02d}",
                   ((h * 60 + mi) * 60 + se) * nom + fr, nom, m.group(4) == ";")
    except Exception:
        out = None
    TC_CACHE[path] = out
    return out


def _el(parent, tag, text=None):
    e = ET.SubElement(parent, tag)
    if text is not None:
        e.text = str(text)
    return e


def _rate(parent, tb, ntsc):
    r = _el(parent, "rate")
    _el(r, "timebase", tb)
    _el(r, "ntsc", "TRUE" if ntsc else "FALSE")
    return r


def rewrite(src, out=None, progress=None, cancel=lambda: False, tc=True):
    """The DaVinci Resolve file written from scratch out of any xmeml of the app (see the module text)."""
    say = progress or (lambda t, f: None)
    out = out or src
    root = _unwrap(ET.parse(src).getroot())
    seq = root.find("sequence") if root.tag == "xmeml" else None
    if seq is None:
        seq = next(root.iter("sequence"))
    full = {}
    for f in root.iter("file"):
        if f.get("id") and len(f) and f.get("id") not in full:
            full[f.get("id")] = f
    stb = seq.findtext("rate/timebase") or "25"
    sntsc = (seq.findtext("rate/ntsc") or "FALSE").upper() == "TRUE"
    new = ET.Element("xmeml", version="5")
    s = _el(new, "sequence")
    _el(s, "name", seq.findtext("name") or "Timeline")
    _el(s, "duration", seq.findtext("duration") or "0")
    _rate(s, stb, sntsc)
    _el(s, "in", -1)
    _el(s, "out", -1)
    t = _el(s, "timecode")
    _el(t, "string", seq.findtext("timecode/string") or "00:00:00:00")
    _el(t, "frame", seq.findtext("timecode/frame") or "0")
    _el(t, "displayformat", "NDF")
    _rate(t, stb, sntsc)
    media = _el(s, "media")
    w = seq.findtext("media/video/format/samplecharacteristics/width") or "1920"
    h = seq.findtext("media/video/format/samplecharacteristics/height") or "1080"
    # ids: every clipitem gets "<file name> <n>" (Resolve's own scheme); links are rewritten to the new ids
    idmap, count = {}, {}
    src_clips = []
    for kind in ("video", "audio"):
        for tr in seq.findall(f"media/{kind}/track"):
            for c in tr.findall("clipitem"):
                f = c.find("file")
                fid = f.get("id") if f is not None else None
                fe = full.get(fid)
                nm = Path(_path(fe.findtext("pathurl"))).name if fe is not None and fe.findtext("pathurl") else (
                    c.findtext("name") or "clip")
                n = count.get(nm, 0)
                count[nm] = n + 1
                idmap[c.get("id")] = f"{nm} {n}"
                src_clips.append(c)
    written, total = set(), max(1, len(src_clips))
    k = [0]

    def clip(tr_new, c, kind):
        if cancel():
            raise RuntimeError("Cancelled")
        k[0] += 1
        if k[0] % 200 == 0:
            say(f"Writing the clips for DaVinci: {k[0]} of {total}", 0.05 + 0.45 * k[0] / total)
        f = c.find("file")
        fid = f.get("id") if f is not None else None
        fe = full.get(fid)
        if fe is None:
            return
        name = idmap[c.get("id")].rsplit(" ", 1)[0]
        ci = _el(tr_new, "clipitem", None)
        ci.set("id", idmap[c.get("id")])
        _el(ci, "name", name)
        ftb = fe.findtext("rate/timebase") or stb
        fntsc = (fe.findtext("rate/ntsc") or "FALSE").upper() == "TRUE"
        fdur = int(fe.findtext("duration") or 0)
        sdur = int(round(fdur * float(stb) / float(ftb))) if fdur else int(c.findtext("duration") or 0)
        _el(ci, "duration", sdur)
        _rate(ci, stb, sntsc)
        for tag in ("start", "end"):
            _el(ci, tag, c.findtext(tag) or "0")
        en = (c.findtext("enabled") or "TRUE").upper()
        _el(ci, "enabled", "FALSE" if en == "FALSE" else "TRUE")
        _el(ci, "in", c.findtext("in") or "0")
        _el(ci, "out", c.findtext("out") or "0")
        if fid in written:
            ET.SubElement(ci, "file", id=f"{name} file")
        else:
            written.add(fid)
            fx = ET.SubElement(ci, "file", id=f"{name} file")
            _el(fx, "name", name)
            _el(fx, "pathurl", fe.findtext("pathurl"))
            _rate(fx, ftb, fntsc)
            _el(fx, "duration", fdur)
            code = file_tc(_path(fe.findtext("pathurl")), float(ftb)) if tc else None
            ft = _el(fx, "timecode")
            _el(ft, "string", code[0] if code else "00:00:00:00")
            _el(ft, "frame", code[1] if code else 0)
            _el(ft, "displayformat", "DF" if code and code[3] else "NDF")
            _rate(ft, code[2] if code else ftb, fntsc)
            fm = _el(fx, "media")
            vw = fe.find("media/video/samplecharacteristics")
            if fe.find("media/video") is not None:
                v = _el(_el(fm, "video"), "samplecharacteristics")
                _el(v, "width", vw.findtext("width") if vw is not None else w)
                _el(v, "height", vw.findtext("height") if vw is not None else h)
            chans = 0
            po = fe.find("media/pproOriginalAudio")
            if po is not None:
                chans = int(po.findtext("channelcount") or 0)
            else:
                chans = sum(int(a.findtext("channelcount") or 0) for a in fe.findall("media/audio"))
            if chans:
                a = _el(fm, "audio")
                sc = _el(a, "samplecharacteristics")
                _el(sc, "depth", 16)
                _el(sc, "samplerate", fe.findtext("media/audio/samplecharacteristics/samplerate") or "48000")
                _el(a, "channelcount", chans)
        if kind == "video":
            _el(ci, "compositemode", "normal")
        else:
            stn = _el(ci, "sourcetrack")
            _el(stn, "mediatype", "audio")
            _el(stn, "trackindex", c.findtext("sourcetrack/trackindex") or "1")
        for l in c.findall("link"):
            ref = idmap.get(l.findtext("linkclipref"))
            if not ref:
                continue
            ln = _el(ci, "link")
            _el(ln, "linkclipref", ref)
            _el(ln, "mediatype", l.findtext("mediatype") or ("video" if "video" in ref else "audio"))
            _el(ln, "trackindex", l.findtext("trackindex") or "1")
            _el(ln, "clipindex", l.findtext("clipindex") or "1")
        lab = c.findtext("labels/label2")
        if lab:
            _el(_el(ci, "labels"), "label2", lab)
    vid = _el(media, "video")
    fmt = _el(_el(vid, "format"), "samplecharacteristics")
    _el(fmt, "width", w)
    _el(fmt, "height", h)
    _el(fmt, "anamorphic", "FALSE")
    _el(fmt, "pixelaspectratio", "square")
    _el(fmt, "fielddominance", "none")
    _rate(fmt, stb, sntsc)
    for tr in seq.findall("media/video/track"):
        tn = _el(vid, "track")
        for c in tr.findall("clipitem"):
            clip(tn, c, "video")
        _el(tn, "enabled", "FALSE" if (tr.findtext("enabled") or "").upper() == "FALSE" else "TRUE")
        _el(tn, "locked", "FALSE")
    aud = _el(media, "audio")
    for tr in seq.findall("media/audio/track"):
        tn = _el(aud, "track")
        for c in tr.findall("clipitem"):
            clip(tn, c, "audio")
        _el(tn, "enabled", "FALSE" if (tr.findtext("enabled") or "").upper() == "FALSE" else "TRUE")
        _el(tn, "locked", "FALSE")
    # links point at the REAL position of every clip in the new tracks (generator items are gone)
    pos = {}
    for kind in ("video", "audio"):
        for ti, tr in enumerate(media.find(kind).findall("track"), 1):
            for k2, c in enumerate(tr.findall("clipitem"), 1):
                pos[c.get("id")] = (kind, ti, k2)
    for c in media.iter("clipitem"):
        for ln in list(c.findall("link")):
            p = pos.get(ln.findtext("linkclipref"))
            if not p:
                c.remove(ln)
                continue
            ln.find("mediatype").text, ln.find("trackindex").text, ln.find("clipindex").text = p[0], str(p[1]), str(p[2])
    for m in seq.findall("marker"):
        mk = _el(s, "marker")
        _el(mk, "name", m.findtext("name") or "")
        _el(mk, "in", m.findtext("in") or "0")
        _el(mk, "out", m.findtext("out") or "-1")
    ET.indent(new, space="    ")
    Path(out).write_text(HEAD + ET.tostring(new, encoding="unicode") + "\n", encoding="utf-8")
    return dict(filters_removed=0, scale_removed=0, colour_removed=0, project_unwrapped=root.find("project") is not None,
                renamed=0, rewritten=True, clips=len(src_clips))


def make(src, out=None, progress=None, cancel=lambda: False):
    """The DaVinci export: written from scratch in Resolve's own way (rewrite), then verified. -> summary + verify."""
    say = progress or (lambda t, f: None)
    say("Making the DaVinci Resolve version…", 0.0)
    r = rewrite(src, out, lambda t, f: say(t, 0.5 * f), cancel)
    v = verify(out or src, lambda t, f: say(t, 0.5 + 0.5 * f), cancel)
    r.update(v)
    return r


def name_for(path, target):
    """'Wedding.xml' -> 'Wedding (DaVinci).xml' for the Resolve file, unchanged for Premiere."""
    p = Path(path)
    if target != "davinci" or p.stem.endswith("(DaVinci)"):
        return str(p)
    return str(p.with_name(f"{p.stem} (DaVinci){p.suffix}"))


def how(target):
    return "DaVinci Resolve: File > Import > Timeline" if target == "davinci" else "Premiere Pro: File > Import"
