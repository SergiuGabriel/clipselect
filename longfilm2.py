"""Long Film v2 (BETA): the long film from the editor's labelled sequence, every colour handled its own way.

After Create Project (a chronological or a timecode synced sequence) he labels the shots in Premiere and exports the
sequence as XML. Only the labelled cameras matter (one, two, three or more of the cameras in the sequence).

Colours (v2 only, nothing to do with the old Long Film / Teaser Studio colours):
  Blue groom, Rose bride        -> selection (Auto: minimum cut 2 s, threshold 60), groom and bride together, chronological
  Teal first look               -> synced only (the cameras one above the other, he cuts)
  Forest vornic (switch ON/OFF) -> 2 cameras synced by their own sound, cut like the old Long Film (V1 / V2 / V3)
  Brown church                  -> selection; the PRIEST's shot (at least 60 s still on one face, speaking) stays whole
  Yellow venue, Purple couple, Violet drone -> selection
  Iris / Cerulean party         -> multicam of every labelled camera + the recorder files in the sequence (sync by the
                                   sound, Auto Edit with his party settings, Slower cuts zones for the hora)
  Tan interviews and any other colour -> ignored for now
The order of the parts = the order in which the colours appear on camera A (V1 of a timecode sequence, the first camera
of a chronological one). The export: ONE 25 fps 1920x1080 sequence, other frame sizes scaled to fill it, every camera
with its own sound tracks (stereo pairs like Premiere), the recorder under the party.
"""
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core
import director
import longfilm
import projectsetup
import sync
import teaser
import xmlimport

KINDS = {"Blue": "groom", "Rose": "bride", "Teal": "firstlook", "Forest": "vornic", "Brown": "church", "Yellow": "venue",
         "Purple": "couple", "Violet": "drone", "Iris": "party", "Cerulean": "party"}
PART_OF = {"groom": "ready", "bride": "ready"}
PART_NAMES = {"ready": "Groom and bride", "firstlook": "First look", "vornic": "Vornic", "church": "Church",
              "couple": "Couple", "venue": "Venue", "drone": "Drone", "party": "Party"}
DEFAULT_ORDER = ["ready", "firstlook", "vornic", "church", "couple", "venue", "drone", "party"]
SELECT = ("ready", "church", "couple", "venue", "drone")       # parts made with the Auto selection
SEL_THR, SEL_MIN = 60, 2.0          # owner: Auto, minimum cut length 2 s, selection threshold 60
SHORT_WHOLE = 6.0                   # a clip HE labelled that is this short is a deliberate detail: kept whole
                                    # (his Alex & Andreea venue: 63257-63261, 3-5 s each, were all dropped by the selection)
PARTY_GAP = 30.0                    # a stretch of the party where no camera filmed, longer than this, is taken out
PARTY_PAUSE = 2.0                   # ... and replaced by this little pause (his v3.15 test: 121 + 65 + 23 min of nothing)
PRIEST_MIN = 60.0                   # the priest: at least 60 s on him, the camera still
PARTY = dict(minshot=3, maxshot=120, pace=50, energy=65, beat=True, drop_beats=4, buildup="accelerate",
             energy_cuts=True)      # owner's party settings (editable on the page)
SEQ_FPS, SEQ_W, SEQ_H = 25.0, 1920, 1080


AUTO = "?"                          # a clip whose moment is not known yet (no colour: found automatically)


def part_of(kind):
    return PART_OF.get(kind, kind)


