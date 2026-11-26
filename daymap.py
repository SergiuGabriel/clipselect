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
AI_CHURCH = 0.40             # AI: a clip is "church" when that is its top scene or its probability >= this
AI_SURE = 0.90               # AI: a sure church clip (the ceremony starts and ends with one)
AI_DRONE = 0.35              # AI: a DJI_ file outside a drone folder is the drone only when seen from high above
SPEECH_FRAC = 0.8            # vornic: a continuous take with this share of speech (no music) ...
VORNIC_TAKE = 120.0          # ... of at least 2 min, that another camera films at the same time:
VORNIC_BOTH = 60.0           #     a take of 2 min too, overlapping >= 1 min (measured on his Alex & Andreea: 4 / 4)
VORNIC_OTHER = 30.0          #     or other clips >= 30 s inside it when the AI sees someone giving a speech
PARTY_RUN = (4, 6)           # AI: 4 of 6 clips in a row are the party -> the couple / venue part is over
SAME = 0.363                 # faces.SAME
DRONE_RE = re.compile(r"(?i)(drona|drone|mavic|dji|avata|mini ?\d|air ?\d)")


GIMBAL_RE = re.compile(r"(?i)(osmo|pocket|action|gopro|insta ?360|ronin)")


def is_drone(path, sc=None):
    """A drone clip: a drone folder (drona, mavic, dji...) or a DJI_ file name, but NEVER a gimbal / action camera
    folder (OSMO, Pocket, Action, GoPro): DJI's Osmo cameras name their files DJI_... too (his friend's OSMO went to
    the drone part). A DJI_ file outside a drone folder, with the AI's judgement `sc`, is the drone only when the AI
    sees it from high above (an Osmo lifted 3-5 m is not; a drone flies higher)."""
    p = Path(path)
    if any(GIMBAL_RE.search(x) for x in (p.parent.name, p.parent.parent.name)):
        return False
    if DRONE_RE.search(p.parent.name):
        return True
    if p.name.upper().startswith("DJI_"):
        if sc:
            return sc.get("drone", 0.0) >= AI_DRONE or max(
                (c for c in sc if not c.startswith("_")), key=lambda c: sc[c]) == "drone"
        return True
    return False


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


def _vornic(morning, clips, speech, ai):
    """The vornic = a speech in front of the family that BOTH cameras film for minutes. Measured on Alex & Andreea:
    his 4 vornic clips are 2 pairs of simultaneous takes of 3-5 min on fx6 + fx3 with only speech; a long take of one
    camera alone (getting ready: 63181, 4 min) is not the vornic. Any number of clips: the other camera can film it in
    short clips when the AI sees someone giving a speech (house or yard)."""
    ks = [k for s in morning for k in s]
    cam = lambda k: Path(clips[k]["path"]).parent.name
    t0 = lambda k: clips[k]["t0"]
    t1 = lambda k: clips[k]["t0"] + clips[k]["dur"]
    ov = lambda a, b: max(0.0, min(t1(a), t1(b)) - max(t0(a), t0(b)))
    takes = [k for k in ks if clips[k]["dur"] >= VORNIC_TAKE and speech.get(k, 0.0) >= SPEECH_FRAC]
    out = set()
    for a in takes:
        others = [b for b in ks if cam(b) != cam(a) and ov(a, b) > 0]
        both = [b for b in others if b in takes and ov(a, b) >= VORNIC_BOTH]
        sc = ai.get(a) or {}
        talk = sc.get("speech", 0.0) >= 0.3 or scenes_top(sc) == "speech"
        if both or (talk and sum(ov(a, b) for b in others) >= VORNIC_OTHER):
            out.add(a)
            out.update(both if both else others)
    return out


def scenes_top(sc):
    return max((c for c in sc if not c.startswith("_")), key=lambda c: sc[c]) if sc else ""


def _church_by_ai(rest, clips, ai):
    """The ceremony seen by the AI: runs of "church" clips in time order (up to 3 other clips inside a run), weighted by
    their length; the EARLIEST run with at least half of the biggest run's church time (the party can have chandeliers
    that look like a church to the AI, the ceremony comes first). None when the AI found no run of >= 3 church clips."""
    def churchy(k):
        sc = ai.get(k)
        if not sc:
            return False
        best = max((c for c in sc if not c.startswith("_")), key=lambda c: sc[c])
        return best == "church" or sc.get("church", 0.0) >= AI_CHURCH
    runs, cur, other = [], [], 0
    for k in rest:
        if churchy(k):
            if cur and (other > 3 or clips[k]["t0"] - max(clips[x]["t0"] + clips[x]["dur"] for x in cur) > CHURCH_GAP):
                runs.append(cur)
                cur = []
            cur.append(k)
            other = 0
        elif cur:
            other += 1
            if other > 3:
                runs.append(cur)
                cur, other = [], 0
    if cur:
        runs.append(cur)
    runs = [r for r in runs if len(r) >= 3]
    if not runs:
        return None
    w = [sum(clips[k]["dur"] for k in r) for r in runs]
    big = max(w)
    run = next(r for r, x in zip(runs, w) if x >= 0.5 * big)
    # the run starts / ends at a SURE church clip: the arrival in front of the church looks a bit like a church too
    sure = [i for i, k in enumerate(run) if ai[k].get("church", 0.0) >= AI_SURE]
    if len(sure) >= 2:
        run = run[sure[0]:sure[-1] + 1]
    return run


