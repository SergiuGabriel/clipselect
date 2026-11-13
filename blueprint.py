"""Blueprints (like Hailo's): one of HIS finished films with the footage taken out. The cuts, the music / sound effects
and the pacing stay; every cut is refilled from the new wedding's labelled selections, with a shot of the SAME colour,
chosen like Teaser Studio chooses (the best part of a selection, the order of the day, never the same moment twice).

His films carry his colour on every shot, so a slot knows what it needs: Rose = bride, Blue = groom, ... A slot of
Tan (interview) stays empty with a marker (he puts the new interview there); a nested multicam (the party) becomes a
party slot; the adjustment layer (Lavender) is ignored. On the audio side the music and the sound effects (anything that
is not a camera file and not a recorder file of the old wedding) stay exactly on their tracks and times.
Two styles to choose from: Modern and Traditional (he tags every blueprint when he adds it).
"""
import random
import re
import uuid
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape

import core
import teaser

STYLES = ("modern", "traditional")
ADJUST = {"Lavender"}                # his adjustment layer colour
INTERVIEW = {"Tan"}


def _n(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _rate(el, d=25.0):
    tb = el.findtext("rate/timebase") if el is not None else None
    if not tb:
        return d
    return float(tb) * 1000 / 1001 if (el.findtext("rate/ntsc") or "").upper() == "TRUE" else float(tb)


def _recorder_name(name):
    """A recorder / lavalier file of THAT wedding (e.g. 260530_0160_3.wav, ZOOM0001.WAV): not part of the blueprint."""
    stem = Path(name).stem
    return bool(re.fullmatch(r"[0-9_\-]+", stem)) or bool(re.fullmatch(r"(ZOOM|TASCAM|ZOOM_|DR|LR|TR)[0-9_\-]+", stem, re.I))


def extract(path, name=None, style="modern"):
    """Read one of his finished films (FCP7 XML from Premiere) into a blueprint."""
    root = ET.parse(path).getroot()
    seqs = list(root.iter("sequence"))
    if not seqs:
        raise ValueError("No sequence in this XML.")
    seq = max(seqs, key=lambda s: sum(1 for _ in s.iter("clipitem")))
    fps = _rate(seq)
    files = {}
    for f in root.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            p = urllib.parse.unquote(f.findtext("pathurl")).replace("file://localhost", "").replace("file://", "")
            files[f.get("id")] = dict(path=p, name=f.findtext("name") or Path(p).name, fps=_rate(f, fps))
    video = seq.find("media/video")
    clips, video_files = [], set()
    for ti, tr in enumerate(video.findall("track") if video is not None else [], 1):
        if (tr.findtext("enabled") or "TRUE").upper() == "FALSE":
            continue
        for c in tr.findall("clipitem"):
            if (c.findtext("enabled") or "TRUE").upper() == "FALSE":
                continue
            st, en = _n(c.findtext("start"), -1), _n(c.findtext("end"), -1)
            nested = c.find("sequence") is not None
            fe = c.find("file")
            if fe is not None:
                video_files.add(fe.get("id"))
            if st < 0 or en <= st:
                continue
            lab = c.findtext("labels/label2") or ""
            if lab in ADJUST:
                continue
            if nested:
                cat = "party"                            # a nested multicam in his films is the party
            elif lab in INTERVIEW:
                cat = "interview"
            else:
                cat = teaser.CATS.get(lab)               # None: no colour (filled like its neighbours)
            if not nested and (fe is None or fe.get("id") not in files) and cat != "interview":
                continue                                 # a title, a graphic, a generator
            clips.append(dict(track=ti, t0=st / fps, t1=en / fps, cat=cat, label=lab))
    if not clips:
        raise ValueError("No video clips found in this XML.")
    # the shot SEEN at every moment (the top track)
    edges = sorted({x for c in clips for x in (c["t0"], c["t1"])})
    slots = []
    for a, b in zip(edges, edges[1:]):
        if b - a < 0.02:
            continue
        on = [c for c in clips if c["t0"] <= (a + b) / 2 < c["t1"]]
        if not on:
            continue
        top = max(on, key=lambda c: c["track"])
        if slots and slots[-1]["clip"] is top and abs(slots[-1]["t1"] - a) < 0.02:
            slots[-1]["t1"] = b
        else:
            slots.append(dict(t0=a, t1=b, cat=top["cat"], clip=top))
    for k, s in enumerate(slots):                        # no colour: the colour of the neighbour
        if s["cat"] is None:
            prev = next((x["cat"] for x in reversed(slots[:k]) if x["cat"] not in (None, "interview")), None)
            nxt = next((x["cat"] for x in slots[k + 1:] if x["cat"] not in (None, "interview")), None)
            s["cat"] = prev or nxt or "party"
    # music and sound effects, on their own tracks and times (no camera sound, no recorder of the old wedding)
    audio = []
    aud = seq.find("media/audio")
    for ti, tr in enumerate(aud.findall("track") if aud is not None else [], 1):
        for c in tr.findall("clipitem"):
            fe = c.find("file")
            if fe is None or fe.get("id") in video_files:
                continue
            info = files.get(fe.get("id"))
            if info is None:                             # a later reference to a file defined above
                info = next((files[k] for k in files if k == fe.get("id")), None)
            if info is None or _recorder_name(info["name"]) or \
                    Path(info["name"]).suffix.lower() in (".mxf", ".mp4", ".mov", ".mts", ".m2ts", ".avi", ".mkv", ".lrf", ".lrv"):
                continue                                 # a camera's sound of THAT wedding (vows...), not music
            st, en = _n(c.findtext("start"), -1), _n(c.findtext("end"), -1)
            if st < 0 or en <= st:
                continue
            cr = _rate(c, fps)
            audio.append(dict(track=ti, start=st / fps, end=en / fps, a=_n(c.findtext("in")) / cr,
                              path=info["path"], name=info["name"], src=_n(c.findtext("sourcetrack/trackindex"), 1)))
    dur = max(s["t1"] for s in slots)
    return dict(id=uuid.uuid4().hex, name=name or Path(path).stem, style=style if style in STYLES else "modern",
                source=Path(path).name, created=datetime.now().isoformat(timespec="seconds"), duration=round(dur, 3),
                slots=[[round(s["t0"], 3), round(s["t1"], 3), s["cat"]] for s in slots], audio=audio)


def summary(bp):
    """What the blueprint asks for: seconds of every kind, the number of cuts."""
    need = {}
    for t0, t1, c in bp["slots"]:
        need[c] = need.get(c, 0.0) + (t1 - t0)
    return dict(cuts=len(bp["slots"]), duration=bp["duration"], need=need,
                interviews=sum(1 for *_, c in bp["slots"] if c == "interview"),
                songs=len({a["name"] for a in bp["audio"]}))


def _teaser_end(slots):
    """His films open with a teaser (all kinds mixed); it ends where the first run of getting ready begins."""
    run = 0
    for k, (t0, t1, c) in enumerate(slots):
        run = run + 1 if c in ("bride", "groom") else 0
        if run >= 6:
            return slots[k - 5][0]
    return slots[0][0]


def build(pieces, bp, seed=1):
    """Refill the blueprint from the new wedding. Returns dict(shots=[(t0, t1, piece)], gaps=[(t0, t1, kind)])."""
    rng = random.Random(seed)
    pool = teaser.Pool(pieces, rng, True)
    slots = bp["slots"]
    tend = _teaser_end(slots)
    first_church = next((t0 for t0, t1, c in slots if c == "church" and t0 >= tend), None)
    count = {}
    for t0, t1, c in slots:
        if t0 >= tend:
            count[c] = count.get(c, 0) + 1
    seen = {}
    shots, gaps = [], []
    for t0, t1, c in slots:
        if c == "interview":
            gaps.append((t0, t1, "interview"))
            continue
        mode = "teaser" if t0 < tend else "story"
        if mode == "story":                              # where this cut sits in its kind's part of the film
            seen[c] = seen.get(c, 0) + 1
            frac = (seen[c] - 0.5) / max(1, count.get(c, 1))
        else:
            frac = rng.random()
        when = None
        if c == "party" and first_church is not None:
            when = "after" if t0 >= first_church else "before"
        p = pool.take(c, t1 - t0, mode, frac=frac, when=when, energy=0.3 if mode == "teaser" else 0.0)
        if p is None:
            gaps.append((t0, t1, c))
            continue
        shots.append((t0, t0 + (p["e"] - p["s"]), p))
    return dict(shots=shots, gaps=gaps)


def export_xml(edit, bp, out_path, name, fps=25.0):
    """The refilled film: the new shots on V1 (with his colours), the blueprint's music and sound effects on their own
    tracks, a marker where an interview goes and where a kind ran out of footage."""
    import i18n
    import sync
    rate_xml, sf = core._rate(fps)
    n = [0]

    def nid():
        n[0] += 1
        return f"clipitem-{n[0]}"
    defined = {}

    def vfile(p):
        if p["path"] in defined:
            return f'<file id="{defined[p["path"]]}"/>'
        defined[p["path"]] = f"file-{len(defined) + 1}"
        frate, ffps = core._rate(p["fps"])
        return (f'<file id="{defined[p["path"]]}"><name>{escape(Path(p["path"]).name)}</name>'
                f'<pathurl>{escape(core._url(p["path"]))}</pathurl>{frate}<duration>{int(p["fdur"] * ffps)}</duration>'
                f'<media><video>{core._sc(frate, p["w"], p["h"], "none")}</video></media></file>')
    v = []
    shots = sorted(edit["shots"], key=lambda x: x[0])
    fr = [[round(t0 * sf), round(t1 * sf)] for t0, t1, _ in shots]
    for k in range(len(shots) - 1):                       # touching shots share the boundary frame
        if abs(shots[k][1] - shots[k + 1][0]) < 0.05:
            fr[k][1] = fr[k + 1][0]
    for (t0, t1, p), (st, en) in zip(shots, fr):
        if en <= st:
            continue
        fin = round(p["s"] * sf)
        fout = fin + (en - st)
        sdur = max(fout, int(p["fdur"] * sf))
        v.append(f'<clipitem id="{nid()}"><name>{escape(Path(p["path"]).name)}</name><duration>{sdur}</duration>{rate_xml}'
                 f'<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fout}</out>'
                 f'<labels><label2>{p.get("label") or teaser.LABEL_OF[p["cat"]]}</label2></labels>{vfile(p)}</clipitem>')
    tracks = {}
    afile = {}
    for it in bp["audio"]:
        if not Path(it["path"]).exists():
            continue
        if it["path"] not in afile:
            r, ch = sync.audio_info(it["path"])
            afile[it["path"]] = f"file-a{len(afile) + 1}"
            body = (f'<file id="{afile[it["path"]]}"><name>{escape(it["name"])}</name>'
                    f'<pathurl>{escape(core._url(it["path"]))}</pathurl>{rate_xml}<duration>{int((it["a"] + it["end"] - it["start"]) * sf) + 1}</duration>'
                    f'<media><audio><samplecharacteristics><depth>16</depth><samplerate>{r}</samplerate></samplecharacteristics>'
                    f'<channelcount>{ch}</channelcount></audio></media></file>')
        else:
            body = f'<file id="{afile[it["path"]]}"/>'
        st, en, fin = round(it["start"] * sf), round(it["end"] * sf), round(it["a"] * sf)
        tracks.setdefault(it["track"], []).append(
            f'<clipitem id="{nid()}"><name>{escape(it["name"])}</name><duration>{fin + en - st}</duration>{rate_xml}'
            f'<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fin + en - st}</out>{body}'
            f'<sourcetrack><mediatype>audio</mediatype><trackindex>{it.get("src", 1)}</trackindex></sourcetrack></clipitem>')
    marks = [(f'{i18n.T("Blueprint")}: {bp["name"]}', 0.0)]
    for t0, t1, kind in edit["gaps"]:
        marks.append((i18n.T("Interview here") if kind == "interview" else
                      i18n.T("No footage left for: {}").format(i18n.T(teaser.CAT_NAME.get(kind, kind))), t0))
    mk = "".join(f'<marker><name>{escape(m)}</name><comment></comment><in>{round(t * sf)}</in><out>-1</out></marker>'
                 for m, t in marks)
    trk = lambda its: f'<track>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    atr = "".join(trk(tracks.get(k, [])) for k in range(1, max(tracks, default=0) + 1))
    first = shots[0][2] if shots else dict(w=1920, h=1080)
    total = round(bp["duration"] * sf)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}{mk}'
           f'<media><video><format>{core._sc(rate_xml, first["w"], first["h"], "none")}</format>{trk(v)}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{atr}</audio></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return len(v)
