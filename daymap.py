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
NEAR_SIDE = 30 * 60          # a detail / room goes with the groom / bride filmed within 30 min of it
NEAR_VENUE = NEAR_SIDE       # (a shorter limit for venue-looking rooms cost 4 bride clips at Alex & Andreea)
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
            q = sc.get("_p") or sc
            return q.get("drone", 0.0) >= AI_DRONE or max(
                (c for c in q if not c.startswith("_")), key=lambda c: q[c]) == "drone"
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


def who_of(sc):
    """The AI's WHO judgement of a clip (scenes.WHO): {bride, groom, both, none}, {} when there is none."""
    return (sc or {}).get("_who") or {}


def couple_faces(keys, faces, ai, groom0=None, bride0=None):
    """The groom and the bride over the WHOLE day: the faces seen in the most clips (the couple is filmed at every
    moment), told apart by what the AI sees in the clips where each face is: a white dress / veil = the bride, a suit =
    the groom. Works whatever was filmed first (28 August: the venue's decorators came first, the old 'first scene =
    groom' rule made the groom pink). Returns (groom, bride) unit features; the old ones when the AI cannot tell."""
    cands, ex = [], None
    pool = [k for k in keys if faces.get(k)]
    for _ in range(4):
        f = top_person(pool, faces, exclude=None)
        if f is None:
            break
        cands.append(f)
        pool = [k for k in pool if not has(f, faces.get(k, []))]
    scored = []
    for f in cands:
        seen = [k for k in keys if has(f, faces.get(k, [])) and who_of(ai.get(k))]
        if len(seen) < 3:
            continue
        w = [who_of(ai[k]) for k in seen]
        bride = float(np.mean([x.get("bride", 0.0) for x in w]))
        groom = float(np.mean([x.get("groom", 0.0) for x in w]))
        scored.append((f, bride - groom, len(seen)))
    if len(scored) < 2:
        return groom0, bride0
    if groom0 is not None and bride0 is not None:     # the first scene / next scenes rule, checked by the AI: kept when
        def lean(f):                                  # the AI sees the dress on its bride and the suit on its groom
            w = [who_of(ai[k]) for k in keys if has(f, faces.get(k, [])) and who_of(ai.get(k))]
            return float(np.mean([x.get("bride", 0.0) - x.get("groom", 0.0) for x in w])) if len(w) >= 3 else None
        lb, lg = lean(bride0), lean(groom0)
        if lb is not None and lg is not None and lb >= 0.1 and lg <= -0.1:
            return groom0, bride0
    scored.sort(key=lambda x: -x[2])
    top = scored[:3]
    b = max(top, key=lambda x: x[1])
    g = min((x for x in top if x is not b), key=lambda x: x[1])
    if b[1] - g[1] < 0.15:                  # the AI does not really see a dress on one and a suit on the other
        return groom0, bride0
    return g[0], b[0]


