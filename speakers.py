"""Who speaks when, MEASURED from the sound (v3.10.0). Nothing about a wedding is written here.

1. The speech regions: Silero VAD (shipped with faster-whisper, onnxruntime, no torch); when it is missing, the app's
   own energy detection. A region ends at every real pause of at least 0.15 s.
2. The videographer is far from the lavalier: his voice is weaker on it.
   - A file with a lavalier AND a camera microphone (FX6: different channels): per region, how much louder the
     lavalier is than the camera mic (measured on his real interview: the bride +10..+19 dB, the videographer +1..+4 dB).
   - One channel only: per region, its level (groom's lavalier: him -28..-41 dB, the videographer -44..-55 dB).
   The regions fall into two groups (two-means on the measure); the quieter group is the videographer, but only when the
   two groups are far apart (6 dB with a camera mic, 8 dB with one channel). Near the middle, or a region too short to
   measure, the speaker is UNSURE ('?') and the old text rule decides ('?' at the end, his short lines).
3. Two lavaliers (the interview with both at once, each with a lavalier on its own channel): per region, which lavalier
   is clearly louder ('1' / '2'); the camera mic still finds the videographer.
Labels: 'c' the couple / the interviewee, '1' / '2' one of two interviewees, 'v' the videographer, '?' unsure.
"""
import numpy as np

SR = 16000
MIN_REGION = 0.30          # shorter regions cannot be measured well: unsure
GAP_REF, GAP_ONE = 6.0, 8.0


def _db_frames(x):
    n = SR // 100
    k = len(x) // n
    if k == 0:
        return np.zeros(0)
    return 10 * np.log10((x[:k * n].astype("float64").reshape(k, n) ** 2).mean(axis=1) + 1e-12)


def _energy_regions(x):
    """The app's own detection: loud stretches (threshold relative to the recording), joined over gaps < 0.15 s."""
    import transcribe
    d = _db_frames(x)
    if not len(d):
        return []
    thr = transcribe._thr(d)
    loud = np.convolve(d > thr, np.ones(3), "same") > 0
    out, k = [], 0
    while k < len(loud):
        if loud[k]:
            j = k
            while j < len(loud) and (loud[j] or loud[j:j + 15].any()):
                j += 1
            out.append((k / 100, j / 100))
            k = j
        else:
            k += 1
    return out


def vad(x):
    """Speech regions [(start s, end s)]: Silero VAD, a new region after every pause >= 0.15 s. When Silero is
    missing, or finds far less speech than there is sound (a strange recording), the energy detection is used."""
    energy = _energy_regions(x)
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps
        ts = get_speech_timestamps(np.ascontiguousarray(x, dtype=np.float32),
                                   VadOptions(min_silence_duration_ms=150, speech_pad_ms=30, threshold=0.5))
        reg = [(t["start"] / SR, t["end"] / SR) for t in ts]
        if sum(b - a for a, b in reg) >= 0.25 * sum(b - a for a, b in energy):
            return reg, "silero"
    except Exception:
        pass
    return energy, "energy"


def _distinct(chans):
    """Drop channels that are copies of another one (FX6 records the lavalier and the camera mic twice)."""
    out = []
    for c in chans:
        n = min(len(c), SR * 120)
        if any(len(o) >= n and np.allclose(o[:n], c[:n], atol=1e-4) for o in out):
            continue
        out.append(c)
    return out


def _corr(a, b):
    n = min(len(a), len(b), SR * 120)
    if n < SR:
        return 1.0
    a, b = a[:n], b[:n]
    if a.std() == 0 or b.std() == 0:
        return 1.0
    return float(abs(np.corrcoef(a, b)[0, 1]))


def _two_means(vals, weights):
    """1-D two-means: (low centre, high centre, threshold)."""
    v = np.asarray(vals, float)
    w = np.asarray(weights, float)
    lo, hi = np.percentile(v, 15), np.percentile(v, 85)
    for _ in range(30):
        thr = (lo + hi) / 2
        a, b = v <= thr, v > thr
        if not a.any() or not b.any():
            break
        nlo, nhi = np.average(v[a], weights=w[a]), np.average(v[b], weights=w[b])
        if abs(nlo - lo) < 1e-3 and abs(nhi - hi) < 1e-3:
            break
        lo, hi = nlo, nhi
    return lo, hi, (lo + hi) / 2


