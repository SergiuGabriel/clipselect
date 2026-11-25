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
for i in range(4):                        # guests congratulating at the venue: faces, but not the couple -> party
    add(838.5 + i * 0.3, 6, "Iris", ("o", "o"), cam="fx3")
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

# 2. his friend's style (R&A, v4.0.0 gave 5 h of "couple" and the Osmo as drone): no getting ready, the church, the couple
# session, the venue, then the party filmed WITHOUT any break of 40 min until the night; an OSMO folder with DJI_ files
clips, faces, want = {}, {}, {}
for i, d in enumerate([300, 600, 400, 200]):          # 14:00 church
    add(840 + i * 6, d, "Brown", ("o",))
for i in range(10):                                    # 15:00 couple session
    add(900 + i * 3, 12, "Purple", ("g", "b") if i % 2 else ("b",))
for i in range(5):                                     # 15:40 venue, no faces
    add(940 + i, 6, "Yellow")
for i in range(60):                                    # 16:00 -> 22:00 party, a clip every 6 min, guests
    add(960 + i * 6, 40, "Iris", ("o", "o"), cam="fx3" if i % 2 else "fx6")
for i in range(3):                                     # Osmo filming the party: DJI_ names in an OSMO folder
    add(1000 + i * 60, 500, "Iris", ("o",), path=f"/w/OSMO/DJI_20260718{16 + i:02d}0000_000{i}_D.MP4")
lab, info = daymap.classify(clips, faces)
ok = sum(lab[k] == want[k] for k in clips)
bad = [(k, want[k], lab[k]) for k in clips if lab[k] != want[k]]
print(f"daymap (no getting ready, no breaks): {ok} of {len(clips)} right · {info}")
for b in bad:
    print("  wrong:", b)
assert not any(lab[k] == "Violet" for k in clips if "/OSMO/" in k), "an Osmo clip went to the drone"
assert sum(lab[k] == "Purple" for k in clips) <= 12, "the party became couple shots"
assert ok >= 0.9 * len(clips), "the day map without getting ready got worse"
print("daymap check 2 OK")