# ---------------------------------------------------------------- 1. the labelled sequence
def load(xml_path):
    """His labelled sequence -> dict(pieces, recorder, cams, cam_a, layout, order, skipped).
    pieces: every labelled video clip of a known colour: path, a / b (seconds in the file), st (timeline s), track,
    label, kind, w, h, fps, fdur, cam (camera index, camera A = 0). recorder: the sound-only files on the timeline."""
    root = ET.parse(xml_path).getroot()
    files = {}
    for f in root.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            sc = f.find("media/video/samplecharacteristics")
            files[f.get("id")] = dict(path=xmlimport._path(f.findtext("pathurl")), fps=xmlimport._rate(f, 25.0),
                                      dur=teaser._n(f.findtext("duration")), video=f.find("media/video") is not None,
                                      w=int(sc.findtext("width") or 1920) if sc is not None else 1920,
                                      h=int(sc.findtext("height") or 1080) if sc is not None else 1080)
    seqs = list(root.iter("sequence"))
    if not seqs:
        raise ValueError("No sequence in this XML.")
    seq = max(seqs, key=lambda s: (sum(1 for c in s.iter("clipitem") if c.findtext("labels/label2") in KINDS),
                                   sum(1 for _ in s.iter("clipitem"))))
    sfps = xmlimport._rate(seq, 25.0)
    clips, skipped = [], {}
    vid = seq.find("media/video")
    for t, tr in enumerate(vid.findall("track") if vid is not None else [], 1):
        for ci in tr.findall("clipitem"):
            f = ci.find("file")
            info = files.get(f.get("id")) if f is not None else None
            if not info or not info["path"] or ci.find("sequence") is not None:
                continue
            cfps = xmlimport._rate(ci, sfps)
            a, b = teaser._n(ci.findtext("in")) / cfps, teaser._n(ci.findtext("out")) / cfps
            real = info["dur"] / max(1e-6, info["fps"])
            cd = teaser._n(ci.findtext("duration")) / cfps
            interp = cd / real if real > 0 and cd > 0 else 1.0
            if interp > 1.2 or interp < 0.8:            # footage interpreted at another rate in Premiere
                a, b = a / interp, b / interp
            b = min(b, real) if real > 0 else b
            tt = teaser._times(ci, sfps, cfps)
            if b - a < 0.2 or not tt:
                continue
            lab = ci.findtext("labels/label2") or ""
            clips.append(dict(path=info["path"], a=a, b=b, st=tt[0], en=tt[1], track=t, label=lab, kind=KINDS.get(lab),
                              w=info["w"], h=info["h"], fps=info["fps"], fdur=real))
    if not clips:
        raise ValueError("No video clips found in this XML.")
    auto = not any(c["kind"] for c in clips)
    if auto:                                # no colours: every clip once, the moments are found by daymap in build()
        seen_c, uniq = set(), []
        for c in sorted(clips, key=lambda c: (c["st"], c["track"])):
            k = (c["path"], round(c["a"], 2), round(c["b"], 2))
            if k not in seen_c:
                seen_c.add(k)
                c["kind"] = AUTO
                uniq.append(c)
        clips = uniq
    # the recorder: sound-only files on the audio tracks (each file once)
    recorder, seen = [], set()
    aud = seq.find("media/audio")
    for tr in (aud.findall("track") if aud is not None else []):
        for ci in tr.findall("clipitem"):
            f = ci.find("file")
            info = files.get(f.get("id")) if f is not None else None
            if not info or not info["path"] or info["video"] or info["path"] in seen:
                continue
            tt = teaser._times(ci, sfps, xmlimport._rate(ci, sfps))
            seen.add(info["path"])
            recorder.append(dict(path=info["path"], st=tt[0] if tt else 0.0, group=Path(info["path"]).parent.name))
    recorder.sort(key=lambda r: r["st"])
    # cameras by their files; camera A = the camera of the first clip on the lowest video track
    keys = {}
    for c in clips:
        keys.setdefault(longfilm.camera_key(c), []).append(c)
    low = min(c["track"] for c in clips)
    first = min((c for c in clips if c["track"] == low), key=lambda c: c["st"])
    ka = longfilm.camera_key(first)
    order = [ka] + sorted((k for k in keys if k != ka), key=lambda k: min((c["track"], c["st"]) for c in keys[k]))
    labelled = [k for k in order if any(c["kind"] for c in keys[k])]
    if ka not in labelled and labelled:                # camera A has no labels: the first labelled camera leads
        ka = labelled[0]
    cam_keys = [ka] + [k for k in labelled if k != ka] if labelled else [ka]
    cams = [dict(key=k, name=longfilm.camera_name(keys[k])) for k in cam_keys]
    idx = {k: i for i, k in enumerate(cam_keys)}
    pieces = []
    for c in clips:
        if not c["kind"]:
            if c["label"]:
                skipped[c["label"]] = skipped.get(c["label"], 0) + 1
            continue
        c["cam"] = idx[longfilm.camera_key(c)]
        pieces.append(c)
    pieces.sort(key=lambda p: (p["st"], p["track"]))
    # timecode synced (cameras side by side on their own tracks, overlapping in time) or chronological (one after another)
    by_cam = {}
    for p in clips:
        by_cam.setdefault(longfilm.camera_key(p), []).append((p["st"], p["en"], p["track"]))
    layout = "chronological"
    ks = list(by_cam)
    for i in range(len(ks)):
        for j in range(i + 1, len(ks)):
            if any(a0 < b1 and b0 < a1 for a0, a1, _ in by_cam[ks[i]] for b0, b1, _ in by_cam[ks[j]]):
                layout = "timecode"
    # the order of the parts = the order of the colours on camera A, then the others
    seen_parts = []
    for p in pieces:
        if p["cam"] == 0 and part_of(p["kind"]) not in seen_parts:
            seen_parts.append(part_of(p["kind"]))
    for k in DEFAULT_ORDER:
        if k not in seen_parts and any(part_of(p["kind"]) == k for p in pieces):
            seen_parts.append(k)
    if "party" in seen_parts:               # the party always closes the film (Iris shots of the morning on camera A
        seen_parts.remove("party")          # put it before the church in his first test)
        seen_parts.append("party")
    if auto:
        seen_parts = []
    return dict(pieces=pieces, recorder=recorder, cams=cams, layout=layout, order=seen_parts, skipped=skipped, auto=auto)


def chrono(ps, layout, infos):
    """Recording order: the timeline itself in a timecode synced sequence; else the cameras' clocks (creation time, else
    time of day) when every piece has one, else the timeline."""
    if ps and all(p.get("t") is not None for p in ps):          # the automatic day map's common clock
        return sorted(ps, key=lambda p: (p["t"], p["st"]))
    if layout == "timecode":
        return sorted(ps, key=lambda p: p["st"])
    ct = [(infos.get(p["path"]) or {}).get("ctime") for p in ps]
    if ps and all(c is not None for c in ct):
        return [p for _c, p in sorted(zip(ct, ps), key=lambda x: (x[0] + x[1]["a"], x[1]["st"]))]
    td = [(infos.get(p["path"]) or {}).get("tod") for p in ps]
    if ps and all(c is not None for c in td):
        td = [c + 86400 if c < projectsetup.SYNC_DAY else c for c in td]
        return [p for _c, p in sorted(zip(td, ps), key=lambda x: (x[0] + x[1]["a"], x[1]["st"]))]
    return sorted(ps, key=lambda p: (p["cam"], p["st"]))


def key_of(p, a=None, b=None):
    a = p["a"] if a is None else a
    b = p["b"] if b is None else b
    return f'{p["path"]}#{a:.3f}-{b:.3f}'


def stamp(path):
    try:
        st = Path(path).stat()
        return f"{st.st_size}-{int(st.st_mtime)}"
    except OSError:
        return ""


# ---------------------------------------------------------------- 2. selection + the priest
def selection(an, a0):
    """The Auto selection of one labelled clip (analysis of that range): [(src in, src out)] in file seconds."""
    return [(a0 + s0, a0 + s1) for s0, s1, lv in core.auto_segments(an, SEL_THR, SEL_MIN) if lv == 2 and s1 - s0 >= SEL_MIN - 1e-6]


