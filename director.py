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
DEFAULTS = dict(minshot=3, maxshot=10, pace=50, energy=60, beat=True)
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


def _dp(cost, mn, mx, pen, over_pen):
    """Viterbi over (camera, shot length). cost: C x T (lower is better). Returns camera index per cell."""
    C, T = cost.shape
    D = max(mx, mn + 1)
    INF = 1e18
    acc = np.full((C, D), INF)
    acc[:, 0] = cost[:, 0]
    bp_c = np.zeros((T, C), np.int16)
    bp_d = np.zeros((T, C), np.int16)
    bp_sat = np.zeros((T, C), bool)
    ar = np.arange(C)
    for t in range(1, T):
        ex = acc[:, mn - 1:]
        exv = ex.min(1)
        exd = ex.argmin(1) + mn - 1
        new = np.full((C, D), INF)
        if C > 1:
            order = np.argsort(exv)
            src = np.where(ar == order[0], order[1], order[0])
            new[:, 0] = exv[src] + pen
            bp_c[t] = src
            bp_d[t] = exd[src]
        new[:, 1:] = acc[:, :-1]
        stay = acc[:, D - 1] + over_pen
        sat = stay < new[:, D - 1]
        new[:, D - 1] = np.where(sat, stay, new[:, D - 1])
        bp_sat[t] = sat
        acc = new + cost[:, t][:, None]
    c, d = np.unravel_index(np.argmin(acc), acc.shape)
    path = np.zeros(T, int)
    for t in range(T - 1, -1, -1):
        path[t] = c
        if t == 0:
            break
        if d == 0:
            c, d = int(bp_c[t, c]), int(bp_d[t, c])
        elif d == D - 1 and bp_sat[t, c]:
            pass
        else:
            d -= 1
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
        refs = {}
        for ci in range(C):
            js = [_smooth_jitter(x[4].fs) for x in mem if x[0] == ci]
            refs[ci] = np.sort(np.concatenate(js)) if js else None
        for ci, p, off, dur, a in mem:
            role = cams[ci]["role"]
            qs = sample_quality(a, role, refs[ci]) + (bias if role == "Handheld" else -bias)
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
        path = _dp(cost, mn, mx, pen, 6.0)
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


# ---------------- XML: per master an "Auto Edit" sequence and a "Synced Cameras" sequence ----------------

