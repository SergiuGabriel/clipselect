"""Shortmovie / Teaser maker, built on the owner's own pattern (learned from 5 of his shortmovies):

  1. TEASER   (~1 min, song with a drop): before the drop bride / groom getting ready, church, couple, drone;
               after the drop party alternated with couple, quick cuts.
  2. PREGĂTIRI (calm song, ~120-140 s): bride and groom alternating, ends with the couple (first look).
  3. BISERICA  (<= 120 s): church shots, the last part only the couple (leaving the church).
  4. PETRECERE: venue presentation (+ drone) first, then the party shots he selected.

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
PARTS = ["Teaser", "Pregătiri", "Biserica", "Cuplu", "Sala", "Petrecere"]
# target length of a shot (seconds), from his films: ~40-47 cuts/min in the teaser and getting ready, a bit calmer later
TARGET = {"teaser_pre": 1.2, "teaser_post": 0.9, "pregatiri": 1.3, "biserica": 1.4, "cuplu": 1.5, "sala": 1.0,
          "petrecere": 1.0}
FALLBACK = {"drone": ["venue", "couple"], "venue": ["drone", "couple"], "couple": ["bride", "groom"],
            "bride": ["couple", "groom"], "groom": ["couple", "bride"], "church": ["couple"], "party": ["couple", "venue"]}


# ---------------------------------------------------------------- footage (labelled XML from Premiere)

def load_footage(xml_path):
    """Every labelled video clip of the XML = one usable piece: (category, file, in s, out s, order on his timeline)."""
    root = ET.parse(xml_path).getroot()
    files = {}
    for f in root.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            sc = f.find("media/video/samplecharacteristics")
            files[f.get("id")] = dict(path=xmlimport._path(f.findtext("pathurl")), fps=xmlimport._rate(f, 25.0),
                                      dur=int(f.findtext("duration") or 0),
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
            a, b = int(ci.findtext("in", "0")) / cfps, int(ci.findtext("out", "0")) / cfps
            if b - a < 0.4:
                continue
            st = int(ci.findtext("start", "0"))
            pieces.append(dict(cat=CATS[lab], path=info["path"], a=a, b=b, order=st / sfps + t * 1e-3, fps=info["fps"],
                               fdur=info["dur"] / max(1e-6, info["fps"]), w=info["w"], h=info["h"]))
    pieces.sort(key=lambda p: p["order"])
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
                st, en = int(ci.findtext("start", "-1")), int(ci.findtext("end", "-1"))
                if not p or st < 0 or en <= st:
                    continue
                cf = xmlimport._rate(ci, fps)
                items.append(dict(path=p, start=st / fps, end=en / fps, a=int(ci.findtext("in", "0")) / cf))
        if not items:
            raise ValueError("No audio clips in this XML.")
        dur = max(i["end"] for i in items)
        x = np.zeros(int(dur * SR) + SR, np.float32)
        cache = {}
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
        spans = {}
        for it in items:
            sp = spans.setdefault(it["path"], [it["start"], it["end"]])
            sp[0], sp[1] = min(sp[0], it["start"]), max(sp[1], it["end"])
        songs = sorted((s for s in spans.values() if s[1] - s[0] >= 15), key=lambda s: s[0])
        return dict(kind="xml", items=items, x=x, duration=dur, song_starts=[s[0] for s in songs[1:]])
    x = sync.audio_pcm(path)
    return dict(kind="file", path=path, x=x, duration=len(x) / SR, song_starts=[])


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


BOUNDS = [("drop", "Drop"), ("teaser_end", "Teaser ends (after the drop)"), ("pregatiri_end", "Pregătiri ends"),
          ("biserica_end", "Biserica ends (couple + vows start)"), ("party_start", "Party song starts (venue)"),
          ("venue_end", "Venue ends (party starts)")]


def guess_parts(music):
    """All six boundaries. Song changes from a music XML win; otherwise his usual lengths (teaser ~1 min, getting ready
    ~130 s, church ~100 s, couple = last quarter before the party song, venue presentation ~25 s)."""
    D = music["duration"]
    s = sorted(t for t in music["song_starts"] if 20 < t < D - 10)
    if len(s) >= 3:            # teaser song | calm song | (church song) | party song
        t_end, p_end, party = s[0], s[1], s[-1]
    elif len(s) == 2:          # no own song for the church
        t_end, party = s
        p_end = t_end + 0.6 * (party - t_end)
    elif len(s) == 1:
        t_end = s[0]
        party = max(t_end + 60, min(t_end + 230.0, D * 0.85))
        p_end = t_end + 0.6 * (party - t_end)
    else:
        t_end, p_end, party = min(60.0, D * 0.2), min(190.0, D * 0.6), min(290.0, D * 0.85)
    t_end, p_end, party = sorted([t_end, p_end, party])
    b_end = p_end + 0.75 * (party - p_end)
    venue_end = party + min(25.0, 0.3 * (D - party))
    drop = find_drop(music["x"], 0, t_end)
    return dict(drop=drop, teaser_end=t_end, pregatiri_end=p_end, biserica_end=b_end, party_start=party, venue_end=venue_end)


def valid(b, duration):
    v = [b[k] for k, _ in BOUNDS]
    return all(0 < x for x in v) and all(x < y for x, y in zip(v, v[1:])) and v[-1] < duration


# ---------------------------------------------------------------- the edit

class Pool:
    """Usable pieces per category; every take consumes footage so the same moment is not repeated."""

    def __init__(self, pieces, rng, chronological):
        self.rng, self.chrono = rng, chronological
        self.by = {}
        for p in pieces:
            self.by.setdefault(p["cat"], []).append(dict(p, cur=p["a"]))

    def has(self, cat):
        return any(p["b"] - p["cur"] >= 0.5 for p in self.by.get(cat, []))

    def take(self, cat, length, mode):
        """mode 'teaser': random pieces, from their middle (the teaser previews the best moments);
        otherwise in his timeline order (chronological story) or at random."""
        for c in [cat] + FALLBACK.get(cat, []):
            ps = [p for p in self.by.get(c, []) if p["b"] - p["cur"] >= min(length, 0.8)]
            if not ps:
                continue
            if mode == "teaser":
                p = self.rng.choice(ps)
                mid = (p["a"] + p["b"]) / 2
                s = max(p["a"], min(mid - length / 2 + self.rng.uniform(-0.4, 0.4) * (p["b"] - p["a"]) / 2, p["b"] - length))
                return dict(p, cat=c, s=s, e=min(p["b"], s + length))
            p = ps[0] if self.chrono else self.rng.choice(ps)     # ps keeps his timeline order = the story order
            s = p["cur"]
            e = min(p["b"], s + length)
            p["cur"] = e + 0.2
            return dict(p, cat=c, s=s, e=e)
        # everything of this kind is used up: start reusing it rather than leaving a hole in the edit
        for c in [cat] + FALLBACK.get(cat, []):
            if self.by.get(c):
                for p in self.by[c]:
                    p["cur"] = p["a"]
                return self.take(cat, length, mode)
        return None


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
    for (t0, t1, name), part in zip(sections, ["Teaser", "Teaser", "Pregătiri", "Biserica", "Biserica", "Petrecere", "Petrecere"]):
        if t1 - t0 < 0.5:
            continue
        grid, bpm = beats(music["x"], t0, t1)
        bpms[part] = bpm or bpms.get(part, 0)
        if len(grid) < 2:
            grid = list(np.arange(t0, t1, 0.5))
        bl = float(np.median(np.diff(grid))) if len(grid) > 1 else 0.5
        cuts = [t0] + [g for g in grid if g > t0 + 0.25]
        k, n_in = 0, 0
        while k < len(cuts) and cuts[k] < t1 - 0.3:
            nb = max(1, round(TARGET[name] / bl))
            if rng.random() < 0.25:
                nb = max(1, nb + rng.choice([-1, 1]))
            j = min(len(cuts) - 1, k + nb)
            a, e = cuts[k], (cuts[j] if j > k and cuts[j] <= t1 else t1)
            if e - a < 0.3:
                break
            if name == "teaser_pre":
                cat = "drone" if n_in == 0 and pool.has("drone") else rng.choices(
                    ["bride", "groom", "church", "couple", "drone"], [25, 20, 20, 25, 10])[0]
            elif name == "teaser_post":
                cat = rng.choices(["party", "couple", "bride", "groom"], [45, 35, 10, 10])[0]
            elif name == "pregatiri":
                if (a - t0) / max(1e-6, t1 - t0) > 0.9:
                    cat = "couple"
                else:
                    if n_in % rng.choice([2, 3, 3, 4]) == 0:
                        side ^= 1
                    cat = ["bride", "groom"][side]
            elif name == "biserica":
                cat = "church"
            elif name == "cuplu":
                cat = "couple"
            elif name == "sala":
                cat = "drone" if n_in == 0 and pool.has("drone") else "venue"
            else:
                cat = "party"
            mode = "teaser" if name.startswith("teaser") else "story"
            p = pool.take(cat, e - a, mode)
            if p:
                shots.append((a, a + (p["e"] - p["s"]), p))
            k = j if j > k else k + 1
            n_in += 1
    return dict(shots=shots, bpm=bpms, sections=sections, bounds=dict(b))


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
    marks = [("Teaser", 0.0), ("DROP", bb["drop"]), ("Pregătiri", bb["teaser_end"]), ("Biserica", bb["pregatiri_end"]),
             ("Cuplu + jurăminte", bb["biserica_end"]), ("Petrecere: sala", bb["party_start"]), ("Petrecere: party", bb["venue_end"])]
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