def still_run(an):
    """The longest stretch (s, from the start of the range) where the camera does not move: (start, end)."""
    if not an.fs:
        return (0.0, 0.0)
    mv = core.moving_mask(an.fs)
    sr = core.SAMPLE_FPS
    # a blip of up to 1 s (a hand, a lens breath) does not break the shot
    still = ~mv
    i, n, best = 0, len(still), (0, 0)
    while i < n:
        if not still[i]:
            i += 1
            continue
        j, gap = i, 0
        k = i
        while k < n:
            if still[k]:
                j, gap = k + 1, 0
            else:
                gap += 1
                if gap > sr:
                    break
            k += 1
        if j - i > best[1] - best[0]:
            best = (i, j)
        i = max(j, i + 1)
    return best[0] / sr, best[1] / sr


def speaks(x, sr=sync.SR):
    """Someone speaks most of the time: at least half of the 0.5 s windows clearly above the quiet floor."""
    hop = sr // 2
    n = len(x) // hop
    if n < 20:
        return False
    db = 10 * np.log10((x[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1) + 1e-12)
    floor = np.percentile(db, 10)
    return float(np.mean(db > floor + 10)) >= 0.5 and float(np.percentile(db, 90)) > -55


def one_face(path, t0, t1, model):
    """The same single face all along (the biggest face of 5 frames is the same person). None = no face model."""
    if model is None:
        return None
    import faces
    feats = []
    for f in np.linspace(0.1, 0.9, 5):
        img = faces.frame_bgr(path, t0 + (t1 - t0) * f)
        if img is None:
            return False
        fs = model.faces(img)
        if not fs:
            return False
        feats.append(max(fs, key=lambda x: x[1])[0])
    return all(float(feats[0] @ g) >= faces.SAME for g in feats[1:])


def is_priest(p, an, model=None):
    """A church clip with at least 60 s where the camera stays on one face (the priest) and someone speaks."""
    if p["b"] - p["a"] < PRIEST_MIN:
        return False
    s0, s1 = still_run(an)
    if s1 - s0 < PRIEST_MIN:
        return False
    try:
        x = longfilm._clip_audio(dict(p, a=p["a"] + s0, b=p["a"] + s1))
    except Exception:
        x = np.zeros(0, np.float32)
    if not speaks(x):
        return False
    face = one_face(p["path"], p["a"] + s0, p["a"] + s1, model)
    return face is not False                    # no face model: still + speaking is enough


# ---------------------------------------------------------------- 3. the party (multicam)
def party_inputs(pieces, recorder, infos):
    """Like Multicam (sync.classify): the MAIN recorder = the folder of sound-only files with the most hours, sorted by
    name; the other sound folders (a second recorder, lavaliers) are EXTRA sources synced like clips and exported whole
    on their own tracks. No recorder: the longest party file with sound. Returns (party, files, masters, extras)."""
    party = [p for p in pieces if p["kind"] == "party"]
    files = sorted({p["path"] for p in party})
    rec = [r for r in recorder if Path(r["path"]).exists()]
    masters, extras = [], []
    if rec:
        tot = {}
        for r in rec:
            g = r.get("group") or Path(r["path"]).parent.name
            tot[g] = tot.get(g, 0.0) + ((infos.get(r["path"]) or {}).get("dur") or 0.0)
        main = max(tot, key=lambda g: (tot[g], g))
        masters = sorted(r["path"] for r in rec if (r.get("group") or Path(r["path"]).parent.name) == main)
        extras = sorted(r["path"] for r in rec if r["path"] not in masters)
    if not masters:
        snd = [f for f in files if (infos.get(f) or {}).get("ach")]
        if snd:
            masters = [max(snd, key=lambda f: infos[f]["dur"])]
    return party, files, masters, extras


def party_edit(party, results, masters, analyses, cams_n, roles, st):
    """director.build on the labelled party ranges (each one a clip of its own). Returns (edits, cams for the director,
    {key: piece})."""
    by_key, res, an = {}, {}, {}
    clips = [[] for _ in range(cams_n)]
    for p in party:
        r = results.get(p["path"])
        k = key_of(p)
        if not r or r.get("conf") not in ("high", "medium") or k not in analyses:
            continue
        by_key[k] = p
        res[k] = dict(r, offset=r["offset"] + p["a"], dur=p["b"] - p["a"])
        an[k] = analyses[k]
        clips[p["cam"]].append(k)
    dcams = [dict(name=str(i), role=roles.get(i, "Handheld"), clips=c) for i, c in enumerate(clips)]
    edits = director.build(dcams, res, an, masters, st) if by_key else []
    return edits, dcams, by_key


def party_layout(edits, by_key, masters, rec_paths=None, results=None, extras=()):
    """The party part, laid out like the Multicam export: every camera's cuts on its own video track (camera index + 1,
    picture only), every camera's sound WHOLE (each labelled party range uncut) on that camera's audio tracks, the main
    recorder and every extra sound source (second recorder, lavaliers) uncut under the party.
    Returns (length, video items, audio items); audio items = (t0, path, src in, src out, audio key, label)."""
    starts = sync.master_starts(masters)
    cuts = []
    for e in edits or []:
        if not e:
            continue
        g = starts[e["master"]]
        for ci, k, cin, cout, s0 in e["pieces"]:
            p = by_key[k]
            cuts.append((g + s0, g + s0 + (cout - cin), p, p["a"] + cin, p["a"] + cout))
    if not cuts:
        return 0.0, [], []
    # the stretches where the cameras filmed; empty ones longer than PARTY_GAP are taken out (dinner, a break)
    segs = []
    for t0, t1, *_ in sorted(cuts, key=lambda c: c[0]):
        if segs and t0 - segs[-1][1] <= PARTY_GAP:
            segs[-1][1] = max(segs[-1][1], t1)
        else:
            segs.append([t0, t1])
    pos = 0.0
    for sg in segs:
        sg.append(pos)
        pos += sg[1] - sg[0] + PARTY_PAUSE
    length = pos - PARTY_PAUSE

    def where(t):
        for lo, hi, new in segs:
            if lo - 1e-6 <= t <= hi + 1e-6:
                return new + t - lo
        return None
    items = [(p["cam"] + 1, where(t0), p, a, b) for t0, _t1, p, a, b in sorted(cuts, key=lambda c: c[0])]
    ncam = max(p["cam"] for p in by_key.values()) + 1 if by_key else 1
    for e in edits or []:                   # the alternative angle: the second best camera, ABOVE, switched off
        if not e or not e.get("alt"):
            continue
        g = starts[e["master"]]
        for _ci, k, cin, cout, s0 in e["alt"]:
            p = by_key.get(k)
            w = where(g + s0)
            if p is not None and w is not None:
                items.append((ncam + 1, w, p, p["a"] + cin, p["a"] + cout, {"off"}))
    rec = []

    def put(g0, path, a, b, key, label=None):
        for lo, hi, new in segs:            # every stretch it covers, each one in its new place
            lo2, hi2 = max(lo, g0), min(hi, g0 + (b - a))
            if hi2 - lo2 > 0.1:
                rec.append((new + lo2 - lo, path, a + lo2 - g0, a + hi2 - g0, key, label))
    results = results or {}
    for p in sorted(by_key.values(), key=lambda p: (p["cam"], p["a"])):   # the cameras' sound, whole
        r = results.get(p["path"])
        if r and r.get("conf") in ("high", "medium") and r.get("master", 0) < len(starts):
            put(starts[r.get("master", 0)] + r["offset"] + p["a"], p["path"], p["a"], p["b"], ("cam", p["cam"]), p.get("label"))
    for m, s in zip(masters, starts):
        if not m.get("path") or (rec_paths is not None and m["path"] not in rec_paths):
            continue                        # no recorder: the master is a party clip, its sound is already there
        put(s, m["path"], 0.0, m["duration"], ("rec", 0))
    for j, f in enumerate(extras, 1):       # extra sound sources, each folder its own tracks
        r = results.get(f)
        if r and r.get("conf") in ("high", "medium") and r.get("master", 0) < len(starts):
            put(starts[r.get("master", 0)] + r["offset"], f, 0.0, r.get("dur") or 0.0,
                ("rec", 1 + sorted({Path(x).parent.name for x in extras}).index(Path(f).parent.name)))
    return length, items, rec


# ---------------------------------------------------------------- 4. the XML
def _scale(w, h):
    """Basic Motion scale so the picture fills the 1920x1080 frame (a 4K clip -> 50 %); vertical / odd shapes fit."""
    if (w, h) == (SEQ_W, SEQ_H) or not w or not h:
        return None
    fill, fit = max(SEQ_W / w, SEQ_H / h), min(SEQ_W / w, SEQ_H / h)
    s = fill if abs((w / h) / (SEQ_W / SEQ_H) - 1) < 0.12 else fit
    return round(s * 100, 3)


def _motion(s):
    return ('<filter><effect><name>Basic Motion</name><effectid>basic</effectid><effectcategory>motion</effectcategory>'
            '<effecttype>motion</effecttype><mediatype>video</mediatype><parameter authoringApp="PremierePro">'
            f'<parameterid>scale</parameterid><name>Scale</name><valuemin>0</valuemin><valuemax>1000</valuemax>'
            f'<value>{s}</value></parameter></effect></filter>')


def export_xml(parts, infos, cam_names, out_path, name, marker=lambda s: s, look=None):
    """parts: [(part name, length s, items, recorder items)]; items = (video track, t0 in the part, piece, src in,
    src out, flags) with flags in {"sound", "off"} ("off" = the clip is switched off: the vornic's whole 2nd camera);
    recorder items = (t0 in the part, path, src in, src out). One 25 fps 1920x1080 sequence. Every camera has its own
    audio tracks (stereo pairs / mono like Premiere, projectsetup.groups), the recorder last; links = position in the
    track. Returns (clips written, video tracks, audio tracks)."""
    rate_xml, sf = core._rate(SEQ_FPS)
    ents, markers, g = [], [], 0.0
    for pname, length, items, rec in parts:
        if not items and not rec:
            continue
        markers.append((pname, g))
        for it in items:
            track, t0, p, a, b = it[:5]
            flags = it[5] if len(it) > 5 else {"sound"}
            st = round((g + t0) * sf)
            en = st + max(1, round((b - a) * sf))
            ents.append(dict(path=p["path"], v=track, st=st, en=en, fin=max(0, round(a * sf)), label=p.get("label"),
                             ak=("cam", p["cam"]) if "sound" in flags else None, on="off" not in flags))
        for it in rec:
            t0, path, a, b = it[:4]
            st = round((g + t0) * sf)
            ents.append(dict(path=path, v=None, st=st, en=st + max(1, round((b - a) * sf)), fin=max(0, round(a * sf)),
                             label=it[5] if len(it) > 5 else None, ak=it[4] if len(it) > 4 else ("rec", 0), on=True))
        g += length
    if not ents:
        raise ValueError("Nothing to export yet: press Build first.")
    for e in ents:                          # never past the end of the file
        i = infos.get(e["path"]) or {}
        mx = int((i.get("dur") or 0) * sf)
        if mx and e["fin"] + (e["en"] - e["st"]) > mx:
            e["en"] = e["st"] + max(1, mx - e["fin"])
    # audio slots: cameras in their order, then the recorder; inside: stereo pairs first, then mono
    gr = lambda e: projectsetup.groups((infos.get(e["path"]) or {}).get("ach", 0))
    slots = sorted({(e["ak"], k, kind) for e in ents if e["ak"] for k, (kind, _c) in enumerate(gr(e))},
                   key=lambda s: (s[0][0] == "rec", s[0][1], s[2] != "stereo", s[1]))
    tix, tracks = {}, []
    for sl in slots:
        for ex in range(2 if sl[2] == "stereo" else 1):
            tix[(sl, ex)] = len(tracks) + 1
            tracks.append((sl, ex))
    busy = {}                               # one clip at a time on an audio track: a second one keeps only its picture
    for e in sorted(ents, key=lambda e: e["st"]):
        if not e["ak"]:
            continue
        if any(not (e["en"] <= s or e["st"] >= t) for s, t in busy.get(e["ak"], [])):
            e["ak"] = None
            continue
        busy.setdefault(e["ak"], []).append((e["st"], e["en"]))
    nv = max([e["v"] for e in ents if e["v"]] or [1])
    n = [0]

    def nid():
        n[0] += 1
        return f"clipitem-{n[0]}"
    for t in range(1, nv + 1):
        for ci, e in enumerate(sorted((e for e in ents if e["v"] == t), key=lambda e: e["st"]), 1):
            e["vid"] = (nid(), t, ci)
    for e in ents:
        e["aud"] = []
    for (sl, ex), ti in tix.items():
        lst = sorted((e for e in ents if e["ak"] == sl[0] and len(gr(e)) > sl[1] and gr(e)[sl[1]][0] == sl[2]),
                     key=lambda e: e["st"])
        for ci, e in enumerate(lst, 1):
            ch = gr(e)[sl[1]][1][ex]
            e["aud"].append((nid(), ti, ci, ch, sl[2]))
    files = {}

    def links(e):
        out = []
        if e.get("vid"):
            out.append(f'<link><linkclipref>{e["vid"][0]}</linkclipref><mediatype>video</mediatype><trackindex>'
                       f'{e["vid"][1]}</trackindex><clipindex>{e["vid"][2]}</clipindex></link>')
        out += [f'<link><linkclipref>{cid}</linkclipref><mediatype>audio</mediatype><trackindex>{ti}</trackindex>'
                f'<clipindex>{ci}</clipindex><groupindex>1</groupindex></link>' for cid, ti, ci, _ch, _k in e["aud"]]
        return "".join(out) if len(out) > 1 else ""

    def head(cid, e, attr=""):
        i = infos.get(e["path"]) or {}
        sdur = max(e["fin"] + e["en"] - e["st"], int((i.get("dur") or 0) * sf))
        return (f'<clipitem id="{cid}"{attr}><name>{escape(Path(e["path"]).name)}</name>'
                f'<enabled>{"TRUE" if e["on"] else "FALSE"}</enabled><duration>{sdur}</duration>{rate_xml}'
                f'<start>{e["st"]}</start><end>{e["en"]}</end><in>{e["fin"]}</in><out>{e["fin"] + e["en"] - e["st"]}</out>')

    lab = lambda e: f'<labels><label2>{escape(e["label"])}</label2></labels>' if e.get("label") else ""
    import colour
    looks = colour.clip_filters(look)       # his LUT(s) + crop on every picture clip
    vx = {t: [] for t in range(1, nv + 1)}
    ax = {ti: [] for ti in tix.values()}
    for e in sorted(ents, key=lambda e: e["st"]):
        i = infos.get(e["path"]) or {}
        if e.get("vid"):
            s = _scale(i.get("w"), i.get("h"))
            vx[e["vid"][1]].append(head(e["vid"][0], e) + projectsetup._file_xml(e["path"], i, files) +
                                   (_motion(s) if s else "") + looks + links(e) + lab(e) + "</clipitem>")
    for e in sorted(ents, key=lambda e: e["st"]):
        i = infos.get(e["path"]) or {}
        for cid, ti, _ci, ch, kind in e["aud"]:
            ax[ti].append(head(cid, e, f' premiereChannelType="{kind}"') + projectsetup._file_xml(e["path"], i, files) +
                          f'<sourcetrack><mediatype>audio</mediatype><trackindex>{ch}</trackindex></sourcetrack>' +
                          links(e) + lab(e) + "</clipitem>")
    total = max(e["en"] for e in ents)
    trk = lambda its, attrs="": f'<track{attrs}>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    arate = next(((infos.get(e["path"]) or {}).get("arate") for e in ents if (infos.get(e["path"]) or {}).get("ach")), 48000)
    audio = (f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
             f'<samplerate>{arate}</samplerate></samplecharacteristics></format>'
             f'{"".join(trk(ax[tix[(sl, ex)]], projectsetup._track_attrs(sl[2], ex)) for sl, ex in tracks)}</audio>')
    mk = "".join(f'<marker><name>{escape(marker(m))}</name><comment></comment><in>{round(t * sf)}</in><out>-1</out></marker>'
                 for m, t in markers)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}{mk}'
           f'<media><video><format>{core._sc(rate_xml, SEQ_W, SEQ_H, "none")}</format>'
           f'{"".join(trk(vx[t]) for t in range(1, nv + 1))}</video>{audio}</media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return len(ents), nv, len(tracks)


