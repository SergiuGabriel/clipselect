"""Music map of a recorder file: what the auto edit needs to cut ON the music.

One pass over the whole audio (4 kHz mono, the same signal the sync uses):
  - onset strength (spectral flux) at 100 frames / s, plus loudness and bass per frame;
  - LOCAL tempo every second (8 s windows), linked by a Viterbi path: DJ tempo jumps are allowed between songs,
    a live band's slow drift is followed;
  - beats tracked one by one (predicted from the local tempo, pulled to the real hit, re-locked when the phase
    jumps, e.g. a DJ transition), each beat refined to the START of the hit in the raw audio (not its peak);
  - downbeats (beat 1 of every bar) per song, from where the kick / bass and the strongest hits fall;
  - regions: music / speech / silence. Where the beat is not clear (a ballad without drums) there is NO beat grid:
    a wrong beat is worse than none;
  - energy curve 0..1, drops (big jump in loudness on a bar line) with their length and the build-up before them;
  - pauses in speech (for cuts between sentences).
Everything is returned as plain lists (saved with the project).
"""
import numpy as np

SR = 4000
HOP = 40                    # 100 frames per second
FPS = SR / HOP
NFFT = 256
T_OFF = 0.05                # a hit shows in the flux of the frame that ENDS on it: frame time + 50 ms = the hit
LAT = 0.0                   # extra latency correction (s) after the attack refinement; measured in the tests


def _frames(x):
    """Spectral flux, loudness (dB) and bass energy per frame, computed in chunks (hours of audio)."""
    n = (len(x) - NFFT) // HOP + 1
    if n < 10:
        return np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0), np.zeros(0)
    win = np.hanning(NFFT).astype(np.float32)
    flux = np.zeros(n, np.float32)
    lowf = np.zeros(n, np.float32)
    body = np.zeros(n, np.float32)
    db = np.zeros(n, np.float32)
    bass = np.zeros(n, np.float32)
    prev = None
    step = 6000
    for s in range(0, n, step):
        e = min(n, s + step)
        idx = (np.arange(s, e) * HOP)[:, None] + np.arange(NFFT)[None, :]
        fr = x[idx].astype(np.float32)
        mag = np.abs(np.fft.rfft(fr * win, axis=1))
        lm = np.log1p(100 * mag)
        d = np.maximum(np.diff(np.vstack([lm[:1] if prev is None else prev[None], lm]), axis=0), 0)
        # the beat lives in the kick / bass / snare body: low bins count fully, the rest (hats, shakers that play
        # BETWEEN the beats) only a little, or the tracker locks on the off-beat
        flux[s:e] = d[:, 1:20].sum(1) + 0.3 * d.sum(1)
        lowf[s:e] = d[:, 1:9].sum(1)                  # < 125 Hz: kick and bass only
        body[s:e] = d[:, 1:20].sum(1)                 # < 300 Hz: kick, bass, snare body (no hats)
        prev = lm[-1]
        db[s:e] = 10 * np.log10((fr ** 2).mean(1) + 1e-10)
        bass[s:e] = mag[:, 1:10].sum(1)            # ~15-150 Hz: kick and bass
    return flux, db, bass, lowf, body


