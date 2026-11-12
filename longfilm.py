"""Long Film: the long wedding film, pre-cut from the editor's labelled selections (he adds the music, the interviews and
the final touches in Premiere).

His selects sequence holds one "train" per camera operator: camera 1's whole day, a pause of a few minutes, then camera
2's whole day. Inside every train the order is his (the day), and the FIRST church shot (Brown) splits the morning from
the rest: Iris before it = first look, Iris after it = party.

Parts, in order, every selection whole and as he cut it:
  Teaser        - the teaser part of a Teaser Studio project (optional), with its music
  Getting ready - bride / groom of camera 1 only
  First look    - Iris (and couple) before the church, both cameras
  Vornic        - optional: Iris shots before the church where the vornic's face is (from one photo), or Mango shots.
                  The camera with the bigger face is the medium one (V1), the other one (wide) is synced to it by the
                  sound (V2), and a cut version alternates them in the pauses of his speech (V3, on top)
  Church        - Brown, exactly in his order
  Couple, venue - couple after the church (both cameras), then the venue (drone first)
  Party         - only a marker: the party is the Multicam edit
"""
import re
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core
import sync

GAP = 20.0                # seconds of empty timeline between two trains (camera operators)
SEQ_FPS = 25.0


def camera_key(p):
    """Which camera filmed it: the file name pattern (digits removed) + picture size + frame rate. Two bodies that name
    their files the same (C9375.MP4 from an FX3, C2002.MP4 from an A7 IV) still differ by size / rate."""
    name = Path(p["path"]).name
    return f'{re.sub(r"[0-9]+", "#", name)}|{p.get("w")}x{p.get("h")}|{round(p.get("fps") or 0)}'


def file_number(p):
    """The camera's own counter (C9375 -> 9375): the order in which it filmed, whatever the timeline or clock says."""
    m = re.search(r"([0-9]+)(?!.*[0-9])", Path(p["path"]).stem)
    return int(m.group(1)) if m else 0


def camera_name(ps):
    """A readable name: the folder of the clips (e.g. 'fx3'), else the file pattern."""
    folders = {Path(p["path"]).parent.name for p in ps}
    pat = re.sub(r"[0-9]+", "#", Path(ps[0]["path"]).name)
    return (folders.pop() + "  ·  " + pat) if len(folders) == 1 else pat


def trains(pieces):
    """One list per CAMERA (by its files), each in the order the camera filmed (file number, then in-point). The main
    camera (most getting-ready shots) is the first. Every piece gets 'train' = its camera's index."""
    groups = {}
    for p in pieces:
        groups.setdefault(camera_key(p), []).append(p)
    out = [sorted(g, key=lambda p: (file_number(p), p["a"])) for g in groups.values()]
    out.sort(key=lambda g: (-sum(1 for p in g if p["cat"] in ("bride", "groom")), -len(g)))
    for k, tr in enumerate(out):
        for p in tr:
            p["train"] = k
    return out


def split_day(train):
    """(before the church, the church, after the church) inside one train, by his order. The church is the BIGGEST
    block of Brown shots (a few other shots inside it are allowed), not the first Brown shot: a church shot that
    appears earlier (in a teaser, a flash-forward) must not swallow the getting ready."""
    idx = [i for i, p in enumerate(train) if p["cat"] == "church"]
    if not idx:
        return [], [], train          # no church on this camera: nothing is "morning" (its Iris is the party)
    blocks, cur = [], [idx[0]]
    for i in idx[1:]:
        if i - cur[-1] <= 4:                   # up to 3 other shots inside the church block
            cur.append(i)
        else:
            blocks.append(cur)
            cur = [i]
    blocks.append(cur)
    best = max(blocks, key=lambda b: sum(train[i]["b"] - train[i]["a"] for i in b))
    first, last = best[0], best[-1]
    church = [train[i] for i in best]
    before = [p for i, p in enumerate(train[:first])]
    after = [p for p in train[last + 1:]]
    # Brown shots outside the main block (teaser / flash-forward) are not lost: they join the church, in his order
    stray = [p for i, p in enumerate(train) if p["cat"] == "church" and i not in best]
    if stray:
        church = sorted(church + stray, key=lambda p: p["order"])
        before = [p for p in before if p["cat"] != "church"]
        after = [p for p in after if p["cat"] != "church"]
    return before, church, after