# ---------------------------------------------------------------- 4a. straight from the wedding folder
def _one_per_take(files):
    """A recorder writes one take as several files (Tascam 260823_0195_3 / _4 / _MIX): keep one per take (the MIX when
    there is one, else the first track), or the takes would be laid one after the other as if they followed."""
    takes = {}
    for f in files:
        m = re.match(r"(.+?)[_-](\d|MIX|mix|LR|lr)$", Path(f).stem)
        takes.setdefault(m.group(1) if m else Path(f).stem, []).append(f)
    out = []
    for _k, fs in sorted(takes.items()):
        mix = [f for f in fs if re.search(r"(?i)[_-](mix|lr)$", Path(f).stem)]
        out.append(mix[0] if mix else sorted(fs)[0])
    return out


def folder_xml(root, progress=None, cancel=None, jobs=4):
    """The Create Project sequence made right here from the wedding folder (Chronological: every camera whole, one after
    the other, the drone after them), WITH the sound folders (recorder, lavaliere) at the end so the party can be synced.
    No colours: the moments are found automatically. Returns the XML path (saved in the wedding folder)."""
    root = Path(root)
    cams = projectsetup.find_cameras(root)
    slots = projectsetup.default_slots(cams)
    cams = [c for c, s_ in projectsetup.by_slot(cams, slots) if s_ != "sound"]
    snd = [dict(c, files=_one_per_take(c["files"])) for c in projectsetup.sound_files(root)]
    if not cams:
        raise ValueError("No camera folders with video in this folder.")
    infos = projectsetup.read_all(cams + snd, progress, cancel, jobs=jobs)
    lay, _bad = projectsetup.layout(cams, infos)
    items = [(f, 1, 0, st, ln) for _cam, row in lay for f, st, ln in row]
    sf = projectsetup.SEQ_FPS
    pos = max((st + ln for _f, _v, _a, st, ln in items), default=0) + round(projectsetup.GAP * sf)
    for j, c in enumerate(snd, 1):
        for f in c["files"]:
            if (infos.get(f) or {}).get("ach") and infos[f].get("dur"):
                n = int(infos[f]["dur"] * sf)
                items.append((f, None, j, pos, n))
                pos += n
        pos += round(60 * sf)
    out = projectsetup.free_path(root / f"{root.name} - Long Film v2 (automatic).xml")
    projectsetup._write(items, infos, str(out), f"{root.name} - automatic", None, [], (), [(c, len(r)) for c, r in lay])
    return str(out)