def side_of(sc):
    """Blue / Rose / Teal from the AI's WHO judgement alone (no face match), None when it does not see the couple."""
    w = who_of(sc)
    if not w:
        return None
    if w.get("both", 0.0) >= 0.7:
        return "Teal"
    if w.get("bride", 0.0) >= 0.4 and w.get("bride", 0.0) > w.get("groom", 0.0):
        return "Rose"
    if w.get("groom", 0.0) >= 0.4 and w.get("groom", 0.0) > w.get("bride", 0.0):
        return "Blue"
    return None


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
    runs, cur, other, last = [], [], 0, None
    for k in rest:
        # the gap is measured to the end of ANY clip seen since the run began: a 27-min take of the service that the
        # AI does not see as church (28 August) must not split the church in two
        end = clips[k]["t0"] + clips[k]["dur"]
        if churchy(k):
            if cur and (other > 3 or clips[k]["t0"] - last > CHURCH_GAP):
                runs.append(cur)
                cur = []
            if not cur:
                last = end
            cur.append(k)
            other = 0
            last = max(last, end)
        elif cur:
            other += 1
            if other > 3:
                runs.append(cur)
                cur, other = [], 0
            else:
                last = max(last, end)
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
    if has_moments(ai):
        return classify_ai(clips, faces, ai, speech)
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
    has_who = use_ai and sum(1 for k in rest if who_of(ai.get(k))) >= 0.5 * len(rest)
    if has_who:
        groom, bride = couple_faces(rest, faces, ai, groom, bride)
    info.update(groom=groom is not None, bride=bride is not None, who=has_who)
    # the vornic: with the sound measured, a MOMENT of speech without music (one clip or several, any length) that
    # lasts >= 1 min and that the AI sees as someone speaking to people (house or yard) when it is there; without the
    # sound measurement the old rule (a long morning clip)
    measured = bool(speech)
    vk = set()
    if measured:
        vk = _vornic(morning, clips, speech, ai)
        info["vornic_by"] = "speech"
    # morning: groom / bride by face, else by the scene (first = groom), the vornic, both together = first look
    loose = []
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
            elif has_who and side_of(ai.get(k)):
                lab[k] = side_of(ai.get(k))
            elif has_who:
                loose.append((k, side))     # details, rooms: they go with the side filmed around them
            else:
                lab[k] = side
    cam = lambda k: Path(clips[k]["path"]).parent.name
    sides = [x for x in lab if lab[x] in ("Blue", "Rose")]
    for k, side in loose:
        near = sorted((abs(t0(x) - t0(k)), lab[x]) for x in sides if cam(x) == cam(k)) or [(1e9, None)]
        near_any = sorted((abs(t0(x) - t0(k)), lab[x]) for x in sides) or [(1e9, None)]
        venue = scenes_top(ai.get(k)) == "venue" and who_of(ai.get(k)).get("none", 0.0) >= 0.5
        lim = NEAR_VENUE if venue else NEAR_SIDE
        if near[0][0] <= lim:               # the same camera was filming the groom / the bride a few minutes away
            lab[k] = near[0][1]
        elif near_any[0][0] <= lim:
            lab[k] = near_any[0][1]
        elif venue or (not faces.get(k) and who_of(ai.get(k)).get("none", 0.0) >= 0.8
                       and scenes_top(ai.get(k)) not in ("ready", "speech")):
            lab[k] = "Yellow"               # the venue filmed apart from the groom / bride (28 August: building, decor)
        else:
            lab[k] = side
    if has_who:
        # the first look: once the groom and the bride have met (2 clips with both of them within 10 min), the shots of
        # one of them before the church are that moment too (her reaction, his back to her), not getting ready
        both = [k for s in morning for k in s if lab.get(k) == "Teal"]
        start = next((k for i, k in enumerate(both[:-1]) if t0(both[i + 1]) - t0(k) <= 10 * 60), None)
        if start is not None:
            for s in morning:
                for k in s:
                    if t0(k) >= t0(start) and lab.get(k) in ("Blue", "Rose"):
                        lab[k] = "Teal"
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
                if has_who and side_of(sk) and not (fs and not (has(groom, fs) or has(bride, fs)) and tk == "party"):
                    lab[k] = "Purple"               # the AI sees the bride / groom (faces too small for the match)
                elif not fs:
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


# ---------------------------------------------------------------- v4.6.0: the day model (AI + faces + the order of a day)
# No rules made for one videographer: every clip is judged by the AI (scenes.MOMENTS, SigLIP 2), the faces tell who the
# couple is, and the ORDER of a wedding day is used only as likelihood: per camera (its own clock is always coherent),
# the clips go through the phases getting ready -> first look -> couple session -> civil ceremony -> ceremony -> after
# (couple, venue, guests, party), any of them may be missing, never backwards. A Viterbi picks the path that agrees best
# with what the AI sees. Measured (my labels of every clip, real SigLIP 2): 28 August 92 %, 29 August 95 %, ...
MOMENT_LABEL = {"groom": "Blue", "bride": "Rose", "firstlook": "Teal", "couple": "Purple", "venue": "Yellow",
                "church": "Brown", "civil": "Mango", "party": "Iris", "interview": "Tan", "drone": "Violet",
                "vornic": "Forest"}
PHASES = [  # name, {moment: weight in what the phase "looks like"}, the moments a clip of this phase can be
    ("civil0", {"civil": 1, "church": .6, "party": .3}, ("civil",)),    # a civil ceremony in the morning, before
    ("ready", {"groom": 1, "bride": 1, "details": 1, "venue": 1, "speech": 1, "firstlook": .15},
     ("groom", "bride", "details", "venue", "speech")),
    ("firstlook", {"firstlook": 1, "groom": .35, "bride": .35, "couple": .35, "church": .3, "speech": .3, "party": .2},
     ("firstlook",)),
    ("couplem", {"couple": 1, "venue": 1, "firstlook": .3}, ("couple", "venue")),
    ("civil", {"civil": 1, "church": .6, "party": .3}, ("civil",)),
    ("church", {"church": 1}, ("church",)),
    ("after", {"couple": 1, "venue": 1, "party": 1, "interview": 1}, ("couple", "venue", "party", "interview")),
]
PH_MOVE = -2.0              # log cost of going to a later phase
PH_START = -0.5             # per phase skipped at the first clip of a camera (from "ready"; a morning civil = 1)
PH_GAP = 15 * 60            # a pause of 15 min (travel) makes moving on cheap and staying a little costly
PH_GAP_STAY = -1.0
CIVIL_SURE = 0.7            # a frame with the officer's tricolour sash (his officer clip: 1.0, nothing else above 0.5)
CIVIL_AROUND = 10 * 60      # the other cameras' clips this close to a sure civil clip are the civil ceremony too
SIDE_SWITCH = 2.0
START_LOOK = 60 * 60         # a camera's first clip starts in the phase the other cameras reached in the hour before it
BOTH_READY = -1.5           # log cost of "getting ready" for a clip where both faces of the couple are seen           # getting ready: groom / bride are filmed in blocks