def looks_like_an_edit(pieces):
    """A finished film (cuts of 1-2 s) instead of a selects sequence."""
    if len(pieces) < 40:
        return False
    L = sorted(p["b"] - p["a"] for p in pieces)
    return L[len(L) // 2] < 2.5


def _by_time(ps):
    """Every camera: the main one first, each in the order it filmed (file numbers; the clocks can differ)."""
    return sorted(ps, key=lambda p: (p["train"], file_number(p), p["a"]))


def interleave(a, b, max_run=4):
    """Groom and bride getting ready told IN PARALLEL, as if it happened at the same time: each side keeps the order it
    was filmed in, and the side whose story is behind (share of its shots already used) gets the next 1-4 shots.
    Both reach the end together; no long run of one side."""
    a = sorted(a, key=lambda p: (file_number(p), p["a"]))
    b = sorted(b, key=lambda p: (file_number(p), p["a"]))
    if not a or not b:
        return a + b
    if (file_number(b[0]), b[0]["a"]) < (file_number(a[0]), a[0]["a"]):
        a, b = b, a
    tot = {0: sum(p["b"] - p["a"] for p in a) or 1.0, 1: sum(p["b"] - p["a"] for p in b) or 1.0}
    side, used, pos, out = (a, b), {0: 0.0, 1: 0.0}, {0: 0, 1: 0}, []
    frac = lambda k: pos[k] / len(side[k])       # progress by SHOTS: that is what the eye follows on screen
    while pos[0] < len(a) or pos[1] < len(b):
        if pos[1] >= len(b):
            k = 0
        elif pos[0] >= len(a):
            k = 1
        else:
            k = 0 if frac(0) <= frac(1) else 1
        o, took = 1 - k, 0
        while pos[k] < len(side[k]) and took < max_run and (took == 0 or pos[o] >= len(side[o]) or frac(k) <= frac(o)):
            p = side[k][pos[k]]
            out.append(p)
            used[k] += p["b"] - p["a"]
            pos[k] += 1
            took += 1
    return out


def dedupe(pieces):
    """The same selection twice (same file, same in / out: a copy on another track) is used once."""
    seen, out = set(), []
    for p in sorted(pieces, key=lambda p: p["order"]):
        k = (p["path"], round(p["a"], 1), round(p["b"], 1))
        if k not in seen:
            seen.add(k)
            out.append(p)
    return out


def plan(pieces, vornic_ids=None):
    """The parts: [(name, [pieces])]. vornic_ids: id() of the pieces that are the vornic (face found or Mango).
    The 'First look' part holds the main camera's first look first; firstlook_candidates() gives the other cameras'
    Iris shots that are matched to it by the sound when the film is built."""
    vornic_ids = vornic_ids or set()
    pieces = dedupe(pieces)
    trs = trains(pieces)
    before, after = [], []
    for tr in trs:
        b, c, a = split_day(tr)
        before += b
        after += a
    cam1 = [p for p in before if p["train"] == 0]
    parts = []
    parts.append(("Getting ready", interleave([p for p in cam1 if p["cat"] == "groom"],
                                              [p for p in cam1 if p["cat"] == "bride"])))
    parts.append(("First look", _by_time([p for p in before if p["cat"] in ("party", "couple") and id(p) not in vornic_ids])))
    v = [p for p in pieces if id(p) in vornic_ids or p["cat"] == "vornic"]
    if v:
        parts.append(("Vornic", _by_time(v)))
    # the church exactly as HE laid it out on the timeline (every camera), each selection once
    parts.append(("Church", sorted([p for p in pieces if p["cat"] == "church"], key=lambda p: p["order"])))
    couple = _by_time([p for p in after if p["cat"] == "couple"])
    drone = sorted([p for p in pieces if p["cat"] == "drone"], key=lambda p: (p["train"], file_number(p), p["a"]))
    venue = _by_time([p for p in after if p["cat"] == "venue"])
    parts.append(("Couple and venue", couple + drone + venue))
    return trs, parts


def firstlook_candidates(pieces, vornic_ids=None):
    """Iris shots of the OTHER cameras that may be the first look: those after their church or on a camera with no
    church at all (they count as party unless their sound matches the main camera's first look)."""
    vornic_ids = vornic_ids or set()
    out = []
    for tr in trains(dedupe(pieces)):
        if tr and tr[0]["train"] == 0:
            continue
        b, c, a = split_day(tr)
        out += [p for p in a if p["cat"] == "party" and id(p) not in vornic_ids]
    return out


def vornic_candidates(pieces):
    """Where the vornic can be: Iris before the church, in every train."""
    out = []
    for tr in trains(pieces):
        b, _, _ = split_day(tr)
        out += [p for p in b if p["cat"] == "party"]
    return out


def _pauses(x, sr=sync.SR):
    """Pauses in speech (seconds): quiet stretches of at least 0.3 s."""
    hop = sr // 20
    n = len(x) // hop
    if n < 20:
        return []
    db = 10 * np.log10((x[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1) + 1e-10)
    thr = np.median(db) - 8
    low = db < thr
    out, i = [], 0
    while i < n:
        if low[i]:
            j = i
            while j < n and low[j]:
                j += 1
            if j - i >= 6:
                out.append((i + j) / 2 / 20)
            i = j
        else:
            i += 1
    return out


def stack_layout(ps, master_train, cut=False, progress=None, label="Placing the second camera by the sound"):
    """The master camera on V1 (one after the other), the other cameras' shots placed by their SOUND on top of the master
    on V2 (same moment), and, with cut=True, a version alternating them in the pauses of the speech on V3.
    Shots that cannot be placed by the sound go after the master ones on V1. Returns (length, items)."""
    med = [p for p in ps if p["train"] == master_train]
    wide = [p for p in ps if p["train"] != master_train]
    items, t, starts = [], 0.0, []
    for p in med:
        items.append((1, t, p, p["a"], p["b"]))
        starts.append(t)
        t += p["b"] - p["a"]
    length = t
    if not med or not wide:
        for p in wide:
            items.append((1, length, p, p["a"], p["b"]))
            length += p["b"] - p["a"]
        return length, items
    pcm = {}

    def audio(p):
        if p["path"] not in pcm:
            pcm[p["path"]] = sync.audio_pcm(p["path"])
        x = pcm[p["path"]]
        return x[int(p["a"] * sync.SR):int(p["b"] * sync.SR)]
    idx, auds = [], []
    for p in med:
        try:
            x = audio(p)
        except Exception:
            x = np.zeros(sync.SR, np.float32)
        auds.append(x)
        idx.append(sync.MasterIndex(x))
    placed = []
    for k, p in enumerate(wide):
        if progress:
            progress(f"{label}: {k + 1} of {len(wide)}", (k + 1) / max(1, len(wide)))
        try:
            r = sync.sync_clip(idx, audio(p))
        except Exception:
            r = dict(conf="fail")
        if r.get("conf") in ("high", "medium"):
            g = starts[r["master"]] + r["offset"]
            s0, s1 = max(0.0, g), min(length, g + (p["b"] - p["a"]))
            if s1 - s0 > 0.5:
                items.append((2, s0, p, p["a"] + (s0 - g), p["a"] + (s1 - g)))
                placed.append((s0, s1, p, g))
                continue
        items.append((1, length, p, p["a"], p["b"]))       # not found by the sound: after the master ones, on V1
        length += p["b"] - p["a"]
    if cut and placed:
        pz = []
        for st, x in zip(starts, auds):
            pz += [st + q for q in _pauses(x)]
        cuts, last = [0.0], 0.0
        for q in sorted(pz):
            if q - last >= 6.0:
                cuts.append(q)
                last = q
        cuts.append(sum(p["b"] - p["a"] for p in med))
        use_wide = False
        for a, b in zip(cuts, cuts[1:]):
            w = next((w for w in placed if w[0] <= a and w[1] >= b), None) if use_wide else None
            if w:
                s0, s1, p, g = w
                items.append((3, a, p, p["a"] + (a - g), p["a"] + (b - g)))
            else:
                k = max(i for i, st in enumerate(starts) if st <= a + 1e-6)
                b2 = min(b, starts[k] + (med[k]["b"] - med[k]["a"]))
                items.append((3, a, med[k], med[k]["a"] + (a - starts[k]), med[k]["a"] + (b2 - starts[k])))
            use_wide = not use_wide
    return length, items


def vornic_layout(vps, sizes, progress=None):
    """The vornic: the camera with the bigger face is the medium one (V1), the wide one by the sound (V2), a cut (V3)."""
    trs = sorted({p["train"] for p in vps})
    med_t = max(trs, key=lambda k: np.median([sizes.get(id(p), (0, 0))[1] for p in vps if p["train"] == k] or [0]))
    return stack_layout(vps, med_t, cut=True, progress=progress, label="Placing the wide camera by the sound")


def _clip_audio(p):
    """Only the selection's sound (not the whole file): mono, 4 kHz."""
    import subprocess
    dur = max(0.1, p["b"] - p["a"])
    cmd = [core.ffmpeg_exe(), "-v", "error", "-nostdin", "-ss", f"{p['a']:.3f}", "-t", f"{dur:.3f}", "-i", p["path"],
           "-vn", "-ac", "1", "-ar", str(sync.SR), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True, **core._NOWIN).stdout
    return np.frombuffer(out, np.float32).copy()


def firstlook_layout(ps, candidates=(), progress=None):
    """The first look of every camera, SYNCED: the main camera's (or the camera with the most first look) on V1, every
    other camera's shot placed by its sound on top of the same moment (V2). Candidates (Iris of other cameras that may
    be the party) are used only when their sound matches the first look. He cuts between the cameras himself."""
    trs = sorted({p["train"] for p in ps})
    if not ps:
        return 0.0, []
    master = 0 if 0 in trs else max(trs, key=lambda k: sum(p["b"] - p["a"] for p in ps if p["train"] == k))
    med = [p for p in ps if p["train"] == master]
    others = [(p, True) for p in ps if p["train"] != master] + [(p, False) for p in candidates]
    items, t, starts = [], 0.0, []
    for p in med:
        items.append((1, t, p, p["a"], p["b"]))
        starts.append(t)
        t += p["b"] - p["a"]
    length = t
    if not others:
        return length, items
    idx = []
    for p in med:
        try:
            x = _clip_audio(p)
        except Exception:
            x = np.zeros(sync.SR, np.float32)
        idx.append(sync.MasterIndex(x if len(x) > sync.SR else np.zeros(sync.SR, np.float32)))
    lanes = {}
    for k, (p, keep) in enumerate(others):
        if progress:
            progress(f"Syncing the first look of the second camera: {k + 1} of {len(others)}", (k + 1) / max(1, len(others)))
        try:
            x = _clip_audio(p)
            r = sync.sync_clip(idx, x) if len(x) > sync.SR else dict(conf="fail")
        except Exception:
            r = dict(conf="fail")
        if r.get("conf") in ("high", "medium"):
            g = starts[r["master"]] + r["offset"]
            s0, s1 = max(0.0, g), min(length, g + (p["b"] - p["a"]))
            if s1 - s0 > 0.5:
                # the first free track above the master (two shots of the same moment never on one track)
                lane = next((tr for tr in (2, 3, 4, 5) if all(not (s0 < e1 and s1 > e0) for e0, e1 in lanes.get(tr, []))), None)
                if lane:
                    lanes.setdefault(lane, []).append((s0, s1))
                    items.append((lane, s0, p, p["a"] + (s0 - g), p["a"] + (s1 - g)))
                    continue
        if keep:                                            # his first look but no sound to place it: after, on V1
            items.append((1, length, p, p["a"], p["b"]))
            length += p["b"] - p["a"]
    return length, items


def _ai(path):
    try:
        return sync.audio_info(path)
    except Exception:
        return (48000, 0)


def export_xml(parts_layout, out_path, name, teaser_part=None):
    """parts_layout: [(part name, length, [(track, t0 in the part, piece, src in, src out)])]. teaser_part: optional
    (length, [(t0, t1, piece)], [(music path, start, end, src in)]). One 25 fps sequence; the shots on V1 carry their own
    camera sound on A1/A2, LINKED to the picture the way Premiere / DaVinci expect it (every link names the clip's track
    and its position in that track, the sound in one group); the teaser's music on A3/A4; a marker on every part."""
    import i18n
    rate_xml, sf = core._rate(SEQ_FPS)
    files, ainfo = {}, {}

    def info(path):
        if path not in ainfo:
            ainfo[path] = _ai(path)
        return ainfo[path]

    LAB = {"bride": "Rose", "groom": "Blue", "couple": "Purple", "church": "Brown", "venue": "Yellow", "party": "Iris",
           "drone": "Violet", "vornic": "Mango"}
    # ---- 1. every clip as an entry, in timeline frames
    vids, music, markers, g = [], [], [], 0.0      # vids: dict(track, st, en, fin, fout, p, sound)

    def add(track, t0, p, a, b, sound):
        st, en = round(t0 * sf), round((t0 + (b - a)) * sf)
        if en > st:
            fin = round(a * sf)
            vids.append(dict(track=track, st=st, en=en, fin=fin, fout=fin + (en - st), p=p, sound=sound))
    if teaser_part:
        tl, shots, mus = teaser_part
        markers.append(("Teaser", 0.0))
        for t0, t1, p in shots:
            add(1, t0, p, p["s"], p["s"] + (t1 - t0), False)
        for path, s0, s1, src in mus:
            if Path(path).exists() and s1 > s0:
                st, en = round(s0 * sf), round(s1 * sf)
                music.append(dict(path=path, st=st, en=en, fin=round(src * sf)))
        g = tl
    for pname, length, items in parts_layout:
        if not items:
            continue
        markers.append((pname, g))
        for track, t0, p, a, b in items:
            add(track, g + t0, p, a, b, track == 1)
        g += length
    markers.append(("Party (the Multicam edit)", g))
    # ---- 2. ids and positions (clip index = position in its track, by start)
    n = [0]

    def nid():
        n[0] += 1
        return f"clipitem-{n[0]}"
    vt = {k: sorted([e for e in vids if e["track"] == k], key=lambda e: e["st"]) for k in (1, 2, 3, 4, 5)}
    for k, lst in vt.items():
        for ci, e in enumerate(lst, 1):
            e["id"], e["ti"], e["ci"] = nid(), k, ci
    aud = {1: [], 2: []}
    for e in vt[1]:
        if e["sound"]:
            ch = info(e["p"]["path"])[1]
            e["aud"] = [dict(e=e, k=k) for k in range(min(2, ch))]
            for a in e["aud"]:
                aud[a["k"] + 1].append(a)
    for k, lst in aud.items():
        lst.sort(key=lambda a: a["e"]["st"])
        for ci, a in enumerate(lst, 1):
            a["id"], a["ti"], a["ci"] = nid(), k, ci

    def links(e):
        if not e.get("aud"):
            return ""
        out = [f'<link><linkclipref>{e["id"]}</linkclipref><mediatype>video</mediatype><trackindex>{e["ti"]}</trackindex>'
               f'<clipindex>{e["ci"]}</clipindex></link>']
        out += [f'<link><linkclipref>{a["id"]}</linkclipref><mediatype>audio</mediatype><trackindex>{a["ti"]}</trackindex>'
                f'<clipindex>{a["ci"]}</clipindex><groupindex>1</groupindex></link>' for a in e["aud"]]
        return "".join(out)

    def file_xml(p):
        path = p["path"]
        if path in files:
            return f'<file id="{files[path]}"/>'
        files[path] = f"file-{len(files) + 1}"
        r, ch = info(path)
        aud_ = (f'<audio><samplecharacteristics><depth>16</depth><samplerate>{r}</samplerate></samplecharacteristics>'
                f'<channelcount>{ch}</channelcount></audio>') if ch else ""
        frate, ffps = core._rate(p["fps"])
        return (f'<file id="{files[path]}"><name>{escape(Path(path).name)}</name><pathurl>{escape(core._url(path))}</pathurl>'
                f'{frate}<duration>{int(p["fdur"] * ffps)}</duration><media><video>{core._sc(frate, p["w"], p["h"], "none")}'
                f'</video>{aud_}</media></file>')

    def labels(p):
        lab = p.get("label") or LAB.get(p["cat"], "")
        return f"<labels><label2>{escape(lab)}</label2></labels>" if lab else ""
    # ---- 3. the XML (video first: a file is fully defined the first time it is written)
    vx = {k: [] for k in (1, 2, 3, 4, 5)}
    for k in (1, 2, 3, 4, 5):
        for e in vt[k]:
            p = e["p"]
            sdur = max(e["fout"], int(p["fdur"] * sf))
            vx[k].append(f'<clipitem id="{e["id"]}"><name>{escape(Path(p["path"]).name)}</name><duration>{sdur}</duration>'
                         f'{rate_xml}<start>{e["st"]}</start><end>{e["en"]}</end><in>{e["fin"]}</in><out>{e["fout"]}</out>'
                         f'{file_xml(p)}{links(e)}{labels(p)}</clipitem>')
    ax = {1: [], 2: [], 3: [], 4: []}
    for k in (1, 2):
        for a in aud[k]:
            e, p = a["e"], a["e"]["p"]
            sdur = max(e["fout"], int(p["fdur"] * sf))
            ax[k].append(f'<clipitem id="{a["id"]}"><name>{escape(Path(p["path"]).name)}</name><duration>{sdur}</duration>'
                         f'{rate_xml}<start>{e["st"]}</start><end>{e["en"]}</end><in>{e["fin"]}</in><out>{e["fout"]}</out>'
                         f'<file id="{files[p["path"]]}"/><sourcetrack><mediatype>audio</mediatype>'
                         f'<trackindex>{a["k"] + 1}</trackindex></sourcetrack>{links(e)}{labels(p)}</clipitem>')
    mdef = {}
    for m in music:
        r, ch = info(m["path"])
        if m["path"] not in mdef:
            mdef[m["path"]] = f"file-m{len(mdef) + 1}"
            fx = (f'<file id="{mdef[m["path"]]}"><name>{escape(Path(m["path"]).name)}</name>'
                  f'<pathurl>{escape(core._url(m["path"]))}</pathurl>{rate_xml}<duration>{m["fin"] + m["en"] - m["st"] + 1}</duration>'
                  f'<media><audio><samplecharacteristics><depth>16</depth><samplerate>{r}</samplerate></samplecharacteristics>'
                  f'<channelcount>{ch}</channelcount></audio></media></file>')
        else:
            fx = f'<file id="{mdef[m["path"]]}"/>'
        for k in range(min(2, max(1, ch))):
            ax[3 + k].append(f'<clipitem id="{nid()}"><name>{escape(Path(m["path"]).name)}</name>'
                             f'<duration>{m["fin"] + m["en"] - m["st"]}</duration>{rate_xml}<start>{m["st"]}</start>'
                             f'<end>{m["en"]}</end><in>{m["fin"]}</in><out>{m["fin"] + m["en"] - m["st"]}</out>'
                             f'{fx if k == 0 else chr(60) + "file id=" + chr(34) + mdef[m["path"]] + chr(34) + "/" + chr(62)}'
                             f'<sourcetrack><mediatype>audio</mediatype><trackindex>{k + 1}</trackindex></sourcetrack></clipitem>')
    total = round(g * sf) + 1
    trk = lambda its: f'<track>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    mk = "".join(f'<marker><name>{escape(i18n.T(m))}</name><comment></comment><in>{round(t * sf)}</in><out>-1</out></marker>'
                 for m, t in markers)
    first = next((it[2] for _, _, its in parts_layout for it in its), None) or dict(w=1920, h=1080)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}{mk}'
           f'<media><video><format>{core._sc(rate_xml, first["w"], first["h"], "none")}</format>'
           f'{"".join(trk(vx[k]) for k in (1, 2, 3, 4, 5) if vx[k])}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{"".join(trk(ax[k]) for k in (1, 2, 3, 4) if ax[k])}</audio>'
           f'</media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return len(vids), [m for m, _ in markers]