def analyse(chans):
    """chans = every channel of the file (16 kHz). -> dict(x = the clearest channel (what Whisper hears), regions =
    [(a, b, label)], method, gap (dB between the two voices), sure = 'sure' / 'medium' / 'unsure' / 'none')."""
    import transcribe
    chans = _distinct([c for c in chans if len(c)])
    if not chans:
        raise ValueError("No sound in this file")
    clar = [transcribe.clarity(c) for c in chans]
    order = sorted(range(len(chans)), key=lambda k: -clar[k])
    x = chans[order[0]]
    # close microphones = lavaliers (clear, and not the same sound as the best one); the rest = camera microphones
    close = [order[0]] + [k for k in order[1:] if clar[k] >= clar[order[0]] - 6 and _corr(chans[k], x) < 0.5]
    ref = next((k for k in order[1:] if k not in close and clar[k] < clar[order[0]] - 3), None)
    close = sorted(close[:2])                          # S1 = the lavalier on the lower channel, S2 = the other one
    # speech is looked for on ALL the microphones (the videographer is weak on the lavalier, clear on the camera mic)
    mics = [chans[k] for k in close] + ([chans[ref]] if ref is not None else [])
    n = min(len(m) for m in mics)
    regions, method = vad(x)
    for k in close[1:] + ([ref] if ref is not None else []):    # speech the lavalier missed (a weak voice)
        for a, b in vad(chans[k])[0]:
            parts = [(a, b)]
            for ra, rb in regions:
                parts = [q for pa, pb in parts for q in ((pa, min(pb, ra)), (max(pa, rb), pb)) if q[1] - q[0] > 0]
            regions += [q for q in parts if q[1] - q[0] >= MIN_REGION]
        regions.sort()
    P = _db_frames(x) if len(close) == 1 else np.maximum(_db_frames(chans[close[0]][:n]), _db_frames(chans[close[1]][:n]))
    R = _db_frames(chans[ref]) if ref is not None else None
    L2 = _db_frames(chans[close[1]]) if len(close) > 1 else None
    feats, keep = [], []
    for a, b in regions:
        s, e = int(a * 100), max(int(a * 100) + 1, int(b * 100))
        p = P[s:e]
        if not len(p):
            feats.append(None)
            continue
        top = p >= np.percentile(p, 50)
        if R is not None:
            m = min(e, len(R))
            f = float(np.median((p[:m - s] - R[s:m])[top[:m - s]])) if m > s else None
        else:
            f = float(np.percentile(p, 90))
        feats.append(f)
        if f is not None and b - a >= MIN_REGION:
            keep.append((f, b - a))
    labels = ["c"] * len(regions)
    gap, sure = 0.0, "none"
    need = GAP_REF if R is not None else GAP_ONE
    if len(keep) >= 4:
        lo, hi, thr = _two_means([f for f, _ in keep], [w for _, w in keep])
        gap = float(hi - lo)
        if gap >= need:
            band = max(1.5, 0.2 * gap)
            sure = "sure" if gap >= need + 4 else "medium"
            for k, (f, (a, b)) in enumerate(zip(feats, regions)):
                if f is None or b - a < MIN_REGION or abs(f - thr) < band:
                    labels[k] = "?"
                else:
                    labels[k] = "v" if f < thr else "c"
        else:
            sure = "unsure"
            labels = ["?"] * len(regions)
    else:
        labels = ["?"] * len(regions)
    if L2 is not None:                                 # two lavaliers: which one speaks
        for k, (a, b) in enumerate(regions):
            if labels[k] == "v":
                continue
            s, e = int(a * 100), int(b * 100)
            P1 = _db_frames(chans[close[0]][int(a * SR):int(b * SR)])
            P2 = _db_frames(chans[close[1]][int(a * SR):int(b * SR)])
            m = min(len(P1), len(P2))
            if m == 0:
                continue
            d = float(np.median(P1[:m] - P2[:m]))
            labels[k] = "1" if d > 6 else "2" if d < -6 else "?"
    return dict(x=x, regions=[(a, b, lab) for (a, b), lab in zip(regions, labels)], method=method,
                gap=round(gap, 1), sure=sure, ref=ref is not None, two=L2 is not None)


def label_of(a, b, regions):
    """The speaker of the stretch a-b: the label covering most of it; a stretch where the videographer and the couple
    both speak a lot (the smaller over a quarter) is unsure."""
    cover = {}
    for ra, rb, lab in regions:
        o = min(b, rb) - max(a, ra)
        if o > 0:
            cover[lab] = cover.get(lab, 0.0) + o
    if not cover:
        return "?"
    tot = sum(cover.values())
    best = max(cover, key=cover.get)
    definite = {k: v for k, v in cover.items() if k != "?"}
    if len(definite) > 1:
        second = sorted(definite.values())[-2]
        if second > 0.25 * tot:
            return "?"
    return best
