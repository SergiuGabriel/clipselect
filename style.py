"""Learn my editing style: measures a party the editor cut himself (FCP7 XML from Premiere / DaVinci) and proposes
the Auto Director settings that cut like him. Saved on THIS computer only (every editor has his own).

What is measured on his edit (the clip seen on top at every moment):
  - shot lengths (everywhere, on calm music, on intense music, on drops);
  - where his cuts fall against the beat (on it / a frame or two before / after);
  - how much he uses the handheld cameras against the static ones (when the files belong to this project).
The music is read from the recorder files of his timeline when they are on this computer; without them only the
shot lengths are measured.
"""
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

import music
import sync
import xmlimport

LONG_AUDIO = 240          # an audio clip longer than this (s) is a recorder / mixer file (or a whole song)


def _n(v, d=0):
    try:
        return int(round(float(v)))
    except (TypeError, ValueError):
        return d


def _times(ci, fps, cfps):
    st, en = _n(ci.findtext("start"), -1), _n(ci.findtext("end"), -1)
    ln = round((_n(ci.findtext("out")) - _n(ci.findtext("in"))) / cfps * fps)
    if st < 0 and en >= 0:
        st = en - ln
    if en < 0 and st >= 0:
        en = st + ln
    return (st / fps, en / fps) if 0 <= st < en else None


def read_edit(xml_path):
    """Shots seen on his timeline [(t0, t1, file name)] and the recorder clips [(path, seq start, file in)]."""
    root = ET.parse(xml_path).getroot()
    seq = max(root.iter("sequence"), key=lambda s: sum(1 for _ in s.iter("clipitem")))
    fps = xmlimport._rate(seq, 25.0)
    files = {}
    for f in root.iter("file"):
        if f.get("id") and f.findtext("name"):
            files[f.get("id")] = dict(name=f.findtext("name"), path=xmlimport._path(f.findtext("pathurl") or ""),
                                      dur=_n(f.findtext("duration")) / max(1e-6, xmlimport._rate(f, fps)))
    items = []
    vid = seq.find("media/video")
    for ti, tr in enumerate(vid.findall("track") if vid is not None else []):
        if (tr.findtext("enabled") or "TRUE").upper() == "FALSE":
            continue
        for c in tr.findall("clipitem"):
            if c.find("sequence") is not None or (c.findtext("enabled") or "TRUE").upper() == "FALSE":
                continue
            f = c.find("file")
            info = files.get(f.get("id")) if f is not None else None
            if not info:
                continue                                    # adjustment layers, titles, graphics
            tt = _times(c, fps, xmlimport._rate(c, fps))
            if tt and tt[1] - tt[0] < 600:                  # a whole long clip under everything is not a shot
                items.append((tt[0], tt[1], ti, info["name"]))
    # what is seen: the top track at every moment
    edges = sorted({t for a, b, _, _ in items for t in (a, b)})
    shots = []
    for a, b in zip(edges, edges[1:]):
        m = (a + b) / 2
        on = [x for x in items if x[0] <= m < x[1]]
        if not on:
            continue
        top = max(on, key=lambda x: x[2])
        if shots and shots[-1][2] == top[3] and abs(shots[-1][1] - a) < 1e-6 and shots[-1][3] == top[0]:
            shots[-1][1] = b
        else:
            shots.append([a, b, top[3], top[0]])
    shots = [(a, b, n) for a, b, n, _ in shots if b - a > 0.05]
    rec = []
    aud = seq.find("media/audio")
    for tr in (aud.findall("track") if aud is not None else []):
        for c in tr.findall("clipitem"):
            f = c.find("file")
            info = files.get(f.get("id")) if f is not None else None
            tt = _times(c, fps, xmlimport._rate(c, fps))
            if info and tt and tt[1] - tt[0] >= LONG_AUDIO and Path(info["name"]).suffix.lower() in sync.AUDIO_EXT:
                rec.append((info["path"], tt[0], _n(c.findtext("in")) / xmlimport._rate(c, fps), tt[1]))
    return dict(fps=fps, shots=shots, recorders=rec)