def _tempo_path(env, lo=60, hi=200):
    """Local tempo every second: autocorrelation of 8 s windows, harmonics reinforced, linked by a Viterbi path."""
    W, H = 800, 100
    lags = np.arange(int(FPS * 60 / hi), int(FPS * 60 / lo) + 1)
    nw = max(1, (len(env) - W) // H + 1)
    sal = np.zeros((nw, len(lags)), np.float32)
    conf = np.zeros(nw, np.float32)
    nf = 2048
    for k in range(0, nw, 512):
        ks = range(k, min(nw, k + 512))
        seg = np.stack([env[i * H:i * H + W] if i * H + W <= len(env) else np.pad(env[i * H:], (0, W - len(env[i * H:])))
                        for i in ks]).astype(np.float64)
        seg = seg - seg.mean(1, keepdims=True)
        F = np.fft.rfft(seg, nf, axis=1)
        ac = np.fft.irfft(F * np.conj(F), nf, axis=1)[:, :W]
        ac = ac / (ac[:, :1] + 1e-9)
        s = ac[:, lags] + 0.5 * ac[:, np.minimum(2 * lags, W - 1)]
        sal[k:k + len(ks)] = s
        conf[k:k + len(ks)] = ac[:, lags].max(1)
    bpm = FPS * 60 / lags
    prior = np.exp(-0.5 * (np.log2(bpm / 110.0) / 1.6) ** 2)          # mild: the parity check below decides octaves
    score = sal * prior[None, :]
    # Viterbi: staying near the same tempo is cheap, jumps cost (DJ changes songs), octave jumps cost more
    lg = np.log2(lags)
    trans = 6.0 * np.abs(lg[:, None] - lg[None, :])
    acc = score[0].copy()
    bp = np.zeros((nw, len(lags)), np.int32)
    for t in range(1, nw):
        m = acc[None, :] - trans
        bp[t] = np.argmax(m, axis=1)
        acc = m[np.arange(len(lags)), bp[t]] + score[t]
    path = np.zeros(nw, np.int32)
    path[-1] = int(np.argmax(acc))
    for t in range(nw - 1, 0, -1):
        path[t - 1] = bp[t, path[t]]
    period = lags[path].astype(np.float64)                # frames per beat, one value per second
    centers = (np.arange(nw) * H + W / 2) / FPS
    return centers, period, conf


def _attack(x, t, period_s):
    """Move a beat to the START of its hit: first point where the short energy reaches half of the local peak."""
    a, b = int((t - min(0.03, period_s * 0.1)) * SR), int((t + 0.05) * SR)
    if a < 0 or b > len(x) or b - a < 40:
        return t
    seg = x[a:b].astype(np.float32) ** 2
    k = 8                                                   # 2 ms energy
    e = np.convolve(seg, np.ones(k) / k, "same")
    pk = e.max()
    if pk <= 0:
        return t
    i = int(np.argmax(e >= 0.5 * pk))
    return (a + i) / SR + LAT


def analyze(x, progress=None):
    x = np.asarray(x, np.float32)
    dur = len(x) / SR
    flux, db, bass, lowf, body = _frames(x)
    if len(flux) < FPS * 10:
        return dict(beats=[], down=[], bpm=[], regions=[[0.0, round(dur, 2), "silence", 0]], drops=[], builds=[],
                    energy=dict(rate=2, v=[]), pauses=[], duration=dur)
    env = flux / (np.percentile(flux, 99) + 1e-9)
    env = np.maximum(0, env - np.convolve(env, np.ones(50) / 50, "same"))       # remove the slow part
    kick = lowf / (np.percentile(lowf, 99) + 1e-9)
    kick = np.maximum(0, kick - np.convolve(kick, np.ones(50) / 50, "same"))
    lock = env + kick                     # where the beat is anchored: the kick / bass weigh double
    if progress:
        progress(0.3)
    centers, period, conf = _tempo_path(env)
    if progress:
        progress(0.55)
    # ---- regions per second: silence / music / speech
    loud = np.array([db[int(c * FPS - 50):int(c * FPS + 50)].mean() if int(c * FPS + 50) <= len(db) else db[-100:].mean()
                     for c in centers])
    floor = np.percentile(db, 5)
    kind = np.where(loud < max(floor + 6, -70), 0, np.where(conf > 0.45, 2, 1))     # 0 silence, 1 speech/other, 2 music
    k5 = np.array([np.bincount(kind[max(0, i - 3):i + 4], minlength=3).argmax() for i in range(len(kind))])
    regions = []
    for i, k in enumerate(k5):
        t0 = 0.0 if i == 0 else (centers[i - 1] + centers[i]) / 2
        if regions and regions[-1][2] == k:
            regions[-1][1] = (centers[i] + centers[i + 1]) / 2 if i + 1 < len(centers) else dur
        else:
            regions.append([t0, (centers[i] + centers[i + 1]) / 2 if i + 1 < len(centers) else dur, int(k)])
    # music shorter than 10 s is not a song
    for r in regions:
        if r[2] == 2 and r[1] - r[0] < 10:
            r[2] = 1
    merged = []
    for r in regions:
        if merged and merged[-1][2] == r[2]:
            merged[-1][1] = r[1]
        else:
            merged.append(list(r))
    regions = merged
    per_at = lambda t: float(np.interp(t, centers, period))
    # ---- beats, region by region
    beats, bpms, sid = [], [], []
    songs = []
    for r0, r1, k in regions:
        if k != 2:
            continue
        # a new song = the tempo path STEPS (a DJ change); a band's drift moves it by tiny steps only.
        # The tracks stop 2 s before and start 2 s after the step: the 8 s windows blur the exact moment.
        idx = [i for i in range(1, len(centers)) if r0 < centers[i] < r1
               and abs(np.log(period[i] / period[i - 1])) > np.log(1.03)]
        cuts = [(r0, None)]
        for i in idx:
            if centers[i] - cuts[-1][0] > 10:
                cuts.append((float(centers[i]), True))
        edges = [c for c, _ in cuts] + [r1]
        for k in range(len(cuts)):
            u = edges[k] + (2.0 if k > 0 else 0.0)
            v = edges[k + 1] - (2.0 if k + 1 < len(cuts) else 0.0)
            if v - u > 6:
                songs.append((u, v))
    for si, (r0, r1) in enumerate(songs):
        a, b = int(r0 * FPS), int(r1 * FPS)
        P = per_at(r0 + 4)
        first = env[a:a + int(16 * P) + 1]
        if len(first) < P:
            continue
        ph = max(range(int(P)), key=lambda f: lock[a + f:min(b, a + int(16 * P)):int(round(P))].sum() if a + f < b else 0)
        t = a + ph
        last_int = P
        miss = 0
        while t < b:
            # pull to the strongest hit near the prediction
            w = int(0.15 * P) + 1
            lo, hi = max(a, int(t) - w), min(b, len(env), int(t) + w + 1)
            if hi > lo:
                seg = lock[lo:hi]
                wt = np.exp(-0.5 * ((np.arange(lo, lo + len(seg)) - t) / (0.08 * P + 1)) ** 2)
                j = int(np.argmax(seg * wt))
                if seg[j] > 0.05:
                    off = (lo + j) - t
                    t = lo + j
                    miss = miss + 1 if abs(off) > 0.1 * P else 0
            Pnow = per_at(t / FPS)
            if abs(P - Pnow) / Pnow > 0.12:                 # the tempo moved away from what we follow: start again
                P = Pnow
                miss = 4
            if miss >= 4:                                   # phase jumped (DJ transition): lock again
                c0 = int(t)
                cand = range(c0 - int(P / 2), c0 + int(P / 2))
                t = max(cand, key=lambda f: lock[max(a, f):min(b, f + int(4 * P)):int(round(P))].sum() if a <= f < b else -1)
                miss = 0
            tt = t / FPS + T_OFF
            beats.append(tt)
            bpms.append(60 * FPS / P)
            sid.append(si)
            Pl = per_at(t / FPS)
            P = 0.7 * Pl + 0.3 * last_int if abs(last_int - Pl) < 0.15 * Pl else Pl
            nt = t + P
            last_int = P
            t = nt
    if progress:
        progress(0.75)
    # octave check per song: if every other beat is much weaker, those are off-beats (hats): keep the strong half
    if beats:
        bt, bp, sd = np.array(beats), np.array(bpms), np.array(sid)
        keep = np.ones(len(bt), bool)
        for r0, r1 in songs:
            k = np.where((bt >= r0) & (bt < r1 + T_OFF + 0.1))[0]
            if len(k) < 16 or np.median(bp[k]) / 2 < 55:
                continue
            # judged on the low / mid hits only: an off-beat hat has none, a snare on 2 and 4 has its body
            st = np.array([body[max(0, int((t - T_OFF) * FPS) - 2):int((t - T_OFF) * FPS) + 3].max(initial=0) for t in bt[k]])
            e, o = st[0::2].mean(), st[1::2].mean()
            if min(e, o) < 0.5 * max(e, o):
                weak = k[1::2] if e > o else k[0::2]
                keep[weak] = False
                bp[k] = bp[k] / 2
        beats, bpms, sid = list(bt[keep]), list(bp[keep]), list(sd[keep])
    beats = np.array(beats)
    bpms = np.array(bpms)
    sid = np.array(sid, int)
    if len(beats):
        strength = np.array([env[max(0, int((b - T_OFF) * FPS) - 3):int((b - T_OFF) * FPS) + 4].max(initial=0) for b in beats])
        good = strength >= 0.15 * np.median(strength)
        # remove only weak beats that are not between strong ones (a soft beat inside the song stays)
        keep = good.copy()
        run = np.convolve(good.astype(int), np.ones(5, int), "same")
        keep |= run >= 3
        beats, bpms, sid = beats[keep], bpms[keep], sid[keep]
    if len(beats):
        beats = np.array([_attack(x, b, 60 / max(1, bp)) for b, bp in zip(beats, bpms)])
        keep = np.r_[True, np.diff(beats) > 0.18]
        beats, bpms, sid = beats[keep], bpms[keep], sid[keep]
    # one tempo per song (the tracker's per-beat value wobbles a little on real music)
    for k in set(sid.tolist()):
        m_ = sid == k
        bpms[m_] = np.median(bpms[m_])
    # ---- songs (tempo steady inside) and downbeats
    down = np.zeros(len(beats), bool)
    if len(beats):
        cut = [0] + [i for i in range(1, len(beats)) if sid[i] != sid[i - 1]
                     or beats[i] - beats[i - 1] > 2.5 * 60 / bpms[i - 1]] + [len(beats)]
        fb = lambda t: int(min(len(bass) - 1, max(0, (t - T_OFF) * FPS)))
        for s, e in zip(cut, cut[1:]):
            if e - s < 4:
                continue
            bb = np.array([bass[fb(t)] + 0.5 * bass[min(len(bass) - 1, fb(t) + 2)] for t in beats[s:e]])
            ee = np.array([env[fb(t)] for t in beats[s:e]])
            sc = bb / (bb.mean() + 1e-9) + 0.5 * ee / (ee.mean() + 1e-9)
            p = int(np.argmax([sc[q::4].mean() for q in range(4)]))
            down[s + p:e:4] = True
    # ---- energy 0..1 (2 per second): loudness + bass, smoothed 2 s, scaled on the music
    r2 = int(FPS / 2)
    n2 = len(db) // r2
    edb = db[:n2 * r2].reshape(n2, r2).mean(1)
    eb = 10 * np.log10(bass[:n2 * r2].reshape(n2, r2).mean(1) + 1e-6)
    raw = np.convolve(edb + 0.5 * eb, np.ones(4) / 4, "same")
    mus = np.zeros(n2, bool)
    for r0, r1, k in regions:
        if k == 2:
            mus[int(r0 * 2):int(r1 * 2)] = True
    ref = raw[mus] if mus.sum() > 20 else raw
    lo_, hi_ = np.percentile(ref, 10), np.percentile(ref, 95)
    energy = np.clip((raw - lo_) / max(1e-6, hi_ - lo_), 0, 1)
    # ---- drops: on a bar line the KICK / BASS come back hard after bars without them (the build-up)
    drops, builds = [], []
    if down.any():
        bars = list(beats[down])
        bdb = 10 * np.log10(bass + 1e-6)
        bar_b = []
        for i, t0 in enumerate(bars):
            t1 = bars[i + 1] if i + 1 < len(bars) and bars[i + 1] - t0 < 6 else t0 + 2
            a_, b_ = int((t0 - T_OFF) * FPS), int((t1 - T_OFF) * FPS)
            bar_b.append(float(np.percentile(bdb[a_:max(a_ + 1, b_)], 80)) if a_ < len(bdb) else -99)
        bar_b = np.array(bar_b)
        bar_l = []
        for i, t0 in enumerate(bars):
            t1 = bars[i + 1] if i + 1 < len(bars) and bars[i + 1] - t0 < 6 else t0 + 2
            a_, b_ = int((t0 - T_OFF) * FPS), int((t1 - T_OFF) * FPS)
            bar_l.append(float(db[a_:max(a_ + 1, b_)].mean()) if a_ < len(db) else -99)
        bar_l = np.array(bar_l)

        def same_song(i, k):          # bars evenly spaced around i (no gap, no other song inside)
            lo, hi = max(0, i - k), min(len(bars) - 1, i + k)
            sp = np.diff(bars[lo:hi + 1])
            return len(sp) > 0 and sp.max() < 1.15 * np.median(sp) and sp.min() > 0.85 * np.median(sp)
        last = -99
        hi_ = np.percentile(bar_b, 60) if len(bar_b) else 0
        for i in range(2, len(bars) - 2):
            if i - last < 16 or not same_song(i, 2):
                continue
            jb = bar_b[i] - bar_b[i - 2:i].mean()            # kick / bass come back
            jn = bar_b[i + 1] - bar_b[i - 2:i].mean()         # ... and stay
            # loudness is no proof (risers are loudest right before the drop); the kick / bass coming back is:
            # a clear jump that stays, after bars with less bass than usual (or a very big jump)
            # a clear rise that LASTS 4 bars and is the biggest rise around (not a small variation)
            lasting = bar_b[i:i + 4].mean() - bar_b[i - 2:i].mean()
            rises = [bar_b[j] - bar_b[max(0, j - 2):j].mean() for j in range(max(2, i - 4), min(len(bars) - 1, i + 5))]
            if jb >= 3.0 and jn >= 2.5 and lasting >= 3.0 and bar_b[i] >= hi_ and jb >= max(rises) - 1e-6:
                end = i + 8
                while end < min(len(bars), i + 32) and bar_b[end] > bar_b[i] - 4 and same_song(end, 1):
                    end += 1
                drops.append([round(bars[i], 4), round(bars[min(end, len(bars) - 1)], 4)])
                nb = 0
                while nb < 8 and i - nb - 1 >= 0 and bar_b[i - nb - 1] < bar_b[i] - 2.5 and same_song(i - nb - 1, 1):
                    nb += 1
                if nb >= 2:
                    builds.append([round(bars[i - nb], 4), round(bars[i], 4)])
                last = i
    # ---- pauses in speech (cut points between sentences)
    pauses = []
    for r0, r1, k in regions:
        if k != 1:
            continue
        a, b = int(r0 * FPS), int(r1 * FPS)
        seg = db[a:b]
        if len(seg) < 50:
            continue
        thr = np.median(seg) - 10
        low = seg < thr
        i = 0
        while i < len(low):
            if low[i]:
                j = i
                while j < len(low) and low[j]:
                    j += 1
                if j - i >= 25:
                    pauses.append(round((a + (i + j) / 2) / FPS, 3))
                i = j
            else:
                i += 1
    names = {0: "silence", 1: "speech", 2: "music"}
    reg_out = []
    for r0, r1, k in regions:
        bp = float(np.median(bpms[(beats >= r0) & (beats < r1)])) if k == 2 and len(beats) and ((beats >= r0) & (beats < r1)).any() else 0
        reg_out.append([round(r0, 3), round(r1, 3), names[k], round(bp, 1)])
    if progress:
        progress(1.0)
    return dict(beats=np.round(beats, 4).tolist(), down=[int(i) for i in np.where(down)[0]], bpm=np.round(bpms, 1).tolist(),
                song=[int(i) for i in sid],
                regions=reg_out, drops=drops, builds=builds, energy=dict(rate=2, v=np.round(energy, 3).tolist()),
                pauses=pauses, duration=round(dur, 3))
