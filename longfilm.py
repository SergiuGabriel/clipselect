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
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core
import sync

GAP = 20.0                # seconds of empty timeline between two trains (camera operators)
SEQ_FPS = 25.0


def trains(pieces):
    """Split his selections into trains (cameras) at the pauses of the timeline. Every piece gets 'train'."""
    ps = sorted(pieces, key=lambda p: p["order"])
    out, end = [], None
    for p in ps:
        ln = p["b"] - p["a"]
        if end is None or p["order"] - end > GAP:
            out.append([])
        out[-1].append(p)
        end = max(end or 0, p["order"] + ln)
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
        return train, [], []
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
    """Both cameras together: camera 1 then camera 2, each in his order (the cameras' clocks can differ)."""
    return sorted(ps, key=lambda p: (p["train"], p["order"]))


def plan(pieces, vornic_ids=None):
    """The parts: [(name, [pieces])]. vornic_ids: id() of the pieces that are the vornic (face found or Mango)."""
    vornic_ids = vornic_ids or set()
    trs = trains(pieces)
    before, church, after = [], [], []
    for tr in trs:
        b, c, a = split_day(tr)
        before += b
        church += c
        after += a
    cam1 = [p for p in before if p["train"] == 0]
    parts = []
    parts.append(("Getting ready", [p for p in cam1 if p["cat"] in ("bride", "groom")]))
    parts.append(("First look", _by_time([p for p in before if p["cat"] in ("party", "couple") and id(p) not in vornic_ids])))
    v = [p for p in pieces if id(p) in vornic_ids or p["cat"] == "vornic"]
    if v:
        parts.append(("Vornic", _by_time(v)))
    parts.append(("Church", sorted(church, key=lambda p: p["order"])))
    couple = _by_time([p for p in after if p["cat"] == "couple"])
    venue = _by_time([p for p in after if p["cat"] == "drone"]) + _by_time([p for p in after if p["cat"] == "venue"])
    parts.append(("Couple and venue", couple + venue))
    return trs, parts


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


def vornic_layout(vps, sizes, progress=None):
    """Medium camera on V1 (one after the other), the wide one synced to it by the sound on V2, a cut version on V3.
    Returns (length, [(track, t0 on the part, piece, src in, src out)])."""
    trs = sorted({p["train"] for p in vps})
    med_t = max(trs, key=lambda k: np.median([sizes.get(id(p), (0, 0))[1] for p in vps if p["train"] == k] or [0]))
    med = [p for p in vps if p["train"] == med_t]
    wide = [p for p in vps if p["train"] != med_t]
    items, t = [], 0.0
    starts = []
    for p in med:
        items.append((1, t, p, p["a"], p["b"]))
        starts.append(t)
        t += p["b"] - p["a"]
    length = t
    if not med:                                           # only one camera: just one after the other
        for p in wide:
            items.append((1, t, p, p["a"], p["b"]))
            t += p["b"] - p["a"]
        return t, items
    # the wide camera, placed by its sound on the medium one
    idx, auds = [], []
    for p in med:
        x = sync.audio_pcm(p["path"])[int(p["a"] * sync.SR):int(p["b"] * sync.SR)]
        auds.append(x)
        idx.append(sync.MasterIndex(x))
    placed = []
    for k, p in enumerate(wide):
        if progress:
            progress(f"Placing the wide camera by the sound: {k + 1} of {len(wide)}", (k + 1) / max(1, len(wide)))
        try:
            x = sync.audio_pcm(p["path"])[int(p["a"] * sync.SR):int(p["b"] * sync.SR)]
            r = sync.sync_clip(idx, x)
        except Exception:
            r = dict(conf="fail")
        if r.get("conf") in ("high", "medium"):
            g = starts[r["master"]] + r["offset"]
            s0, s1 = max(0.0, g), min(length, g + (p["b"] - p["a"]))
            if s1 - s0 > 0.5:
                items.append((2, s0, p, p["a"] + (s0 - g), p["a"] + (s1 - g)))
                placed.append((s0, s1, p, g))
        else:                                              # not found by the sound: after the medium ones, on V1
            items.append((1, length, p, p["a"], p["b"]))
            length += p["b"] - p["a"]
    # the cut version: medium / wide alternating in the pauses of his speech, at least 6 s per shot
    if placed:
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


def _ai(path):
    try:
        return sync.audio_info(path)
    except Exception:
        return (48000, 0)


