"""The map of the wedding day: which MOMENT every clip belongs to, found without his colour labels.

Measured on Alex & Andreea (fx6 clock coherent, his labels as the answer):
  - the day is made of SCENES separated by gaps of 15+ minutes where no camera films (travel, a break);
  - getting ready = the scenes before the church; the groom is filmed first (all his weddings so far), the bride after;
    the groom / bride are the faces seen in the most clips of the first / second scene (12 of 27 groom clips, 12 of 29
    bride clips show them; the others are details, rooms, family);
  - the church = the first scene with long clips (>= 150 s, at least 900 s of them: the ceremony runs whole);
  - long morning clips (>= 150 s) = the vornic;
  - after the church (its first scene, then until a break of 40+ minutes): the VENUE has no faces at all (14 of 14 Yellow clips) and
    the COUPLE shots show the groom or the bride (other faces = guests -> party; v4.1.0);
  - the rest is the party; a party scene that is mostly the couple in short shots (the sunset session) = couple;
  - drone = folders / files of a drone (DJI, mavic, drona).
Clock: every camera's own clock (creation time, else file date minus duration), shifted by the camera's clock error
when the sync with the recorder measured it (cameras' clocks are often hours off: his fx3 2 h, his a74 a day).
Returns the colour names of Long Film v2 (Blue, Rose, Teal, Forest, Brown, Yellow, Purple, Violet, Iris) so the rest
of v2 works as if he had labelled the clips himself; the editor lets him correct them.
"""
import re
from pathlib import Path

import numpy as np

SCENE_GAP = 15 * 60          # a pause of 15 min where nobody films separates two scenes
LONG = 150.0                 # a long clip (ceremony, vornic speech)
CHURCH_LONG = 900.0          # the church scene has at least this much of long clips
CHURCH_GAP = 15 * 60         # long clips of the ceremony follow each other within 15 min
TAIL = 10 * 60               # short clips up to 10 min after the ceremony still belong to the church
HEAD = 5 * 60                # and up to 5 min before it (the entrance)
AFTER_BREAK = 40 * 60        # couple + venue last until the first break of 40 min after the church
SAME = 0.363                 # faces.SAME
DRONE_RE = re.compile(r"(?i)(drona|drone|mavic|dji|avata|mini ?\d|air ?\d)")


def is_drone(path):
    p = Path(path)
    return bool(DRONE_RE.search(p.parent.name) or p.name.upper().startswith("DJI_"))


def _unit(f):
    f = np.asarray(f, np.float32)
    return f / max(1e-6, float(np.linalg.norm(f)))


def clip_faces(fr):
    """fr = [[(size, feature), ...] per frame] -> list of unit features of the clip."""
    return [_unit(f) for frame in fr or [] for _sz, f in frame]


def top_person(clips, faces, exclude=None):
    """The face seen in the most clips of this group (and not `exclude`). Returns a unit feature or None."""
    pool = [(p, f) for p in clips for f in faces.get(p, [])
            if exclude is None or float(f @ exclude) < SAME]
    best, score = None, (0, 0)
    for p, f in pool:
        seen = {q for q, g in pool if float(f @ g) >= SAME}
        sc = (len(seen), sum(1 for _q, g in pool if float(f @ g) >= SAME))
        if sc > score:
            best, score = f, sc
    return best if score[0] >= 2 else None


def has(person, feats):
    return person is not None and any(float(person @ f) >= SAME for f in feats)


def scenes(items):
    """items sorted by time: [(t0, t1, key)] -> list of lists of keys (split at gaps >= SCENE_GAP)."""
    out, end = [], None
    for t0, t1, k in items:
        if end is None or t0 - end >= SCENE_GAP:
            out.append([])
        out[-1].append(k)
        end = t1 if end is None else max(end, t1)
    return out


