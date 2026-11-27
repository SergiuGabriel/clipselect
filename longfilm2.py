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
import logging
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

KINDS = {"Blue": "groom", "Rose": "bride", "Teal": "firstlook", "Forest": "vornic", "Mango": "civil", "Brown": "church", "Yellow": "venue",
         "Purple": "couple", "Violet": "drone", "Iris": "party", "Cerulean": "party"}
# his own colours (card "Clip colours"): every moment -> a Premiere label / a DaVinci Resolve clip colour
MOMENTS = ["groom", "bride", "firstlook", "vornic", "civil", "church", "venue", "couple", "drone", "party"]
MOMENT_NAMES = {"groom": "Groom", "bride": "Bride", "firstlook": "First look", "vornic": "Vornic", "civil": "Civil ceremony", "church": "Church",
                "venue": "Venue", "couple": "Couple", "drone": "Drone", "party": "Party"}
PR_COLOURS = ["Violet", "Iris", "Caribbean", "Lavender", "Cerulean", "Forest", "Rose", "Mango", "Purple", "Blue", "Teal",
              "Magenta", "Tan", "Green", "Brown", "Yellow"]
DV_COLOURS = ["Orange", "Apricot", "Yellow", "Lime", "Olive", "Green", "Teal", "Navy", "Blue", "Purple", "Violet", "Pink",
              "Tan", "Beige", "Brown", "Chocolate"]
DEFAULT_PR = {"groom": "Blue", "bride": "Rose", "firstlook": "Teal", "vornic": "Forest", "civil": "Mango", "church": "Brown",
              "venue": "Yellow", "couple": "Purple", "drone": "Violet", "party": "Iris"}
DEFAULT_DV = {"groom": "Blue", "bride": "Pink", "firstlook": "Teal", "vornic": "Green", "civil": "Orange", "church": "Brown",
              "venue": "Yellow", "couple": "Purple", "drone": "Violet", "party": "Navy"}


def colour_maps(c):
    """(Premiere map, DaVinci map) {moment: colour}: his choice when the switch is on, else the defaults."""
    c = c or {}
    pr, dv = dict(DEFAULT_PR), dict(DEFAULT_DV)
    if c.get("on"):
        pr.update({k: v for k, v in (c.get("premiere") or {}).items() if v in PR_COLOURS})
        dv.update({k: v for k, v in (c.get("davinci") or {}).items() if v in DV_COLOURS})
    return pr, dv


def kinds_for(c):
    """Label -> moment used to READ his labelled sequence: the defaults, his own colours on top of them."""
    if not (c or {}).get("on"):
        return dict(KINDS)
    pr, dv = colour_maps(c)
    out = {}
    for m in (dv, pr):                      # his Premiere colours win when a name is in both lists
        out.update({v: k for k, v in m.items()})
    for lab, k in KINDS.items():            # a default colour he did not give to another moment still works
        out.setdefault(lab, k)
    return out


def labels_out(c, target):
    """{moment: colour} written on the exported clips (None = keep the labels as they are: Premiere, no own colours)."""
    pr, dv = colour_maps(c)
    if target == "davinci":
        return dv
    return pr if (c or {}).get("on") else None


PART_OF = {"groom": "ready", "bride": "ready"}
PART_NAMES = {"ready": "Groom and bride", "firstlook": "First look", "vornic": "Vornic", "civil": "Civil ceremony", "church": "Church",
              "couple": "Couple", "venue": "Venue", "drone": "Drone", "party": "Party"}
DEFAULT_ORDER = ["ready", "firstlook", "vornic", "civil", "church", "couple", "venue", "drone", "party"]
SELECT = ("ready", "church", "couple", "venue", "drone")       # parts made with the Auto selection
SEL_THR, SEL_MIN = 60, 2.0          # owner: Auto, minimum cut length 2 s, selection threshold 60
SEL_KEEP = 1.0                      # the good part of a short clip is kept from 1 s (Keep every good frame)
SHORT_WHOLE = 6.0                   # a clip HE labelled that is this short is a deliberate detail: kept whole
                                    # (his Alex & Andreea venue: 63257-63261, 3-5 s each, were all dropped by the selection)
STATIC_CLIP = 600.0                 # a camera whose clips are this long (median) stands on a tripod
PARTY_GAP = 0.04                    # every stretch of the party where no camera filmed is taken out (owner: never black)
PARTY_PAUSE = 0.0                   # ... with no pause: the next filmed moment follows at once
PRIEST_MIN = 60.0                   # the priest: at least 60 s on him, the camera still
PARTY = dict(minshot=3, maxshot=120, pace=50, energy=65, beat=True, drop_beats=4, buildup="accelerate",
             energy_cuts=True)      # owner's party settings (editable on the page)
SEQ_FPS, SEQ_W, SEQ_H = 25.0, 1920, 1080


AUTO = "?"                          # a clip whose moment is not known yet (no colour: found automatically)


def part_of(kind):
    return PART_OF.get(kind, kind)


