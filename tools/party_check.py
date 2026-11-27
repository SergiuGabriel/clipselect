"""Long Film v2 party sync rules (no audio needed): one file per recorder take, and a camera's clips in the order of
their numbers without overlaps (his friend's Denisa & Cornel: Tascam X8 _3-4 + _MIX copies laid one after the other,
A7iv8619 / 8620 synced after 8622)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import longfilm2 as L  # noqa: E402
import sync  # noqa: E402

fs = ["/w/Tascam/260711_0190_3-4.wav", "/w/Tascam/260711_0190_MIX.wav", "/w/Tascam/260711_0191_3-4.wav",
      "/w/Tascam/260711_0191_MIX.wav"]
inf = {fs[0]: dict(dur=14897), fs[1]: dict(dur=14897), fs[2]: dict(dur=12760), fs[3]: dict(dur=12760)}
one = L._one_per_take(fs, inf)
assert one == [fs[1], fs[3]], one
lav = ["/w/lav/Lav_01.wav", "/w/lav/Lav_02.wav"]
assert L._one_per_take(lav, {lav[0]: dict(dur=60, ctime=1), lav[1]: dict(dur=60, ctime=900)}) == lav

# a camera with 5 clips; 8619 / 8620 matched far too late (a copy of the take): they must go out
info = [dict(path="/w/a.wav", duration=20000, clock=None, start=0.0)]
P = lambda n, cam: dict(path=f"/w/a7iv/A7iv{n}.MP4", cam=cam, kind="party", a=0, b=100)
party = [P(n, 1) for n in (8618, 8619, 8620, 8621, 8622)]
res = {p["path"]: dict(conf="high", master=0, offset=o, dur=300) for p, o in
       zip(party, (100, 9000, 9400, 1000, 1500))}
n = L.camera_order_check(party, res, info)
bad = sorted(p["path"][-8:] for p in party if res[p["path"]]["conf"] == "low")
assert n == 2 and bad == ["8619.MP4", "8620.MP4"], (n, bad)
# overlapping clips of one camera: the shorter chain loses
party2 = [P(n, 2) for n in (1, 2, 3)]
res2 = {party2[0]["path"]: dict(conf="high", master=0, offset=0, dur=600),
        party2[1]["path"]: dict(conf="high", master=0, offset=100, dur=50),
        party2[2]["path"]: dict(conf="high", master=0, offset=700, dur=600)}
assert L.camera_order_check(party2, res2, info) == 1 and res2[party2[1]["path"]]["conf"] == "low"
assert sync.master_starts(info) == [0.0]
print("party sync rules: OK")

# the clock check after the sync: church clips given by mistake matched on the party must be refused
import sync  # noqa: E402
info = [dict(path="/r/rec.wav", duration=4 * 3600, clock=19.5 * 3600)]
res, clocks, groups = {}, {}, {}
for i in range(6):                                   # party clips: clock error 120 s, all agree
    c = f"/w/fx6/P{i}.MXF"
    res[c] = dict(conf="high", offset=600.0 + i * 900, master=0, dur=60.0)
    clocks[c] = 19.5 * 3600 + 600 + i * 900 + 120
    groups[c] = "fx6"
for i in range(2):                                   # church clips (17:05) matched on the first dance (21:00)
    c = f"/w/fx6/C{i}.MXF"
    res[c] = dict(conf="high", offset=5400.0 + i * 30, master=0, dur=300.0)
    clocks[c] = 17.08 * 3600 + i * 400
    groups[c] = "fx6"
n = sync.verify_clocks(res, info, clocks, groups)
assert n == 2 and all(res[f"/w/fx6/C{i}.MXF"]["conf"] == "low" for i in range(2)), (n, res)
assert all(res[f"/w/fx6/P{i}.MXF"]["conf"] == "high" for i in range(6))
print("clock check OK")
