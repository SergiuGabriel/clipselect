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
assert one == [fs[0], fs[2]], one                    # a TRACK by default (owner: his auto track, never the mix)
sync.TAKE_PREF = "mix"
assert L._one_per_take(fs, inf) == [fs[1], fs[3]]
three = ["/w/T/0190_1-2.wav", "/w/T/0190_3-4.wav", "/w/T/0190_MIX.wav"]
i3 = {f: dict(dur=100) for f in three}
sync.TAKE_PREF = "2"
assert L._one_per_take(three, i3) == [three[1]]
sync.TAKE_PREF = "1"
assert L._one_per_take(three, i3) == [three[0]]
sync.TAKE_PREF = "auto"
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

# Syncaila's order check after the sync: clips given by mistake (first look C9754 / C9759 on his 28 August fx3) matched on
# the party are out of the camera's file order -> refused; the clocks do not matter (this camera's clock is years off)
import sync  # noqa: E402
info = [dict(path="/r/rec.wav", duration=6 * 3600, clock=None)]
res, groups = {}, {}
place = {"C9754": 258.8, "C9759": 83.1, "C9773": 2.9, "C9775": 3.9, "C9778": 22.6, "C9779": 84.5, "C9780": 105.9,
         "C9781": 192.2, "C9782": 246.2, "C9783": 249.1, "C9784": 335.1, "C0001": 400.0, "C0002": 410.0}
dur = {"C9778": 318, "C9779": 426, "C9780": 384, "C9781": 1272, "C9783": 526, "C9784": 182}
for k, m in place.items():
    res[f"/w/fx3/{k}.MP4"] = dict(conf="high", offset=m * 60, master=0, dur=float(dur.get(k, 20)))
    groups[f"/w/fx3/{k}.MP4"] = "fx3"
n = sync.order_check(res, info, groups)
low = sorted(k for k in res if res[k]["conf"] == "low")
assert low == ["/w/fx3/C9754.MP4", "/w/fx3/C9759.MP4"], (n, low)       # C0001 / C0002 after the wrap stay
print("order check after the sync OK")
