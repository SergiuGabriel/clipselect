"""Import an already synced timeline (FCP7 XML / xmeml from Syncaila, Premiere Pro or DaVinci Resolve).

Every video track becomes a camera, every clip keeps the position it has on that timeline, audio-only files on the
audio tracks become the recorder (master). After the import, Auto Edit works exactly as after our own Sync.
"""
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlparse

import core
import sync


def _rate(el, default):
    r = el.find("rate") if el is not None else None
    if r is None or r.find("timebase") is None:
        return default
    tb = float(r.findtext("timebase"))
    ntsc = (r.findtext("ntsc") or "").upper() == "TRUE"
    return tb * 1000 / 1001 if ntsc else tb


def _path(url):
    if not url:
        return None
    u = urlparse(url)
    p = unquote(u.path if u.scheme == "file" else url)
    if len(p) > 2 and p[0] == "/" and p[2] == ":":      # file://localhost/C:/... on Windows
        p = p[1:]
    return p


def parse(xml_path):
    """Returns dict(fps, video=[[(path, zero)]] one list per video track, audio=[(path, zero)], end) where `zero` is
    the timeline time (s) at which the clip's first frame / sample sits."""
    root = ET.parse(xml_path).getroot()
    files = {}
    for f in root.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            files[f.get("id")] = _path(f.findtext("pathurl"))
    seqs = list(root.iter("sequence"))
    if not seqs:
        raise ValueError("No sequence found in this XML.")
    seq = max(seqs, key=lambda s: sum(1 for _ in s.iter("clipitem")))
    fps = _rate(seq, 25.0)
    media = seq.find("media")
    if media is None:
        raise ValueError("This XML sequence has no media.")

    def items(kind):
        out = []
        el = media.find(kind)
        for tr in (el.findall("track") if el is not None else []):
            row = []
            for ci in tr.findall("clipitem"):
                f = ci.find("file")
                path = files.get(f.get("id")) if f is not None else None
                if not path:
                    continue
                cfps = _rate(ci, fps)
                num = lambda v, d: int(round(float(v))) if v not in (None, "") else d
                st, en = num(ci.findtext("start"), -1), num(ci.findtext("end"), -1)
                cin, cout = num(ci.findtext("in"), 0), num(ci.findtext("out"), 0)
                if st < 0 and en >= 0:          # next to a transition: start is -1
                    st = en - round((cout - cin) / cfps * fps)
                if en < 0 and st >= 0:          # ... or end is -1
                    en = st + round((cout - cin) / cfps * fps)
                if st < 0:
                    continue
                row.append((path, st / fps - cin / cfps, (en if en >= 0 else st) / fps))
            out.append(row)
        return out

    video, audio = items("video"), items("audio")
    if not any(video):
        raise ValueError("No video clips found in this XML.")
    vids = {p for row in video for p, _, _ in row}
    aud = {}
    for row in audio:
        for p, z, _ in row:
            if p not in vids:
                aud.setdefault(p, z)
    ends = [e for row in video + audio for _, _, e in row]
    return dict(fps=fps, video=[[(p, z) for p, z, _ in row] for row in video], audio=sorted(aud.items(), key=lambda x: x[1]),
                end=max(ends) if ends else 0.0)


def build(xml_path, progress=None, cancel=None):
    """Everything the multicam page needs: files, infos, masters, results, cams."""
    x = parse(xml_path)
    files, infos, seen = [], {}, set()
    clip_zero, clip_track = {}, {}
    for t, row in enumerate(x["video"]):
        for p, z in row:
            if p not in clip_zero:
                clip_zero[p], clip_track[p] = z, t
    allp = list(clip_zero) + [p for p, _ in x["audio"]]
    missing = [p for p in allp if not Path(p).exists()]
    if missing:   # skip what is not on this computer instead of refusing the whole timeline
        allp = [p for p in allp if p not in missing]
        clip_zero = {p: z for p, z in clip_zero.items() if p not in missing}
        x["audio"] = [(p, z) for p, z in x["audio"] if p not in missing]
        x["video"] = [[(p, z) for p, z in row if p not in missing] for row in x["video"]]
        if not clip_zero:
            raise ValueError(f"None of the video files in the XML were found on this computer, e.g. {missing[0]}")
    for i, p in enumerate(allp):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        if progress:
            progress(f"Reading the XML: file {i + 1} of {len(allp)}", 0.6 * i / max(1, len(allp)))
        infos[p] = sync.media_info(p)
        if p not in seen:
            seen.add(p)
            files.append(dict(path=p, group=Path(p).parent.name))
    masters = []
    for k, (p, z) in enumerate(x["audio"]):
        if progress:
            progress(f"Reading the recorder for the beat: {k + 1} of {len(x['audio'])}", 0.6 + 0.4 * k / max(1, len(x["audio"])))
        a = sync.audio_pcm(p)
        masters.append(dict(path=p, duration=len(a) / sync.SR, onsets=sync.onsets(a), clock=None, start=z))
    if not masters:   # no recorder in the XML: the timeline itself is the reference (no beat detection)
        masters = [dict(path=None, duration=x["end"], onsets=[], clock=None, start=0.0)]
    results = {}
    for p, z in clip_zero.items():
        mi = min(range(len(masters)), key=lambda i: 0 if masters[i]["start"] <= z < masters[i]["start"] + masters[i]["duration"]
                 else min(abs(z - masters[i]["start"]), abs(z - masters[i]["start"] - masters[i]["duration"])))
        results[p] = dict(conf="high", z=0.0, n=0, k=0, offset=z - masters[mi]["start"], drift_ppm=0.0, master=mi,
                          dur=infos[p]["duration"], manual=False, source="xml")
    cams = []
    for t, row in enumerate(x["video"]):
        clips = [p for p in dict.fromkeys(p for p, _ in row) if clip_track.get(p) == t]
        if clips:
            g = Counter(Path(p).parent.name for p in clips).most_common(1)[0][0]
            cams.append(dict(name=f"V{t + 1} · {g}", role="Handheld", clips=clips, user=False))
    if progress:
        progress("XML imported", 1.0)
    return dict(files=files, infos=infos, masters=masters, results=results, cams=cams, missing=missing)