# ---------------------------------------------------------------- 4b. the moments without colours (daymap)
def own_clock(paths, infos):
    """Every file's start on ITS camera's clock: the recording time when every clip of the camera has one, else the
    file date minus its length (copies keep the date of the end of the recording)."""
    if paths and all((infos.get(f) or {}).get("ctime") for f in paths):
        return {f: infos[f]["ctime"] for f in paths}
    return {f: (infos.get(f) or {}).get("mtime", 0.0) - (infos.get(f) or {}).get("dur", 0.0) for f in paths}


def auto_moments(L, pieces, recorder, infos, prog, cancel, jobs, model_dir):
    """No colours in his sequence: 1. every clip with sound is synced to the recorder (like Multicam) -> every camera's
    clock error; 2. the faces of 5 frames of every clip; 3. daymap.classify -> colours. Sets p["label"] / p["kind"] /
    p["t"] (common clock). Returns (info for the page, (masters info, sync results) or None)."""
    import daymap
    cams = sorted({p["cam"] for p in pieces})
    own = {}
    for c in cams:
        own.update(own_clock(sorted({p["path"] for p in pieces if p["cam"] == c}), infos))
    # 1. the recorder sync gives every camera's clock error
    shift, synced = {c: 0.0 for c in cams}, None
    tmp = [dict(p, kind="party") for p in pieces]
    _party, files, masters, extras = party_inputs(tmp, recorder, infos)
    if masters and recorder:
        clips = [f for f in files if f not in masters and (infos.get(f) or {}).get("ach")]
        clocks = {}
        for f in clips + masters + extras:
            try:
                clocks[f] = sync.media_info(f)["clock"]
            except Exception:
                clocks[f] = None
        camk = {p["path"]: str(p["cam"]) for p in pieces}
        camk.update({f: "rec:" + Path(f).parent.name for f in extras})
        try:
            info, res = sync.run_sync(masters, clips + extras, lambda s, f: prog(s, 0.06 + 0.3 * f), cancel,
                                      clocks=clocks, groups=camk, jobs=jobs)
            synced = (info, res)
            starts = sync.master_starts(info)
            d = {}
            for p in pieces:
                r = res.get(p["path"])
                if r and r.get("conf") == "high" and r.get("master", 0) < len(starts):
                    d.setdefault(p["cam"], []).append(starts[r.get("master", 0)] + r["offset"] - own[p["path"]])
            med = {c: float(np.median(v)) for c, v in d.items()}
            ref = 0 if 0 in med else (min(med) if med else None)
            if ref is not None:
                shift = {c: med.get(c, med[ref]) - med[ref] for c in cams}
        except InterruptedError:
            raise
        except Exception:
            synced = None
    # 2. faces
    model = None
    if model_dir:
        try:
            import faces
            model = faces.Faces(faces.ensure_models(model_dir))
        except Exception:
            model = None
    fz = {}
    for k, p in enumerate(pieces):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        prog(f"Looking at who is in every clip: {k + 1} of {len(pieces)}", 0.36 + 0.1 * k / max(1, len(pieces)))
        feats = []
        if model is not None and p.get("w"):
            import faces
            for f in np.linspace(0.1, 0.9, 5):
                img = faces.frame_bgr(p["path"], p["a"] + (p["b"] - p["a"]) * f)
                if img is not None:
                    try:
                        feats += [daymap._unit(x[0]) for x in model.faces(img)]
                    except Exception:
                        pass
        fz[key_of(p)] = feats
    # 3. the moments
    clips = {key_of(p): dict(t0=own[p["path"]] + shift[p["cam"]] + p["a"], dur=p["b"] - p["a"], path=p["path"])
             for p in pieces}
    lab, info = daymap.classify(clips, fz)
    for p in pieces:
        k = key_of(p)
        p["t"] = clips[k]["t0"]
        p["label"] = lab.get(k, "Iris")
        p["kind"] = KINDS.get(p["label"], AUTO)
    info["counts"] = {}
    for p in pieces:
        info["counts"][p["label"]] = info["counts"].get(p["label"], 0) + 1
    info["faces"] = model is not None
    info["shift"] = {str(c): round(v) for c, v in shift.items()}
    return info, synced