def export_xml(masters, cams, results, analyses, edits, out_path, name):
    ids = dict(clip=0, file=0)
    defined = {}

    def nid(k):
        ids[k] += 1
        return f"{'clipitem' if k == 'clip' else 'file'}-{ids[k]}"

    def vfile(p, inf, frate, fdur):
        if p in defined:
            return f'<file id="{defined[p]}"/>'
        defined[p] = nid("file")
        return (f'<file id="{defined[p]}"><name>{escape(Path(p).name)}</name><pathurl>{escape(core._url(p))}</pathurl>{frate}'
                f'<duration>{fdur}</duration><media><video>{core._sc(frate, inf.width, inf.height, "none")}</video></media></file>')

    def audio_tracks(m, rate_xml, fps, T0):
        arate, ach = sync.audio_info(m["path"])
        ach = max(1, min(2, ach))
        mdur = int(np.ceil(m["duration"] * fps))
        key = "master:" + m["path"]
        tracks = []
        for ch in range(1, ach + 1):
            if key in defined:
                f = f'<file id="{defined[key]}"/>'
            else:
                defined[key] = nid("file")
                f = (f'<file id="{defined[key]}"><name>{escape(Path(m["path"]).name)}</name><pathurl>{escape(core._url(m["path"]))}</pathurl>'
                     f'{rate_xml}<duration>{mdur}</duration><media><audio><samplecharacteristics><depth>16</depth>'
                     f'<samplerate>{arate}</samplerate></samplecharacteristics><channelcount>{ach}</channelcount></audio></media></file>')
            st = round(-T0 * fps)
            tracks.append(f'<track><clipitem id="{nid("clip")}"><name>{escape(Path(m["path"]).name)}</name><duration>{mdur}</duration>'
                          f'{rate_xml}<start>{st}</start><end>{st + mdur}</end><in>0</in><out>{mdur}</out>{f}'
                          f'<sourcetrack><mediatype>audio</mediatype><trackindex>{ch}</trackindex></sourcetrack></clipitem>'
                          f'<enabled>TRUE</enabled><locked>FALSE</locked></track>')
        fmt = (f'<numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
               f'<samplerate>{arate}</samplerate></samplecharacteristics></format>')
        return fmt + "".join(tracks)

    def clipitem(ci, p, cin, cout, seq_t, T0, fps, label_extra=""):
        inf = analyses[p].info
        frate, ffps = core._rate(inf.fps)
        fdur = int(inf.duration * ffps)
        st = round((seq_t - T0) * fps)
        en = st + max(1, round((cout - cin) * fps))
        fin = max(0, round(cin * ffps))
        fout = min(fdur, fin + max(1, round((en - st) / fps * ffps)))
        return (f'<clipitem id="{nid("clip")}"><name>{escape(cams[ci]["name"] + " · " + Path(p).stem + label_extra)}</name>'
                f'<duration>{fdur}</duration>{frate}<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fout}</out>'
                f'<labels><label2>{sync.CAM_LABELS[ci % len(sync.CAM_LABELS)]}</label2></labels>{vfile(p, inf, frate, fdur)}</clipitem>')

    seqs = []
    for e in edits:
        if not e:
            continue
        m = masters[e["master"]]
        first = analyses[e["pieces"][0][1]].info if e["pieces"] else None
        if first is None:
            continue
        rate_xml, fps = core._rate(first.fps)
        sc = core._sc(rate_xml, first.width, first.height, "none")
        T0, total = e["T0"], int(np.ceil((e["T1"] - e["T0"]) * fps))
        stem = Path(m["path"]).stem
        # 1) auto edit
        v = "".join(clipitem(ci, p, a, b, s, T0, fps) for ci, p, a, b, s in e["pieces"])
        seqs.append(f'<sequence id="sequence-{len(seqs) + 1}"><name>{escape(name)} - Auto Edit - {escape(stem)}</name>'
                    f'<duration>{total}</duration>{rate_xml}<media><video><format>{sc}</format>'
                    f'<track>{v}<enabled>TRUE</enabled><locked>FALSE</locked></track></video>'
                    f'<audio>{audio_tracks(m, rate_xml, fps, T0)}</audio></media></sequence>')
        # 2) every camera on its own track, synced
        vt = []
        for ci, cam in enumerate(cams):
            items = sorted(((p, results[p]["offset"]) for p in cam["clips"] if p in analyses and results.get(p)
                            and results[p]["conf"] != "fail" and results[p]["master"] == e["master"]), key=lambda x: x[1])
            if items:
                flag = lambda p: " [CHECK SYNC]" if results[p]["conf"] == "low" else ""
                vt.append("<track>" + "".join(clipitem(ci, p, 0.0, analyses[p].duration, off, T0, fps, flag(p)) for p, off in items)
                          + "<enabled>TRUE</enabled><locked>FALSE</locked></track>")
        seqs.append(f'<sequence id="sequence-{len(seqs) + 1}"><name>{escape(name)} - Synced Cameras - {escape(stem)}</name>'
                    f'<duration>{total}</duration>{rate_xml}<media><video><format>{sc}</format>{"".join(vt)}</video>'
                    f'<audio>{audio_tracks(m, rate_xml, fps, T0)}</audio></media></sequence>')
    if not seqs:
        raise ValueError("Nothing to export yet: run Sync & Analyze first.")
    Path(out_path).write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">' + "".join(seqs)
                              + "</xmeml>", encoding="utf-8")
    return len(seqs)
