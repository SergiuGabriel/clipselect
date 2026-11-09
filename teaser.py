"""Shortmovie / Teaser maker, built on the owner's own pattern (learned from 5 of his shortmovies):

  1. TEASER   (~1 min, song with a drop): before the drop bride / groom getting ready, church, couple, drone;
               after the drop party alternated with couple, quick cuts.
  2. GETTING READY (calm song, ~120-140 s): bride and groom alternating, ends with the couple (first look).
  3. CHURCH (<= 120 s): church shots, then only the couple over the end of the vows.
  4. PARTY: venue presentation (+ drone) first, then the party shots he selected.

Categories come from his Premiere label colours (he labels his footage anyway):
Rose bride · Blue groom · Purple couple · Brown church · Yellow / Caribbean venue · Iris party · Violet drone.
Ignored: Tan (interviews), Forest (nests), Lavender (adjustment layers).
Testimonials and vows are added by him in Premiere afterwards; the export carries markers for every part.
"""
import random
import xml.etree.ElementTree as ET
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core
import sync
import xmlimport

CATS = {"Rose": "bride", "Blue": "groom", "Purple": "couple", "Brown": "church", "Yellow": "venue", "Caribbean": "venue",
        "Iris": "party", "Violet": "drone"}
IGNORE = {"Tan", "Forest", "Lavender"}
CAT_COLOR = {"bride": "#f472b6", "groom": "#3b82f6", "couple": "#a855f7", "church": "#a16207", "venue": "#eab308",
             "party": "#7dd3fc", "drone": "#8b5cf6"}
CAT_NAME = {"bride": "Bride", "groom": "Groom", "couple": "Couple", "church": "Church", "venue": "Venue", "party": "Party",
            "drone": "Drone"}
LABEL_OF = {"bride": "Rose", "groom": "Blue", "couple": "Purple", "church": "Brown", "venue": "Yellow", "party": "Iris",
            "drone": "Violet"}
PARTS = ["Teaser", "Getting ready", "Church", "Couple", "Venue", "Party"]
# target length of a shot (seconds), from his films: ~40-47 cuts/min in the teaser and getting ready, a bit calmer later
TARGET = {"teaser_pre": 1.2, "teaser_post": 0.9, "pregatiri": 1.3, "biserica": 1.4, "cuplu": 1.5, "sala": 1.0,
          "petrecere": 1.0}
FALLBACK = {"drone": ["venue", "couple"], "venue": ["drone", "couple"], "couple": ["bride", "groom"],
            "bride": ["couple", "groom"], "groom": ["couple", "bride"], "church": ["couple"], "party": ["couple", "venue"]}


# ---------------------------------------------------------------- footage (labelled XML from Premiere)

def _n(v, d="0"):
    """Frame numbers: integers in Premiere's XML, sometimes written with decimals by other apps."""
    try:
        return int(round(float(v if v not in (None, "") else d)))
    except ValueError:
        return int(d)


def _times(ci, fps, cfps):
    """(start, end) on the timeline in seconds. Next to a transition xmeml writes -1 for start or end."""
    st, en = _n(ci.findtext("start"), "-1"), _n(ci.findtext("end"), "-1")
    cin, cout = _n(ci.findtext("in")), _n(ci.findtext("out"))
    ln = round((cout - cin) / cfps * fps)
    if st < 0 and en >= 0:
        st = en - ln
    if en < 0 and st >= 0:
        en = st + ln
    if st < 0 or en <= st:
        return None
    return st / fps, en / fps


