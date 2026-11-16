"""Test of "who speaks" (speakers.py) and of the chunks sent to Whisper, on synthetic interviews (no Whisper needed).

1. One interviewee: a lavalier channel + a camera microphone channel (like the FX6). The interviewee is loud on the
   lavalier; the videographer is far from it (weak on the lavalier, about the same on the camera mic).
2. One channel only (a lavalier): the videographer is ~14 dB weaker.
3. Both at once: two lavaliers on two channels + the camera microphone.
Every check: each speech burst gets the right label and no chunk crosses a change of speaker.
    python tools/speakers_check.py   -> exit code 0 when everything is right
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import speakers  # noqa: E402
import transcribe  # noqa: E402

SR = 16000
rng = np.random.default_rng(7)


def voice(n, f0):
    """Speech-like sound: a buzzing tone with syllables (4-6 per second) and a little noise."""
    t = np.arange(n) / SR
    syl = 0.5 + 0.5 * np.sin(2 * np.pi * (4.5 + rng.random()) * t) ** 2
    src = sum(np.sin(2 * np.pi * f0 * k * t) / k for k in range(1, 8))
    return (src * syl + 0.05 * rng.standard_normal(n)).astype(np.float32)


def scene(turns, chans, floor=0.002):
    """turns = [(who, seconds)], a 0.6 s pause between turns; chans = {channel: {who: gain}}."""
    total = sum(d for _, d in turns) + 0.6 * (len(turns) + 1)
    out = {c: floor * rng.standard_normal(int(total * SR)).astype(np.float32) for c in chans}
    pos, truth = 0.6, []
    for who, d in turns:
        n = int(d * SR)
        v = voice(n, {"v": 110, "c": 210, "1": 130, "2": 240}[who])
        for c, g in chans.items():
            out[c][int(pos * SR):int(pos * SR) + n] += g.get(who, 0.0) * v
        truth.append((pos, pos + d, who))
        pos += d + 0.6
    return [out[c] for c in chans], truth


def check(name, chans, truth, expect):
    an = speakers.analyse(chans)
    probs = []
    for a, b, who in truth:
        got = speakers.label_of(a, b, an["regions"])
        want = expect.get(who, who)
        if got != want:
            probs.append(f"{name}: {a:.1f}-{b:.1f} s should be '{want}', got '{got}'")
    for a, b, lab, _hard in transcribe.chunks(an["regions"]):
        whos = {expect.get(w, w) for ta, tb, w in truth if min(b, tb) - max(a, ta) > 0.2}
        if len(whos) > 1:
            probs.append(f"{name}: the chunk {a:.1f}-{b:.1f} s mixes {sorted(whos)}")
    print(f"{name}: {an['method']}, voices {an['gap']} dB apart ({an['sure']}), "
          f"{len(an['regions'])} regions, {'OK' if not probs else 'WRONG'}")
    return probs


def main():
    turns = [("v", 1.8), ("c", 6.0), ("v", 1.5), ("c", 4.0), ("c", 3.0), ("v", 2.2), ("c", 7.5), ("v", 1.2), ("c", 2.5)]
    probs = []
    ch, tr = scene(turns, {"lav": {"c": 0.30, "v": 0.012}, "cam": {"c": 0.03, "v": 0.03}})
    probs += check("lavalier + camera mic", ch, tr, {})
    ch, tr = scene(turns, {"lav": {"c": 0.30, "v": 0.06}})
    probs += check("one channel", ch, tr, {})
    both = [("v", 1.8), ("1", 4.0), ("2", 3.5), ("v", 1.5), ("2", 5.0), ("1", 3.0), ("v", 2.0), ("1", 2.5), ("2", 2.5)]
    ch, tr = scene(both, {"lav1": {"1": 0.30, "2": 0.03, "v": 0.012}, "lav2": {"1": 0.03, "2": 0.30, "v": 0.012},
                          "cam": {"1": 0.03, "2": 0.03, "v": 0.03}})
    probs += check("both at once (two lavaliers)", ch, tr, {})
    for p in probs:
        print("  ✗", p)
    print("who speaks:", "OK" if not probs else f"{len(probs)} problem(s)")
    return 1 if probs else 0


if __name__ == "__main__":
    sys.exit(main())