def has_moments(ai):
    return bool(ai) and sum(1 for v in ai.values() if (v or {}).get("_p")) >= 0.5 * len(ai)


def _couple_ids(keys, faces):
    """The two faces seen in the most clips (the couple is filmed all day). Returns (a, b) unit features or None."""
    cents = []
    for k in keys:
        for f in faces.get(k, []):
            best, bi = -1.0, -1
            for i, (c, ks) in enumerate(cents):
                s = float(f @ (c / np.linalg.norm(c)))
                if s > best:
                    best, bi = s, i
            if best >= SAME + 0.1:
                cents[bi][0] += f
                cents[bi][1].add(k)
            else:
                cents.append([np.array(f, np.float32), {k}])
    cents.sort(key=lambda x: -len(x[1]))
    return [c / np.linalg.norm(c) for c, ks in cents[:2]]


def _probs(ai, keys, faces, ids):
    """{key: np.array over scenes.MOMENT_CATS (without 'unclear')} with the faces' evidence: both of the couple seen ->
    first look / couple; one of them -> not an empty room."""
    import scenes
    cats = [c for c in scenes.MOMENT_CATS if c != scenes.UNCLEAR]
    out, pres = {}, {}
    for k in keys:
        p = (ai.get(k) or {}).get("_p")
        if not p:
            continue
        q = np.array([p.get(c, 0.0) for c in cats], float) + 1e-6
        fs = faces.get(k, [])
        ab = tuple(has(i, fs) for i in ids) + (False,) * (2 - len(ids))
        pres[k] = ab
        if ab[0] and ab[1]:
            for c in ("firstlook", "couple"):
                q[cats.index(c)] *= 1.5
            for c in ("groom", "bride", "details", "venue"):
                q[cats.index(c)] *= 0.3
        elif ab[0] or ab[1]:
            for c in ("venue", "details"):
                q[cats.index(c)] *= 0.5
        out[k] = q / q.sum()
    return out, pres, cats


def _phase_path(keys, P, cats, t0, both=frozenset(), start=1):
    n, m = len(keys), len(PHASES)
    em = np.zeros((n, m))
    for i, k in enumerate(keys):
        for j, (_, w, _) in enumerate(PHASES):
            em[i, j] = np.log(1e-3 + sum(P[k][cats.index(c)] * x for c, x in w.items()))
        if k in both:                   # the groom AND the bride in one clip: they are not getting ready apart any more
            em[i, [j for j, ph in enumerate(PHASES) if ph[0] == "ready"]] += BOTH_READY
    D = np.full((n, m), -1e18)
    B = np.zeros((n, m), int)
    D[0] = em[0] + np.array([PH_START * abs(j - start) for j in range(m)])
    for i in range(1, n):
        big = t0(keys[i]) - t0(keys[i - 1]) >= PH_GAP
        for j in range(m):
            prev = [D[i - 1, jj] + ((PH_GAP_STAY if big else 0.0) if jj == j else (PH_MOVE * 0.3 if big else PH_MOVE))
                    for jj in range(j + 1)]
            bj = int(np.argmax(prev))
            D[i, j] = prev[bj] + em[i, j]
            B[i, j] = bj
    j = int(D[-1].argmax())
    path = [0] * n
    for i in range(n - 1, -1, -1):
        path[i] = j
        j = B[i, j]
    return path