# ---------------------------------------------------------------- 5. the build job (heavy work, in a thread)
def build(xml_path, vornic_on, cache, progress=None, cancel=None, jobs=2, model_dir=None):
    """Everything that reads the media: probe, analyses (cached in `cache`: {key: dict(key=stamp, a=json)}), the
    priest, first look and vornic sync, the party sync and its music. Returns a JSON-able result for the page."""
    from concurrent.futures import ThreadPoolExecutor
    prog = progress or (lambda s, f: None)

    def chk():
        if cancel and cancel():
            raise InterruptedError("Cancelled")
    L = load(xml_path)
    pieces, recorder = L["pieces"], L["recorder"]
    missing = sorted({p["path"] for p in pieces if not Path(p["path"]).exists()})
    pieces = [p for p in pieces if Path(p["path"]).exists()]
    if not pieces:
        raise ValueError("None of the labelled clips were found on this computer: connect the disk with the footage.")
    paths = sorted({p["path"] for p in pieces} | {r["path"] for r in recorder if Path(r["path"]).exists()})
    infos = {}
    for k, f in enumerate(paths):
        chk()
        prog(f"Reading the files: {k + 1} of {len(paths)}", 0.05 * k / max(1, len(paths)))
        try:
            infos[f] = projectsetup.probe(f)
        except Exception:
            infos[f] = dict(video=False, dur=0.0, fps=25.0, w=1920, h=1080, ach=0, arate=48000, ctime=None, tod=None)
    auto = None
    psync_res = None
    if L.get("auto"):
        auto, psync_res = auto_moments(L, pieces, recorder, infos, prog, cancel, jobs, model_dir)
        pieces = [p for p in pieces if p["kind"] != AUTO]
    # analyses: every selection range + every party range (once, cached)
    use = [p for p in pieces if part_of(p["kind"]) in SELECT or p["kind"] == "party"]
    analyses, todo = {}, []
    for p in use:
        k = key_of(p)
        c = cache.get(k)
        if c and c.get("key") == stamp(p["path"]):
            try:
                analyses[k] = core.Analysis.from_json(c["a"])
                continue
            except Exception:
                pass
        todo.append(p)
    done = [0]

    def one(p):
        if cancel and cancel():
            return
        k = key_of(p)
        try:
            a = core.analyze(p["path"], cancel=cancel, a=p["a"], b=p["b"])
            analyses[k] = a
            cache[k] = dict(key=stamp(p["path"]), a=a.to_json())
        except InterruptedError:
            return
        except Exception:
            pass
        done[0] += 1
        prog(f"Looking at your selections: {done[0]} of {len(todo)}", 0.05 + 0.45 * done[0] / max(1, len(todo)))
    with ThreadPoolExecutor(max(1, jobs)) as ex:
        list(ex.map(one, todo))
    chk()
    # the priest (church clips of at least 60 s)
    model = None
    long_church = [p for p in pieces if p["kind"] == "church" and p["b"] - p["a"] >= PRIEST_MIN and key_of(p) in analyses]
    if long_church and model_dir:
        try:
            import faces
            model = faces.Faces(faces.ensure_models(model_dir))
        except Exception:
            model = None
    priests = []
    for k, p in enumerate(long_church):
        chk()
        prog(f"Looking for the priest: {k + 1} of {len(long_church)}", 0.5 + 0.05 * k / max(1, len(long_church)))
        try:
            if is_priest(p, analyses[key_of(p)], model):
                priests.append(key_of(p))
        except Exception:
            pass
    # selections
    sel = {}
    for p in pieces:
        if part_of(p["kind"]) in SELECT and key_of(p) in analyses and key_of(p) not in priests:
            if not L.get("auto") and p["b"] - p["a"] <= SHORT_WHOLE:
                sel[key_of(p)] = [(p["a"], p["b"])]
            else:
                sel[key_of(p)] = selection(analyses[key_of(p)], p["a"])
    # first look: synced only
    fl = chrono([p for p in pieces if p["kind"] == "firstlook"], L["layout"], infos)
    for p in fl:
        p["train"] = p["cam"]
    prog("Syncing the first look", 0.56)
    fl_len, fl_items = longfilm.firstlook_layout(fl, progress=lambda s, f: prog(s, 0.56 + 0.06 * f)) if fl else (0.0, [])
    # vornic: always 2 cameras
    vo_len, vo_items, vo_cams = 0.0, [], []
    vps = [p for p in pieces if p["kind"] == "vornic"]
    if vornic_on and vps:
        foot = {}
        for p in vps:
            foot[p["cam"]] = foot.get(p["cam"], 0.0) + p["b"] - p["a"]
        two = sorted(foot, key=lambda c: -foot[c])[:2]
        main = 0 if 0 in two else two[0]
        vo_cams = [main] + [c for c in two if c != main]
        mp = chrono([p for p in vps if p["cam"] == main], L["layout"], infos)
        op = chrono([p for p in vps if p["cam"] in vo_cams[1:]], L["layout"], infos)
        vo_len, vo_items = longfilm.vornic_cut(mp, op, progress=lambda s, f: prog(s, 0.62 + 0.06 * f), cancel=cancel)
    chk()
    # the party: sync with the recorder + its music
    party, pfiles, masters, extras = party_inputs(pieces, recorder, infos)
    psync = None
    if party and masters:
        clips = [f for f in pfiles if f not in masters and (infos.get(f) or {}).get("ach")] + extras
        clocks = {}
        for f in clips + masters:
            try:
                clocks[f] = sync.media_info(f)["clock"]
            except Exception:
                clocks[f] = None
        camk = {p["path"]: str(p["cam"]) for p in party}
        camk.update({f: "rec:" + Path(f).parent.name for f in extras})
        if psync_res and all(f in psync_res[1] for f in clips):
            info, res = psync_res                   # already synced by the automatic day map
        else:
            info, res = sync.run_sync(masters, clips, lambda s, f: prog(s, 0.68 + 0.22 * f), cancel,
                                      clocks=clocks, groups=camk, jobs=jobs)
        for f in pfiles:
            if f in masters:                # the longest party clip itself is the master
                res[f] = dict(conf="high", master=masters.index(f), offset=0.0, dur=infos[f]["dur"], drift_ppm=0.0)
        for i, m in enumerate(info):
            chk()
            prog(f"Reading the music (beats, bars, drops): {i + 1} of {len(info)}", 0.9 + 0.09 * i / max(1, len(info)))
            try:
                import music
                m["music"] = music.analyze(sync.audio_pcm(m["path"]))
            except Exception:
                m["music"] = None
        psync = dict(masters=info, results=res, extras=extras)
    prog("Done", 1.0)
    order = L["order"]
    if auto is not None:                    # the parts in the order of the day, the party last
        order = []
        for p in sorted(pieces, key=lambda p: p.get("t", 0.0)):
            k = part_of(p["kind"])
            if k not in order:
                order.append(k)
        if "party" in order:
            order.remove("party")
            order.append("party")
    return dict(pieces=pieces, recorder=recorder, cams=L["cams"], layout=L["layout"], order=order, auto=auto,
                skipped=L["skipped"], missing=missing, infos=infos, sel=sel, priests=priests,
                firstlook=[fl_len, [(t, t0, key_of(p), a, b, ["sound"]) for t, t0, p, a, b in fl_items]],
                vornic=[vo_len, [(t, t0, key_of(p), a, b, ["sound"] if t == 1 else (["sound", "off"] if t == 2 else []))
                                 for t, t0, p, a, b in vo_items], vo_cams],
                party=psync, faces=model is not None)


