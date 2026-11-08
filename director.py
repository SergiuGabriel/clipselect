"""Multicam auto director.

Every camera gets a quality score on a 0.5 s grid of the master timeline (focus, exposure, stability, camera moves).
Handheld cameras are judged against their own footage (some wobble is part of their look); static cameras get a bonus
when something happens in frame. A dynamic-programming search then picks the camera for every moment, respecting the
minimum / maximum shot length and a switch penalty, and cuts are moved onto the nearest musical onset.
"""
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core
import sync

GRID = 0.5
SR = core.SAMPLE_FPS
DEFAULTS = dict(minshot=3, maxshot=30, pace=50, energy=60, beat=True, static_backup=False)
CAM_COLORS = ["#a78bfa", "#2dd4bf", "#fb923c", "#22c55e", "#818cf8", "#f472b6", "#38bdf8", "#c4b5fd"]  # = sync.CAM_LABELS


def detect_role(analyses):
    """Static if the camera itself (robust shift, ignores people moving) practically never moves."""
    sp = [np.hypot(a.fs["sx"], a.fs["sy"]) for a in analyses if a is not None and a.fs]
    if not sp:
        return "Handheld"
    sp = np.concatenate(sp)
    return "Static" if np.median(sp) < 0.6 and np.mean(sp > 2) < 0.1 else "Handheld"


def _smooth_jitter(fs):
    return np.convolve(core.jitter_vec(fs), np.ones(8) / 8, "same")


def sample_quality(a, role, jit_ref=None):
    fs = a.fs
    F = core.focus_vec(fs["lap"])
    E = core.exposure_vec(fs["mean"], fs["bright"])
    j = _smooth_jitter(fs)
    S = np.clip(1 - (j - 1.5) / 8, 0, 1)
    if role == "Handheld" and jit_ref is not None and len(jit_ref):
        S = 0.5 * S + 0.5 * (1 - np.searchsorted(jit_ref, j) / len(jit_ref))
    q = 100 * (0.6 * (0.4 * F + 0.3 * S + 0.3 * E) + 0.4 * np.minimum(np.minimum(F, S), E))
    if role == "Static":
        q = q + 10 * np.clip(np.asarray(fs["diff"]) / 10, 0, 1)
    q[core.moving_mask(fs)] *= 0.15
    return q


def _dp(cost, mn, pen):
    """Viterbi over (camera, shot length capped at mn). A switch is allowed only after mn cells.
    cost: C x T (lower is better). Returns the camera index for every cell."""
    C, T = cost.shape
    D = max(1, mn)
    INF = 1e18
    acc = np.full((C, D), INF)
    acc[:, 0] = cost[:, 0]
    bp_src = np.zeros((T, C), np.int16)
    bp_sat = np.zeros((T, C), bool)
    ar = np.arange(C)
    for t in range(1, T):
        last = acc[:, D - 1]
        if C > 1:
            order = np.argsort(last)
            src = np.where(ar == order[0], order[1], order[0])
            sw = last[src] + pen
        else:
            src, sw = ar, np.full(C, INF)
        new = np.empty_like(acc)
        if D == 1:
            stay = acc[:, 0]
            take = sw < stay
            new[:, 0] = np.where(take, sw, stay)
            bp_src[t] = np.where(take, src, ar)
        else:
            new[:, 0] = sw
            bp_src[t] = src
            new[:, 1:D - 1] = acc[:, 0:D - 2]
            stay, prev = acc[:, D - 1], acc[:, D - 2]
            sat = stay < prev
            new[:, D - 1] = np.where(sat, stay, prev)
            bp_sat[t] = sat
        acc = new + cost[:, t][:, None]
    c, d = np.unravel_index(np.argmin(acc), acc.shape)
    path = np.zeros(T, int)
    for t in range(T - 1, 0, -1):
        path[t] = c
        if d == 0:
            c = int(bp_src[t, c])
            d = D - 1 if D > 1 else 0
        elif d == D - 1 and bp_sat[t, c]:
            pass
        else:
            d -= 1
    path[0] = c
    return path