def _sides(keys, P, cats, face_side):
    """Groom / bride of the getting-ready clips of one camera (time order): a 2-state Viterbi with a switch cost; a
    detail / room with nobody in it takes the side of the nearest clip with a person (the next one first)."""
    gi, bi = cats.index("groom"), cats.index("bride")
    ev, neutral = [], []
    for k in keys:
        p = P[k]
        e = np.log(p[gi] + 0.03) - np.log(p[bi] + 0.03)
        fs = face_side.get(k)
        e += 2.5 if fs == "groom" else -2.5 if fs == "bride" else 0.0
        nt = fs is None and p[gi] + p[bi] < 0.25
        neutral.append(nt)
        ev.append(0.0 if nt else e / 2)
    n = len(keys)
    if not n:
        return {}
    D = np.zeros((n, 2))
    B = np.zeros((n, 2), int)
    D[0] = [ev[0], -ev[0]]
    for i in range(1, n):
        for s in range(2):
            a, b = D[i - 1, s], D[i - 1, 1 - s] - SIDE_SWITCH
            B[i, s] = s if a >= b else 1 - s
            D[i, s] = max(a, b) + (ev[i] if s == 0 else -ev[i])
    s = int(D[-1].argmax())
    out = {}
    for i in range(n - 1, -1, -1):
        out[keys[i]] = "groom" if s == 0 else "bride"
        s = B[i, s]
    for i in range(n):
        if neutral[i]:
            j = next((x for x in sorted(range(n), key=lambda x: (abs(x - i), x < i)) if not neutral[x]), None)
            if j is not None:
                out[keys[i]] = out[keys[j]]
    return out


OFF_STEP, OFF_RANGE, OFF_NEAR, OFF_BETTER = 60, 26 * 3600, 600, 0.05    # clock search of a camera the sound could not place


def clock_offsets(clips, faces, ai, free):
    """Cameras (folder names in `free`) whose clock is not known (an Osmo set to a random time, no sound match): the
    shift that makes what its clips show agree best with what the other cameras filmed at that time (the AI's moment
    probabilities, Bhattacharyya similarity to the nearest clips). The camera's own order is kept, only its place in
    the day moves; its own clock (shift 0) is kept unless another shift fits clearly better. Returns {folder: s}."""
    if not free or not has_moments(ai):
        return {}
    t0 = lambda k: clips[k]["t0"]
    cam = lambda k: Path(clips[k]["path"]).parent.name
    rest = sorted((k for k in clips if not is_drone(clips[k]["path"], ai.get(k))), key=t0)
    P, _, _ = _probs(ai, rest, faces, _couple_ids(rest, faces))
    ref = [k for k in rest if cam(k) not in free and k in P]
    if len(ref) < 20:
        return {}
    rs = np.array([t0(k) for k in ref])
    re_ = rs + np.array([clips[k]["dur"] for k in ref])
    R = np.sqrt(np.array([P[k] for k in ref]))
    out = {}
    for c in free:
        ks = [k for k in rest if cam(k) == c and k in P]
        if len(ks) < 3 or len(ks) > len(ref):
            continue
        a0 = np.array([t0(k) for k in ks])
        a1 = a0 + np.array([clips[k]["dur"] for k in ks])
        S = np.sqrt(np.array([P[k] for k in ks])) @ R.T          # similarity of every clip to every reference clip

        def score(off):                     # reference clips filmed at the same time (within OFF_NEAR) count
            near = (re_[None, :] >= a0[:, None] + off - OFF_NEAR) & (rs[None, :] <= a1[:, None] + off + OFF_NEAR)
            return float(np.where(near, S, 0.0).max(axis=1).mean())
        base = score(0.0)
        best = max(((score(off), -abs(off), off) for off in range(-OFF_RANGE, OFF_RANGE + 1, OFF_STEP)))
        if best[0] > base + OFF_BETTER:
            out[c] = float(best[2])
    return out


