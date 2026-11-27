"""CI check: the story order of an automatic Long Film v2 (longfilm2.auto_order) with the drone shots first, and the video track order (director.video_order)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
import director  # noqa: E402
import longfilm2  # noqa: E402

P = lambda kind, t: dict(kind=kind, t=t * 60.0, path=f"/w/{kind}{t}.mp4", a=0.0, b=5.0)
# 28 August: venue + drone filmed first, then groom, bride, first look, church, the tables + drone, couple, party
ps = [P("venue", 710), P("drone", 717), P("groom", 770), P("bride", 810), P("firstlook", 870), P("church", 1000),
      P("venue", 1086), P("drone", 1092), P("couple", 1115), P("party", 1200), P("drone", 1213)]
order = longfilm2.auto_order(ps)
assert order == ["drone", "ready", "firstlook", "church", "venue", "couple", "party"], order
ps2 = [P("groom", 540), P("drone", 545), P("bride", 600), P("church", 720), P("drone", 760), P("couple", 830),
       P("venue", 900), P("party", 1000)]
o2 = longfilm2.auto_order(ps2)
assert o2[:5] == ["drone", "ready", "church", "couple", "venue"], o2
# video tracks: static on V1, main camera (most footage) on top, the others between; a chosen track wins
cams = [dict(name="fx3", role="Handheld", clips=[1, 2]), dict(name="a74", role="Static", clips=[1]),
        dict(name="fx6", role="Handheld", clips=[1, 2, 3, 4]), dict(name="rec", role="Audio", clips=[1])]
assert director.video_order(cams) == [1, 0, 2], director.video_order(cams)
cams[0]["track"] = 3
assert director.video_order(cams) == [1, 2, 0], director.video_order(cams)
print("order check OK")