# ---------------------------------------------------------------- 1. the labelled sequence
def load(xml_path, kinds=None):
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
    kinds = kinds or KINDS
    seq = max(seqs, key=lambda s: (sum(1 for c in s.iter("clipitem") if c.findtext("labels/label2") in kinds),
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
            clips.append(dict(path=info["path"], a=a, b=b, st=tt[0], en=tt[1], track=t, label=lab, kind=kinds.get(lab),
                              w=info["w"], h=info["h"], fps=info["fps"], fdur=real))
    if not clips:
        raise ValueError("No video clips found in this XML.")
    labs = {c["label"] for c in clips}
    # Premiere gives every video clip "Iris" by itself: a sequence where EVERY clip is Iris was never labelled
    # (his 28 August "selectie": 309 clips, all Iris) -> the moments are found automatically, not 309 party clips
    auto = not any(c["kind"] for c in clips) or (labs == {"Iris"} and len(clips) >= 10)
    if auto:
        for c in clips:
            c["kind"] = None
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


def auto_order(pieces):
    """The parts of an automatic film in the order of the story: the drone shots first (owner), getting ready, first look, vornic, church, then the
    couple and the venue in the order they were filmed AFTER the church (a venue filmed only in the morning comes after
    the couple), the party last. The day itself can start anywhere (28 August:
    the venue's decorations were filmed first, before the groom)."""
    have = {part_of(p["kind"]) for p in pieces}
    order = [k for k in ("ready", "firstlook", "vornic", "civil", "church") if k in have]
    ch = [p["t"] for p in pieces if p["kind"] == "church" and p.get("t") is not None]
    c1 = max(ch) if ch else None

    def when(part):
        ts = [p["t"] for p in pieces if part_of(p["kind"]) == part and p.get("t") is not None]
        after = [t for t in ts if c1 is None or t > c1]
        return float(np.median(after)) if after else float("inf")
    order += sorted((k for k in ("couple", "venue") if k in have), key=lambda k: (when(k), k != "couple"))
    if "drone" in have:                     # owner (v4.3.1): all the drone shots at the start of the timeline
        order.insert(0, "drone")
    if "party" in have:
        order.append("party")
    return order


LONG_TAKE = 120.0                           # automatic mode: a church clip longer than this is a take of the service
THIN_SHARE, THIN_MIN, THIN_MAX, THIN_PIECE = 0.12, 20.0, 90.0, 6.0


def thin(cuts, length):
    """A long take of the church (automatic mode; 28 August: two 27-min takes + the priest's 12-min shot made a 53-min
    church): about 12 % of the take (20-90 s) in pieces of up to 6 s spread evenly over its good (selected) parts, like
    his own long films (a few 6 s pieces of every long church clip)."""
    good = sum(b - a for a, b in cuts)
    want = min(THIN_MAX, max(THIN_MIN, THIN_SHARE * length))
    if good <= want:
        return list(cuts)
    n = max(1, int(round(want / THIN_PIECE)))
    out, step = [], good / n
    for i in range(n):
        t = step * (i + 0.5) - THIN_PIECE / 2
        acc = 0.0
        for a, b in cuts:
            if acc + (b - a) > t:
                s0 = a + max(0.0, t - acc)
                e0 = min(b, s0 + THIN_PIECE)
                if e0 - s0 >= 1.0 and (not out or s0 >= out[-1][1]):
                    out.append((s0, e0))
                break
            acc += b - a
    return out or list(cuts)


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
    """The Auto selection of one clip (analysis of that range): [(src in, src out)] in file seconds. "Keep every good
    frame" (v4.6.0, owner: a good shot he filmed for 2 s must never be dropped): smooth camera moves that stay sharp are
    kept, and the good part of a short clip (>= 1 s) survives even under the minimum cut."""
    return [(a0 + s0, a0 + s1) for s0, s1, lv in core.auto_segments(an, SEL_THR, SEL_MIN, keep_all=True)
            if lv == 2 and s1 - s0 >= SEL_KEEP - 1e-6]


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
        allm = sorted(r["path"] for r in rec if (r.get("group") or Path(r["path"]).parent.name) == main)
        masters = _one_per_take(allm, infos)        # one file per take (MIX), never the copies one after the other
        extras = _one_per_take(sorted(r["path"] for r in rec if r["path"] not in allm), infos)
    if not masters:
        # no recorder: the camera that filmed the most of the party (with sound) is the reference, ALL its clips laid on
        # its own clock (one camera never films two things at once). Before, only its longest clip was the master and
        # every clip not overlapping it was left out (his friend's R&A: no multicam at all).
        snd = [p for p in party if (infos.get(p["path"]) or {}).get("ach")]
        if snd:
            tot = {}
            for p in snd:
                tot[p["cam"]] = tot.get(p["cam"], 0.0) + ((infos.get(p["path"]) or {}).get("dur") or 0.0)
            main = max(tot, key=lambda c: (tot[c], -c))
            mf = sorted({p["path"] for p in snd if p["cam"] == main},
                        key=lambda f: ((infos.get(f) or {}).get("ctime") or (infos.get(f) or {}).get("mtime") or 0.0, f))
            masters = mf
    return party, files, masters, extras


def _zero(p):
    """Where the file's first frame sits on his timeline (s)."""
    return p["st"] - p["a"]


def timeline_sync(party, infos):
    """A timeline already synced (Syncaila, DaVinci / Premiere sync, timecode) with NO recorder: the timeline itself is
    the reference, every clip keeps its place (like Multicam > Import XML). Before, the longest party clip was the
    master and only the clips overlapping it were used (a friend's Syncaila XML: one camera, 30 min of 4 h)."""
    zs = {}
    for p in party:
        zs.setdefault(p["path"], _zero(p))
    t0 = min(zs.values()) if zs else 0.0
    end = max((z - t0 + ((infos.get(f) or {}).get("dur") or 0.0) for f, z in zs.items()), default=0.0)
    info = [dict(path=None, duration=end, onsets=[], clock=None, start=0.0)]
    res = {f: dict(conf="high", z=0.0, n=0, k=0, offset=z - t0, drift_ppm=0.0, master=0,
                   dur=(infos.get(f) or {}).get("dur") or 0.0, manual=False, source="xml") for f, z in zs.items()}
    return info, res


def timeline_fill(party, recorder, info, res, infos):
    """Synced timeline WITH a recorder: a clip the sound could not place (silent gimbal, mic off) keeps the place it has
    on his timeline relative to the recorder file under it."""
    rst = {r["path"]: r["st"] for r in recorder}
    ms = [(i, rst.get(m.get("path"))) for i, m in enumerate(info)]
    ms = [(i, s) for i, s in ms if s is not None]
    if not ms:
        return
    for p in party:
        r = res.get(p["path"])
        if r and r.get("conf") in ("high", "medium"):
            continue
        z = _zero(p)
        i, s = min(ms, key=lambda x: 0 if x[1] <= z < x[1] + (info[x[0]].get("duration") or 0)
                   else min(abs(z - x[1]), abs(z - x[1] - (info[x[0]].get("duration") or 0))))
        res[p["path"]] = dict(conf="high", z=0.0, n=0, k=0, offset=z - s, drift_ppm=0.0, master=i,
                              dur=(infos.get(p["path"]) or {}).get("dur") or 0.0, manual=False, source="xml")


def _natkey(f):
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r"(\d+)", Path(f).name)]