def learn(xml_path, cams=None, progress=None):
    """Measures his edit. cams: this project's cameras (to know which files are static / handheld)."""
    e = read_edit(xml_path)
    shots, fps = e["shots"], e["fps"]
    if len(shots) < 20:
        raise ValueError("Too few shots in this XML: export the sequence of a party you edited.")
    L = np.array([b - a for a, b, _ in shots])
    res = dict(shots=len(shots), median=float(np.median(L)), p15=float(np.percentile(L, 15)),
               p95=float(np.percentile(L, 95)), music=False)
    # ---- the music under his cuts (only if the recorder files are on this computer)
    beats, energy, drops = [], [], []
    seen = set()
    recs = [r for r in e["recorders"] if r[0] and Path(r[0]).exists()]
    for k, (path, s0, fin, s1) in enumerate(recs):
        if progress:
            progress(f"Reading the music of your edit: {k + 1} of {len(recs)}", (k + 0.5) / max(1, len(recs)))
        if path in seen:
            continue
        seen.add(path)
        mm = music.analyze(sync.audio_pcm(path))
        to_seq = lambda t: s0 + (t - fin)
        beats += [to_seq(t) for t in mm["beats"] if fin <= t <= fin + (s1 - s0)]
        ev, er = mm["energy"]["v"], mm["energy"]["rate"]
        energy += [(to_seq(i / er), v) for i, v in enumerate(ev) if fin <= i / er <= fin + (s1 - s0)]
        drops += [(to_seq(a), to_seq(b)) for a, b in mm["drops"] if fin <= a <= fin + (s1 - s0)]
        bp = np.median(mm["bpm"]) if mm["bpm"] else 120
        res.setdefault("beat_len", 60 / bp)
    if len(beats) > 50:
        res["music"] = True
        B = np.array(sorted(beats))
        cuts = np.array([a for a, b, _ in shots[1:]])
        near = np.array([B[np.argmin(np.abs(B - c))] for c in cuts])
        off = (cuts - near) * fps                         # frames, + = after the beat
        onb = np.abs(off) <= 2.5
        res["on_beat"] = float(onb.mean())
        res["offset_frames"] = float(np.median(off[onb])) if onb.any() else 0.0
        et = np.array([t for t, _ in energy])
        ev = np.array([v for _, v in energy])
        en_of = lambda a, b: float(ev[(et >= a) & (et < b)].mean()) if ((et >= a) & (et < b)).any() else 0.5
        in_drop = lambda a: any(d0 - 0.1 <= a < d1 for d0, d1 in drops)
        calm = [b - a for a, b, _ in shots if not in_drop(a) and en_of(a, b) <= 0.35]
        hot = [b - a for a, b, _ in shots if not in_drop(a) and en_of(a, b) >= 0.7]
        dr = [b - a for a, b, _ in shots if in_drop(a)]
        res["calm"] = float(np.median(calm)) if calm else None
        res["intense"] = float(np.median(hot)) if hot else None
        res["drop"] = float(np.median(dr)) if dr else None
    # ---- static / handheld (files of this project)
    if cams:
        role = {Path(p).name: c["role"] for c in cams for p in c["clips"]}
        tot = {"Static": 0.0, "Handheld": 0.0}
        for a, b, n in shots:
            r = role.get(n)
            if r in tot:
                tot[r] += b - a
        if sum(tot.values()) > 0:
            res["handheld_share"] = tot["Handheld"] / sum(tot.values())
    res["suggest"] = suggest(res)
    return res


def suggest(r):
    """His numbers -> Auto Director settings."""
    s = {}
    s["minshot"] = float(min(10, max(1, round(r["p15"] * 2) / 2)))
    s["maxshot"] = int(min(60, max(10, round(r["p95"]))))
    # median shot 3 s -> pace 70, 6 s -> 50, 10 s -> 25
    s["pace"] = int(min(95, max(5, round(70 - (r["median"] - 3) * (45 / 7)))))
    if r.get("handheld_share") is not None:
        s["energy"] = int(min(95, max(5, round(20 + 70 * r["handheld_share"]))))
    if r.get("music"):
        bl = r.get("beat_len", 0.5)
        if r.get("drop"):
            beats = r["drop"] / bl
            s["drop_beats"] = min((1, 2, 4, 8, 16), key=lambda x: abs(np.log2(x) - np.log2(max(0.5, beats))))
    return s                 # faster cuts on intense music and the cut 1 frame before the beat are automatic now
