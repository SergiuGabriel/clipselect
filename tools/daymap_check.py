"""CI check of the automatic day map (daymap.classify) on a synthetic wedding day shaped like Alex & Andreea:
groom scene, bride scene, a church of long clips, venue without faces, couple with faces, a break, the party,
a sunset couple session inside the party, a drone clip. Two cameras, the second one only partly overlapping."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import daymap  # noqa: E402

rng = np.random.default_rng(3)
G, B = daymap._unit(rng.normal(size=128)), daymap._unit(rng.normal(size=128))
other = lambda: daymap._unit(rng.normal(size=128))
near = lambda f: daymap._unit(f + 0.15 * rng.normal(size=128) / 11)

clips, faces, want = {}, {}, {}
n = [0]


def add(t, dur, label, who=(), cam="fx6", path=None):
    n[0] += 1
    k = path or f"/w/{cam}/C{n[0]:04d}.MXF"
    clips[k] = dict(t0=t * 60.0, dur=float(dur), path=k)
    faces[k] = [near(G) if w == "g" else near(B) if w == "b" else other() for w in who]
    want[k] = label


for i in range(12):                       # 9:00 groom
    add(540 + i * 2, 8, "Blue", ("g",) if i % 2 == 0 else ())
for i in range(14):                       # 10:00 bride (after a 40 min drive)
    add(600 + i * 2.5, 6, "Rose", ("b",) if i % 2 == 0 else ("o",))
add(640, 200, "Forest", ("o",))           # the vornic speech
for i, d in enumerate([20, 600, 300, 8, 500]):  # 12:00 church
    add(720 + i * 9, d, "Brown", ("o",))
for i in range(6):                        # 13:40 venue (no faces) + couple
    add(820 + i, 5, "Yellow")
for i in range(8):
    add(830 + i, 10, "Purple", ("g", "b") if i % 2 else ("b",))
for i in range(6):                        # 15:30 party, after a 50 min break
    add(930 + i * 10, 400, "Iris", ("o", "o"))
for i in range(6):                        # 19:00 sunset couple session in the party
    add(1140 + i * 1.5, 12, "Purple", ("g", "b"))
for i in range(4):
    add(1200 + i * 15, 600, "Iris", ("o",))
add(830, 60, "Violet", path="/w/mavic/DJI_0001.MP4")
for i in range(4):                        # second camera in the church
    add(725 + i * 10, 300, "Brown", ("o",), cam="fx3")

lab, info = daymap.classify(clips, faces)
ok = sum(lab[k] == want[k] for k in clips)
bad = [(k, want[k], lab[k]) for k in clips if lab[k] != want[k]]
print(f"daymap: {ok} of {len(clips)} right · {info}")
for b in bad:
    print("  wrong:", b)
assert info["groom"] and info["bride"], "groom / bride not found"
assert ok >= 0.95 * len(clips), "the day map got worse"
print("daymap check OK")