def load_footage(xml_path):
    """Every labelled video clip of the XML = one usable piece: (category, file, in s, out s, order on his timeline)."""
    root = ET.parse(xml_path).getroot()
    files = {}
    for f in root.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            sc = f.find("media/video/samplecharacteristics")
            files[f.get("id")] = dict(path=xmlimport._path(f.findtext("pathurl")), fps=xmlimport._rate(f, 25.0),
                                      dur=_n(f.findtext("duration")),
                                      w=int(sc.findtext("width") or 1920) if sc is not None else 1920,
                                      h=int(sc.findtext("height") or 1080) if sc is not None else 1080)
    seqs = list(root.iter("sequence"))
    if not seqs:
        raise ValueError("No sequence in this XML.")
    seq = max(seqs, key=lambda s: sum(1 for _ in s.iter("clipitem")))
    sfps = xmlimport._rate(seq, 25.0)
    pieces, skipped = [], {}
    vid = seq.find("media/video")
    for t, tr in enumerate(vid.findall("track") if vid is not None else []):
        for ci in tr.findall("clipitem"):
            if ci.find("sequence") is not None:
                skipped["multicam / nested"] = skipped.get("multicam / nested", 0) + 1
                continue
            lab = ci.findtext("labels/label2") or ""
            f = ci.find("file")
            info = files.get(f.get("id")) if f is not None else None
            if not info or not info["path"]:
                continue
            if lab in IGNORE or lab not in CATS:
                skipped[lab or "(no colour)"] = skipped.get(lab or "(no colour)", 0) + 1
                continue
            cfps = xmlimport._rate(ci, sfps)
            a, b = _n(ci.findtext("in")) / cfps, _n(ci.findtext("out")) / cfps
            if b - a < 0.4:
                continue
            tt = _times(ci, sfps, cfps)
            st = tt[0] if tt else 0.0
            pieces.append(dict(cat=CATS[lab], path=info["path"], a=a, b=b, order=st + t * 1e-3, fps=info["fps"],
                               fdur=info["dur"] / max(1e-6, info["fps"]), w=info["w"], h=info["h"]))
    pieces.sort(key=lambda p: p["order"])
    # recording time of every file (timecode, creation time or file date), for the chronological story order
    clocks = {}
    for p in pieces:
        if p["path"] not in clocks:
            try:
                clocks[p["path"]] = sync.media_info(p["path"])["clock"] if Path(p["path"]).exists() else None
            except Exception:
                clocks[p["path"]] = None
    for p in pieces:
        c = clocks.get(p["path"])
        if c is not None and c < 5 * 3600:      # after midnight: still the same wedding day
            c += 86400
        p["clock"] = None if c is None else c + p["a"]
    return pieces, skipped


def footage_summary(pieces):
    out = {}
    for p in pieces:
        c = out.setdefault(p["cat"], [0, 0.0])
        c[0] += 1
        c[1] += p["b"] - p["a"]
    return out


# ---------------------------------------------------------------- music (one audio file or an XML of the music edit)

SR = sync.SR


def load_music(path):
    """Returns dict(kind, path / items, x (mono 4 kHz), duration, song_starts). For an XML the songs are mixed
    together exactly as they sit on his timeline; song_starts are where a new song begins (part boundaries)."""
    if str(path).lower().endswith(".xml"):
        root = ET.parse(path).getroot()
        seq = max(root.iter("sequence"), key=lambda s: sum(1 for _ in s.iter("clipitem")))
        fps = xmlimport._rate(seq, 25.0)
        files = {f.get("id"): xmlimport._path(f.findtext("pathurl")) for f in root.iter("file")
                 if f.get("id") and f.findtext("pathurl")}
        items = []
        aud = seq.find("media/audio")
        for tr in (aud.findall("track") if aud is not None else []):
            for ci in tr.findall("clipitem"):
                f = ci.find("file")
                p = files.get(f.get("id")) if f is not None else None
                cf = xmlimport._rate(ci, fps)
                tt = _times(ci, fps, cf)
                if not p or not tt:
                    continue
                items.append(dict(path=p, start=tt[0], end=tt[1], a=_n(ci.findtext("in")) / cf, track=len(items)))
        if not items:
            raise ValueError("No audio clips in this XML.")
        dur = max(i["end"] for i in items)
        x = np.zeros(int(dur * SR) + SR, np.float32)
        cache = {}
        missing = sorted({Path(it["path"]).name for it in items if not Path(it["path"]).exists()})
        for it in items:
            if not Path(it["path"]).exists():
                continue
            if it["path"] not in cache:
                cache[it["path"]] = sync.audio_pcm(it["path"])
            src = cache[it["path"]]
            s0, n = int(it["a"] * SR), int((it["end"] - it["start"]) * SR)
            seg = src[s0:s0 + n]
            d0 = int(it["start"] * SR)
            x[d0:d0 + len(seg)] += seg
        # where one music piece hands over to the next (a cut or a crossfade), also inside ONE joined file
        long_ = sorted((it for it in items if it["end"] - it["start"] >= 15), key=lambda it: it["start"])
        starts = []
        for it in long_[1:]:
            t = it["start"]
            if all(abs(t - u) > 5 for u in starts):
                starts.append(round(t, 2))
        return dict(kind="xml", items=items, x=x, duration=dur, song_starts=starts, missing=missing)
    x = sync.audio_pcm(path)
    return dict(kind="file", path=path, x=x, duration=len(x) / SR, song_starts=[], missing=[])