def classify(clips, faces, ai=None, speech=None):
    """clips: {key: dict(t0, dur, path)} on ONE common clock (seconds); faces: {key: [unit features]}; ai: {key: scene
    probabilities} from scenes.py (optional); speech: {key: share of the clip that is speech without music} (optional).
    Returns ({key: colour}, info) with info = dict(groom=, bride=, church=(t0, t1), scenes=n, church_by=)."""
    ai = ai or {}
    speech = speech or {}
    keys = sorted(clips, key=lambda k: clips[k]["t0"])
    lab, info = {}, {}
    for k in keys:
        if is_drone(clips[k]["path"], ai.get(k)):
            lab[k] = "Violet"
    rest = [k for k in keys if k not in lab]
    t0 = lambda k: clips[k]["t0"]
    t1 = lambda k: clips[k]["t0"] + clips[k]["dur"]
    use_ai = bool(rest) and sum(1 for k in rest if ai.get(k)) >= 0.5 * len(rest)
    core = _church_by_ai(rest, clips, ai) if use_ai else None
    info["church_by"] = "ai" if core else "clips"
    if core is None:
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
            if info["church_by"] == "clips" and t0(k) < c0 and c0 - t1(k) <= HEAD:
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
    # the vornic: with the sound measured, a MOMENT of speech without music (one clip or several, any length) that
    # lasts >= 1 min and that the AI sees as someone speaking to people (house or yard) when it is there; without the
    # sound measurement the old rule (a long morning clip)
    measured = bool(speech)
    vk = set()
    if measured:
        vk = _vornic(morning, clips, speech, ai)
        info["vornic_by"] = "speech"
    # morning: groom / bride by face, else by the scene (first = groom), the vornic, both together = first look
    for si, s in enumerate(morning):
        g = sum(has(groom, faces.get(k, [])) for k in s)
        b = sum(has(bride, faces.get(k, [])) for k in s)
        side = "Blue" if si == 0 or g > b else "Rose"
        for k in s:
            fs = faces.get(k, [])
            if k in vk or (not measured and clips[k]["dur"] >= LONG):
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
    # after the church: couple + venue until the first long break (or, with the AI, until the party clearly starts),
    # then the party
    after = [x for x in sc[ci + 1:] if x]
    end = info.get("church", (clips[keys[0]]["t0"] if keys else 0, 0))[1]
    in_cv, cv_seen = True, False
    recent = []
    for s in after:
        start = clips[s[0]]["t0"]
        if in_cv and cv_seen and start - end >= AFTER_BREAK:   # the first scene after the church is always couple/venue
            in_cv = False
        cv_seen = True
        if in_cv:
            for k in s:
                sk = ai.get(k)
                tk = max((c for c in sk if not c.startswith("_")), key=lambda c: sk[c]) if sk else ""
                if use_ai and in_cv:
                    recent = (recent + [tk == "party"])[-PARTY_RUN[1]:]
                    if sum(recent) >= PARTY_RUN[0]:
                        in_cv = False           # filmed without a break: the AI sees the party has begun
                if not in_cv:
                    lab[k] = "Iris"
                    continue
                fs = faces.get(k)
                if not fs:
                    lab[k] = "Yellow"
                elif has(groom, fs) or has(bride, fs):
                    lab[k] = "Purple"
                elif use_ai and tk == "party":              # guests at the party, not the couple
                    lab[k] = "Iris"
                else:                                       # faces too small / in profile for the match: the couple
                    lab[k] = "Purple"
        else:
            couple = sum(has(groom, faces.get(k, [])) or has(bride, faces.get(k, [])) for k in s)
            short = float(np.median([clips[k]["dur"] for k in s])) < 40
            for k in s:
                sk = ai.get(k)
                party = use_ai and bool(sk) and scenes_top(sk) == "party"
                lab[k] = "Purple" if (couple >= 0.4 * len(s) and short and len(s) >= 4 and not party) else "Iris"
        end = max(end, max(clips[k]["t0"] + clips[k]["dur"] for k in s))
    return lab, info
