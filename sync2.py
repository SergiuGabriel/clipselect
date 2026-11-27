"""Sync 2 (v4.4.0): every recording against every other one, like Align / PluralEyes / Syncaila.

The classic sync (sync.run_sync) looks for every clip inside the recorder only. Here:
1. every file gets an audio FINGERPRINT (spectral peaks paired into hashes, 4 kHz, 64 ms frames);
2. the hashes of ALL files are matched at once: every pair of files that heard the same sound votes for one time
   offset (camera with recorder, camera with camera, lavalier with camera...);
3. each candidate pair is REFINED on the waveform (GCC-PHAT on up to 3 windows of 10 s, sample accurate) and kept
   only when the windows agree;
4. the pairs form a GRAPH; each connected group is solved at once (weighted least squares, the worst pair dropped
   while it disagrees with the others by more than 40 ms);
5. Syncaila's order rule (sync.order_check: a camera films its files one after the other) removes what is left of
   false matches.
Result: the same (info, results) as sync.run_sync, so Multicam and Long Film v2 use it unchanged. Clips that only
match other cameras (the first look on two cameras, no recorder) are placed through them; the recorder files are
placed by the cameras that span them. Written from the published idea, not from Align's code (GPL).
"""
import time as _t
from concurrent.futures import ThreadPoolExecutor

import numpy as np

import sync

SR = sync.SR                 # 4000
NFFT, HOP = 512, 256         # 128 ms window, 64 ms frames
FPS = SR / HOP
LO_BIN, HI_BIN = 4, 256       # 31 Hz - 2 kHz
PER_FRAME = 5                # landmarks kept per frame
FAN = 8                      # each peak is paired with up to 8 later peaks
DT_MAX = 40                  # ... at most 40 frames (2.6 s) later
GROUP_MAX = 60               # a hash heard more than 60 times (hum, a repeated beat) says nothing
MIN_VOTES = 5                # a pair of files needs this many agreeing hashes
WIN, NWIN = 10.0, 3          # refinement windows
AGREE = 0.004                # windows agree within 4 ms
MAX_RES = 0.04               # a pair disagreeing with its group by more than 40 ms is dropped


# ------------------------------------------------------------------------------------------------- fingerprints
def _maxfilt(L, nt, nf):
    """Separable max filter (nt frames x nf bins, edges repeated); numpy only (scipy is not in every build)."""
    def one(a, n, axis):
        r = n // 2
        pad = [(0, 0)] * a.ndim
        pad[axis] = (r, r)
        p = np.pad(a, pad, mode="edge")
        out = a.copy()
        for k in range(n):
            sl = [slice(None)] * a.ndim
            sl[axis] = slice(k, k + a.shape[axis])
            np.maximum(out, p[tuple(sl)], out=out)
        return out
    return one(one(L, nt, 0), nf, 1)