def roles_of(party, analyses):
    """Static / Handheld per camera, from its party footage."""
    out = {}
    for c in sorted({p["cam"] for p in party}):
        out[c] = director.detect_role([analyses.get(key_of(p)) for p in party if p["cam"] == c])
    return out


def shot_key(path, a, b):
    return f"{path}|{a:.3f}|{b:.3f}"


def alternate(a, b, base=4):
    """Groom and bride told in parallel the way he cuts the getting ready (longfilm.interleave_blocks, measured on two
    weddings): a big block of the side filmed first, a big block of the other, then turns of 2-7 shots so both end
    together. Each side keeps its own order (here: the common clock of the day, so cameras can be mixed)."""
    if not a or not b:
        return a + b
    out = []
    i = min(len(a), max(4, min(20, round(len(a) * 0.27))))
    j = min(len(b), max(4, min(14, round(len(b) * 0.2))))
    out += a[:i] + b[:j]
    turn = 0
    while i < len(a) or j < len(b):
        ra, rb = len(a) - i, len(b) - j
        if turn == 0 and ra:
            n = ra if not rb else max(1, min(7, round(base * ra / max(1, rb) * 0.5 + base * 0.5)))
            out += a[i:i + n]
            i += n
        elif rb:
            n = rb if not ra else max(1, min(7, round(base * rb / max(1, ra) * 0.5 + base * 0.5)))
            out += b[j:j + n]
            j += n
        turn ^= 1
    return out