def _limit_long_shots(path, q, avail, mn, mx):
    """A shot longer than the maximum gets interrupted by the best other camera (if that camera is usable
    for at least the minimum shot length), then the edit returns to the original camera."""
    T = len(path)
    t = 0
    while t < T:
        c = path[t]
        e = t
        while e < T and path[e] == c:
            e += 1
        k = t + mx
        while k + mn <= e - mn:
            span = slice(k, k + mn * 2)
            best, bq = -1, -1e9
            for c2 in range(q.shape[0]):
                if c2 != c and avail[c2, span].all():
                    v = q[c2, span].mean()
                    if v > bq:
                        best, bq = c2, v
            if best >= 0 and bq >= q[c, span].mean() - 25:
                path[span] = best
                k += mn * 2 + mx
            else:
                k += mn
        t = e
    return path


def build(cams, results, analyses, masters, st):
    """Returns one edit per master: dict(master, T0, T1, segs=[(t0, t1, cam)], pieces=[(cam, path, in, out, seq_t)],
    stats). Times are master times (seconds)."""
    st = {**DEFAULTS, **(st or {})}
    out = []
    for mi, m in enumerate(masters):
        mem = []
        for ci, c in enumerate(cams):
            for p in c["clips"]:
                r, a = results.get(p), analyses.get(p)
                if r and r["conf"] != "fail" and r["master"] == mi and a is not None and a.fs:
                    mem.append((ci, p, r["offset"], a.duration, a))
        if not mem:
            out.append(None)
            continue
        T0 = min(0.0, min(x[2] for x in mem))
        T1 = max(m["duration"], max(x[2] + x[3] for x in mem))
        nT = max(2, int(np.ceil((T1 - T0) / GRID)))
        C = len(cams)
        q = np.full((C, nT), -np.inf)
        bias = (st["energy"] - 50) / 50 * 25
        static_pen = 40 if st.get("static_backup") else 0
        refs = {}
        for ci in range(C):
            js = [_smooth_jitter(x[4].fs) for x in mem if x[0] == ci]
            refs[ci] = np.sort(np.concatenate(js)) if js else None
        for ci, p, off, dur, a in mem:
            role = cams[ci]["role"]
            qs = sample_quality(a, role, refs[ci]) + (bias if role == "Handheld" else -bias - static_pen)
            cell = ((off - T0 + np.arange(len(qs)) / SR) / GRID).astype(int)
            ok = (cell >= 0) & (cell < nT)
            s = np.bincount(cell[ok], weights=qs[ok], minlength=nT)
            n = np.bincount(cell[ok], minlength=nT)
            q[ci] = np.maximum(q[ci], np.where(n >= 2, s / np.maximum(n, 1), -np.inf))
        avail = np.isfinite(q)
        cost = np.where(avail, 100 - q, 1e4)
        mn = max(1, int(round(st["minshot"] / GRID)))
        mx = max(mn + 1, int(round(st["maxshot"] / GRID)))
        pen = 2 + (100 - st["pace"]) / 100 * 18
        path = _limit_long_shots(_dp(cost, mn, pen), np.where(avail, q, -1e9), avail, mn, mx)
        # segments (skip cells where the chosen camera has no footage)
        segs = []
        for t in range(nT):
            c = int(path[t]) if avail[path[t], t] else -1
            if segs and segs[-1][2] == c:
                segs[-1][1] = t + 1
            else:
                segs.append([t, t + 1, c])
        segs = [[T0 + a * GRID, min(T1, T0 + b * GRID), c] for a, b, c in segs if c >= 0]
        # cuts on the beat
        on = np.array(m.get("onsets") or [])
        if st["beat"] and len(on):
            for k in range(1, len(segs)):
                prev, cur = segs[k - 1], segs[k]
                if abs(prev[1] - cur[0]) > 1e-6:
                    continue
                b = cur[0]
                i = np.searchsorted(on, b)
                cand = [on[j] for j in (i - 1, i) if 0 <= j < len(on) and abs(on[j] - b) <= 0.3]
                if not cand:
                    continue
                nb = min(cand, key=lambda x: abs(x - b))
                cell_new = int((nb - T0) / GRID)
                who = cur[2] if nb < b else prev[2]
                if 0 <= cell_new < nT and avail[who, cell_new] and nb - prev[0] >= 0.8 * st["minshot"] and cur[1] - nb >= 0.8 * st["minshot"]:
                    prev[1] = cur[0] = float(nb)
        # map to clip pieces
        pieces = []
        for t0, t1, ci in segs:
            for c2, p, off, dur, a in sorted((x for x in mem if x[0] == ci), key=lambda x: x[2]):
                s0, s1 = max(t0, off), min(t1, off + dur)
                if s1 - s0 > 0.04:
                    pieces.append((ci, p, s0 - off, s1 - off, s0))
        shots = [s[1] - s[0] for s in segs]
        share = {}
        for t0, t1, ci in segs:
            share[ci] = share.get(ci, 0) + t1 - t0
        out.append(dict(master=mi, T0=T0, T1=T1, segs=[tuple(s) for s in segs], pieces=pieces,
                        stats=dict(shots=len(segs), avg=float(np.mean(shots)) if shots else 0.0,
                                   share={ci: v / max(1e-9, sum(share.values())) for ci, v in share.items()})))
    return out


