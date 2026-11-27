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
add(640, 200, "Forest", ("o",))           # the vornic speech, filmed by both cameras (measured on his Alex & Andreea)
add(641, 180, "Forest", ("o",), cam="fx3")
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

# 1b. the same day with the sound measured and the AI's judgement where it agrees with his labels: nothing may change
SC = {"Blue": "ready", "Rose": "ready", "Teal": "ready", "Forest": "speech", "Brown": "church", "Yellow": "venue",
      "Purple": "couple", "Iris": "party", "Violet": "drone"}


def judge(lbl, strong=0.7):
    d = {c: (1 - strong) / 6 for c in ("ready", "church", "couple", "venue", "party", "drone", "speech")}
    d[SC[lbl]] = strong
    return d


for i in range(4):                        # guests congratulating at the venue: faces, not the couple, the AI sees a party
    add(838.5 + i * 0.3, 6, "Iris", ("o", "o"), cam="fx3")
AI = {k: judge(want[k]) for k in clips}
SP = {k: (0.9 if want[k] in ("Forest", "Rose") else 0.2) for k in clips}     # the bride's room talks too
lab2, info2 = daymap.classify(clips, faces, AI, SP)
ok2 = sum(lab2[k] == want[k] for k in clips)
print(f"daymap with AI + sound: {ok2} of {len(clips)} right · church by {info2['church_by']}")
assert ok2 == len(clips), "the AI made his own day worse"

# 2. the friend with HIS style (v4.0.0 left the church out): the church filmed in SHORT clips (no long clip at all)
clips, faces, want = {}, {}, {}
for i in range(12):
    add(540 + i * 2, 8, "Blue", ("g",) if i % 2 == 0 else ())
for i in range(14):
    add(600 + i * 2.5, 6, "Rose", ("b",) if i % 2 == 0 else ("o",))
for i in range(30):                                    # church: 30 short clips of 20-40 s on two cameras
    add(720 + i * 1.5, 20 + (i % 3) * 10, "Brown", ("o",), cam="fx6" if i % 2 else "fx3")
for i in range(6):
    add(820 + i, 5, "Yellow")
for i in range(8):
    add(830 + i, 10, "Purple", ("g", "b") if i % 2 else ("b",))
for i in range(6):
    add(930 + i * 10, 120, "Iris", ("o", "o"))
AI = {k: judge(want[k], 0.55) for k in clips}
lab, info = daymap.classify(clips, faces, AI)
ok = sum(lab[k] == want[k] for k in clips)
print(f"daymap, church in short clips, with AI: {ok} of {len(clips)} right · {info}")
assert info["church_by"] == "ai" and sum(lab[k] == "Brown" for k in clips) >= 28, "the church in short clips was not found"
assert ok >= 0.9 * len(clips)

# 3. the friend with ANOTHER style (R&A, v4.0.0: getting ready taken for the church, 5 h of couple, the OSMO as the drone):
# getting ready with two long clips (4 and 7 min, no speech), the church, the couple session, then the party filmed
# WITHOUT any 40-min break until the night, an OSMO folder with DJI_ files; the vornic = 3 short clips of speech
clips, faces, want = {}, {}, {}
for i in range(10):
    add(540 + i * 2, 10, "Blue", ("g",) if i % 2 == 0 else ())
add(562, 255, "Blue", ("g",))
for i in range(10):
    add(600 + i * 2.5, 8, "Rose", ("b",) if i % 2 == 0 else ("o",))
add(628, 431, "Rose", ("b",))
add(640, 150, "Forest", ("o",))                        # the vornic in the yard: one take of 2.5 min on fx6 ...
for i in range(3):                                     # ... and 3 short clips of it on fx3
    add(640.2 + i * 0.7, 30, "Forest", ("o",), cam="fx3")
for i, d in enumerate([200, 400, 300, 250]):           # 14:00 church
    add(840 + i * 6, d, "Brown", ("o",))
for i in range(10):                                    # 15:00 couple session
    add(900 + i * 3, 12, "Purple", ("g", "b") if i % 2 else ("b",))
for i in range(5):                                     # 15:40 venue, no faces
    add(940 + i, 6, "Yellow")
for i in range(60):                                    # 16:00 -> 22:00 party, a clip every 6 min, guests
    add(960 + i * 6, 40, "Iris", ("o", "o"), cam="fx3" if i % 2 else "fx6")
for i in range(3):                                     # the Osmo at the party: DJI_ names in an OSMO folder
    add(1000 + i * 60, 500, "Iris", ("o",), path=f"/w/OSMO/DJI_20260718{16 + i:02d}0000_000{i}_D.MP4")