def camera_order_check(party, res, info):
    """Syncaila's rule for the party (sync.order_check): one camera films its files one after the other, in the order of
    their numbers, never two things at once; clips out of that chain go out of the multicam (conf "low"). Returns the
    number taken out. (His friend's Denisa & Cornel: A7iv8619 / 8620 landed after 8622.)"""
    groups = {p["path"]: f"cam{p['cam']}" for p in party}
    return sync.order_check({f: r for f, r in res.items() if f in groups}, info, groups)


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


def party_tracks(party, roles, names, user=None):
    """Video track of every party camera: static camera on V1, the main camera (most party footage) on top
    (director.video_order); user = {camera name: track} chosen on the page wins. Returns {cam index: track}."""
    cs = sorted({p["cam"] for p in party})
    foot = {}
    for p in party:
        foot[p["cam"]] = foot.get(p["cam"], 0.0) + (p["b"] - p["a"])
    user = user or {}
    pseudo = [dict(role=roles.get(c, "Handheld"), clips=[], name=names[c] if c < len(names) else str(c),
                   track=user.get(names[c] if c < len(names) else str(c))) for c in cs]
    order = director.video_order(pseudo, {i: foot.get(c, 0.0) for i, c in enumerate(cs)})
    return {cs[i]: k + 1 for k, i in enumerate(order)}


def party_layout(edits, by_key, masters, rec_paths=None, results=None, extras=(), tmap=None):
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
    tr = (lambda c: tmap.get(c, c + 1)) if tmap else (lambda c: c + 1)
    items = [(tr(p["cam"]), where(t0), p, a, b) for t0, _t1, p, a, b in sorted(cuts, key=lambda c: c[0])]
    ncam = max([tr(p["cam"]) for p in by_key.values()] or [1])
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


def export_xml(parts, infos, cam_names, out_path, name, marker=lambda s: s, look=None, labels=None):
    """parts: [(part name, length s, items, recorder items)]; items = (video track, t0 in the part, piece, src in,
    src out, flags) with flags in {"sound", "off"} ("off" = the clip is switched off: the vornic's whole 2nd camera);
    recorder items = (t0 in the part, path, src in, src out). One 25 fps 1920x1080 sequence. Every camera has its own
    audio tracks (stereo pairs / mono like Premiere, projectsetup.groups), the recorder last; links = position in the
    track. Returns (clips written, video tracks, audio tracks)."""
    ents, markers = _ents(parts, labels)
    return _write(ents, markers, infos, out_path, name, marker, look)


def _relabel(lab, labels):
    """A camera's sound under the party keeps the colour of its moment in the chosen colours."""
    if not labels or not lab:
        return lab
    return labels.get(KINDS.get(lab), lab)


def _ents(parts, labels=None):
    """The parts laid one after the other -> (entries in sequence frames, markers [(name, seconds)])."""
    _rate_xml, sf = core._rate(SEQ_FPS)
    ents, markers, g = [], [], 0.0
    for pname, length, items, rec in parts:
        if not items and not rec:
            continue
        markers.append((pname, g))
        for it in items:
            track, t0, p, a, b = it[:5]
            flags = it[5] if len(it) > 5 else {"sound"}
            st = round((g + t0) * sf)          # start AND end from absolute times: touching shots share the frame
            en = max(st + 1, round((g + t0 + b - a) * sf))
            lab = labels.get(p.get("kind"), p.get("label")) if labels else p.get("label")
            ents.append(dict(path=p["path"], v=track, st=st, en=en, fin=max(0, round(a * sf)), label=lab, kind=p.get("kind"),
                             ak=("cam", p["cam"]) if "sound" in flags else None, on="off" not in flags))
        for it in rec:
            t0, path, a, b = it[:4]
            st = round((g + t0) * sf)
            ents.append(dict(path=path, v=None, st=st, en=max(st + 1, round((g + t0 + b - a) * sf)), fin=max(0, round(a * sf)),
                             label=_relabel(it[5] if len(it) > 5 else None, labels), kind=KINDS.get(it[5] if len(it) > 5 else ""),
                             ak=it[4] if len(it) > 4 else ("rec", 0), on=True))
        g += length
    return ents, markers


