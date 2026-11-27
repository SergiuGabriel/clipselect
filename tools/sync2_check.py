"""CI check of Sync 2 (every file with every other) on synthetic audio: a recorder of 'music + voices', camera clips
cut out of it (other level, other EQ, room noise), two cameras that only hear each other (no recorder at that
moment), and a clip from somewhere else. No real footage needed."""
import os
import sys
import tempfile
import wave

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import sync  # noqa: E402
import sync2  # noqa: E402

SR = 16000
rng = np.random.default_rng(5)


def scene(sec, seed):
    r = np.random.default_rng(seed)
    t = np.arange(int(sec * SR)) / SR
    x = np.zeros_like(t)
    for _ in range(int(sec * 2)):                      # notes / syllables at random times and pitches
        t0, f, d = r.uniform(0, sec), r.uniform(120, 1500), r.uniform(0.08, 0.5)
        m = (t >= t0) & (t < t0 + d)
        x[m] += np.sin(2 * np.pi * f * (t[m] - t0)) * np.hanning(m.sum()) * r.uniform(0.2, 1)
    return x + 0.02 * r.normal(size=len(t))


def save(path, x):
    x = np.clip(x / (np.abs(x).max() + 1e-9) * 0.8, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def camera(x):                                         # another mic: filtered, quieter, room noise
    y = np.convolve(x, np.ones(6) / 6, mode="same") * 0.5
    return y + 0.05 * rng.normal(size=len(y))


d = tempfile.mkdtemp()
rec = scene(600, 1)
save(f"{d}/rec.wav", rec)
truth = {}
for k, (a, ln) in enumerate([(30, 40), (100, 25), (250, 60), (400, 12), (520, 50)]):
    save(f"{d}/cam_C{k:04d}.wav", camera(rec[int(a * SR):int((a + ln) * SR)]))
    truth[f"cam_C{k:04d}.wav"] = a
other = scene(80, 9)                                   # first look: heard by two cameras only
save(f"{d}/cam_C0100.wav", camera(other[: 50 * SR]))
save(f"{d}/gim_D0001.wav", camera(other[20 * SR: 70 * SR]))
save(f"{d}/cam_C0200.wav", camera(scene(30, 77)))       # a clip from somewhere else
clips = sorted(f"{d}/{f}" for f in os.listdir(d) if f != "rec.wav")
groups = {c: os.path.basename(c).split("_")[0] for c in clips}
info, res = sync2.run_sync([f"{d}/rec.wav"], clips, groups=groups)
ok = 0
for f, a in truth.items():
    r = res[f"{d}/{f}"]
    err = abs(r["offset"] - a)
    print(f, r["conf"], round(r["offset"], 4), "error ms", round(err * 1000, 2))
    assert r["conf"] in ("high", "medium") and err < 0.005, (f, r)
    ok += 1
assert res[f"{d}/cam_C0200.wav"]["conf"] in ("fail", "low"), res[f"{d}/cam_C0200.wav"]
isl = (res[f"{d}/cam_C0100.wav"]["error"], res[f"{d}/gim_D0001.wav"]["error"])
assert all("other clips" in e for e in isl), isl          # matched each other, not the recorder
print(sync2.run_sync.report)
sync.ENGINE = "graph"
i2, r2 = sync.run_sync([f"{d}/rec.wav"], clips[:2], groups=groups)
assert all(x["conf"] != "fail" for x in r2.values())
print("sync2 check OK")