def apply_edits(parts, keys, edits):
    """The editor's changes: edits = {part key: [shot keys in order]} for the selection parts. A shot can be moved to
    another part, removed (missing from every list) or reordered. keys = the part key of every part of `parts`."""
    if not edits:
        return parts
    pool = {}
    for (name, ln, items, rec), k in zip(parts, keys):
        if k in SELECT:
            for it in items:
                pool[shot_key(it[2]["path"], it[3], it[4])] = it
    out = []
    for (name, ln, items, rec), k in zip(parts, keys):
        if k in SELECT and k in edits:
            new, t = [], 0.0
            for sk in edits[k]:
                it = pool.get(sk)
                if it:
                    new.append((1, t, it[2], it[3], it[4], set(it[5])))
                    t += it[4] - it[3]
            out.append((name, t, new, rec))
        else:
            out.append((name, ln, items, rec))
    return out


def assemble(r, analyses, st, zones, marker=lambda s: s, vornic_on=True, edits=None):
    """The parts in his order, ready for export_xml, + the party edit for the map.
    r: build() result; st: party settings; zones: Slower cuts zones (timeline seconds of the party map);
    edits: the editor's changes (apply_edits). info["keys"] = the part key of every part."""
    by_key = {key_of(p): p for p in r["pieces"]}
    parts, info = [], {}
    stat = {}
    user_edits = edits                      # (the party branch below has its own "edits": the director's)
    for part in r["order"]:
        name = marker(PART_NAMES[part])
        if part in SELECT:
            ps = chrono([p for p in r["pieces"] if part_of(p["kind"]) == part], r["layout"], r["infos"])
            shots = []
            for p in ps:
                k = key_of(p)
                cuts = [(p["a"], p["b"])] if k in r["priests"] else r["sel"].get(k, [])
                shots += [(p, a, b) for a, b in cuts]
            if part == "ready":                 # groom and bride in parallel, not one after the other
                shots = alternate([x for x in shots if x[0]["kind"] == "groom"],
                                  [x for x in shots if x[0]["kind"] != "groom"])
            items, t = [], 0.0
            for p, a, b in shots:
                items.append((1, t, p, a, b, {"sound"}))
                t += b - a
            parts.append((name, t, items, []))
            stat[part] = (len(items), t)
        elif part in ("firstlook", "vornic"):
            ln, its = r[part][0], r[part][1]
            if part == "vornic" and (not its or not vornic_on):
                continue
            items = [(tr, t0, by_key[k], a, b, set(fl)) for tr, t0, k, a, b, fl in its if k in by_key]
            parts.append((name, ln, items, []))
            stat[part] = (len(items), ln)
        elif part == "party":
            ps = r.get("party")
            if not ps:
                continue
            party = [p for p in r["pieces"] if p["kind"] == "party"]
            roles = roles_of(party, analyses)
            edits, dcams, bk = party_edit(party, ps["results"], ps["masters"], analyses, len(r["cams"]), roles,
                                          {**director.DEFAULTS, **st, "zones": zones})
            ln, items, rec = party_layout(edits, bk, ps["masters"], {x["path"] for x in r["recorder"]},
                                          ps["results"], ps.get("extras") or ())
            parts.append((name, ln, [it if len(it) > 5 else (*it, set()) for it in items], rec))
            info.update(edits=edits, dcams=dcams, roles=roles)
            stat[part] = (len(items), ln)
    keys = [k for k in r["order"] if k in stat]
    if user_edits:
        parts = apply_edits(parts, keys, user_edits)
        for (name, ln, items, rec), k in zip(parts, keys):
            stat[k] = (len(items), ln)
    info["stat"] = stat
    info["keys"] = keys
    return parts, info