def _write(ents, markers, infos, out_path, name, marker=lambda s: s, look=None):
    """Writes the entries as ONE 25 fps 1920x1080 xmeml (cameras' audio tracks, recorder last, links by position)."""
    rate_xml, sf = core._rate(SEQ_FPS)
    if not ents:
        raise ValueError("Nothing to export yet: press Build first.")
    for e in ents:                          # never past the end of the file
        i = infos.get(e["path"]) or {}
        mx = int((i.get("dur") or 0) * sf)
        if mx and e["fin"] + (e["en"] - e["st"]) > mx:
            e["en"] = e["st"] + max(1, mx - e["fin"])
    # one clip at a time on a video track: a piece that starts inside the previous one is trimmed to start where it ends
    # (his v4.0.0 party had 3 overlapping C2048 pieces on the a74 track: DaVinci trims / refuses them)
    for t in sorted({e["v"] for e in ents if e["v"]}):
        end = None
        for e in sorted((e for e in ents if e["v"] == t), key=lambda e: (e["st"], e["en"])):
            if end is not None and e["st"] < end:
                d = end - e["st"]
                if d >= e["en"] - e["st"]:
                    e["drop"] = True
                    continue
                e["st"] += d
                e["fin"] += d
            end = e["en"] if end is None else max(end, e["en"])
    ents[:] = [e for e in ents if not e.get("drop")]
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

    def head(cid, e, attr="", on=None):
        i = infos.get(e["path"]) or {}
        sdur = max(e["fin"] + e["en"] - e["st"], int((i.get("dur") or 0) * sf))
        on = e["on"] if on is None else on
        return (f'<clipitem id="{cid}"{attr}><name>{escape(Path(e["path"]).name)}</name>'
                f'<enabled>{"TRUE" if on else "FALSE"}</enabled><duration>{sdur}</duration>{rate_xml}'
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
            ax[ti].append(head(cid, e, f' premiereChannelType="{kind}"', on=e.get("aon", True)) + projectsetup._file_xml(e["path"], i, files) +
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


# ---------------------------------------------------------------- 4c. the editor's timeline
def timeline(parts, marker=lambda s: s):
    """The whole film as a free timeline for the editor (Premiere-like): items in SECONDS.
    item = dict(path, v (video track or None), ak (audio lane key list or None), start, src, dur, label, on, aon)."""
    ents, markers = _ents(parts)
    _r, sf = core._rate(SEQ_FPS)
    items = [dict(path=e["path"], v=e["v"], ak=list(e["ak"]) if e["ak"] else None, start=e["st"] / sf, src=e["fin"] / sf,
                  dur=(e["en"] - e["st"]) / sf, label=e.get("label"), kind=e.get("kind"), on=bool(e["on"]), aon=True)
             for e in ents]
    return dict(items=items, markers=[[marker(m), t] for m, t in markers])


def export_timeline(tl, infos, out_path, name, look=None, hidden=(), muted=(), labels=None, size=None):
    """size = (w, h) of the sequence (Multicam keeps the camera's size); default 1920 x 1080."""
    global SEQ_W, SEQ_H
    keep = (SEQ_W, SEQ_H)
    if size and size[0] and size[1]:
        SEQ_W, SEQ_H = int(size[0]), int(size[1])
    try:
        return _export_timeline(tl, infos, out_path, name, look, hidden, muted, labels)
    finally:
        SEQ_W, SEQ_H = keep


def _export_timeline(tl, infos, out_path, name, look=None, hidden=(), muted=(), labels=None):
    """The editor's timeline -> XML (hidden video tracks = clips switched off, muted audio lanes = sound switched off)."""
    _r, sf = core._rate(SEQ_FPS)
    ents = []
    for it in tl["items"]:
        if it["dur"] <= 0.02:
            continue
        st = round(it["start"] * sf)
        ak = tuple(it["ak"]) if it.get("ak") else None
        ents.append(dict(path=it["path"], v=it.get("v"), st=st, en=max(st + 1, round((it["start"] + it["dur"]) * sf)),
                         fin=max(0, round(it["src"] * sf)),
                         label=labels.get(it.get("kind"), it.get("label")) if labels else it.get("label"), ak=ak,
                         on=bool(it.get("on", True)) and it.get("v") not in set(hidden),
                         aon=bool(it.get("aon", True)) and (list(ak) if ak else None) not in [list(m) for m in muted]))
    return _write(ents, [tuple(m) for m in tl.get("markers", [])], infos, out_path, name, lambda s: s, look)


# ---------------------------------------------------------------- 4a. straight from the wedding folder
TAKE_RE = sync.TAKE_RE


def _one_per_take(files, infos=None):
    """See sync.one_per_take (longfilm2 infos: dur, ctime / mtime)."""
    inf = infos or {}
    return sync.one_per_take(files, lambda f: (inf.get(f) or {}).get("dur"),
                             lambda f: (inf.get(f) or {}).get("ctime") or (inf.get(f) or {}).get("mtime"))


def folder_xml(root, progress=None, cancel=None, jobs=4):
    """The Create Project sequence made right here from the wedding folder (Chronological: every camera whole, one after
    the other, the drone after them), WITH the sound folders (recorder, lavaliere) at the end so the party can be synced.
    No colours: the moments are found automatically. Returns the XML path (saved in the wedding folder)."""
    root = Path(root)
    cams = projectsetup.find_cameras(root)
    slots = projectsetup.default_slots(cams)
    cams = [c for c, s_ in projectsetup.by_slot(cams, slots) if s_ not in ("sound", "out")]   # never the trash folder
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


def auto_moments(L, pieces, recorder, infos, prog, cancel, jobs, model_dir, cache=None):
    """No colours in his sequence: 1. every clip with sound is synced to the recorder (like Multicam) -> every camera's
    clock error; 2. the faces of 5 frames of every clip; 3. daymap.classify -> colours. Sets p["label"] / p["kind"] /
    p["t"] (common clock). Returns (info for the page, (masters info, sync results) or None)."""
    import daymap
    cams = sorted({p["cam"] for p in pieces})
    own = {}
    if use_timeline(L, pieces, recorder):   # a synced timeline of the whole day: its places ARE the common clock
        for p in pieces:
            own.setdefault(p["path"], _zero(p))
    else:
        for c in cams:
            own.update(own_clock(sorted({p["path"] for p in pieces if p["cam"] == c}), infos))
    # 1. the recorder sync gives every camera's clock error
    shift, synced, unsure = {c: 0.0 for c in cams}, None, set()
    tmp = [dict(p, kind="party") for p in pieces]
    _party, files, masters, extras = party_inputs(tmp, recorder, infos)
    if masters:                             # the recorder, else the camera that filmed the most (no recorder)
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
            info, res = sync.run_sync(masters, clips + extras, prog("auto_sync"), cancel,
                                      clocks=clocks, groups=camk, jobs=jobs)
            for i, f in enumerate(masters):         # a camera used as the reference is placed by itself
                if f not in res:
                    res[f] = dict(conf="high", master=i, offset=0.0, dur=(infos.get(f) or {}).get("dur") or 0.0,
                                  drift_ppm=0.0)
            synced = (info, res)
            starts = sync.master_starts(info)
            d = {}
            for p in pieces:
                r = res.get(p["path"])
                if r and r.get("conf") == "high" and r.get("master", 0) < len(starts):
                    d.setdefault(p["cam"], []).append(starts[r.get("master", 0)] + r["offset"] - own[p["path"]])
            med = {c: float(np.median(v)) for c, v in d.items()}
            ref = 0 if 0 in med else (min(med) if med else None)
            if ref is not None and not use_timeline(L, pieces, recorder):
                shift = {c: med.get(c, med[ref]) - med[ref] for c in cams}
                unsure = {c for c in cams if c not in med}      # no sound match: its clock may be anything (an Osmo)
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
    pf = prog("auto_faces")
    for k, p in enumerate(pieces):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        pf(f"Looking at who is in every clip: {k + 1} of {len(pieces)}", (k + 1) / max(1, len(pieces)))
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
    # 3. what every clip shows, seen by the AI (church, drone, a speech...): style-free, the same model as the AI test
    sc_ai = scene_judgements(pieces, model_dir, cache, prog("auto_ai"), cancel)
    # 4. the moments: a first map gives the morning, the speech of the morning clips is measured (vornic), then the map
    clips = {key_of(p): dict(t0=own[p["path"]] + shift[p["cam"]] + p["a"], dur=p["b"] - p["a"], path=p["path"])
             for p in pieces}
    if unsure and sc_ai:                    # cameras the sound could not place: their place in the day from what they show
        folders = {Path(p["path"]).parent.name: p["cam"] for p in pieces if p["cam"] in unsure}
        try:
            offs = daymap.clock_offsets(clips, fz, sc_ai, set(folders))
        except Exception:
            logging.exception("clock offsets failed")
            offs = {}
        for p in pieces:
            o = offs.get(Path(p["path"]).parent.name)
            if o and p["cam"] in unsure:
                clips[key_of(p)]["t0"] += o
        if offs:
            logging.info("clocks moved by what the clips show: %s", {f: round(o / 60) for f, o in offs.items()})
    lab, info = daymap.classify(clips, fz, sc_ai)
    church0 = info.get("church", (float("inf"), 0))[0]
    morning = [p for p in pieces if clips[key_of(p)]["t0"] < church0 and lab.get(key_of(p)) != "Violet"]
    speech = speech_shares(morning, infos, prog("auto_speech"), cancel)
    if speech:
        lab, info = daymap.classify(clips, fz, sc_ai, speech)
    info["ai"] = bool(sc_ai)
    still = static_cams(pieces, infos)
    if still >= set(cams):                  # every camera films long takes: none of them is "the tripod one"
        still = set()
    for p in pieces:
        k = key_of(p)
        p["t"] = clips[k]["t0"]
        p["label"] = lab.get(k, "Iris")
        if p["cam"] in still and p["label"] not in ("Brown", "Iris"):
            p["label"] = "Iris"             # a tripod camera is never the couple / venue / getting ready (a74 = Purple)
        p["kind"] = KINDS.get(p["label"], AUTO)
    info["counts"] = {}
    for p in pieces:
        info["counts"][p["label"]] = info["counts"].get(p["label"], 0) + 1
    info["faces"] = model is not None
    info["shift"] = {str(c): round(v) for c, v in shift.items()}
    info["static"] = sorted(still)
    # the first look: another camera's clip joins it only when its SOUND is the same moment (the clock alone took a
    # clip of the bride with her friends on the fx3, filmed a few minutes earlier)
    info["firstlook_joined"] = join_firstlook(pieces, still, prog("auto_fl"), cancel)
    # the vornic the same way: the other cameras' morning clips of that moment, checked by the sound
    info["vornic_joined"] = join_by_sound(pieces, still, "vornic", "Forest", ("groom", "bride"), prog("auto_fl"), cancel)
    return info, synced


def scene_judgements(pieces, model_dir, cache, progress=None, cancel=None):
    """{piece key: scene probabilities} from scenes.py (SigLIP 2), cached per clip in the project's analysis cache.
    {} when the model cannot be loaded / downloaded (the old rules then work alone)."""
    if not model_dir:
        return {}
    import scenes
    cache = cache if cache is not None else {}
    out, todo = {}, []
    for p in pieces:
        ck = scenes.cache_key(p["path"], p["a"], p["b"], stamp(p["path"]))
        if (cache.get(ck) or {}).get("scene"):
            out[key_of(p)] = cache[ck]["scene"]
        elif p.get("w"):
            todo.append((p, ck))
    if not todo:
        return out
    try:
        judge = scenes.Judge(scenes.load(model_dir, progress, cancel))
    except InterruptedError:
        raise
    except Exception:
        return out
    for k, (p, ck) in enumerate(todo):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        if progress:
            progress(f"The AI is looking at every clip: {k + 1} of {len(todo)}", (k + 1) / len(todo))
        try:
            sc = judge.clip(p["path"], p["a"], p["b"])
        except Exception:
            sc = None
        if sc:
            out[key_of(p)] = sc
            cache[ck] = dict(scene=sc)
    return out


def speech_shares(pieces, infos, progress=None, cancel=None):
    """{piece key: share of the clip that is speech without music} for clips with sound (music.py regions)."""
    import music
    out = {}
    ps = [p for p in pieces if (infos.get(p["path"]) or {}).get("ach") and p["b"] - p["a"] >= 4]
    pcm = {}
    for k, p in enumerate(ps):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        if progress:
            progress(f"Listening to the morning clips (vornic): {k + 1} of {len(ps)}", (k + 1) / max(1, len(ps)))
        try:
            if p["path"] not in pcm:
                pcm = {p["path"]: sync.audio_pcm(p["path"])}
            x = pcm[p["path"]][int(p["a"] * sync.SR):int(p["b"] * sync.SR)]
            m = music.analyze(x)
            out[key_of(p)] = sum(r[1] - r[0] for r in m["regions"] if r[2] == "speech") / max(1e-6, p["b"] - p["a"])
        except Exception:
            pass
    return out


def use_timeline(L, pieces, recorder):
    """Automatic mode: the places on a SYNCED timeline (Syncaila, Premiere / DaVinci sync, Create Project timecode) are
    the common clock when the timeline holds the day (>= 3 h) or there is no recorder to measure the cameras' clocks."""
    if L.get("layout") != "timecode" or not pieces:
        return False
    span = max(p["en"] for p in pieces) - min(p["st"] for p in pieces)
    return span >= 3 * 3600 or not any(Path(r["path"]).exists() for r in recorder)


FL_WINDOW = 30 * 60     # other cameras' clips up to 30 min (by the clock) around the first look are checked by sound


def join_firstlook(pieces, still, progress=None, cancel=None):
    return join_by_sound(pieces, still, "firstlook", "Teal", ("groom", "bride", "firstlook"), progress, cancel)


def join_by_sound(pieces, still, kind, label, cand_kinds, progress=None, cancel=None):
    """Automatic mode: a moment (first look found by the faces, vornic found by the speech) is mostly on one camera.
    Every other camera's clip of the morning near it by the clock is synced by SOUND to it; a sure match (conf high,
    overlapping it by >= min(5 s, half the clip)) joins the moment. Returns the number joined."""
    fl = [p for p in pieces if p["kind"] == kind and p.get("t") is not None]
    if not fl:
        return 0
    foot = {}
    for p in fl:
        foot[p["cam"]] = foot.get(p["cam"], 0.0) + p["b"] - p["a"]
    main = max(foot, key=lambda c: (foot[c], -c))
    med = [p for p in fl if p["cam"] == main]
    lo = min(p["t"] for p in med) - FL_WINDOW
    hi = max(p["t"] + p["b"] - p["a"] for p in med) + FL_WINDOW
    cands = [p for p in pieces if p["cam"] != main and p["cam"] not in still and p.get("t") is not None
             and p["kind"] in cand_kinds and p["kind"] != kind and p["t"] < hi and p["t"] + p["b"] - p["a"] > lo]
    if not cands:
        return 0
    pcm, idx = {}, []

    def audio(path):
        if path not in pcm:
            try:
                pcm[path] = sync.audio_pcm(path)
            except Exception:
                pcm[path] = np.zeros(sync.SR, np.float32)
        return pcm[path]
    for m in med:
        x = audio(m["path"])
        idx.append(sync.MasterIndex(x if len(x) > sync.SR else np.zeros(sync.SR, np.float32)))
    n = 0
    for k, p in enumerate(cands):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        if progress:
            progress((f"Checking the vornic on the other cameras: {k + 1} of {len(cands)}" if kind == "vornic" else
                      f"Checking the first look on the other cameras: {k + 1} of {len(cands)}"), (k + 1) / len(cands))
        x = audio(p["path"])[int(p["a"] * sync.SR):int(p["b"] * sync.SR)]
        try:
            r = sync.sync_clip(idx, x) if len(x) > 2 * sync.SR else dict(conf="fail")
        except Exception:
            r = dict(conf="fail")
        ok = False
        if r.get("conf") == "high":
            m = med[r["master"]]
            g0 = r["offset"]                              # where this selection starts in the first-look file
            ov = min(g0 + (p["b"] - p["a"]), m["b"]) - max(g0, m["a"])
            ok = ov >= min(5.0, 0.5 * (p["b"] - p["a"]))
        if ok:
            p["kind"], p["label"] = kind, label
            n += 1
    return n


def static_cams(pieces, infos):
    """Cameras on a tripod (the wide of the party / church): their clips are very long (median >= STATIC_CLIP).
    At Alex & Andreea the a74: 7 clips, median 24 min (fx6 11 s, fx3 91 s)."""
    out = set()
    for c in {p["cam"] for p in pieces}:
        durs = [(infos.get(f) or {}).get("dur") or 0.0 for f in {p["path"] for p in pieces if p["cam"] == c}]
        if len(durs) >= 2 and float(np.median(durs)) >= STATIC_CLIP:
            out.add(c)
    return out


def firstlook_sync(fl, progress=None):
    """The first look SYNCED: the camera with the most first look on V1, every other camera's shot on top of the same
    moment (V2, V3...). Placed by the SOUND of the whole files (the loudest single channel, never a mix: the FX6's first
    channel can be empty), else by the common clock of the automatic mode (p["t"]), else after the others on V1.
    Returns (length, [(track, t0, piece, src in, src out)])."""
    if not fl:
        return 0.0, []
    foot = {}
    for p in fl:
        foot[p["cam"]] = foot.get(p["cam"], 0.0) + p["b"] - p["a"]
    main = max(foot, key=lambda c: (foot[c], -c))
    med = [p for p in fl if p["cam"] == main]
    others = [p for p in fl if p["cam"] != main]
    items, starts, t = [], [], 0.0
    for p in med:
        items.append((1, t, p, p["a"], p["b"]))
        starts.append(t)
        t += p["b"] - p["a"]
    length = t
    pcm = {}

    def audio(path):
        if path not in pcm:
            try:
                pcm[path] = sync.audio_pcm(path)
            except Exception:
                pcm[path] = np.zeros(sync.SR, np.float32)
        return pcm[path]
    idx = []
    for p in med:
        x = audio(p["path"])
        idx.append(sync.MasterIndex(x if len(x) > sync.SR else np.zeros(sync.SR, np.float32)))
    lanes = {}
    for k, p in enumerate(others):
        if progress:
            progress(f"Syncing the first look of the other cameras: {k + 1} of {len(others)}", (k + 1) / max(1, len(others)))
        g = None
        x = audio(p["path"])[int(p["a"] * sync.SR):int(p["b"] * sync.SR)]
        try:
            r = sync.sync_clip(idx, x) if len(x) > sync.SR else dict(conf="fail")
        except Exception:
            r = dict(conf="fail")
        if r.get("conf") in ("high", "medium"):
            m = med[r["master"]]
            g = starts[r["master"]] + r["offset"] - m["a"]        # where this selection starts on the timeline
        elif p.get("t") is not None:
            for st, m in zip(starts, med):                        # the common clock of the automatic mode
                if m.get("t") is not None and m["t"] - 1 <= p["t"] + (p["b"] - p["a"]) and p["t"] <= m["t"] + (m["b"] - m["a"]) + 1:
                    g = st + (p["t"] - m["t"])
                    break
        if g is not None:
            s0, s1 = max(0.0, g), min(length, g + (p["b"] - p["a"]))
            if s1 - s0 > 0.5:
                lane = next((tr for tr in range(2, 8) if all(not (s0 < e1 and s1 > e0) for e0, e1 in lanes.get(tr, []))), None)
                if lane:
                    lanes.setdefault(lane, []).append((s0, s1))
                    items.append((lane, s0, p, p["a"] + (s0 - g), p["a"] + (s1 - g)))
                    continue
        items.append((1, length, p, p["a"], p["b"]))              # no sound and no clock: after the others, on V1
        length += p["b"] - p["a"]
    return length, items


class Stages:
    """One honest bar for a job made of steps: every step gets a share of 0..1 as big as the work it is expected to
    take (seconds of footage to read, clips to sync...), so the bar never jumps back and the time left holds.
    replan() shares what is left again when a step learns more (the automatic mode finds the moments of the day)."""

    def __init__(self, prog, weights):
        self.prog, self.pos, self.span = prog, 0.0, {}
        self.replan(weights)

    def replan(self, weights):
        tot = sum(max(0.0, w) for _n, w in weights) or 1.0
        lo, left = self.pos, 1.0 - self.pos
        self.span = {}
        for n, w in weights:
            hi = lo + left * max(0.0, w) / tot
            self.span[n] = (lo, hi)
            lo = hi

    def __call__(self, name):
        lo, hi = self.span.get(name, (self.pos, self.pos))

        def f(text, x):
            p = lo + (hi - lo) * max(0.0, min(1.0, x))
            self.pos = max(self.pos, p)
            self.prog(text, self.pos)
        return f


def _weights(pieces, recorder, infos, auto, jobs, todo_sec=None, kinds=True):
    """Expected work of every step (relative seconds on his Mac: analysis ~ 15x real time per job, sync ~ 60x)."""
    jobs = max(1, jobs)
    dur = lambda ps: sum(max(0.0, p["b"] - p["a"]) for p in ps)
    rec_h = sum((infos.get(r["path"]) or {}).get("dur") or 0.0 for r in recorder) / 3600.0
    if todo_sec is None:
        use = pieces if not kinds else [p for p in pieces if part_of(p["kind"]) in SELECT or p["kind"] == "party"]
        todo_sec = dur(use)
    party = dur([p for p in pieces if p["kind"] == "party"]) if kinds else dur(pieces)
    w = []
    if auto:
        w += [("auto_sync", dur(pieces) / 60.0 / jobs + rec_h * 20), ("auto_faces", 2.0 * len(pieces)),
              ("auto_ai", 3.0 * len(pieces)), ("auto_speech", 0.3 * len(pieces)), ("auto_fl", 30.0)]
    w += [("analyse", todo_sec / 15.0 / jobs),
          ("priest", 2.0 * sum(1 for p in pieces if p["kind"] == "church" and p["b"] - p["a"] >= PRIEST_MIN) if kinds else 5),
          ("firstlook", 4.0 * max(1, sum(1 for p in pieces if p["kind"] == "firstlook")) if kinds else 8),
          ("vornic", 20.0 if kinds and any(p["kind"] == "vornic" for p in pieces) else 2.0),
          ("civil", 20.0 if kinds and any(p["kind"] == "civil" for p in pieces) else 2.0),
          ("party", party / 60.0 / jobs + rec_h * 20), ("music", rec_h * 6 + 1)]
    return w


# ---------------------------------------------------------------- 5. the build job (heavy work, in a thread)
def build(xml_path, vornic_on, cache, progress=None, cancel=None, jobs=2, model_dir=None, colours=None):
    """Everything that reads the media: probe, analyses (cached in `cache`: {key: dict(key=stamp, a=json)}), the
    priest, first look and vornic sync, the party sync and its music. Returns a JSON-able result for the page."""
    from concurrent.futures import ThreadPoolExecutor
    prog = progress or (lambda s, f: None)

    def chk():
        if cancel and cancel():
            raise InterruptedError("Cancelled")
    L = load(xml_path, kinds_for(colours))
    pieces, recorder = L["pieces"], L["recorder"]
    missing = sorted({p["path"] for p in pieces if not Path(p["path"]).exists()})
    pieces = [p for p in pieces if Path(p["path"]).exists()]
    if not pieces:
        raise ValueError("None of the labelled clips were found on this computer: connect the disk with the footage.")
    paths = sorted({p["path"] for p in pieces} | {r["path"] for r in recorder if Path(r["path"]).exists()})
    infos = {}
    st = Stages(prog, [("probe", 0.3 * len(paths))] + _weights(pieces, recorder, {}, L.get("auto"), jobs,
                                                              kinds=not L.get("auto")))
    sp = st("probe")
    for k, f in enumerate(paths):
        chk()
        sp(f"Reading the files: {k + 1} of {len(paths)}", (k + 1) / max(1, len(paths)))
        try:
            infos[f] = projectsetup.probe(f)
        except Exception:
            infos[f] = dict(video=False, dur=0.0, fps=25.0, w=1920, h=1080, ach=0, arate=48000, ctime=None, tod=None)
    auto = None
    psync_res = None
    st.replan(_weights(pieces, recorder, infos, L.get("auto"), jobs, kinds=not L.get("auto")))
    if L.get("auto"):
        auto, psync_res = auto_moments(L, pieces, recorder, infos, st, cancel, jobs, model_dir, cache)
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
    st.replan([w for w in _weights(pieces, recorder, infos, False, jobs,
                                    todo_sec=sum(p["b"] - p["a"] for p in todo)) if not w[0].startswith("auto")])
    pa = st("analyse")
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
        pa(f"Looking at your selections: {done[0]} of {len(todo)}", done[0] / max(1, len(todo)))
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
        st("priest")(f"Looking for the priest: {k + 1} of {len(long_church)}", (k + 1) / max(1, len(long_church)))
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
    st("firstlook")("Syncing the first look", 0.0)
    fl_len, fl_items = firstlook_sync(fl, progress=st("firstlook")) if fl else (0.0, [])
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
        vo_len, vo_items = longfilm.vornic_cut(mp, op, progress=st("vornic"), cancel=cancel)
    # the civil ceremony (v4.6.0): built like the vornic: the camera that filmed it most (the officer) WHOLE on V1 with
    # its sound, the other camera's clips of that moment synced by the sound on top (cut in), so he only trims
    cv_len, cv_items, cv_cams = 0.0, [], []
    cps = [p for p in pieces if p["kind"] == "civil"]
    if cps:
        foot = {}
        for p in cps:
            foot[p["cam"]] = foot.get(p["cam"], 0.0) + p["b"] - p["a"]
        two = sorted(foot, key=lambda c: -foot[c])[:2]
        cv_cams = two
        mp = chrono([p for p in cps if p["cam"] == two[0]], L["layout"], infos)
        op = chrono([p for p in cps if p["cam"] in two[1:]], L["layout"], infos)
        st("civil")("Syncing the civil ceremony", 0.0)
        cv_len, cv_items = longfilm.vornic_cut(mp, op, progress=st("civil"), cancel=cancel)
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
        no_rec = not any(Path(r["path"]).exists() for r in recorder)
        if no_rec and L["layout"] == "timecode":
            info, res = timeline_sync(party, infos)     # a synced timeline (Syncaila, timecode) without a recorder
            masters = []
        elif psync_res and all(f in psync_res[1] for f in clips):
            info, res = psync_res                   # already synced by the automatic day map
        else:
            info, res = sync.run_sync(masters, clips, st("party"), cancel,
                                      clocks=clocks, groups=camk, jobs=jobs)
        if L["layout"] == "timecode" and not no_rec:
            timeline_fill(party, recorder, info, res, infos)   # clips the sound could not place keep their timeline place
        if info and info[0].get("path"):
            camera_order_check(party, res, info)    # a camera films its files in order and never two things at once
        mpaths = [m.get("path") for m in info]
        for f in pfiles:
            if f in mpaths:                 # a party clip used as the reference (no recorder) is placed by itself
                res[f] = dict(conf="high", master=mpaths.index(f), offset=0.0, dur=infos[f]["dur"], drift_ppm=0.0)
        for i, m in enumerate(info):
            chk()
            if not m.get("path"):
                m["music"] = None
                continue
            st("music")(f"Reading the music (beats, bars, drops): {i + 1} of {len(info)}", i / max(1, len(info)))
            try:
                import music
                m["music"] = music.analyze(sync.audio_pcm(m["path"]))
            except Exception:
                m["music"] = None
        psync = dict(masters=info, results=res, extras=extras)
    prog("Done", 1.0)
    order = L["order"]
    if auto is not None:                    # the story order (owner, v4.3.0), whatever was filmed first
        order = auto_order(pieces)
    return dict(pieces=pieces, recorder=recorder, cams=L["cams"], layout=L["layout"], order=order, auto=auto,
                skipped=L["skipped"], missing=missing, infos=infos, sel=sel, priests=priests,
                firstlook=[fl_len, [(t, t0, key_of(p), a, b, ["sound"]) for t, t0, p, a, b in fl_items]],
                vornic=[vo_len, [(t, t0, key_of(p), a, b, ["sound"] if t == 1 else (["sound", "off"] if t == 2 else []))
                                 for t, t0, p, a, b in vo_items], vo_cams],
                civil=[cv_len, [(t, t0, key_of(p), a, b, ["sound"] if t == 1 else (["sound", "off"] if t == 2 else []))
                                for t, t0, p, a, b in cv_items], cv_cams],
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


def assemble(r, analyses, st, zones, marker=lambda s: s, vornic_on=True, edits=None, ready="interleave"):
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
            ps = chrono([p for p in r["pieces"] if part_of(p["kind"]) == part and not p.get("dpart")],
                        r["layout"], r["infos"])
            # drone shots that open this moment (automatic mode: attach_drone), in their own time order
            dps = chrono([p for p in r["pieces"] if p.get("dpart") == part], r["layout"], r["infos"])

            auto_mode = r.get("auto") is not None

            def cut(ps):
                out = []
                for p in ps:
                    k = key_of(p)
                    long_take = auto_mode and part == "church" and p["b"] - p["a"] > LONG_TAKE
                    if k in r["priests"] and not long_take:
                        cuts = [(p["a"], p["b"])]
                    else:
                        cuts = r["sel"].get(k, [])
                        if long_take:               # a whole service filmed in one take: a few pieces of it
                            cuts = thin(cuts, p["b"] - p["a"])
                    out += [(p, a, b) for a, b in cuts]
                return out
            shots = cut(ps)
            if part == "ready":
                g = [x for x in shots if x[0]["kind"] == "groom"]
                b = [x for x in shots if x[0]["kind"] != "groom"]
                if ready == "sequential":       # owner's option: all of the side filmed first, then the other
                    first_g = not b or (g and (g[0][0].get("t") or 0) <= (b[0][0].get("t") or 0))
                    shots = g + b if first_g else b + g
                else:                           # groom and bride in parallel, not one after the other
                    shots = alternate(g, b)
            shots = cut(dps) + shots
            items, t = [], 0.0
            for p, a, b in shots:
                items.append((1, t, p, a, b, {"sound"}))
                t += b - a
            parts.append((name, t, items, []))
            stat[part] = (len(items), t)
        elif part in ("firstlook", "vornic", "civil"):
            if part not in r:               # a build made before the civil ceremony existed
                continue
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
            names = [c["name"] if isinstance(c, dict) else str(c) for c in r["cams"]]
            tmap = party_tracks(party, roles, names, st.get("tracks"))
            ln, items, rec = party_layout(edits, bk, ps["masters"], {x["path"] for x in r["recorder"]},
                                          ps["results"], ps.get("extras") or (), tmap)
            parts.append((name, ln, [it if len(it) > 5 else (*it, set()) for it in items], rec))
            info.update(edits=edits, dcams=dcams, roles=roles, tracks={names[c] if c < len(names) else str(c): t
                                                                       for c, t in tmap.items()})
            stat[part] = (len(items), ln)
    keys = [k for k in r["order"] if k in stat]
    if user_edits:
        parts = apply_edits(parts, keys, user_edits)
        for (name, ln, items, rec), k in zip(parts, keys):
            stat[k] = (len(items), ln)
    info["stat"] = stat
    info["keys"] = keys
    return parts, info