def classify(clips, faces):
    """clips: {key: dict(t0, dur, path)} on ONE common clock (seconds); faces: {key: [unit features]}.
    Returns ({key: colour}, info) with info = dict(groom=, bride=, church=(t0, t1), scenes=n)."""
    keys = sorted(clips, key=lambda k: clips[k]["t0"])
    lab, info = {}, {}
    for k in keys:
        if is_drone(clips[k]["path"]):
            lab[k] = "Violet"
    rest = [k for k in keys if k not in lab]
    t0 = lambda k: clips[k]["t0"]
    t1 = lambda k: clips[k]["t0"] + clips[k]["dur"]
    # the church: the first cluster of long clips (ceremony) with at least CHURCH_LONG of them; with two cameras the
    # scenes run into each other, so the ceremony is found by its long clips, not by the gaps
    longs = [k for k in rest if clips[k]["dur"] >= LONG]
    clusters, cur = [], []
    for k in longs:
        if cur and t0(k) - max(t1(x) for x in cur) > CHURCH_GAP:
            clusters.append(cur)
            cur = []
        cur.append(k)
    if cur:
        clusters.append(cur)
    core = next((c for c in clusters if sum(clips[k]["dur"] for k in c) >= CHURCH_LONG and len(c) >= 2), None)
    if core is None and clusters:
        core = max(clusters, key=lambda c: sum(clips[k]["dur"] for k in c))
    if core:
        c0, c1 = t0(core[0]), max(t1(k) for k in core)
        for k in reversed(rest):            # short clips just before the first long one (the entrance)
            if t0(k) < c0 and c0 - t1(k) <= HEAD:
                c0 = t0(k)
        for k in rest:                      # short clips right after the last long one (exit, congratulations)
            if c1 <= t0(k) <= c1 + TAIL:
                c1 = max(c1, t1(k))
    else:
        c0 = c1 = float("inf")
    church = [k for k in rest if c0 <= t0(k) <= c1]
    sc = scenes([(t0(k), t1(k), k) for k in rest if t0(k) < c0])
    info["scenes"] = len(sc)
    ci = len(sc)
    sc = [x for x in sc if x] + [church] + scenes([(t0(k), t1(k), k) for k in rest if t0(k) > c1])
    ci = min(ci, len(sc) - 1) if sc else 0
    morning = sc[:ci]
    groom = top_person(morning[0], faces) if morning else None
    bride = None
    if len(morning) >= 2:
        bride = top_person([k for s in morning[1:] for k in s], faces, exclude=groom)
    elif morning:
        bride = top_person(morning[0], faces, exclude=groom)
    info.update(groom=groom is not None, bride=bride is not None)
    # morning: groom / bride by face, else by the scene (first = groom), long clips = vornic, both together = first look
    for si, s in enumerate(morning):
        g = sum(has(groom, faces.get(k, [])) for k in s)
        b = sum(has(bride, faces.get(k, [])) for k in s)
        side = "Blue" if si == 0 or g > b else "Rose"
        for k in s:
            fs = faces.get(k, [])
            if clips[k]["dur"] >= LONG:
                lab[k] = "Forest"
            elif has(groom, fs) and has(bride, fs):
                lab[k] = "Teal"
            elif has(groom, fs):
                lab[k] = "Blue"
            elif has(bride, fs):
                lab[k] = "Rose"
            else:
                lab[k] = side
    for k in sc[ci] if ci < len(sc) else []:
        lab[k] = "Brown"
    if ci < len(sc) and sc[ci]:
        info["church"] = (clips[sc[ci][0]]["t0"], max(clips[k]["t0"] + clips[k]["dur"] for k in sc[ci]))
    # after the church: couple + venue until the first long break, then the party
    after = [x for x in sc[ci + 1:] if x]
    end = info.get("church", (clips[keys[0]]["t0"] if keys else 0, 0))[1]
    in_cv, cv_seen = True, False
    for s in after:
        start = clips[s[0]]["t0"]
        if in_cv and cv_seen and start - end >= AFTER_BREAK:   # the first scene after the church is always couple/venue
            in_cv = False
        cv_seen = True
        if in_cv:
            for k in s:
                fs = faces.get(k)
                if not fs:
                    lab[k] = "Yellow"
                elif groom is None and bride is None:       # no one known (no faces in the morning): any face
                    lab[k] = "Purple"
                elif has(groom, fs) or has(bride, fs):      # the couple only when the groom or the bride is seen
                    lab[k] = "Purple"
                else:                                       # guests (congratulations, arriving at the venue)
                    lab[k] = "Iris"
        else:
            couple = sum(has(groom, faces.get(k, [])) or has(bride, faces.get(k, [])) for k in s)
            short = float(np.median([clips[k]["dur"] for k in s])) < 40
            for k in s:
                lab[k] = "Purple" if (couple >= 0.4 * len(s) and short and len(s) >= 4) else "Iris"
        end = max(end, max(clips[k]["t0"] + clips[k]["dur"] for k in s))
    return lab, info