def classify_ai(clips, faces, ai, speech=None):
    """The day model. Same arguments / result as classify (+ 'Mango' = the civil ceremony)."""
    speech = speech or {}
    keys = sorted(clips, key=lambda k: clips[k]["t0"])
    t0 = lambda k: clips[k]["t0"]
    lab, info = {}, {"church_by": "day model"}
    for k in keys:
        if is_drone(clips[k]["path"], ai.get(k)):
            lab[k] = "Violet"
    rest = [k for k in keys if k not in lab]
    ids = _couple_ids(rest, faces)
    P, pres, cats = _probs(ai, rest, faces, ids)
    gi, bi = cats.index("groom"), cats.index("bride")
    vote = [0.0, 0.0]                       # which of the two faces is the groom: the AI's suit vs dress where it is alone
    for k, (a, b) in pres.items():
        if a != b:
            vote[0 if a else 1] += P[k][gi] - P[k][bi]
    groom_is = 0 if vote[0] >= vote[1] else 1
    face_side = {k: ("groom" if (0 if a else 1) == groom_is else "bride") for k, (a, b) in pres.items() if a != b}
    info.update(groom=len(ids) > 0, bride=len(ids) > 1, who=True)
    phase = {}
    cam = lambda k: Path(clips[k]["path"]).parent.name
    seen = []                               # (time, phase index) of the cameras already done (the busiest first)
    for c in sorted({cam(k) for k in rest}, key=lambda c: -sum(1 for k in rest if cam(k) == c)):
        ks = sorted((k for k in rest if cam(k) == c and k in P), key=t0)
        if not ks:
            continue
        # a camera that starts late in the day (an Osmo switched on for the party) starts where the others are by then
        before = [j for t, j in seen if t0(ks[0]) - START_LOOK <= t <= t0(ks[0])]
        path = _phase_path(ks, P, cats, t0, {k for k in ks if all(pres.get(k, (False, False)))},
                           start=max(before) if before else 1)
        seen += [(t0(k), path[i]) for i, k in enumerate(ks)]
        ix = {ph[0]: j for j, ph in enumerate(PHASES)}
        for name, instead in (("civil0", "ready"), ("civil", "church")):
            civ = [i for i in range(len(ks)) if PHASES[path[i]][0] == name]
            if civ and max((ai.get(ks[i]) or {}).get("_civil", 0.0) for i in civ) < CIVIL_SURE:
                for i in civ:
                    path[i] = ix[instead]   # no officer seen: getting ready / a religious ceremony
        for i, k in enumerate(ks):
            phase[k] = PHASES[path[i]]
        rk = [k for k in ks if phase[k][0] == "ready"]
        sd = _sides(rk, P, cats, face_side)
        for k in ks:
            name, _, allowed = phase[k]
            p = P[k]
            if name in ("couplem", "after"):    # once they are married / met: one of them alone = the couple session,
                p = p.copy()                    # a church-like building = the place (venue)
                p[cats.index("couple")] += p[cats.index("groom")] + p[cats.index("bride")]
                p[cats.index("venue")] += 0.5 * p[cats.index("church")]
            best = max(allowed, key=lambda x: p[cats.index(x)])
            if name == "ready":
                if not (best == "venue" and cats[int(np.argmax(p))] == "venue" and not any(pres.get(k, ()))):
                    best = sd.get(k, best)
            lab[k] = MOMENT_LABEL.get(best, "Iris")
    # the civil ceremony seen by one camera: the other cameras' clips around it are that moment too (but not a church)
    sure = [k for k in rest if (ai.get(k) or {}).get("_civil", 0.0) >= CIVIL_SURE]
    if sure:
        c0, c1 = min(t0(k) for k in sure) - CIVIL_AROUND, max(t0(k) + clips[k]["dur"] for k in sure) + CIVIL_AROUND
        gi, bi, ci = cats.index("groom"), cats.index("bride"), cats.index("church")
        near = set()
        for c in {cam(k) for k in rest}:        # a camera's whole scene (no pause >= 15 min) that meets the civil time
            ks = sorted((k for k in rest if cam(k) == c and k in P), key=t0)
            sc = []
            for k in ks:
                if sc and t0(k) - max(t0(x) + clips[x]["dur"] for x in sc[-1]) < PH_GAP:
                    sc[-1].append(k)
                else:
                    sc.append([k])
            for g in sc:
                if t0(g[0]) <= c1 and max(t0(x) + clips[x]["dur"] for x in g) >= c0:
                    near.update(g)
        for k in rest:
            if k not in P or P[k][ci] >= 0.8:
                continue
            win = c0 <= t0(k) <= c1             # the rest of the scene: never the church (often right after it)
            if (win and lab.get(k) in ("Brown", "Teal", "Purple", "Iris")) or \
                    ((win or k in near) and lab.get(k) in ("Rose", "Blue", "Yellow") and P[k][gi] + P[k][bi] < 0.5):
                lab[k] = "Mango"
        info["civil"] = (c0 + CIVIL_AROUND, c1 - CIVIL_AROUND)
    church = [k for k in rest if lab.get(k) == "Brown"]
    if church:
        info["church"] = (min(t0(k) for k in church), max(t0(k) + clips[k]["dur"] for k in church))
    # the vornic (sound measured): a long speech of the morning both cameras film
    if speech:
        morning = [[k for k in rest if lab.get(k) in ("Blue", "Rose")]]
        for k in _vornic(morning, clips, speech, {k: dict(speech=(ai.get(k) or {}).get("_p", {}).get("speech", 0.0))
                                                  for k in rest}):
            lab[k] = "Forest"
        info["vornic_by"] = "speech"
    info["scenes"] = len(scenes([(t0(k), t0(k) + clips[k]["dur"], k) for k in rest]))
    for k in rest:
        lab.setdefault(k, "Iris")
    return lab, info