# ---------------- XML: ONE sequence with everything ----------------
# V1..Vn  = one track per camera. With an auto edit: only that camera's cuts (nothing overlaps, so it plays as the edit).
#           Sync only (no auto edit yet): the full clips.
# A1(/A2) = recorder (all recorder files, one after another on the common timeline)
# then one audio track per camera (camera sound, synced, track disabled so only the recorder plays)

def export_xml(masters, cams, results, analyses, edits, out_path, name, starts=None):
    starts = starts or sync.master_starts(masters)
    ids = dict(clip=0, file=0)
    defined, ainfo = {}, {}

    def nid(k):
        ids[k] += 1
        return f"{'clipitem' if k == 'clip' else 'file'}-{ids[k]}"

    def ai(p):
        if p not in ainfo:
            try:
                ainfo[p] = sync.audio_info(p)
            except Exception:
                ainfo[p] = (48000, 2)
        return ainfo[p]

    def vinfo(p):
        a = analyses.get(p)
        if a is not None:
            return a.info
        return core.probe(p)

    placed = []   # (cam, path, global_start)
    for ci, cam in enumerate(cams):
        for p in cam["clips"]:
            r = results.get(p)
            if r and r["conf"] != "fail":
                placed.append((ci, p, starts[r["master"]] + r["offset"]))
    if not placed:
        raise ValueError("Nothing to export yet: run Sync first.")
    first = vinfo(placed[0][1])
    rate_xml, fps = core._rate(first.fps)
    T0 = min([0.0] + [g for _, _, g in placed])
    sc = core._sc(rate_xml, first.width, first.height, "none")

    def file_xml(p):
        if p in defined:
            return f'<file id="{defined[p]}"/>'
        defined[p] = nid("file")
        inf = vinfo(p)
        frate, ffps = core._rate(inf.fps)
        rate, ch = ai(p)
        return (f'<file id="{defined[p]}"><name>{escape(Path(p).name)}</name><pathurl>{escape(core._url(p))}</pathurl>{frate}'
                f'<duration>{int(inf.duration * ffps)}</duration><media><video>{core._sc(frate, inf.width, inf.height, "none")}</video>'
                f'<audio><samplecharacteristics><depth>16</depth><samplerate>{rate}</samplerate></samplecharacteristics>'
                f'<channelcount>{ch}</channelcount></audio></media></file>')

    def item(p, cin, cout, g_start, label, title, audio_ch=None):
        # Every number of a clipitem is in SEQUENCE frames (like Premiere's own XML); only the <file> keeps the
        # camera's real frame rate. Mixing the two made 50p / 59.94p cameras drift in a 25p sequence.
        inf = vinfo(p)
        sdur = max(1, int(round(inf.duration * fps)))
        st = round((g_start - T0) * fps)
        en = st + max(1, round((cout - cin) * fps))
        fin = max(0, round(cin * fps))
        fout = min(sdur, fin + (en - st))
        en = st + (fout - fin)
        src = (f'<sourcetrack><mediatype>audio</mediatype><trackindex>{audio_ch}</trackindex></sourcetrack>' if audio_ch else "")
        return (f'<clipitem id="{nid("clip")}"><name>{escape(title)}</name><duration>{sdur}</duration>{rate_xml}'
                f'<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fout}</out>'
                f'<labels><label2>{label}</label2></labels>{file_xml(p)}{src}</clipitem>')

    def track(items, enabled=True):
        return f'<track>{"".join(items)}<enabled>{"TRUE" if enabled else "FALSE"}</enabled><locked>FALSE</locked></track>'

    lab = lambda ci: sync.CAM_LABELS[ci % len(sync.CAM_LABELS)]
    flag = lambda p: " [CHECK SYNC]" if results[p]["conf"] == "low" else ""
    dur = lambda p: vinfo(p).duration or results[p].get("dur", 0)
    v_tracks, a_tracks = [], []
    # video: if there is an auto edit, every camera's track holds ONLY its cuts (like a multicam edit already
    # flattened), so a wrong cut is fixed by trimming / swapping on that camera's track. Without an auto edit
    # (sync only) every camera track holds its full clips.
    cuts = {ci: [] for ci in range(len(cams))}
    for e in edits or []:
        if e:
            g0 = starts[e["master"]]
            for ci, p, a, b, s0 in e["pieces"]:
                cuts[ci].append((g0 + s0, p, a, b))
    has_edit = any(cuts.values())
    for ci, cam in enumerate(cams):
        if has_edit:
            its = [item(p, a, b, g, lab(ci), f"{cam['name']} · {Path(p).stem}{flag(p)}") for g, p, a, b in sorted(cuts[ci])]
        else:
            its = [item(p, 0.0, dur(p), g, lab(ci), f"{cam['name']} · {Path(p).stem}{flag(p)}")
                   for c, p, g in sorted(placed, key=lambda x: x[2]) if c == ci]
        v_tracks.append(track(its))
    edit_items = has_edit
    # recorder
    arate, ach = ai(masters[0]["path"])
    ach = max(1, min(2, ach))
    for ch in range(1, ach + 1):
        its = []
        for mi, m in enumerate(masters):
            key = "m:" + m["path"]
            mdur = int(np.ceil(m["duration"] * fps))
            if key in defined:
                f = f'<file id="{defined[key]}"/>'
            else:
                defined[key] = nid("file")
                r_, c_ = ai(m["path"])
                f = (f'<file id="{defined[key]}"><name>{escape(Path(m["path"]).name)}</name><pathurl>{escape(core._url(m["path"]))}</pathurl>'
                     f'{rate_xml}<duration>{mdur}</duration><media><audio><samplecharacteristics><depth>16</depth>'
                     f'<samplerate>{r_}</samplerate></samplecharacteristics><channelcount>{c_}</channelcount></audio></media></file>')
            st = round((starts[mi] - T0) * fps)
            its.append(f'<clipitem id="{nid("clip")}"><name>RECORDER · {escape(Path(m["path"]).name)}</name><duration>{mdur}</duration>'
                       f'{rate_xml}<start>{st}</start><end>{st + mdur}</end><in>0</in><out>{mdur}</out>{f}'
                       f'<sourcetrack><mediatype>audio</mediatype><trackindex>{min(ch, c_ if (c_ := ai(m["path"])[1]) else 1)}</trackindex></sourcetrack></clipitem>')
        a_tracks.append(track(its))
    # camera sound, one track per camera
    for ci, cam in enumerate(cams):
        its = [item(p, 0.0, dur(p), g, lab(ci), f"{cam['name']} audio · {Path(p).stem}", audio_ch=1)
               for c, p, g in sorted(placed, key=lambda x: x[2]) if c == ci and ai(p)[1] > 0]
        if its:
            a_tracks.append(track(its, enabled=False))
    end = max([g + dur(p) for _, p, g in placed] + [starts[i] + m["duration"] for i, m in enumerate(masters)])
    total = int(np.ceil((end - T0) * fps))
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}<media><video><format>{sc}</format>{"".join(v_tracks)}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>{arate}</samplerate>'
           f'</samplecharacteristics></format>{"".join(a_tracks)}</audio></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return dict(video_tracks=len(v_tracks), audio_tracks=len(a_tracks), edit=bool(edit_items))