add(950, 60, "Violet", path="/w/DJI_20260718155000_0001_D.MP4")    # a real drone clip, DJI_ name, no drone folder
AI = {k: judge(want[k], 0.55) for k in clips}
SP = {k: (0.85 if want[k] == "Forest" or clips[k]["dur"] > 200 else 0.1) for k in clips}  # long takes talk too
lab, info = daymap.classify(clips, faces, AI, SP)
ok = sum(lab[k] == want[k] for k in clips)
bad = [(k, want[k], lab[k]) for k in clips if lab[k] != want[k]]
print(f"daymap, R&A style, with AI + sound: {ok} of {len(clips)} right · {info}")
for b in bad:
    print("  wrong:", b)
assert not any(lab[k] == "Violet" for k in clips if "/OSMO/" in k), "an Osmo clip went to the drone"
assert lab["/w/DJI_20260718155000_0001_D.MP4"] == "Violet", "the drone seen from above was missed"
assert sum(lab[k] == "Brown" for k in clips) == 4, "the church is wrong"
assert sum(lab[k] == "Forest" for k in clips) == 4, "the vornic (a take + 3 short clips) was not found"
assert sum(lab[k] == "Purple" for k in clips) <= 12, "the party became couple shots"
assert ok >= 0.9 * len(clips)
print("daymap check 2 OK")

# 3. a whole day at one villa (his 28 August): the venue and its decorators filmed FIRST, then the groom, the bride,
#    the first look, a church with a 27-min take the AI does not see as church, couple + venue, party. The AI's WHO
#    judgement (dress / suit) tells the groom from the bride; the old "first scene = groom" made the groom pink.
clips, faces, want = {}, {}, {}
n = [0]


def W(b=0.0, g=0.0, both=0.0):
    return {"bride": b, "groom": g, "both": both, "none": max(0.0, 1 - b - g - both)}


AI = {}
D = rng.normal(size=128)                                  # the decorator: a face in the first scene


def add3(t, dur, label, who, sc, w, cam="fx6"):
    add(t, dur, label, (), cam)
    k = list(clips)[-1]
    faces[k] = [near(G) if x == "g" else near(B) if x == "b" else daymap._unit(D + 0.02 * rng.normal(size=128))
                if x == "d" else other() for x in who]
    AI[k] = dict(judge({"ready": "Blue", "venue": "Yellow", "church": "Brown", "couple": "Purple", "party": "Iris",
                        "speech": "Forest"}[sc], 0.6), _who=w)


for i in range(10):                                       # 11:50 the villa, the tables, the decorator
    add3(710 + i * 2, 6, "Yellow", ("d",) if i in (4, 5, 6) else (), "venue", W())
for i in range(14):                                       # 12:50 the groom dressing (his face in half of them)
    add3(770 + i * 2.5, 8, "Blue", ("g",) if i % 2 == 0 else (), "ready", W(g=0.6) if i % 3 else W())
for i in range(14):                                       # 13:30 the bride
    add3(810 + i * 3, 10, "Rose", ("b",) if i % 2 == 0 else (), "ready", W(b=0.7) if i % 3 else W())
for i in range(8):                                        # 14:30 first look: together, then her alone, him alone
    add3(870 + i * 2, 12, "Teal", ("g", "b") if i < 3 else (("b",) if i % 2 else ("g",)), "couple",
         W(both=0.8) if i < 3 else (W(b=0.6) if i % 2 else W(g=0.6)))
add3(980, 1600, "Brown", ("o",), "party", W())               # the 27-min take, AI unsure
for i in range(6):
    add3(970 + i * 2, 6, "Brown", (), "church", W())
for i in range(6):
    add3(1008 + i * 4, 40, "Brown", ("o",), "church", W())
for i in range(6):                                        # 18:05 the tables at sunset
    add3(1085 + i, 6, "Yellow", (), "venue", W())
for i in range(10):                                       # 18:30 couple session
    add3(1110 + i * 4, 10, "Purple", ("g", "b") if i % 2 else (), "couple", W(both=0.8))
for i in range(12):                                       # 19:30 party
    add3(1170 + i * 8, 60, "Iris", ("o", "o", "o"), "party", W())
lab, info = daymap.classify(clips, faces, AI)
ok = sum(lab[k] == want[k] for k in clips)
bad = [(k, want[k], lab[k]) for k in clips if lab[k] != want[k]]
print(f"daymap, whole day at one villa, venue first: {ok} of {len(clips)} right · {info}")
for b in bad:
    print("  wrong:", b)
assert all(lab[k] != "Rose" for k in clips if want[k] == "Blue"), "a groom clip became the bride"
assert all(lab[k] != "Blue" for k in clips if want[k] == "Rose"), "a bride clip became the groom"
assert sum(lab[k] == "Brown" for k in clips) == 13, "the church was split by the long take"
assert ok >= 0.9 * len(clips)
print("daymap check 3 OK")