def _onset_env(x, sr=SR, rate=100):
    hop = sr // rate
    n = len(x) // hop
    e = np.log1p(1000 * np.sqrt((x[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1)))
    return np.maximum(0, np.diff(e, prepend=e[0]))


def beats(x, t0, t1, rate=100):
    """Beat grid of one part: tempo from the autocorrelation of the onset strength (60-180 BPM, a slight preference
    for ~120), phase = the offset that lands on the strongest onsets."""
    o = _onset_env(x[int(t0 * SR):int(t1 * SR)], SR, rate)
    if len(o) < rate * 4:
        return [], 0.0
    o = o - o.mean()
    ac = np.correlate(o, o, "full")[len(o) - 1:]
    lags = np.arange(int(rate * 60 / 180), int(rate * 60 / 60) + 1)
    w = np.exp(-0.5 * (np.log2(lags / (rate * 0.5))) ** 2 / 0.6)      # prefer ~120 BPM
    P = int(lags[np.argmax(ac[lags] * w)])
    ph = max(range(P), key=lambda f: o[f::P].sum())
    grid = [t0 + (ph + k * P) / rate for k in range(int((len(o) - ph) / P) + 1)]
    return [b for b in grid if b < t1], 60.0 * rate / P


def find_drop(x, t0, t1):
    """The drop of the teaser song: the biggest jump of loudness (2 s after vs 2 s before)."""
    rate = 20
    hop = SR // rate
    seg = x[int(t0 * SR):int(t1 * SR)]
    n = len(seg) // hop
    if n < rate * 8:
        return (t0 + t1) / 2
    e = np.sqrt((seg[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1)) + 1e-9
    db = 20 * np.log10(e)
    k = 2 * rate
    lo, hi = int(0.25 * n), int(0.9 * n)
    best = max(range(max(k, lo), min(n - k, hi)), key=lambda i: db[i:i + k].mean() - db[i - k:i].mean())
    return t0 + best / rate


BOUNDS = [("drop", "Drop"), ("teaser_end", "Teaser ends (after the drop)"), ("pregatiri_end", "Getting ready ends"),
          ("biserica_end", "Church ends (couple + vows start)"), ("party_start", "Party song starts (venue)"),
          ("venue_end", "Venue ends (party starts)")]


# where each moment usually falls, learned from his films (seconds after the previous moment): (min, typical, max)
PRIOR = dict(teaser_end=(30, 50, 75), pregatiri_end=(45, 70, 140), biserica_end=(30, 45, 120),
             party_start=(12, 23, 45), venue_end=(10, 20, 50))


def _novelty(x, rate=2):
    """How much the sound changes at every half second (loudness, brightness, rhythm density), 8 s before vs after."""
    hop = SR // rate
    n = len(x) // hop
    if n < 20:
        return np.zeros(max(n, 0))
    fr = x[:n * hop].reshape(n, hop).astype(np.float64)
    rms = np.log1p(1000 * np.sqrt((fr ** 2).mean(1)))
    zc = (np.abs(np.diff(np.sign(fr), axis=1)) > 0).mean(1)          # brightness proxy
    on = _onset_env(x)[: n * (100 // rate)].reshape(n, -1).mean(1) if n * (100 // rate) <= len(_onset_env(x)) else np.zeros(n)
    F = np.vstack([(f - f.mean()) / (f.std() + 1e-9) for f in (rms, zc, on)])
    k = 8 * rate
    nov = np.zeros(n)
    for t in range(k, n - k):
        nov[t] = np.linalg.norm(F[:, t:t + k].mean(1) - F[:, t - k:t].mean(1))
    return nov


def guess_parts(music):
    """All six moments. Each one is looked for in the window where he usually puts it (learned from his films):
    a cut between music pieces in the XML wins, otherwise the strongest change in the sound, otherwise the typical
    place. The drop is the biggest loudness jump inside the teaser; the party song is found as a big rise in energy."""
    D, x = music["duration"], music["x"]
    cuts = [t for t in music.get("song_starts", []) if 5 < t < D - 5]
    nov = _novelty(x)
    rate = 2

    def pick(lo, typ, hi):
        lo, hi = max(lo, 1.0), min(hi, D - 2)
        if hi <= lo:
            return min(max(typ, 1.0), D - 2)
        inside = [t for t in cuts if lo <= t <= hi]
        if inside:
            return min(inside, key=lambda t: abs(t - typ))
        a, b = int(lo * rate), int(hi * rate)
        if b > a and nov[a:b].max() > 1.2:              # a clear change in the music
            w = nov[a:b] * np.exp(-0.5 * ((np.arange(a, b) / rate - typ) / max(8.0, (hi - lo) / 2)) ** 2)
            return (a + int(np.argmax(w))) / rate
        return typ

    b = {}
    b["teaser_end"] = pick(*PRIOR["teaser_end"])
    t = b["teaser_end"]
    b["pregatiri_end"] = pick(t + PRIOR["pregatiri_end"][0], t + PRIOR["pregatiri_end"][1], t + PRIOR["pregatiri_end"][2])
    p = b["pregatiri_end"]
    # the next change in the music is the PARTY SONG (church + couple sit on one song / the sermon before it):
    # a cut in the XML wins, otherwise the biggest rise in loudness
    lo, hi = p + PRIOR["biserica_end"][0] + PRIOR["party_start"][0], p + PRIOR["biserica_end"][2] + PRIOR["party_start"][2]
    inside = [c for c in cuts if lo <= c <= hi]
    if inside:
        party = min(inside, key=lambda c: abs(c - (p + PRIOR["biserica_end"][1] + PRIOR["party_start"][1])))
    elif hi - lo > 10 and lo < D - 15:
        party = find_drop(x, lo, min(hi, D - 5))
    else:
        party = min(p + PRIOR["biserica_end"][1] + PRIOR["party_start"][1], D - 25)
    b["party_start"] = party
    b["biserica_end"] = max(p + PRIOR["biserica_end"][0], party - PRIOR["party_start"][1])   # couple + vows ~23 s
    v = PRIOR["venue_end"]
    b["venue_end"] = pick(party + v[0], party + v[1], party + v[2])
    b["drop"] = find_drop(x, 3, b["teaser_end"] - 3)
    ks = ["drop", "teaser_end", "pregatiri_end", "biserica_end", "party_start", "venue_end"]
    for k1, k2 in zip(ks, ks[1:]):                       # keep them in order, inside the music
        if b[k2] <= b[k1] + 1:
            b[k2] = b[k1] + 2
    b["venue_end"] = min(b["venue_end"], D - 1)
    return b


def valid(b, duration):
    v = [b[k] for k, _ in BOUNDS]
    return all(0 < x for x in v) and all(x < y for x, y in zip(v, v[1:])) and v[-1] < duration


# ---------------------------------------------------------------- the edit

def _cut(free, s, e):
    """Remove [s, e] from a list of free (a, b) intervals."""
    out = []
    for a, b in free:
        if e <= a or s >= b:
            out.append((a, b))
            continue
        if s > a:
            out.append((a, s))
        if e < b:
            out.append((e, b))
    return [(a, b) for a, b in out if b - a > 0.05]


class Pool:
    """All labelled footage. Rules (from the owner):
    - a moment is NEVER used twice (not even teaser + later part): every take is removed from that FILE's free time,
      for every labelled piece of the same file;
    - the same clip is never used twice in a row when there is another one;
    - chronological = the shots of a part are spread over ALL the material of that kind, in recording order (with a
      little randomness), not just the first clips;
    - 'before' / 'after' the church (recording time): first look / couple shots of the morning go to getting ready,
      couple shots after the church to the couple part, Iris shots after the church are the party."""

    GAP = 0.3   # seconds kept free around every used shot

    def __init__(self, pieces, rng, chronological):
        self.rng, self.chrono = rng, chronological
        self.by_time = bool(pieces) and all(p.get("clock") is not None for p in pieces)
        key = (lambda p: p["clock"]) if self.by_time else (lambda p: p["order"])
        self.by, self.paths = {}, {}
        for p in sorted(pieces, key=key):
            q = dict(p, free=[(p["a"], p["b"])])
            self.by.setdefault(p["cat"], []).append(q)
            self.paths.setdefault(p["path"], []).append(q)
        for c, ps in self.by.items():            # position of every piece inside its kind's material (story order)
            cum = 0.0
            for q in ps:
                q["cum"] = cum
                cum += q["b"] - q["a"]
        self.total = {c: sum(q["b"] - q["a"] for q in ps) for c, ps in self.by.items()}
        ch = [q["clock"] for q in self.by.get("church", []) if q.get("clock") is not None]
        self.church_t = float(np.median(ch)) if self.by_time and ch else None
        pt = [q["clock"] for q in self.by.get("party", []) if q.get("clock") is not None and
              (self.church_t is None or q["clock"] > self.church_t)]
        self.party_t = float(np.median(pt)) if pt else None
        self.used_instead, self.last_path, self.short = {}, None, 0.0

    def has(self, cat):
        return any(b - a >= 0.5 for q in self.by.get(cat, []) for a, b in q["free"])

    def _mark(self, path, s, e):
        for q in self.paths.get(path, []):
            q["free"] = _cut(q["free"], s - self.GAP, e + self.GAP)

    def take(self, cat, length, mode, frac=0.0, when=None, near=None, fallback=True):
        """mode 'teaser': random moments (a preview of the whole day); otherwise the story order (chronological) or
        random (mixed). near = a recording time to stay close to (drone shot of the church / of the venue)."""
        for c in [cat] + (FALLBACK.get(cat, []) if fallback else []):
            for use_when in ((when, None) if when else (None,)):
                cands = []
                for q in self.by.get(c, []):
                    ck = q.get("clock")
                    if use_when and self.church_t is not None and ck is not None:
                        if (use_when == "before" and ck > self.church_t) or (use_when == "after" and ck < self.church_t):
                            continue
                    cands += [(q, a, b) for a, b in q["free"] if b - a >= length]
                if not cands:
                    continue
                other = [x for x in cands if x[0]["path"] != self.last_path]
                cands = other or cands
                if near is not None and self.by_time:
                    q, a, b = min(cands, key=lambda x: abs((x[0].get("clock") or 0) - near))
                    s0 = a + (b - a - length) / 2
                elif mode == "teaser" or not self.chrono:
                    q, a, b = self.rng.choice(cands)
                    s0 = self.rng.uniform(a, b - length)
                else:
                    tot = max(1e-6, self.total.get(c, 1.0))
                    T = (frac + self.rng.uniform(-0.05, 0.05)) * tot
                    def dist(x):
                        q, a, b = x
                        lo, hi = q["cum"] + a - q["a"], q["cum"] + b - q["a"] - length
                        return 0.0 if lo <= T <= hi else min(abs(T - lo), abs(T - hi))
                    q, a, b = min(cands, key=dist)
                    s0 = min(max(a, T - q["cum"] + q["a"]), b - length)
                self._mark(q["path"], s0, s0 + length)
                self.last_path = q["path"]
                if c != cat:
                    self.used_instead[(cat, c)] = self.used_instead.get((cat, c), 0) + 1
                return dict(q, cat=c, s=s0, e=s0 + length)
        return None

    def extend(self, shot, extra):
        """No new footage left: let the previous shot run longer (only if that footage is still unused)."""
        q = next((x for x in self.paths.get(shot["path"], []) if x["a"] <= shot["e"] < x["b"] + 1e-6), None)
        if q is None:
            return False
        for a, b in q["free"]:
            if a <= shot["e"] + self.GAP + 0.01 and b >= shot["e"] + extra + self.GAP:
                self._mark(q["path"], shot["e"], shot["e"] + extra)
                shot["e"] += extra
                return True
        return False


def build(pieces, music, b, seed=1, chronological=True):
    """b = the six boundaries (see BOUNDS). Returns dict(shots=[(t0, t1, piece)], bpm per part, sections, bounds)."""
    rng = random.Random(seed)
    pool = Pool(pieces, rng, chronological)
    D = music["duration"]
    sections = [(0.0, b["drop"], "teaser_pre"), (b["drop"], b["teaser_end"], "teaser_post"),
                (b["teaser_end"], b["pregatiri_end"], "pregatiri"), (b["pregatiri_end"], b["biserica_end"], "biserica"),
                (b["biserica_end"], b["party_start"], "cuplu"), (b["party_start"], b["venue_end"], "sala"),
                (b["venue_end"], D, "petrecere")]
    bpms = {}
    shots = []
    side = 0
    block, block_left = "bride", 0
    for (t0, t1, name), part in zip(sections, ["Teaser", "Teaser", "Getting ready", "Church", "Church", "Party", "Party"]):
        if t1 - t0 < 0.5:
            continue
        grid, bpm = beats(music["x"], t0, t1)
        bpms[part] = bpm or bpms.get(part, 0)
        if len(grid) < 2:
            grid = list(np.arange(t0, t1, 0.5))
        bl = float(np.median(np.diff(grid))) if len(grid) > 1 else 0.5
        cuts = [t0] + [g for g in grid if g > t0 + 0.25]
        k, n_in = 0, 0
        while k < len(cuts) and cuts[k] < t1 - 0.35:
            nb = max(1, round(TARGET[name] / bl))
            if rng.random() < 0.25:
                nb = max(1, nb + rng.choice([-1, 1]))
            j = min(len(cuts) - 1, k + nb)
            a, e = cuts[k], (cuts[j] if j > k and cuts[j] <= t1 else t1)
            if t1 - e < 0.35:                        # never leave a rest too short for a shot at the end of a part
                e = t1
            if e - a < 0.3:
                break
            spare_drone = len(pool.by.get("drone", [])) > 2      # keep the drone shots for church / venue openings
            if name == "teaser_pre":
                cat = "drone" if n_in == 0 and spare_drone else rng.choices(
                    ["bride", "groom", "church", "couple", "drone"], [25, 20, 20, 25, 10 if spare_drone else 0])[0]
            elif name == "teaser_post":
                cat = rng.choices(["party", "couple", "bride", "groom"], [45, 35, 10, 10])[0]
            elif name == "pregatiri":
                # blocks of 2-4 shots: bride / groom alternating, with couple blocks mixed in (more towards the end)
                pos = (a - t0) / max(1e-6, t1 - t0)
                if n_in == 0 or block_left <= 0:
                    block_left = rng.choice([2, 3, 3, 4])
                    if rng.random() < 0.15 + 0.35 * pos and pool.has("couple"):
                        block = "couple"
                    else:
                        side ^= 1
                        block = ["bride", "groom"][side]
                cat = "couple" if pos > 0.92 else block
                block_left -= 1
            elif name == "biserica":
                cat = "drone" if n_in == 0 and pool.has("drone") else "church"      # every place opens with the drone
            elif name == "cuplu":
                cat = "couple"
            elif name == "sala":
                cat = "drone" if n_in == 0 and pool.has("drone") else "venue"
            else:
                cat = "party"
            mode = "teaser" if name.startswith("teaser") else "story"
            frac = (a - t0) / max(1e-6, t1 - t0)
            when = {"pregatiri": "before", "cuplu": "after", "petrecere": "after", "sala": "after"}.get(name)
            if name == "teaser_post" and cat == "party":
                when = "after"                      # Iris before the church is the first look, not the party
            near = None
            if cat == "drone" and name == "biserica":
                near = pool.church_t
            elif cat == "drone" and name == "sala":
                near = pool.party_t
            if cat == "drone" and name in ("biserica", "sala"):
                p = pool.take("drone", e - a, mode, frac=frac, near=near, fallback=False) or \
                    pool.take("church" if name == "biserica" else "venue", e - a, mode, frac=frac, when=when)
            else:
                p = pool.take(cat, e - a, mode, frac=frac, when=when, near=near)
            if p:
                shots.append([a, a + (p["e"] - p["s"]), p])
            elif shots and shots[-1][1] >= a - 0.05 and pool.extend(shots[-1][2], e - a):
                shots[-1][1] = e                    # nothing new left: the previous shot runs longer
            else:
                pool.short += e - a                 # no unused footage at all for this moment
            k = j if j > k else k + 1
            n_in += 1
        # a tiny rest at the end of the part (shorter than a shot): the last shot runs to the boundary
        if shots and t0 <= shots[-1][0] < t1 and t1 - shots[-1][1] > 0.01:
            if pool.extend(shots[-1][2], t1 - shots[-1][1]):
                shots[-1][1] = t1
    shots = [tuple(x) for x in shots]
    return dict(shots=shots, bpm=bpms, sections=sections, bounds=dict(b), used_instead=pool.used_instead, short=pool.short,
                order=("recording time" if pool.by_time else "your sequence order") if chronological else "mixed")


def export_xml(edit, music, out_path, name, fps=25.0):
    rate_xml, sf = core._rate(fps)
    ids = dict(n=0)
    defined = {}

    def nid():
        ids["n"] += 1
        return f"clipitem-{ids['n']}"

    def vfile(p):
        if p["path"] in defined:
            return f'<file id="{defined[p["path"]]}"/>'
        defined[p["path"]] = f"file-{len(defined) + 1}"
        frate, ffps = core._rate(p["fps"])
        return (f'<file id="{defined[p["path"]]}"><name>{escape(Path(p["path"]).name)}</name>'
                f'<pathurl>{escape(core._url(p["path"]))}</pathurl>{frate}<duration>{int(p["fdur"] * ffps)}</duration>'
                f'<media><video>{core._sc(frate, p["w"], p["h"], "none")}</video></media></file>')

    v = []
    for t0, t1, p in edit["shots"]:
        st, en = round(t0 * sf), round(t1 * sf)
        if en <= st:
            continue
        fin = round(p["s"] * sf)
        fout = fin + (en - st)
        sdur = max(fout, int(p["fdur"] * sf))
        v.append(f'<clipitem id="{nid()}"><name>{escape(Path(p["path"]).name)}</name><duration>{sdur}</duration>{rate_xml}'
                 f'<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fout}</out>'
                 f'<labels><label2>{LABEL_OF[p["cat"]]}</label2></labels>{vfile(p)}</clipitem>')
    a_items = []
    if music["kind"] == "file":
        arate, ach = sync.audio_info(music["path"])
        mitems = [dict(path=music["path"], start=0.0, end=music["duration"], a=0.0)]
    else:
        mitems = music["items"]
    afile = {}
    tracks_a = [[], []]
    for it in mitems:
        if not Path(it["path"]).exists():
            continue
        r, ch = sync.audio_info(it["path"])
        if it["path"] not in afile:
            afile[it["path"]] = f"file-a{len(afile) + 1}"
            fx = (f'<file id="{afile[it["path"]]}"><name>{escape(Path(it["path"]).name)}</name>'
                  f'<pathurl>{escape(core._url(it["path"]))}</pathurl>{rate_xml}<duration>{int(it["end"] * sf) + 1}</duration>'
                  f'<media><audio><samplecharacteristics><depth>16</depth><samplerate>{r}</samplerate></samplecharacteristics>'
                  f'<channelcount>{ch}</channelcount></audio></media></file>')
        else:
            fx = f'<file id="{afile[it["path"]]}"/>'
        st, en = round(it["start"] * sf), round(it["end"] * sf)
        fin = round(it["a"] * sf)
        for k in range(min(2, max(1, ch))):
            body = fx if k == 0 else f'<file id="{afile[it["path"]]}"/>'
            tracks_a[k].append(f'<clipitem id="{nid()}"><name>{escape(Path(it["path"]).name)}</name><duration>{fin + en - st}</duration>'
                               f'{rate_xml}<start>{st}</start><end>{en}</end><in>{fin}</in><out>{fin + en - st}</out>{body}'
                               f'<sourcetrack><mediatype>audio</mediatype><trackindex>{k + 1}</trackindex></sourcetrack></clipitem>')
    bb = edit["bounds"]
    marks = [("Teaser", 0.0), ("DROP", bb["drop"]), ("Getting ready", bb["teaser_end"]), ("Church", bb["pregatiri_end"]),
             ("Couple + vows", bb["biserica_end"]), ("Party: venue", bb["party_start"]), ("Party", bb["venue_end"])]
    markers = "".join(f'<marker><name>{escape(n)}</name><comment></comment><in>{round(t * sf)}</in><out>-1</out></marker>' for n, t in marks)
    total = round(music["duration"] * sf)
    trk = lambda its: f'<track>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    first = edit["shots"][0][2] if edit["shots"] else dict(w=1920, h=1080)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{total}</duration>{rate_xml}{markers}'
           f'<media><video><format>{core._sc(rate_xml, first["w"], first["h"], "none")}</format>{trk(v)}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{"".join(trk(t) for t in tracks_a if t)}</audio></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return len(v)


import hashlib as _h
PASSWORD_SHA256 = "98f03e5c0c28060eea8c17d88d36cd180a7b7932bfc90fbb7d03307e7c2bfed7"   # only the fingerprint of the password is stored, never the password itself


def check_password(pw):
    return _h.sha256(pw.encode("utf-8")).hexdigest() == PASSWORD_SHA256
