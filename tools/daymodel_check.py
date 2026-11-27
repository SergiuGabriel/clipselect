"""The day model (daymap.classify_ai) on two of his real weddings: the real SigLIP 2 judgement of every clip (3 frames)
and which of the couple's faces are seen, saved in daymodel_fixture.json, against my label of every clip.
28 August (villa, first look, civil ceremony, church, couple session), 29 August (outdoor ceremony, no church) and
4 September (civil ceremony in the morning, getting ready after it, first look, no church; fx3 clock corrected 2 h) and
12 September (traditional: groom and bride at home with guests and a band, fetching the bride, church, couple with a car)."""
import json, sys
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import daymap  # noqa: E402

FX = json.loads((Path(__file__).parent / "daymodel_fixture.json").read_text())
LAB = {v: k for k, v in daymap.MOMENT_LABEL.items()}
A, B = np.eye(128, dtype=np.float32)[0], np.eye(128, dtype=np.float32)[1]
NEED = {"w28": 0.90, "w29": 0.90, "w04": 0.90, "w12": 0.90}
for name, rows in FX.items():
    clips = {r["k"]: dict(t0=r["t0"], dur=r["dur"], path="/W/" + r["k"]) for r in rows}
    faces = {r["k"]: [A if f == "A" else B for f in r["faces"]] for r in rows}
    ai = {r["k"]: {"_p": r["p"], "_civil": r["civil"]} for r in rows}
    lab, info = daymap.classify(clips, faces, ai)
    ok = n = 0
    for r in rows:
        g = r["gt"]
        if g == "?":
            continue
        p = LAB.get(lab[r["k"]], lab[r["k"]])
        n += 1
        ok += p in g.split("|") or (g == "interview" and p == "party")
    share = ok / n
    print(f"day model, {name}: {ok} of {n} clips right ({share:.0%})", info.get("church_by"), "civil" in info)
    assert share >= NEED[name], f"{name}: {share:.0%} < {NEED[name]:.0%}"
# a camera whose clock is wrong (an Osmo set to any time, no sound match): its place in the day from what it shows
for name, c in (("w28", "osmo"), ("w28", "fx3"), ("w04", "fx3"), ("w12", "fx3")):
    rows = FX[name]
    for sh in (5 * 3600 + 777, -9 * 3600):
        clips = {r["k"]: dict(t0=r["t0"] + (sh if r["k"].startswith(c + "/") else 0), dur=r["dur"], path="/W/" + r["k"])
                 for r in rows}
        faces = {r["k"]: [A if f == "A" else B for f in r["faces"]] for r in rows}
        ai = {r["k"]: {"_p": r["p"], "_civil": r["civil"]} for r in rows}
        o = daymap.clock_offsets(clips, faces, ai, {c}).get(c, 0.0)
        print(f"clock, {name} {c} moved {sh / 60:.0f} min: found {-o / 60:.0f} min")
        assert abs(o + sh) <= 20 * 60, (name, c, sh, o)
    clips = {r["k"]: dict(t0=r["t0"], dur=r["dur"], path="/W/" + r["k"]) for r in rows}
    assert daymap.clock_offsets(clips, faces, ai, {c}).get(c, 0.0) == 0.0, (name, c, "right clock moved")
print("day model check OK")