def export_xml(parts_layout, out_path, name, teaser_part=None):
    """parts_layout: [(part name, length, [(track, t0 in the part, piece, src in, src out)])]. teaser_part: optional
    (length, [(t0, t1, piece)], [(music path, start, end, src in)]). One 25 fps sequence; the shots on V1 carry their own
    camera sound on A1/A2 (linked); the teaser's music on A3/A4; a marker on every part."""
    rate_xml, sf = core._rate(SEQ_FPS)
    n = [0]
    files, ainfo = {}, {}
    vt = {1: [], 2: [], 3: []}
    at = {1: [], 2: [], 3: [], 4: []}

    def nid():
        n[0] += 1
        return f"clipitem-{n[0]}"

    def info(path):
        if path not in ainfo:
            ainfo[path] = _ai(path)
        return ainfo[path]

    def file_xml(path, p=None):
        """The full <file> the first time, then only its id."""
        if path in files:
            return f'<file id="{files[path]}"/>'
        files[path] = f"file-{len(files) + 1}"
        r, ch = info(path)
        aud = (f'<audio><samplecharacteristics><depth>16</depth><samplerate>{r}</samplerate></samplecharacteristics>'
               f'<channelcount>{ch}</channelcount></audio>') if ch else ""
        if p is not None:
            frate, ffps = core._rate(p["fps"])
            return (f'<file id="{files[path]}"><name>{escape(Path(path).name)}</name><pathurl>{escape(core._url(path))}</pathurl>'
                    f'{frate}<duration>{int(p["fdur"] * ffps)}</duration><media><video>{core._sc(frate, p["w"], p["h"], "none")}'
                    f'</video>{aud}</media></file>')
        return (f'<file id="{files[path]}"><name>{escape(Path(path).name)}</name><pathurl>{escape(core._url(path))}</pathurl>'
                f'{rate_xml}<duration>{10 ** 7}</duration><media>{aud}</media></file>')

    def shot(track, t0, p, a, b, sound):
        st, en = round(t0 * sf), round((t0 + (b - a)) * sf)
        if en <= st:
            return
        fin = round(a * sf)
        fout = fin + (en - st)
        sdur = max(fout, int(p["fdur"] * sf))
        fx = file_xml(p["path"], p)
        fid = files[p["path"]]
        vid = nid()
        r, ch = info(p["path"])
        aids = [nid() for _ in range(min(2, ch))] if sound and ch else []
        links = "".join(f'<link><linkclipref>{x}</linkclipref><mediatype>{m}</mediatype><trackindex>{ti}</trackindex>'
                        f'<clipindex>1</clipindex></link>'
                        for x, m, ti in [(vid, "video", 1)] + [(aid, "audio", k + 1) for k, aid in enumerate(aids)]) if aids else ""
        vt[track].append(f'<clipitem id="{vid}"><name>{escape(Path(p["path"]).name)}</name><duration>{sdur}</duration>{rate_xml}'
                         f'<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fout}</out>{fx}{links}</clipitem>')
        for k, aid in enumerate(aids):
            at[k + 1].append(f'<clipitem id="{aid}"><name>{escape(Path(p["path"]).name)}</name><duration>{sdur}</duration>'
                             f'{rate_xml}<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fout}</out><file id="{fid}"/>'
                             f'<sourcetrack><mediatype>audio</mediatype><trackindex>{min(k + 1, ch)}</trackindex></sourcetrack>'
                             f'{links}</clipitem>')

    markers, g = [], 0.0
    if teaser_part:
        tl, shots, music = teaser_part
        markers.append(("Teaser", 0.0))
        for t0, t1, p in shots:
            shot(1, t0, p, p["s"], p["s"] + (t1 - t0), sound=False)
        for path, s0, s1, src in music:
            if not Path(path).exists() or s1 <= s0:
                continue
            r, ch = info(path)
            st, en = round(s0 * sf), round(s1 * sf)
            fin = round(src * sf)
            for k in range(min(2, max(1, ch))):
                at[3 + k].append(f'<clipitem id="{nid()}"><name>{escape(Path(path).name)}</name><duration>{fin + en - st}</duration>'
                                 f'{rate_xml}<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fin + en - st}</out>'
                                 f'{file_xml(path)}<sourcetrack><mediatype>audio</mediatype><trackindex>{k + 1}</trackindex>'
                                 f'</sourcetrack></clipitem>')
        g = tl
    for pname, length, items in parts_layout:
        if not items:
            continue
        markers.append((pname, g))
        for track, t0, p, a, b in items:
            shot(track, g + t0, p, a, b, sound=(track == 1))
        g += length
    markers.append(("Party (the Multicam edit)", g))
    total = round(g * sf) + 1
    trk = lambda its: f'<track>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    import i18n                                    # the markers in the language of the app
    mk = "".join(f'<marker><name>{escape(i18n.T(m))}</name><comment></comment><in>{round(t * sf)}</in><out>-1</out></marker>'
                 for m, t in markers)
    first = next((it[2] for _, _, its in parts_layout for it in its), None) or dict(w=1920, h=1080)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}{mk}'
           f'<media><video><format>{core._sc(rate_xml, first["w"], first["h"], "none")}</format>'
           f'{"".join(trk(vt[k]) for k in (1, 2, 3) if vt[k])}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{"".join(trk(at[k]) for k in (1, 2, 3, 4) if at[k])}</audio>'
           f'</media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return sum(len(v) for v in vt.values()), [m for m, _ in markers]


def teaser_part(tproj_pieces, music, bounds, seed=1):
    """The teaser of a Teaser Studio project: its shots and music up to 'Teaser ends'."""
    import teaser
    e = teaser.build(tproj_pieces, music, bounds, seed=seed)
    end = bounds["teaser_end"]
    shots = [(t0, min(t1, end), p) for t0, t1, p in e["shots"] if t0 < end - 0.05]
    if music["kind"] == "file":
        mus = [(music["path"], 0.0, end, 0.0)]
    else:
        mus = [(it["path"], it["start"], min(it["end"], end), it["a"]) for it in music["items"] if it["start"] < end]
    return end, shots, mus
