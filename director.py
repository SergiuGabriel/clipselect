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
DEFAULTS = dict(minshot=3, maxshot=30, pace=50, energy=60, beat=True, static_backup=False,
                drop_beats=4, buildup="hold", energy_cuts=True)       # the last three: global (Settings > Auto edit music)
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


def _music_slots(mm, r0, r1, st, en_at):
    """Shots on the music between r0 and r1: list of (t0, t1, kind) on bar / beat lines.
    kind: 'drop' (one cut every drop_beats), 'build' (held or accelerating), 'bar' (1-8 bars, by energy)."""
    beats = np.asarray(mm["beats"], float)
    down = np.asarray(mm["down"], int)
    bars = beats[down] if len(down) else np.array([])
    bars = bars[(bars >= r0 - 1e-6) & (bars < r1)]
    if len(bars) < 2:
        return []
    bar_len = float(np.median(np.diff(bars)))
    drops = [d for d in mm.get("drops", []) if r0 <= d[0] < r1]
    builds = [b for b in mm.get("builds", []) if r0 <= b[1] <= r1 + 1e-6]
    u = int(st.get("drop_beats", 4))
    slots, i = [], 0
    bars_l = list(bars) + [min(r1, bars[-1] + bar_len)]

    def in_span(t, spans):
        return next((sp for sp in spans if sp[0] - 1e-6 <= t < sp[1] - 1e-6), None)
    while i < len(bars_l) - 1:
        t = bars_l[i]
        d = in_span(t, drops)
        bu = in_span(t, builds)
        if d:                                          # drop: one camera change every u beats, from the drop
            bb = beats[(beats >= d[0] - 1e-6) & (beats < min(d[1], r1) - 1e-6)]
            pts = list(bb[::u]) + [min(d[1], r1)]
            for a, b in zip(pts, pts[1:]):
                if b - a > 0.2:
                    slots.append((float(a), float(b), "drop"))
            while i < len(bars_l) - 1 and bars_l[i] < d[1] - 1e-6:
                i += 1
            continue
        if bu:                                         # build-up before a drop
            end = bu[1]
            if st.get("buildup", "hold") == "accelerate":
                bl = [x for x in bars_l if bu[0] - 1e-6 <= x < end - 1e-6]
                n = len(bl)
                pts = bl[:max(1, n // 2):2] + bl[max(1, n // 2):max(1, 3 * n // 4)]
                bb = beats[(beats >= (bl[3 * n // 4] if n >= 4 else bl[-1]) - 1e-6) & (beats < end - 1e-6)]
                pts = sorted(set(pts + list(bb[::2]))) + [end]
                for a, b in zip(pts, pts[1:]):
                    if b - a > 0.2:
                        slots.append((float(a), float(b), "build"))
            else:
                slots.append((float(bu[0]), float(end), "build"))
            while i < len(bars_l) - 1 and bars_l[i] < end - 1e-6:
                i += 1
            continue
        # normal bars: as many as the minimum shot needs (powers of 2), shorter when the music is intense
        k = 1
        while k * bar_len < st["minshot"] * 0.95 and k < 8:
            k *= 2
        if st.get("energy_cuts", True):
            e = en_at(t, t + k * bar_len)
            if e >= 0.7:
                k = max(1, k // 2)
            elif e <= 0.35:
                k = min(8, k * 2)
        while k > 1 and k * bar_len > st["maxshot"]:
            k //= 2
        while k > 1 and i % k:                         # stay on the phrase grid (bar 1, 3, 5... / 1, 5, 9...)
            k //= 2
        j = i + k
        # never run into a drop / build-up
        for sp in drops + builds:
            if t < sp[0] < bars_l[min(j, len(bars_l) - 1)]:
                j = next(n for n, x in enumerate(bars_l) if x >= sp[0] - 1e-6)
        j = max(i + 1, min(j, len(bars_l) - 1))
        slots.append((float(t), float(bars_l[j]), "bar"))
        i = j
    return slots


def _slot_dp(cost, kinds, pace, C):
    """Camera per slot. State = (camera now, camera before): staying costs (we WANT a change on the bar line),
    going back to the camera before costs a bit (no ping-pong between two cameras), most on a drop."""
    S = cost.shape[1]
    stay_n = 10 + 0.3 * pace
    INF = 1e18
    acc = np.repeat(cost[:, 0][:, None], C, axis=1)            # acc[now, before]
    bp = np.zeros((S, C, C), np.int16)
    eye = np.eye(C, dtype=bool)
    for s in range(1, S):
        drop = kinds[s] in ("drop", "build") or kinds[s - 1] == "build"
        stay = 60.0 if drop else stay_n
        pp = (15.0 if drop else 8.0) if C >= 3 else 0.0
        # tmp[c, p, q] = acc[p, q] + stay if c == p + pp if c == q (and c != p)
        tmp = np.broadcast_to(acc[None, :, :], (C, C, C)).copy()
        tmp[eye[:, :, None].repeat(C, 2)] += stay
        back = eye[:, None, :].repeat(C, 1) & ~eye[:, :, None].repeat(C, 2)
        tmp[back] += pp
        bq = tmp.argmin(axis=2)
        acc = tmp.min(axis=2) + cost[:, s][:, None]
        acc = np.minimum(acc, INF)
        bp[s] = bq
    c, p = np.unravel_index(np.argmin(acc), acc.shape)
    path = [0] * S
    for s in range(S - 1, -1, -1):
        path[s] = int(c)
        if s:
            c, p = int(p), int(bp[s, c, p])
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
                if r and r["conf"] in ("high", "medium") and r["master"] == mi and a is not None and a.fs:
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
        mm = m.get("music") if st["beat"] else None
        music_spans = []
        if mm and mm.get("beats"):
            ev = np.asarray(mm["energy"]["v"], float)
            er = mm["energy"]["rate"]
            en_at = lambda a, b: float(ev[int(a * er):max(int(a * er) + 1, int(b * er))].mean()) if int(a * er) < len(ev) else 0.5
            for r0_, r1_, kind_, _bpm in mm["regions"]:
                if kind_ != "music":
                    continue
                sl = _music_slots(mm, max(r0_, T0), min(r1_, T1), st, en_at)
                if len(sl) < 2:
                    continue
                cst = np.full((C, len(sl)), 1e4)
                for k_, (a_, b_, _) in enumerate(sl):
                    c0, c1 = int((a_ - T0) / GRID), max(int((a_ - T0) / GRID) + 1, int(np.ceil((b_ - T0) / GRID)))
                    c0, c1 = max(0, c0), min(nT, c1)
                    if c1 <= c0:
                        continue
                    av = avail[:, c0:c1].mean(1)
                    qm = np.array([q[ci, c0:c1][avail[ci, c0:c1]].mean() if avail[ci, c0:c1].any() else -1e3 for ci in range(C)])
                    cst[:, k_] = np.where(av >= 0.9, 100 - qm, 1e4 * (1 - av) + 100 - np.maximum(qm, -100))
                cpath = _slot_dp(cst, [x[2] for x in sl], st["pace"], C)
                music_spans.append((sl[0][0], sl[-1][1], [(a_, b_, cpath[k_]) for k_, (a_, b_, _) in enumerate(sl)]))
        # segments (skip cells where the chosen camera has no footage)
        segs = []
        for t in range(nT):
            c = int(path[t]) if avail[path[t], t] else -1
            if segs and segs[-1][2] == c:
                segs[-1][1] = t + 1
            else:
                segs.append([t, t + 1, c])
        segs = [[T0 + a * GRID, min(T1, T0 + b * GRID), c] for a, b, c in segs if c >= 0]
        if music_spans:
            out_segs = []
            for a_, b_, c_ in segs:                      # the grid edit OUTSIDE the music
                pieces_ = [(a_, b_)]
                for s0, s1, _ in music_spans:
                    nxt = []
                    for u0, u1 in pieces_:
                        if u1 <= s0 or u0 >= s1:
                            nxt.append((u0, u1))
                        else:
                            if u0 < s0:
                                nxt.append((u0, s0))
                            if u1 > s1:
                                nxt.append((s1, u1))
                    pieces_ = nxt
                out_segs += [[u0, u1, c_] for u0, u1 in pieces_ if u1 - u0 > 0.04]
            for s0, s1, sl in music_spans:
                out_segs += [[a_, b_, c_] for a_, b_, c_ in sl]
            out_segs.sort(key=lambda x: x[0])
            segs = []
            for x in out_segs:                           # merge same camera
                if segs and segs[-1][2] == x[2] and abs(segs[-1][1] - x[0]) < 1e-6:
                    segs[-1][1] = x[1]
                else:
                    segs.append(x)
            # speech: move cuts outside the music into the pauses between sentences
            pz = np.array(mm.get("pauses") or [])
            if len(pz):
                inmus = lambda t: any(s0 - 1e-6 <= t <= s1 + 1e-6 for s0, s1, _ in music_spans)
                for k in range(1, len(segs)):
                    prev, cur = segs[k - 1], segs[k]
                    b = cur[0]
                    if abs(prev[1] - b) > 1e-6 or inmus(b):
                        continue
                    j = np.searchsorted(pz, b)
                    cand = [pz[i] for i in range(max(0, j - 3), min(len(pz), j + 3))
                            if abs(pz[i] - b) <= 1.5 and not inmus(pz[i])]
                    if cand:
                        for nb in sorted(cand, key=lambda x: abs(x - b)):
                            nb = float(nb)
                            if nb - prev[0] >= 0.8 * st["minshot"] and cur[1] - nb >= 0.8 * st["minshot"]:
                                prev[1] = cur[0] = nb
                                break
            # slivers left where the grid edit meets the music: glued to the shot before (never inside a drop)
            protect = [(a_, b_) for _, _, sl in music_spans for a_, b_, _c in sl]
            short = lambda sg: sg[1] - sg[0] < 0.6 * st["minshot"] and not any(abs(sg[0] - a_) < 1e-6 and abs(sg[1] - b_) < 1e-6 for a_, b_ in protect)
            k = 0
            while k < len(segs):
                if short(segs[k]) and len(segs) > 1:
                    if k > 0 and abs(segs[k - 1][1] - segs[k][0]) < 1e-6:
                        segs[k - 1][1] = segs[k][1]
                        segs.pop(k)
                        continue
                    if k + 1 < len(segs) and abs(segs[k][1] - segs[k + 1][0]) < 1e-6:
                        segs[k + 1][0] = segs[k][0]
                        segs.pop(k)
                        continue
                k += 1
            merged_ = []
            for x_ in segs:
                if merged_ and merged_[-1][2] == x_[2] and abs(merged_[-1][1] - x_[0]) < 1e-6:
                    merged_[-1][1] = x_[1]
                else:
                    merged_.append(x_)
            segs = merged_
        # cuts on the beat (old way, only without a music map)
        on = np.array(m.get("onsets") or [])
        if st["beat"] and len(on) and not music_spans:
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
        out.append(dict(master=mi, T0=T0, T1=T1, segs=[tuple(s) for s in segs], pieces=pieces, music=bool(music_spans),
                        stats=dict(shots=len(segs), avg=float(np.mean(shots)) if shots else 0.0,
                                   share={ci: v / max(1e-9, sum(share.values())) for ci, v in share.items()})))
    return out


# ---------------- XML: ONE sequence with everything ----------------
# V1..Vn  = one track per camera. With an auto edit: only that camera's cuts (nothing overlaps, so it plays as the edit).
#           Sync only (no auto edit yet): the full clips.
# A1(/A2) = recorder (all recorder files, one after another on the common timeline)
# then one audio track per camera (camera sound, synced, uncut, NOT muted)

def song_starts(mm):
    """(time, tempo) where every song starts: a tempo change (> 4 %) or a gap in the beats."""
    b, bp = mm.get("beats", []), mm.get("bpm", [])
    out = []
    for i in range(len(b)):
        if i == 0 or abs(bp[i] - bp[i - 1]) / max(1e-6, bp[i - 1]) > 0.04 or b[i] - b[i - 1] > 2.5 * 60 / max(1e-6, bp[i - 1]):
            seg = [x for x, t in zip(bp[i:i + 32], b[i:i + 32])]
            out.append((b[i], float(np.median(seg))))
    return out


def music_markers(masters, starts, T0, fps):
    """Sequence markers: every song start (with its tempo) and every drop."""
    out = []
    for mi, m in enumerate(masters):
        mm = m.get("music")
        if not mm:
            continue
        for t, bpm in song_starts(mm):
            out.append((starts[mi] + t, f"Song · {bpm:.0f} BPM"))
        for d0, d1 in mm.get("drops", []):
            out.append((starts[mi] + d0, "DROP"))
    return "".join(f'<marker><name>{escape(n)}</name><comment></comment><in>{round((t - T0) * fps)}</in><out>-1</out></marker>'
                   for t, n in sorted(out))


def export_beatcheck(masters, out_xml, fps=25.0):
    """To CHECK the beat on your own music: a click track (a click on every beat, higher on beat 1 of the bar, a long
    tone on every drop) next to the recorder, one sequence. Listen / look at the waveform in Premiere or DaVinci."""
    import wave
    starts = sync.master_starts(masters)
    rate_xml, fps = core._rate(fps)
    SRC = 16000
    a1, a2, defs = [], [], []
    n = 0
    for mi, m in enumerate(masters):
        mm = m.get("music")
        if not mm or not m.get("path"):
            continue
        n += 1
        dur = m["duration"]
        x = np.zeros(int(dur * SRC) + SRC, np.float32)
        down = set(mm.get("down", []))
        for k, b in enumerate(mm.get("beats", [])):
            f, ln, amp = (2000, 0.015, 0.9) if k in down else (1000, 0.012, 0.5)
            t = np.arange(int(ln * SRC)) / SRC
            i = int(b * SRC)
            seg = amp * np.sin(2 * np.pi * f * t) * np.exp(-t * 200)
            x[i:i + len(seg)] += seg[:max(0, len(x) - i)]
        for d0, _ in mm.get("drops", []):
            t = np.arange(int(0.4 * SRC)) / SRC
            i = int(d0 * SRC)
            seg = 0.6 * np.sin(2 * np.pi * 3000 * t) * np.exp(-t * 6)
            x[i:i + len(seg)] += seg[:max(0, len(x) - i)]
        wav = Path(out_xml).with_name(f"{Path(out_xml).stem} - beats {n}.wav")
        with wave.open(str(wav), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SRC)
            w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())
        fr = int(np.ceil(dur * fps))
        st = round(starts[mi] * fps)
        r_, c_ = sync.audio_info(m["path"])
        a1.append(f'<clipitem id="rec-{n}"><name>{escape(Path(m["path"]).name)}</name><duration>{fr}</duration>{rate_xml}'
                  f'<start>{st}</start><end>{st + fr}</end><in>0</in><out>{fr}</out><file id="frec-{n}"><name>{escape(Path(m["path"]).name)}</name>'
                  f'<pathurl>{escape(core._url(m["path"]))}</pathurl>{rate_xml}<duration>{fr}</duration><media><audio><samplecharacteristics>'
                  f'<depth>16</depth><samplerate>{r_}</samplerate></samplecharacteristics><channelcount>{c_}</channelcount></audio></media></file>'
                  f'<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')
        a2.append(f'<clipitem id="clk-{n}"><name>{escape(wav.name)}</name><duration>{fr}</duration>{rate_xml}'
                  f'<start>{st}</start><end>{st + fr}</end><in>0</in><out>{fr}</out><file id="fclk-{n}"><name>{escape(wav.name)}</name>'
                  f'<pathurl>{escape(core._url(str(wav)))}</pathurl>{rate_xml}<duration>{fr}</duration><media><audio><samplecharacteristics>'
                  f'<depth>16</depth><samplerate>{SRC}</samplerate></samplecharacteristics><channelcount>1</channelcount></audio></media></file>'
                  f'<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')
    if not n:
        raise ValueError("No music map yet: press Auto Edit first (it reads the music).")
    total = max(round((starts[i] + m["duration"]) * fps) for i, m in enumerate(masters))
    trk = lambda its: f'<track>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(Path(out_xml).stem)}</name><duration>{total}</duration>{rate_xml}{music_markers(masters, starts, 0.0, fps)}'
           f'<media><video><format>{core._sc(rate_xml, 1920, 1080, "none")}</format><track></track></video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{trk(a1)}{trk(a2)}</audio></media></sequence></xmeml>')
    Path(out_xml).write_text(xml, encoding="utf-8")
    return n


def export_xml(masters, cams, results, analyses, edits, out_path, name, starts=None):
    starts = starts or sync.master_starts(masters)
    ids = dict(clip=0, file=0)
    defined, ainfo = {}, {}

    def nid(k):
        ids[k] += 1
        return f"{'clipitem' if k == 'clip' else 'file'}-{ids[k]}"

    snd = {}

    def has_sound(p):
        if p not in snd:
            try:
                snd[p] = core.audio_layout(p)[1] > 0
            except Exception:
                snd[p] = False
        return snd[p]

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
        if cam.get("role") == "Audio":
            continue
        for p in cam["clips"]:
            r = results.get(p)
            if r and r["conf"] != "fail":
                placed.append((ci, p, starts[r["master"]] + r["offset"]))
    if not placed:
        raise ValueError("Nothing to export yet: run Sync first.")
    first = vinfo(placed[0][1])
    rate_xml, fps = core._rate(first.fps)
    T0 = min([0.0] + [g for _, _, g in placed] +
             [starts[results[p]["master"]] + results[p]["offset"] for c in cams if c.get("role") == "Audio"
              for p in c["clips"] if results.get(p) and results[p]["conf"] != "fail"])
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

    def item(p, cin, cout, g_start, label, title, audio_ch=None, frames=None):
        # Every number of a clipitem is in SEQUENCE frames (like Premiere's own XML); only the <file> keeps the
        # camera's real frame rate. Mixing the two made 50p / 59.94p cameras drift in a 25p sequence.
        inf = vinfo(p)
        sdur = max(1, int(round(inf.duration * fps)))
        clip0 = (g_start - cin - T0) * fps   # where the clip's first frame sits on the timeline (may be sub-frame)
        if frames:                           # cut boundaries computed once for the whole edit (shared by neighbours)
            st, en = frames
        else:
            st = round((g_start - T0) * fps)
            en = st + max(1, round((cout - cin) * fps))
        fin = max(0, round(st - clip0))      # source frame derived from the timeline frame: picture stays in sync
        fout = min(sdur, fin + (en - st))
        en = st + (fout - fin)
        src = (f'<sourcetrack><mediatype>audio</mediatype><trackindex>{audio_ch}</trackindex></sourcetrack>' if audio_ch else "")
        # the clip name MUST be the file name: DaVinci Resolve links timeline clips to media by name
        # ("V1 · RS CAM · RS-MAIN6210" made every clip "Media Offline"); the camera is shown by track + colour
        return (f'<clipitem id="{nid("clip")}"><name>{escape(Path(p).name)}</name><duration>{sdur}</duration>{rate_xml}'
                f'<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fout}</out>'
                f'<labels><label2>{label}</label2></labels>{file_xml(p)}{src}</clipitem>')

    def track(items, enabled=True):
        return f'<track>{"".join(items)}<enabled>{"TRUE" if enabled else "FALSE"}</enabled><locked>FALSE</locked></track>'

    lab = lambda ci: sync.CAM_LABELS[ci % len(sync.CAM_LABELS)]
    flag = lambda p: " [CHECK SYNC]" if results[p]["conf"] == "low" else ""
    dur = lambda p: results[p].get("dur") or vinfo(p).duration   # checked against the real sound length
    v_tracks, a_tracks = [], []
    # video: if there is an auto edit, every camera's track holds ONLY its cuts (like a multicam edit already
    # flattened), so a wrong cut is fixed by trimming / swapping on that camera's track. Without an auto edit
    # (sync only) every camera track holds its full clips.
    # All cut boundaries are turned into frames ONCE for the whole edit: when one piece ends where the next begins,
    # both get exactly the same frame, so there is never a 1-frame gap or overlap between cameras.
    allp = []
    for e in edits or []:
        if e:
            g0 = starts[e["master"]]
            allp += [[g0 + s0, g0 + s0 + (b - a), ci, p, a, b] for ci, p, a, b, s0 in e["pieces"]]
    allp.sort(key=lambda x: x[0])
    fr = lambda t: round((t - T0) * fps)
    frames = [[fr(x[0]), fr(x[1])] for x in allp]
    for k in range(len(allp) - 1):
        if abs(allp[k][1] - allp[k + 1][0]) < 0.1:      # touching pieces share the boundary frame
            frames[k][1] = frames[k + 1][0]
    cuts = {ci: [] for ci in range(len(cams))}
    for (g, gend, ci, p, a, b), f in zip(allp, frames):
        if f[1] > f[0]:
            cuts[ci].append((g, p, a, b, tuple(f)))
    has_edit = any(cuts.values())
    for ci, cam in enumerate(cams):
        if cam.get("role") == "Audio":
            continue
        if has_edit and not cam.get("approx") and not cam.get("check"):
            its = [item(p, a, b, g, lab(ci), f"{cam['name']} · {Path(p).stem}{flag(p)}", frames=f) for g, p, a, b, f in cuts[ci]]
        else:
            its = [item(p, 0.0, dur(p), g, lab(ci), f"{cam['name']} · {Path(p).stem}{flag(p)}")
                   for c, p, g in sorted(placed, key=lambda x: x[2]) if c == ci]
        v_tracks.append(track(its))
    edit_items = has_edit
    # recorder (an imported XML may have none: the timeline itself was the reference)
    real = [mi for mi, m in enumerate(masters) if m.get("path")]
    arate, ach = ai(masters[real[0]]["path"]) if real else (48000, 0)
    ach = max(1, min(2, ach)) if real else 0
    for ch in range(1, ach + 1):
        its = []
        for mi, m in enumerate(masters):
            if not m.get("path"):
                continue
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
            its.append(f'<clipitem id="{nid("clip")}"><name>{escape(Path(m["path"]).name)}</name><duration>{mdur}</duration>'
                       f'{rate_xml}<start>{st}</start><end>{st + mdur}</end><in>0</in><out>{mdur}</out>{f}'
                       f'<sourcetrack><mediatype>audio</mediatype><trackindex>{min(ch, c_ if (c_ := ai(m["path"])[1]) else 1)}</trackindex></sourcetrack></clipitem>')
        a_tracks.append(track(its))
    # camera sound, one track per camera
    for ci, cam in enumerate(cams):
        its = [item(p, 0.0, dur(p), g, lab(ci), f"{cam['name']} audio · {Path(p).stem}", audio_ch=1)
               for c, p, g in sorted(placed, key=lambda x: x[2]) if c == ci and has_sound(p)]
        if its:
            a_tracks.append(track(its))            # not muted (owner's wish)
    # extra audio sources (lavaliers, second recorder): one audio track per source folder, uncut, synced
    for ci, cam in enumerate(cams):
        if cam.get("role") != "Audio":
            continue
        its = []
        for p in cam["clips"]:
            r = results.get(p)
            if not r or r["conf"] == "fail":
                continue
            key = "a:" + p
            rate_, ch_ = ai(p)
            adur = int(np.ceil(r["dur"] * fps))
            if key in defined:
                f = f'<file id="{defined[key]}"/>'
            else:
                defined[key] = nid("file")
                f = (f'<file id="{defined[key]}"><name>{escape(Path(p).name)}</name><pathurl>{escape(core._url(p))}</pathurl>'
                     f'{rate_xml}<duration>{adur}</duration><media><audio><samplecharacteristics><depth>16</depth>'
                     f'<samplerate>{rate_}</samplerate></samplecharacteristics><channelcount>{max(1, ch_)}</channelcount></audio></media></file>')
            st = round((starts[r["master"]] + r["offset"] - T0) * fps)
            its.append(f'<clipitem id="{nid("clip")}"><name>{escape(Path(p).name)}</name><duration>{adur}</duration>{rate_xml}'
                       f'<start>{st}</start><end>{st + adur}</end><in>0</in><out>{adur}</out>'
                       f'<labels><label2>{lab(ci)}</label2></labels>{f}'
                       f'<sourcetrack><mediatype>audio</mediatype><trackindex>1</trackindex></sourcetrack></clipitem>')
        if its:
            a_tracks.append(track(its))
    end = max([g + dur(p) for _, p, g in placed] + [starts[i] + m["duration"] for i, m in enumerate(masters)])
    total = int(np.ceil((end - T0) * fps))
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}{music_markers(masters, starts, T0, fps)}'
           f'<media><video><format>{sc}</format>{"".join(v_tracks)}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>{arate}</samplerate>'
           f'</samplecharacteristics></format>{"".join(a_tracks)}</audio></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return dict(video_tracks=len(v_tracks), audio_tracks=len(a_tracks), edit=bool(edit_items))