def peaks(x):
    """[(frame, bin)] of the spectral landmarks: local maxima of the WHITENED log spectrum (every bin minus its own
    usual level, so a camera mic and a mixer feed of the same sound give the same peaks) over +-3 frames and +-4 bins,
    the strongest PER_FRAME of each frame, 31 Hz - 2 kHz."""
    n = max(0, (len(x) - NFFT) // HOP + 1)
    if n < 8:
        return np.zeros(0, np.int32), np.zeros(0, np.int32)
    win = np.hanning(NFFT).astype(np.float32)
    fr, bn = [], []
    for c0 in range(0, n, 20000):
        c1 = min(n, c0 + 20000)
        idx = np.arange(c0, c1)[:, None] * HOP + np.arange(NFFT)[None, :]
        S = np.abs(np.fft.rfft(x[idx] * win, axis=1))[:, LO_BIN:HI_BIN].astype(np.float32)
        L = np.log(S + 1e-6)
        L -= np.median(L, axis=0, keepdims=True)              # whitening: each bin against its usual level
        mx = _maxfilt(L, 7, 9)
        cand = (L >= mx) & (L > 1.0)
        if not cand.any():
            continue
        t, f = np.nonzero(cand)
        v = L[t, f]
        o = np.lexsort((-v, t))                               # per frame, strongest first
        t, f = t[o], f[o]
        first = np.r_[0, np.nonzero(np.diff(t))[0] + 1]
        rank = np.arange(len(t)) - np.repeat(first, np.diff(np.r_[first, len(t)]))
        keep = rank < PER_FRAME
        fr.append(t[keep] + c0)
        bn.append(f[keep] + LO_BIN)
    if not fr:
        return np.zeros(0, np.int32), np.zeros(0, np.int32)
    f = np.concatenate(fr).astype(np.int32)
    b = np.concatenate(bn).astype(np.int32)
    o = np.lexsort((b, f))
    return f[o], b[o]


def hashes(f, b):
    """Peak pairs -> (hash, frame of the first peak)."""
    H, T = [], []
    n = len(f)
    for k in range(1, FAN + 1):
        if n <= k:
            break
        dt = f[k:] - f[:-k]
        ok = (dt > 0) & (dt <= DT_MAX)
        h = (b[:-k][ok].astype(np.int64) << 15) | (b[k:][ok].astype(np.int64) << 6) | dt[ok].astype(np.int64)
        H.append(h)
        T.append(f[:-k][ok])
    if not H:
        return np.zeros(0, np.int64), np.zeros(0, np.int32)
    return np.concatenate(H), np.concatenate(T).astype(np.int32)


# ------------------------------------------------------------------------------------------------- matching
def candidates(prints):
    """prints: [(hash, frame)] per file -> {(i, j): [(dt frames, votes), ...]} best offsets, j's time = i's + dt."""
    H = np.concatenate([p[0] for p in prints])
    T = np.concatenate([p[1] for p in prints])
    F = np.concatenate([np.full(len(p[0]), i, np.int32) for i, p in enumerate(prints)])
    o = np.argsort(H, kind="stable")
    H, T, F = H[o], T[o], F[o]
    if not len(H):
        return {}
    cut = np.nonzero(np.diff(H))[0] + 1
    starts = np.concatenate([[0], cut])
    sizes = np.diff(np.concatenate([starts, [len(H)]]))
    keys = []
    for g in range(2, GROUP_MAX + 1):          # all pairs inside every hash group of size g (vectorised per size)
        sel = starts[sizes == g]
        if not len(sel):
            continue
        ia, ib = np.triu_indices(g, 1)
        a = (sel[:, None] + ia[None, :]).ravel()
        bb = (sel[:, None] + ib[None, :]).ravel()
        fa, fb = F[a], F[bb]
        ok = fa != fb
        a, bb, fa, fb = a[ok], bb[ok], fa[ok], fb[ok]
        sw = fa > fb                            # always (low file, high file)
        lo = np.where(sw, fb, fa).astype(np.int64)
        hi = np.where(sw, fa, fb).astype(np.int64)
        dt = np.where(sw, T[a] - T[bb], T[bb] - T[a]).astype(np.int64)
        keys.append((lo << 44) | (hi << 24) | (dt + (1 << 23)))
    if not keys:
        return {}
    k, c = np.unique(np.concatenate(keys), return_counts=True)
    lo = (k >> 44).astype(int)
    hi = ((k >> 24) & 0xFFFFF).astype(int)
    dt = (k & 0xFFFFFF).astype(int) - (1 << 23)
    out = {}
    pair = lo * 100000 + hi
    order = np.lexsort((-c, pair))
    for i in order:
        key = (lo[i], hi[i])
        lst = out.setdefault(key, [])
        if len(lst) < 4:
            lst.append((int(dt[i]), int(c[i])))
    res = {}
    for key, lst in out.items():
        # neighbouring frames are the same offset (an offset falls between two frames)
        best = lst[0]
        votes = best[1] + sum(v for d, v in lst[1:] if abs(d - best[0]) == 1)
        other = max([v for d, v in lst[1:] if abs(d - best[0]) > 1] or [0])
        if votes >= MIN_VOTES and votes >= 2 * other:
            res[key] = (best[0], votes, other)
    return res


def _gcc(a, b):
    """Lag (samples) of b relative to a by GCC-PHAT, with a peak sharpness."""
    n = 1 << int(np.ceil(np.log2(len(a) + len(b))))
    A = np.fft.rfft(a, n)
    B = np.fft.rfft(b, n)
    R = np.conj(A) * B
    R /= np.abs(R) + 1e-9
    r = np.fft.irfft(R, n)
    k = int(np.argmax(r))
    v = float(r[k])
    sharp = v / (float(np.std(r)) + 1e-12)
    lag = k if k < n // 2 else k - n
    if 0 < k < n - 1:                          # sub-sample (parabola)
        y0, y1, y2 = r[k - 1], r[k], r[k + 1]
        den = y0 - 2 * y1 + y2
        if abs(den) > 1e-12:
            lag += 0.5 * (y0 - y2) / den
    return lag, sharp


def refine(xa, xb, off):
    """Exact offset of b relative to a (b time = a time + off). None when the windows do not agree."""
    lo, hi = max(0.0, -off), min(len(xa) / SR, len(xb) / SR - off)     # overlap in a's time
    if hi - lo < 3.0:
        return None
    w = min(WIN, hi - lo)
    pad = 0.4
    # the loudest windows of the overlap (speech / music, not silence)
    step = w
    cand = []
    t = lo
    while t + w <= hi + 1e-6:
        s = xa[int(t * SR):int((t + w) * SR)]
        cand.append((float(np.sqrt(np.mean(s * s))) if len(s) else 0.0, t))
        t += step
    cand.sort(reverse=True)
    picks = sorted(t for _e, t in cand[:NWIN])
    found = []
    for t in picks:
        a = xa[int(t * SR):int((t + w) * SR)]
        b0 = t + off - pad
        b = xb[max(0, int(b0 * SR)):int((t + off + w + pad) * SR)]
        if len(a) < SR or len(b) < len(a):
            continue
        lag, sharp = _gcc(a, b)
        found.append((t, (max(0, int(b0 * SR)) + lag) / SR - t, sharp))
    if not found:
        return None
    offs = np.array([o for _t0, o, _s in found])
    med = float(np.median(offs))
    agree = [x for x in found if abs(x[1] - med) <= AGREE]
    if len(agree) < min(2, len(found)) or abs(med - off) > pad + 0.1:
        return None
    sharp = float(np.median([s for _t0, _o, s in agree]))
    drift = 0.0
    if len(agree) >= 2 and agree[-1][0] - agree[0][0] > 60:
        drift = (agree[-1][1] - agree[0][1]) / (agree[-1][0] - agree[0][0]) * 1e6
    return dict(offset=float(np.mean([o for _t0, o, _s in agree])), n=len(agree), k=len(found), sharp=sharp,
                drift=drift)


# ------------------------------------------------------------------------------------------------- the graph
def solve(n, edges, roots=()):
    """edges: [(i, j, offset, weight)] with pos[j] - pos[i] = offset. Returns ({node: (component, position)}, used
    edges). Components are solved by weighted least squares; while the worst edge disagrees by > MAX_RES it goes."""
    edges = list(edges)
    while True:
        adj = {}
        for e in edges:
            adj.setdefault(e[0], []).append(e)
            adj.setdefault(e[1], []).append(e)
        comp, cid = {}, 0
        for s in list(roots) + list(range(n)):
            if s in comp or s not in adj:
                continue
            stack = [s]
            comp[s] = cid
            while stack:
                u = stack.pop()
                for e in adj[u]:
                    v = e[1] if e[0] == u else e[0]
                    if v not in comp:
                        comp[v] = cid
                        stack.append(v)
            cid += 1
        pos = {}
        worst, wres = None, 0.0
        for c in range(cid):
            nodes = [u for u in comp if comp[u] == c]
            idx = {u: k for k, u in enumerate(nodes)}
            es = [e for e in edges if comp[e[0]] == c]
            root = next((r for r in roots if r in idx), nodes[0])
            A = np.zeros((len(es) + 1, len(nodes)))
            y = np.zeros(len(es) + 1)
            w = np.ones(len(es) + 1)
            for k, (i, j, o, wt) in enumerate(es):
                A[k, idx[j]], A[k, idx[i]], y[k], w[k] = 1.0, -1.0, o, wt
            A[-1, idx[root]], w[-1] = 1.0, 1e6
            sw = np.sqrt(w)[:, None]
            p = np.linalg.lstsq(A * sw, y * sw[:, 0], rcond=None)[0]
            for u in nodes:
                pos[u] = (c, float(p[idx[u]] - p[idx[root]]))
            for (i, j, o, wt) in es:
                r = abs(pos[j][1] - pos[i][1] - o)
                if r > wres:
                    worst, wres = (i, j, o, wt), r
        if worst is None or wres <= MAX_RES:
            return pos, edges
        edges.remove(worst)


# ------------------------------------------------------------------------------------------------- run
def run_sync(masters, clips, progress=None, cancel=None, clocks=None, groups=None, jobs=2):
    """Same contract as sync.run_sync: (info, results)."""
    T0 = _t.time()
    clocks, groups = clocks or {}, groups or {}
    files = list(masters) + [c for c in clips if c not in masters]
    nm = len(masters)

    def chk():
        if cancel and cancel():
            raise InterruptedError("Cancelled")

    def prog(s, f):
        if progress:
            progress(s, f)

    xs, errs, prints = [None] * len(files), {}, [None] * len(files)

    def work(i):
        try:
            x = sync.audio_pcm(files[i])
        except Exception as e:
            return i, None, str(e), (np.zeros(0, np.int64), np.zeros(0, np.int32))
        return i, x, None, hashes(*peaks(x))
    done = [0]
    with ThreadPoolExecutor(max(1, jobs)) as ex:
        for i, x, err, hp in ex.map(work, range(len(files))):
            chk()
            xs[i], prints[i] = x, hp
            if err:
                errs[i] = err
            done[0] += 1
            prog(f"Step 1 · listening to every file: {done[0]} of {len(files)}", 0.6 * done[0] / len(files))
    t_read = _t.time() - T0
    prog("Step 2 · matching every file with every other", 0.62)
    cands = candidates(prints)
    chk()
    edges, meta = [], {}
    items = sorted(cands.items(), key=lambda kv: -kv[1][1])
    for k, ((i, j), (dt, votes, other)) in enumerate(items):
        chk()
        prog(f"Step 3 · checking the matches on the waveform: {k + 1} of {len(items)}", 0.62 + 0.33 * k / max(1, len(items)))
        if xs[i] is None or xs[j] is None:
            continue
        r = refine(xs[i], xs[j], dt / FPS)       # a sound at time t in i is at t + offset in j
        if r is None:
            continue
        w = r["n"] * min(10.0, r["sharp"]) * np.log1p(votes)
        edges.append((i, j, -r["offset"], w))     # timeline: pos[j] = pos[i] - offset
        meta[(i, j)] = dict(r, votes=votes)
    pos, used = solve(len(files), edges, roots=list(range(nm)))
    prog("Step 4 · placing the groups", 0.97)
    # the recorder files: placed by the graph when they are in one group, else by their clocks (like before)
    info = []
    for mi, m in enumerate(masters):
        x = xs[mi]
        info.append(dict(path=m, duration=(len(x) / SR) if x is not None else 0.0,
                         onsets=sync.onsets(x) if x is not None else [], clock=clocks.get(m)))
    base = sync.master_starts([dict(m) for m in info])
    mcomp = {mi: pos[mi][0] for mi in range(nm) if mi in pos}
    start = list(base)
    for c in set(mcomp.values()):
        ms = sorted(mi for mi, cc in mcomp.items() if cc == c)
        anchor = ms[0]
        for mi in ms[1:]:
            start[mi] = start[anchor] + (pos[mi][1] - pos[anchor][1])
    for mi, m in enumerate(info):
        m["start"] = start[mi]
    used_by = {}
    for (i, j, o, w) in used:
        used_by.setdefault(i, []).append((j, w))
        used_by.setdefault(j, []).append((i, w))
    results = {}
    for fi in range(nm, len(files)):
        f = files[fi]
        x = xs[fi]
        dur = len(x) / SR if x is not None else 0.0
        base_r = dict(conf="fail", z=0.0, n=0, k=0, offset=0.0, drift_ppm=0.0, master=0, dur=dur, manual=False)
        if x is None:
            results[f] = dict(base_r, error=errs.get(fi, "no sound"))
            continue
        if fi not in pos:
            results[f] = dict(base_r, error="no usable sound")
            continue
        c, p = pos[fi]
        ms = [mi for mi, cc in mcomp.items() if cc == c]
        if not ms:
            results[f] = dict(base_r, error="matched other clips but not the recorder")
            continue
        # the recorder file under the clip (else the nearest one)
        gpos = {mi: start[mi] + (p - pos[mi][1]) for mi in ms}    # clip start on the common timeline
        tl = start[ms[0]] + (p - pos[ms[0]][1])
        best = min(ms, key=lambda mi: 0 if start[mi] <= tl < start[mi] + info[mi]["duration"] else
                   min(abs(tl - start[mi]), abs(tl - start[mi] - info[mi]["duration"])))
        nb = used_by.get(fi, [])
        ms_direct = [m for m in meta if fi in m and (m[0] < nm or m[1] < nm)]
        sharp = max([meta[m]["sharp"] for m in meta if fi in m] or [0.0])
        nwin = max([meta[m]["n"] for m in meta if fi in m] or [0])
        conf = "high" if (nb and nwin >= 2 and sharp >= 6) else ("medium" if nb else "low")
        drift = next((meta[m]["drift"] for m in ms_direct), 0.0)
        results[f] = dict(base_r, conf=conf, z=sharp, n=nwin, k=len(nb), offset=gpos[best] - start[best] + 0.0,
                          master=best, drift_ppm=drift)
    for mi, m in enumerate(masters):          # a clip used as the reference (no recorder) is placed by itself
        if m in clips:
            results[m] = dict(conf="high", z=99.0, n=1, k=1, offset=0.0, drift_ppm=0.0, master=mi,
                              dur=info[mi]["duration"], manual=False)
    run_sync.suspect = sync.order_check(results, info, groups)
    fm = lambda v: f"{int(v // 60)}m {int(v % 60):02d}s" if v >= 60 else f"{v:.0f}s"
    run_sync.report = (f"Sync took {fm(_t.time() - T0)}: reading the files {fm(t_read)}, matching every file with "
                       f"every other {fm(_t.time() - T0 - t_read)} ({len(used)} matches)")
    prog(f"Step 1 · sync finished ({len(used)} matches between files)", 1.0)
    return info, results
