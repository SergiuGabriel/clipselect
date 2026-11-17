"""Speech transcription (local, free): interviews, speeches, the vornic, the priest's sermon.

Engine: Whisper on this computer (MLX on the graphics chip of Apple Silicon Macs, else faster-whisper on the processor),
the model downloaded once into <data>/ai_model/whisper. "best" = large-v3, "fast" = large-v3-turbo. Nothing is uploaded.
Results next to the file: <name>.txt (text with times), <name>.srt (subtitles), <name>_raport.txt (quality report).

v4 engine (rewritten from zero, v3.11.0). Nothing about a particular wedding, voice or camera is written here: every
threshold is measured on the recording itself.
  1. Who speaks when (speakers.analyse): speech regions (VAD) and, per region, the interviewee / the videographer,
     measured from the levels of the microphones.
  2. Whisper hears the WHOLE file in one go (its own 30 s windows keep the context, so words are not lost or misheard
     at chunk edges), always with word times.
  3. Cleaning: Whisper's loops, its typical "subtitle" inventions and anything heard where the VAD found no speech are
     removed (counted in the report). Speech regions with no word at all are transcribed again on their own, so a word
     like "Superb!" between a question and an answer is never lost.
  4. Sentences: a piece ends at the end of a sentence (. ? ! … or a capital letter after a real pause where Whisper
     forgot the full stop), at every change of speaker and after every question. A pause alone NEVER cuts a sentence
     (people stop to think in the middle of a sentence). Only a sentence longer than 8 s is cut again, at its best
     inner point (a real pause, after a comma, before "și / dar / așa că"), never after a word that cannot end a
     phrase ("o", "să", "că", "la", "decât"...) and never into a part shorter than 1.5 s.
  5. Every border is moved into the nearest real pause of the sound (when there is one close by).
"""
import logging
import re
import subprocess
import sys
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core

SR = 16000
MODELS = {"fast": "large-v3-turbo", "best": "large-v3"}
MLX_MODELS = {"fast": "mlx-community/whisper-large-v3-turbo", "best": "mlx-community/whisper-large-v3-mlx"}
LANGS = {"ro": "ro", "en": "en", "auto": None}

VERSION = 9            # transcripts made by an older engine ("tv" lower) are marked ↻ and redone by Transcribe

MAX_PIECE = 8.0        # a code lasts at most 8 s (Claude can only cut between codes)
MIN_PIECE = 0.8        # the report counts codes shorter than this (whole short sentences are fine: "Te iubesc.")
MIN_SPLIT = 1.5        # a long sentence is never cut into a part shorter than this
SPLIT_AT = 7.5         # sentences are split down to this, so moving a border into a pause never passes MAX_PIECE
LONG_SILENCE = 2.0     # a silence this long ends a piece even without punctuation

SIL_DB, SIL_MIN, SNAP = -38.0, 0.15, 0.6       # a real pause: under the pause threshold for 0.15 s, looked for within +-0.6 s


# ------------------------------------------------------------------ the engine (MLX / faster-whisper)

def available():
    """'' when the engine is in this build, else the reason."""
    try:
        import faster_whisper
        return "" if faster_whisper else "missing"
    except Exception as e:
        return str(e)


def mlx_ok():
    """Whisper on the Mac's graphics chip (Apple MLX): several times faster. Only on Apple Silicon, only when the app was
    built with it; anything wrong -> faster-whisper on the processor."""
    import platform
    if sys.platform != "darwin" or platform.machine() != "arm64":
        return False
    try:
        import mlx.core  # noqa: F401
        import mlx_whisper  # noqa: F401
        return True
    except Exception:
        return False


def load_model(base, quality="fast", progress=None):
    """MLX (graphics chip) when available, else faster-whisper ('best' = float32, 'fast' = int8)."""
    folder = Path(base) / "ai_model" / "whisper"
    folder.mkdir(parents=True, exist_ok=True)
    if progress:
        progress("Loading the speech model (the first time it is downloaded once, about 1.5-3 GB)…", 0.0)
    if mlx_ok() and not (folder / "mlx_failed").exists():
        try:
            from huggingface_hub import snapshot_download
            local = snapshot_download(MLX_MODELS.get(quality, MLX_MODELS["fast"]), cache_dir=str(folder / "mlx"))
            return dict(engine="mlx", path=local, base=str(base), quality=quality)
        except Exception:
            logging.exception("mlx whisper model: falling back to faster-whisper")
    return _fw_model(folder, quality)


def _fw_model(folder, quality):
    from faster_whisper import WhisperModel
    ct = "float32" if quality == "best" else "int8"
    try:
        return WhisperModel(MODELS.get(quality, MODELS["fast"]), device="auto", compute_type=ct, download_root=str(folder))
    except Exception:
        return WhisperModel(MODELS.get(quality, MODELS["fast"]), device="cpu", compute_type=ct, download_root=str(folder))


def _engine(model, opts):
    """One function for every engine: (sound) -> [dict(start, end, text, words=[(s, e, word, probability)],
    nsp = no-speech probability, logp = average log probability, comp = compression ratio)]."""
    def seg(start, end, text, words, nsp, logp, comp):
        return dict(start=float(start), end=float(end), text=str(text or ""), words=words,
                    nsp=float(nsp or 0.0), logp=float(logp or 0.0), comp=float(comp or 0.0))

    if isinstance(model, dict) and model.get("engine") == "mlx":
        import mlx_whisper

        def run(y, report=None):
            r = mlx_whisper.transcribe(y, path_or_hf_repo=model["path"], verbose=None, **opts)
            return [seg(s["start"], s["end"], s.get("text", ""),
                        [(w["start"], w["end"], w["word"], w.get("probability", 1.0)) for w in s.get("words", [])
                         if w.get("end", 0) > w.get("start", 0)],
                        s.get("no_speech_prob"), s.get("avg_logprob"), s.get("compression_ratio"))
                    for s in r.get("segments", [])]
        return run

    def run(y, report=None):
        segs, _info = model.transcribe(y, vad_filter=False, beam_size=5, **opts)
        out, dur = [], max(1.0, len(y) / SR)
        for s in segs:                       # a generator: Whisper works while we read, so the progress is real
            out.append(seg(s.start, s.end, s.text,
                           [(w.start, w.end, w.word, getattr(w, "probability", 1.0)) for w in (s.words or []) if w.end > w.start],
                           getattr(s, "no_speech_prob", 0.0), getattr(s, "avg_logprob", 0.0),
                           getattr(s, "compression_ratio", 0.0)))
            if report:
                report(min(1.0, float(s.end) / dur))
        return out
    return run


# ------------------------------------------------------------------ reading the sound

def _channels(path):
    """Every audio channel of the file as mono 16 kHz arrays (Sony MXF: one stream per channel, read in ONE pass)."""
    import tempfile
    import sync
    exe = core.ffmpeg_exe()
    streams = sync._audio_streams(str(path))
    if not streams:
        raise ValueError("No sound in this file")
    out = []
    with tempfile.TemporaryDirectory() as td:
        cmd = [exe, "-v", "error", "-nostdin", "-i", str(path)]
        files = []
        for i, ch in enumerate(streams[:8]):
            o = str(Path(td) / f"a{i}.raw")
            cmd += ["-map", f"0:a:{i}", "-vn", "-ar", str(SR), "-f", "f32le", o]
            files.append((o, min(ch, 8)))
        subprocess.run(cmd, capture_output=True, **core._NOWIN)
        for o, ch in files:
            try:
                x = np.fromfile(o, np.float32)
            except Exception:
                continue
            if len(x) < SR // 2 * ch:
                continue
            x = x[:len(x) // ch * ch].reshape(-1, ch)
            for k in range(ch):
                out.append(np.ascontiguousarray(x[:, k]))
    return out


def clarity(x):
    """How clearly speech stands out on a channel: loud parts (p90) above the quiet floor (p20), in dB. A lavalier
    (close to the mouth) scores higher than a camera microphone (room sound)."""
    n = SR // 20
    m = len(x) // n
    if m < 20:
        return -1e9
    e = np.sqrt((x[:m * n].reshape(m, n).astype(np.float64) ** 2).mean(1)) + 1e-9
    if np.percentile(e, 90) < 1e-4:
        return -1e9                                  # silent channel
    db = 20 * np.log10(e)
    return float(np.percentile(db, 90) - np.percentile(db, 20))


def read_audio(path):
    """The sound of a file, mono 16 kHz, from its CLEAREST channel (never a mix: a mix of the lavalier and the camera
    microphone makes Whisper mishear words)."""
    try:
        chans = _channels(path)
    except Exception:
        chans = []
    good = [(clarity(x), k, x) for k, x in enumerate(chans)]
    good = [g for g in good if g[0] > -1e8]
    if good:
        return max(good, key=lambda g: (g[0], -g[1]))[2]
    cmd = [core.ffmpeg_exe(), "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True, **core._NOWIN).stdout
    x = np.frombuffer(out, np.float32).copy()
    if len(x) < SR // 2:
        raise ValueError("No sound in this file")
    return x


def couple_names(path):
    """The couple's names from the wedding folder ("NUNTA 22 AUGUST 2026 Florin si Miruna", "NUNTA 4 IULIE Alexandra si
    Vlad 2026", "WEDDING 4 JULY Alexandra and Vlad 2026"), so Whisper writes them right."""
    for part in reversed(Path(path).parts):
        m = re.match(r"(?i)(?:nunta|wedding)\s+\d{1,2}\s+\S+\s+(?:\d{4}\s+)?(.+?)\s+(?:si|și|and|&)\s+(.+?)(?:\s+\d{4})?$",
                     part.strip())
        if m:
            return [m.group(1).strip(), m.group(2).strip()]
    return []


def hint(path, lang):
    names = couple_names(path)
    if lang == "en":
        return "A wedding interview." + (f" The couple: {names[0]} and {names[1]}." if names else "")
    return ("Interviu de nuntă, în limba română, scris corect, cu diacritice." +
            (f" Mirii: {names[0]} și {names[1]}." if names else "") + " Cuvinte: nunta, mireasa, mirele, biserica, nașii.")


# ------------------------------------------------------------------ measuring pauses in the sound

def _db(x):
    n = int(SR * 0.01)
    k = len(x) // n
    if k == 0:
        return np.zeros(0)
    e = (x[:k * n].astype("float64").reshape(k, n) ** 2).mean(axis=1)
    return 10 * np.log10(e + 1e-12)


def _thr(d):
    """The pause threshold of this stretch of sound, always relative to the recording: about -38 dB on a clean one,
    18 dB under the speaker's loud parts on a quiet one, close to the noise floor on a noisy one (wind, outside)."""
    floor, loud = float(np.percentile(d, 15)), float(np.percentile(d, 90))
    return max(min(SIL_DB, loud - 18.0), floor + 0.3 * (loud - floor))


def pauses(x, a, b):
    """Real pauses in the sound between a and b seconds: [(start, end)], under the pause threshold for >= 0.15 s."""
    if x is None:
        return []
    lo, hi = max(0, int((a - 3.0) * SR)), min(len(x), int((b + 3.0) * SR))
    d = _db(x[lo:hi])
    if not len(d):
        return []
    quiet = d < _thr(d)
    out, k = [], 0
    while k < len(quiet):
        if quiet[k]:
            j = k
            while j < len(quiet) and quiet[j]:
                j += 1
            t0, t1 = lo / SR + k * 0.01, lo / SR + j * 0.01
            if t1 - t0 >= SIL_MIN and t1 > a and t0 < b:
                out.append((t0, t1))
            k = j
        else:
            k += 1
    return out


def snap(x, t, lo=None, hi=None):
    """The nearest real pause to a cut point t (within +-0.6 s and inside [lo, hi]): (pause start, pause end), or None."""
    lo = t - SNAP if lo is None else max(lo, t - SNAP)
    hi = t + SNAP if hi is None else min(hi, t + SNAP)
    if hi <= lo:
        return None
    best = None
    for p0, p1 in pauses(x, lo, hi):
        p0, p1 = max(p0, lo), min(p1, hi)
        if p1 - p0 < SIL_MIN * 0.5:
            continue
        dist = 0.0 if p0 <= t <= p1 else min(abs(t - p0), abs(t - p1))
        if best is None or dist < best[0]:
            best = (dist, p0, p1)
    return None if best is None else (best[1], best[2])


def in_pause(x, t, half=0.03):
    """MEASURED: is the moment t in a real pause (the 10 ms frames around it under the pause threshold)?"""
    if x is None:
        return None
    lo, hi = max(0, int((t - 3.0) * SR)), min(len(x), int((t + 3.0) * SR))
    d = _db(x[lo:hi])
    if not len(d):
        return None
    thr = _thr(d)
    k0, k1 = int((t - half - lo / SR) / 0.01), int((t + half - lo / SR) / 0.01) + 1
    seg = d[max(0, k0):max(0, min(len(d), k1))]
    return bool(len(seg)) and float(seg.max()) < thr


def pause_between(x, a, b):
    """MEASURED: is there a real pause (>= 0.08 s under the threshold) between a and b? None without sound."""
    if x is None:
        return None
    lo, hi = min(a, b) - 0.05, max(a, b) + 0.05
    return any(min(p1, hi) - max(p0, lo) >= 0.08 for p0, p1 in pauses(x, lo, hi))


def _pause_len(x, w1, w2, slack=0.45):
    """How long the longest real pause near the gap between two words is: searched from the middle of the first word
    to the middle of the second one, widened to +-slack around the gap (word times measured on real interviews were
    up to ~0.5 s off). 0 when there is none; the gap between the word times when there is no sound."""
    if x is None:
        return max(0.0, w2[0] - w1[1])
    gap = (w1[1] + w2[0]) / 2
    lo, hi = min((w1[0] + w1[1]) / 2, gap - slack), max((w2[0] + w2[1]) / 2, gap + slack)
    if hi <= lo:
        return 0.0
    best = 0.0
    for p0, p1 in pauses(x, lo, hi):
        best = max(best, min(p1, hi) - max(p0, lo))
    return best


def _quietest(x, a, b):
    """The moment with the least energy in the sound between a and b (50 ms smoothing)."""
    lo, hi = max(0, int(a * SR)), min(len(x), int(b * SR))
    d = _db(x[lo:hi])
    if len(d) < 3:
        return (a + b) / 2
    d = np.convolve(d, np.ones(5) / 5, mode="same")
    return lo / SR + (int(np.argmin(d)) + 0.5) * 0.01


def _at(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


# ------------------------------------------------------------------ words: language rules (general, no names)

LINKS = ("și", "si", "dar", "așa", "asa", "pentru", "deci", "iar", "însă", "insa", "pentru că", "and", "but", "so", "because")
NO_END = {"de", "la", "cu", "pe", "în", "in", "din", "pentru", "lui", "că", "ca", "și", "si", "sau", "dar", "a", "al", "ale",
          "ai", "o", "un", "unei", "unui", "spre", "despre", "după", "dupa", "fără", "fara", "prin", "către", "catre", "între",
          "intre", "sub", "peste", "să", "sa", "mai", "foarte", "cel", "cea", "cei", "cele", "lu", "decât", "decat", "încât",
          "incat", "care", "cum", "când", "cand", "dacă", "daca", "unde", "nu", "ne", "se", "te", "mă", "ma", "îmi", "imi",
          "își", "isi", "le", "îl", "il", "am", "ai", "au", "aș", "as", "ar", "ați", "ati", "vom", "voi", "va", "vor", "e",
          "este", "sunt", "fi", "într-un", "într-o", "dintr-un", "dintr-o", "printr-un", "printr-o", "s-a", "s-au", "m-am",
          "m-a", "ne-am", "ne-a", "v-ați", "v-ati", "v-a", "i-am", "i-a", "mi-a", "mi-am", "ți-a", "ti-a", "ți-am", "l-am",
          "l-a", "le-am", "le-a", "și-a", "si-a", "și-au", "s-ar", "n-am", "n-a", "fiecare", "orice", "oricare", "acel", "acea",
          "acest", "această", "aceste", "acești", "același", "aceeași", "aceleași", "niște", "nişte", "câțiva", "câteva",
          "every", "each", "this", "these", "those", "some", "any", "very", "the", "a", "an", "of", "to", "with", "and", "for", "on", "at", "my", "your", "his", "her",
          "our", "their", "from", "by", "about", "is", "are", "was", "be", "i", "we", "you", "that", "than", "if", "when"}
# words after which a phrase cannot end: a cut there leaves "Sunt | sigură", "… o | să fie", "într-un | an", "s-au | așezat"
NO_START = {"decât", "decat", "încât", "incat", "than"}
# words a phrase cannot start with: "nu e mai rău | decât să nu se țină nunta"

FILLERS = {"da", "păi", "pai", "nu știu", "nu stiu", "deci", "adică", "adica", "ăă", "ăăă", "mm", "ok", "bine", "yes", "well"}

# Whisper's typical inventions in silence / noise (it learned on subtitled videos). General per language, never
# wedding words: a whole segment matching one of these where the sound is not clear speech is removed.
HALLUCINATIONS = [
    r"nu uita(ți|ti)? să", r"abona(ți|ti)[- ]?vă", r"like( și| si)? (subscribe|share)", r"mulțumesc pentru vizionare",
    r"mulțumim pentru vizionare", r"vă mulțumesc pentru (atenție|vizionare)", r"subtitr", r"traducerea( și| si)? adaptarea",
    r"lăsați un comentariu", r"nu lăsați", r"rețele(le)? sociale", r"pe (data|curând) viitoare", r"la revedere\W*$",
    r"thanks? (you )?for watching", r"subscribe", r"like and share", r"see you (in the )?next", r"subtitles by",
    r"amara\.org", r"www\.", r"\.com\b",
]
_HALL = re.compile("|".join(f"(?:{h})" for h in HALLUCINATIONS), re.I)


def _norm(t):
    return re.sub(r"[^\w]+", " ", str(t).lower()).strip()


def _core(t):
    return re.sub(r"[^\w\-]", "", str(t)).strip("-")


def _ends(t):
    return str(t).strip().rstrip('"\'»”)').endswith((".", "?", "!", "…"))


def _asks(t):
    return str(t).strip().rstrip('"\'»”)').endswith("?")


def vocabulary(words, names=(), lang="ro"):
    """What the transcript itself says about its words (no list of names): the words seen with a small letter, how many
    times each word appears, the names chosen in the program and the common words of the language (wordfreq)."""
    import wordfreq
    small, count = set(), {}
    for w in words:
        c = _core(w[2])
        if not c or not c[0].isalpha():
            continue
        k = c.lower()
        count[k] = count.get(k, 0) + 1
        if c[0].islower():
            small.add(k)
    given = set()
    for n in names:
        given |= {x.lower() for x in re.findall(r"[\w\-]+", str(n))}
    return dict(small=small, count=count, names=given, common=wordfreq.common(lang))


def proper_nouns(words, names=(), lang="ro"):
    """The words this transcript treats as names: never with a small letter and either said more than once or not a
    common word, plus the names chosen in the program."""
    v = vocabulary(words, names, lang)
    return {k for k in v["count"] if k not in v["small"] and (v["count"][k] > 1 or k not in v["common"])} | v["names"]


def _cap_start(prev, w, voc):
    """Whisper forgot the full stop: a capitalised word after a word without punctuation starts a new sentence when the
    transcript shows it is an ordinary word (also written with a small letter, or said once and a common word). Never
    before a chosen name, never after a word a phrase cannot end with, never for "I" or an acronym."""
    p = str(prev).strip()
    if not p or not p[-1].isalnum() or _core(p).lower() in NO_END:
        return False
    c = _core(w)
    if not c or not c[0].isupper() or c.isupper() or c in ("I", "I'm"):
        return False
    k = c.lower()
    if k in voc["names"]:
        return False
    return k in voc["small"] or (voc["count"].get(k, 0) == 1 and k in voc["common"])


def estimate_words(a, b, text):
    """A segment without word times: its words get times by their number of letters (an ESTIMATE: the borders are
    moved to real pauses of the sound afterwards). 5th element True = estimated."""
    toks = re.findall(r"\S+", str(text))
    if not toks:
        return []
    weights = [len(_core(t)) + 1 for t in toks]
    tot, out, pos = float(sum(weights)), [], a
    for t, wgt in zip(toks, weights):
        d = (b - a) * wgt / tot
        out.append((pos, pos + d, " " + t, 0.5, True))
        pos += d
    return out


# ------------------------------------------------------------------ cleaning what Whisper heard

def _loop(text):
    """A segment that is one phrase said again and again (a Whisper loop)."""
    w = _norm(text).split()
    if len(w) < 6:
        return False
    for n in range(1, 6):
        grams = [" ".join(w[i:i + n]) for i in range(0, len(w) - n + 1, n)]
        if len(grams) >= 3 and max(grams.count(g) for g in set(grams)) / len(grams) >= 0.6:
            return True
    return False


def _speech_cover(a, b, regions):
    tot = 0.0
    for ra, rb, _lab in regions:
        tot += max(0.0, min(b, rb) - max(a, ra))
    return tot / max(1e-6, b - a)


def _complete_words(s, text, shift=0.0):
    """The words of one segment with their times; when the engine gave fewer words than the text has (the last words of
    a segment without times), the missing ones get estimated times after the last timed word, so no word is lost."""
    ws = [(shift + float(w[0]), shift + float(w[1]), w[2], float(w[3]), False) for w in s["words"]]
    if not ws:
        return estimate_words(shift + s["start"], shift + s["end"], text)
    have, toks = [_norm(w[2]) for w in ws], re.findall(r"\S+", text)
    norm = [_norm(t) for t in toks]
    norm_have = [h for h in have if h]
    norm_toks = [t for t in norm if t]
    if len(norm_toks) > len(norm_have) and norm_toks[:len(norm_have)] == norm_have:
        rest, k = [], 0
        for t, n in zip(toks, norm):
            if not n:
                continue
            k += 1
            if k > len(norm_have):
                rest.append(t)
        a = ws[-1][1]
        b = max(a + 0.25 * len(rest), shift + float(s["end"]))
        ws += estimate_words(a, b, " ".join(rest))
    return ws


def clean(segs, regions):
    """Whisper's segments -> (words [(start, end, text, probability, estimated)], removed [text]).
    Removed: segments Whisper itself marks as no speech, loops, a segment equal to one of the two before it, the
    typical subtitle inventions, and words heard where the speech detection found no speech (a group of such words is
    kept only when Whisper is sure of it: 3+ words with probability >= 0.6 and no invention pattern)."""
    words, removed, last = [], [], []
    for s in segs:
        text = s["text"].strip()
        if not text:
            continue
        n = _norm(text)
        if (s["nsp"] > 0.6 and s["logp"] < -1.0) or s["comp"] > 2.4 or _loop(text) or (n and n in last):
            removed.append(text)
            continue
        last = (last + [n])[-2:]
        ws = _complete_words(s, text)
        if not ws:
            continue
        cover = _speech_cover(ws[0][0], ws[-1][1], regions) if regions else 1.0
        if _HALL.search(text) and (cover < 0.5 or len(ws) <= 8):
            removed.append(text)
            continue
        words += ws
    if not regions:
        return words, removed
    # Words where the speech detection found no speech. Word times are never exact (measured on real interviews: real
    # words up to ~0.55 s outside a region), so a word is removed only when it is FAR from any speech (> 1 s), or
    # outside it and Whisper itself doubts it (probability < 0.3), or it belongs to a subtitle-invention pattern.
    def dist(w):
        m = (w[0] + w[1]) / 2
        return min((0.0 if ra <= m <= rb else min(abs(m - ra), abs(m - rb))) for ra, rb, _l in regions)
    out, group = [], []

    def flush():
        if not group:
            return
        text = "".join(g[2] for g, _d in group).strip()
        far = all(d > 1.0 for _w, d in group)
        doubt = np.mean([g[3] for g, _d in group]) < 0.3
        if far or doubt or _HALL.search(text):
            removed.append(text)
        else:
            out.extend(g for g, _d in group)
        group.clear()
    for w in words:
        d = dist(w)
        if d <= 0.4:
            flush()
            out.append(w)
        else:
            group.append((w, d))
    flush()
    return out, removed


def recover(words, regions, x, run, cancel=None):
    """Speech regions where no word was kept (a short "Superb!" between a question and an answer, a word Whisper
    skipped) are transcribed again on their own, with 1 s of sound around them. -> (words, still lost [(a, b)])."""
    lost, found = [], []
    for a, b, _lab in regions:
        if b - a < 0.4:
            continue
        got = sum(max(0.0, min(b, w[1]) - max(a, w[0])) for w in words if w[1] > a and w[0] < b)
        if got >= 0.25 * (b - a):
            continue
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        lo, hi = max(0.0, a - 1.0), min(len(x) / SR, b + 1.0)
        try:
            segs = run(np.ascontiguousarray(x[int(lo * SR):int(hi * SR)], dtype=np.float32))
        except Exception:
            logging.exception("region %.1f-%.1f could not be transcribed again", a, b)
            segs = []
        new = []
        for s in segs:
            if not s["text"].strip() or (s["nsp"] > 0.6 and s["logp"] < -1.0) or _HALL.search(s["text"]) or _loop(s["text"]):
                continue
            ws = _complete_words(s, s["text"].strip(), lo)
            new += [w for w in ws if a - 0.15 <= (w[0] + w[1]) / 2 <= b + 0.15
                    and not any(min(w[1], o[1]) - max(w[0], o[0]) > 0.5 * (w[1] - w[0]) for o in words)]
        if new:
            found += new
        else:
            lost.append((a, b))
    return sorted(words + found, key=lambda w: w[0]), lost


def calibrate(words, x):
    """Whisper's word times can all be shifted the same way (measured on real interviews: up to ~0.5-0.8 s early).
    The shift is MEASURED on this recording: after every word that ends a sentence, where the next real pause of the
    sound starts. With at least 5 such sentence ends and a median shift over 0.1 s, every word is moved by it (at most
    0.8 s). -> (words, shift in seconds)."""
    if x is None or len(words) < 10:
        return words, 0.0
    shifts = []
    for k, w in enumerate(words[:-1]):
        if not _ends(w[2]) or words[k + 1][0] - w[1] > 1.5:
            continue
        ps = [p for p in pauses(x, w[1] - 0.3, w[1] + 1.0) if p[0] >= w[1] - 0.3 and p[1] - p[0] >= 0.2]
        if ps:
            shifts.append(ps[0][0] - w[1])
    if len(shifts) < 5:
        return words, 0.0
    d = float(np.median(shifts))
    if abs(d) < 0.1:
        return words, 0.0
    d = max(-0.8, min(0.8, d))
    return [(w[0] + d, w[1] + d) + tuple(w[2:]) for w in words], d


# ------------------------------------------------------------------ words -> pieces

class Segs(list):
    """The pieces of a transcript [(start, end, text)]; .spk = who speaks each piece, .forced = borders (after piece k)
    cut with no pause, .sep = how sure the speaker measurement is, .removed / .lost = what the cleaning found."""
    forced = ()


def _text(ws):
    return "".join(w[2] for w in ws).strip()


def _is_filler(ws):
    t = re.sub(r"[^\w\s]", "", _text(ws).lower()).strip()
    return t in FILLERS or not t


def _word_labels(words, regions):
    """Who says each word: the label of the speech region holding its middle (or the nearest one within 0.3 s). A single
    word whose label differs from both neighbours is unsure ('?'): word times are not exact at a change of speaker."""
    out = []
    for w in words:
        m = (w[0] + w[1]) / 2
        best, dist = "?", 0.31
        for ra, rb, lab in regions:
            d = 0.0 if ra <= m <= rb else min(abs(m - ra), abs(m - rb))
            if d < dist:
                best, dist = lab, d
        out.append(best)
    # a run of another speaker shorter than 0.6 s inside one speaker's words (two words heard on the other mic,
    # inexact word times) is unsure, unless it is a whole question
    k = 0
    while k < len(out):
        j = k
        while j + 1 < len(out) and out[j + 1] == out[k]:
            j += 1
        if out[k] != "?" and words[j][1] - words[k][0] < 0.6 and not _asks(words[j][2]):
            left = next((out[i] for i in range(k - 1, -1, -1) if out[i] != "?"), None)
            right = next((out[i] for i in range(j + 1, len(out)) if out[i] != "?"), None)
            if left is not None and left == right and left != out[k]:
                for i in range(k, j + 1):
                    out[i] = "?"
        k = j + 1
    return out


def _sentences(words, labels, x, voc):
    """Words -> sentences: cut at the end of a sentence (Whisper's punctuation), at a forgotten full stop (a capital
    letter after a real pause), after every question, at a change of a definite speaker that punctuation does not
    already separate, and at every silence longer than LONG_SILENCE. Never at a pause alone."""
    groups, cur, who = [], [], "?"
    for k, w in enumerate(words):
        if cur:
            prev = cur[-1][2].strip()
            gap = w[0] - cur[-1][1]
            lab = labels[k]
            change = lab != "?" and who != "?" and lab != who
            if change:      # a full stop just before / after the change does the separation (word times are inexact)
                near = [words[j][2] for j in range(max(0, k - 3), min(len(words), k + 2)) if j != k - 1]
                if any(_ends(t) for t in near):
                    change = False
            cut = (_asks(prev) or change or gap > LONG_SILENCE or _ends(prev) or
                   (_cap_start(prev, w[2], voc) and _pause_len(x, cur[-1], w, 0.2) >= 0.1))
            if cut:
                groups.append(cur)
                cur, who = [], "?"
        cur.append(w)
        if labels[k] != "?":
            who = labels[k]
    if cur:
        groups.append(cur)
    return groups


def _split_long(ws, x, forced):
    """A sentence longer than MAX_PIECE is cut at its best inner point, again and again until every part is <= 8 s.
    Score of a point: the real pause there (measured in the sound), a comma / colon before it, a linking word after it,
    a capital letter after it (a forgotten full stop); never after a word a phrase cannot end with ("o", "să", "într-un",
    "s-au"...) nor before one a phrase cannot start with ("decât"); parts of at least MIN_SPLIT; a slight preference for
    the middle. A point without a real pause is a FORCED cut (listed in the report); among forced points the quietest
    moment of the sound decides only between equally good ones."""
    if len(ws) < 2 or ws[-1][1] - ws[0][0] <= SPLIT_AT:
        return [ws]
    t0, t1 = ws[0][0], ws[-1][1]
    for need in (MIN_SPLIT, MIN_PIECE, 0.0):
        cands = [k for k in range(1, len(ws)) if ws[k - 1][1] - t0 >= need and t1 - ws[k][0] >= need]
        if cands:
            break
    if not cands:
        cands = list(range(1, len(ws)))

    def score(k):
        prev, nxt = ws[k - 1][2].strip(), ws[k][2].strip()
        p = _pause_len(x, ws[k - 1], ws[k])
        s = 4.0 * min(p, 0.8)
        if prev.endswith((",", ";", ":", "—", "–")):
            s += 1.2
        if _norm(nxt).startswith(LINKS):
            s += 0.8
        c = _core(nxt)
        if c[:1].isupper() and not c.isupper():
            s += 0.6
        pk = _core(prev).lower()
        if pk in NO_END and not (pk == "lui" and not c[:1].isupper()):     # "jurul lui | și" ends, "a lui | Florin" not
            s -= 3.0
        if _core(nxt).lower() in NO_START:
            s -= 3.0
        left, right = ws[k - 1][1] - t0, t1 - ws[k][0]
        s -= 0.08 * abs(left - right)
        if max(left, right) > SPLIT_AT:
            s -= 0.4                               # one more cut will be needed
        return s, p

    scored = {k: score(k) for k in cands}
    bk = max(cands, key=lambda k: scored[k][0])
    if scored[bk][1] < 0.08:                       # no real pause at the best point: a forced cut
        if x is not None:                          # between points about as good, the quietest moment of the sound
            top = scored[bk][0]
            near = [k for k in cands if scored[k][0] >= top - 0.3]
            bk = min(near, key=lambda k: _db(x[int((ws[k - 1][1] - 0.03) * SR):int((ws[k][0] + 0.03) * SR) + 1]).mean()
                     if ws[k][0] + 0.03 > ws[k - 1][1] - 0.03 else 0.0)
        forced.add(id(ws[bk]))
    return _split_long(ws[:bk], x, forced) + _split_long(ws[bk:], x, forced)


def _nearest_pause(x, t, lo, hi):
    """Like snap(), but searching the whole window [lo, hi] (not only +-SNAP)."""
    best = None
    for p0, p1 in pauses(x, lo, hi):
        p0, p1 = max(p0, lo), min(p1, hi)
        if p1 - p0 < SIL_MIN * 0.5:
            continue
        dist = 0.0 if p0 <= t <= p1 else min(abs(t - p0), abs(t - p1))
        if best is None or dist < best[0]:
            best = (dist, p0, p1)
    return None if best is None else (best[1], best[2])


def _snap_borders(parts, x, forced_ids):
    """Every border that is not already in a real pause goes into the nearest real pause (within 0.6 s): each piece
    keeps its word times when they fall INSIDE the pause (a soft word like "că" is quiet enough to look like part of
    a pause and must stay with its piece) and is clamped to the pause otherwise. With no pause close by (fluent speech,
    forced cuts) the border goes to the quietest moment within 0.4 s of the gap. After a finished sentence the pause is
    looked for up to 1 s away (word times measured on real interviews were up to ~0.8 s off). A piece never passes
    MAX_PIECE."""
    times = [[float(p[0][0]), float(p[-1][1])] for p in parts]
    if x is None:
        return times
    for k in range(len(parts) - 1):
        end, start = times[k][1], times[k + 1][0]
        gap = (end + start) / 2
        reach = 1.0 if _ends(parts[k][-1][2]) else 0.6     # after a finished sentence the pause can be a bit further
        lo = max(times[k][0] + 0.2, gap - reach)
        hi = min(times[k + 1][1] - 0.2, gap + reach)
        if hi - lo < 0.02:
            continue
        forced = id(parts[k + 1][0]) in forced_ids
        if not forced and (in_pause(x, gap) or pause_between(x, end, start)):
            continue                               # the words already have a real pause between them
        sp = None if forced else _nearest_pause(x, gap, lo, hi)
        if sp:
            p0, p1 = sp[0] + 0.03, max(sp[0] + 0.03, sp[1] - 0.03)
            e = min(max(end, p0), p1)
            b = min(max(start, p0), p1)
            if b < e:
                e = b = (e + b) / 2
            if b - e < 0.02 and (e <= p0 or e >= p1):    # both word times outside the pause: cut in its middle
                e = b = (p0 + p1) / 2
        else:
            q = _quietest(x, max(lo, gap - 0.4), min(hi, gap + 0.4))
            e = b = q
        e = min(e, times[k][0] + MAX_PIECE)        # moving a border never makes a piece longer than 8 s
        b = max(b, times[k + 1][1] - MAX_PIECE, e)
        times[k][1], times[k + 1][0] = e, b
    return times


def _glue_marks(words):
    """Tokens without any letter or digit (a dialogue dash "-", a lone "…") join the next word (or the previous one at
    the end): they are not words and must not become a piece of their own."""
    out, pend = [], None
    for w in words:
        if not _core(w[2]):
            if pend is None:
                pend = w
            continue
        if pend is not None:
            w = (min(pend[0], w[0]), w[1], " " + (str(pend[2]).strip() + " " + str(w[2]).strip()).strip()) + tuple(w[3:])
            pend = None
        out.append(w)
    if pend is not None and out:
        last = out[-1]
        out[-1] = (last[0], max(last[1], pend[1]), str(last[2]) + str(pend[2]).strip()) + tuple(last[3:])
    return out


def sentences(words, audio=None, names=(), lang="ro", regions=None):
    """Words [(start, end, text, ...)] -> Segs of pieces [(start, end, text)] (see the module text, point 4-5)."""
    words = _glue_marks([w for w in words if str(w[2]).strip()])
    if not words:
        return Segs()
    voc = vocabulary(words, names, lang)
    labels = _word_labels(words, regions) if regions else ["?"] * len(words)
    parts, forced = [], set()
    for g in _sentences(words, labels, audio, voc):
        parts += _split_long(g, audio, forced)
    parts = [p for p in parts if _text(p)]
    times = _snap_borders(parts, audio, forced)
    out = Segs()
    for p, (a, b) in zip(parts, times):
        out.append((round(a, 3), round(max(b, a + 0.1), 3), _text(p)))
    out.forced = [k for k in range(len(parts) - 1) if id(parts[k + 1][0]) in forced]
    return out


def chunks(regions):
    """Speech regions [(a, b, label)] -> stretches of one speaker [(start, end, label, hard)]: a stretch never crosses a
    change of definite speaker nor a pause over 2 s and stays under 24 s; hard = it starts with another speaker than
    the one before. Used by the speaker test (tools/speakers_check.py)."""
    out = []
    for a, b, lab in regions:
        if out:
            ca, cb, clab, hard = out[-1]
            change = lab != "?" and clab != "?" and lab != clab
            if not change and a - cb <= 2.0 and b - ca <= 24.0:
                out[-1] = (ca, b, clab if clab != "?" else lab, hard)
                continue
            out.append((a, b, lab, change))
        else:
            out.append((a, b, lab, False))
    return out


# ------------------------------------------------------------------ the whole transcription

def transcribe(path, model, lang="ro", progress=None, cancel=None, names=(), keep=None):
    """[(start s, end s, text)] of one file, one entry per piece (see the module text). The result carries .spk (who
    speaks each piece), .forced, .sep (how sure the speaker measurement is), .removed and .lost."""
    import speakers
    chans = _channels(path)
    an = speakers.analyse(chans)
    x = an["x"]
    if keep is not None:
        keep[path] = x
    names = list(names) + couple_names(path)
    opts = dict(language=LANGS.get(lang, lang), condition_on_previous_text=False, word_timestamps=True,
                initial_prompt=hint(path, lang))
    run = _engine(model, opts)
    if progress:
        progress(f"{Path(path).name}: listening…", 0.05)
    y = np.ascontiguousarray(x, dtype=np.float32)
    dur = len(x) / SR

    def report(f):
        if progress:
            t = f * dur
            progress(f"{Path(path).name}: {int(t // 60)}:{int(t % 60):02d} / {int(dur // 60)}:{int(dur % 60):02d}",
                     0.05 + 0.8 * f)
        if cancel and cancel():
            raise InterruptedError("Cancelled")
    try:
        raw = run(y, report)
    except InterruptedError:
        raise
    except Exception:
        if isinstance(model, dict) and model.get("engine") == "mlx":
            logging.exception("mlx whisper failed: faster-whisper from now on")
            folder = Path(model["base"]) / "ai_model" / "whisper"
            (folder / "mlx_failed").write_text("mlx failed, see app.log")
            run = _engine(_fw_model(folder, model["quality"]), opts)
            raw = run(y, report)
        else:
            raise
    if cancel and cancel():
        raise InterruptedError("Cancelled")
    if progress:
        progress(f"{Path(path).name}: checking every word…", 0.85)
    regions = an["regions"]
    words, removed = clean(raw, regions)
    words, shift = calibrate(words, x)
    words, lost = recover(words, regions, x, run, cancel)
    out = sentences(words, x, names, lang, regions)
    out.spk = [speakers.label_of(a, b, regions) for a, b, _t in out]
    out.sep = dict(method=an["method"], sure=an["sure"], gap=an["gap"], ref=an["ref"], two=an["two"])
    out.removed = removed
    out.lost = lost
    out.shift = shift
    if progress:
        progress(f"{Path(path).name}: done", 1.0)
    return out


# ------------------------------------------------------------------ the quality report (measured)

def quality(segs, x=None, letter=""):
    """The automatic quality report of one transcript (measured, nothing assumed): codes over 8 s and under 0.8 s, codes
    with a '?' INSIDE (a question glued to an answer), how many borders between codes fall in a real pause of the sound
    (target >= 95 %) with the list of those in speech, forced cuts, who speaks, inventions removed and speech without
    any text."""
    code = lambda i: f"{letter}{i + 1}"
    over = [code(i) for i, s in enumerate(segs) if s[1] - s[0] > MAX_PIECE]
    under = [code(i) for i, s in enumerate(segs) if s[1] - s[0] < MIN_PIECE]
    glued = [code(i) for i, s in enumerate(segs) if re.search(r"\?\s*[\w„\"]", str(s[2]).strip())]
    speech, n = [], 0
    forced_k = set(getattr(segs, "forced", ()) or ())
    if x is not None:
        for i in range(len(segs) - 1):
            if i in forced_k:
                continue
            r = pause_between(x, float(segs[i][1]), float(segs[i + 1][0]))
            if r is None:
                continue
            n += 1
            if not r:
                speech.append(f"{code(i)}/{code(i + 1)} ({_at((float(segs[i][1]) + float(segs[i + 1][0])) / 2)})")
    pct = round(100.0 * (n - len(speech)) / n, 1) if n else None
    forced = [f"{code(k)}/{code(k + 1)} ({_at((float(segs[k][1]) + float(segs[k + 1][0])) / 2)})"
              for k in sorted(forced_k) if k + 1 < len(segs)]
    spk = list(getattr(segs, "spk", None) or [])
    vid = [code(i) for i, lab in enumerate(spk) if lab == "v"]
    unsure = [code(i) for i, lab in enumerate(spk) if lab == "?"]
    removed = list(getattr(segs, "removed", None) or [])
    lost = [f"{_at(a)}-{_at(b)}" for a, b in (getattr(segs, "lost", None) or [])]
    return dict(codes=len(segs), over8=over, under08=under, glued=glued, borders=n, in_speech=speech, pause_pct=pct,
                forced=forced, vid=vid, unsure=unsure, sep=dict(getattr(segs, "sep", None) or {}),
                removed=removed, lost=lost)


def _lst(xs, n=40):
    return ", ".join(xs[:n]) + (" …" if len(xs) > n else "")


def quality_line(q, tr=lambda t: t):
    """One line for the app: '0 over 8 s · 2 under 0.8 s · 0 questions glued · 97 % of borders in a pause'."""
    pct = "—" if q.get("pause_pct") is None else f"{q['pause_pct']:g} %"
    line = tr("{} over 8 s · {} under 0.8 s · {} questions glued · {} of borders in a pause").format(
        len(q["over8"]), len(q["under08"]), len(q["glued"]), pct)
    if q.get("lost"):
        line += " · " + tr("{} stretches of speech without text").format(len(q["lost"]))
    return line


def quality_text(name, q, tr=lambda t: t):
    """The report saved as <name>_raport.txt (tr = the app's translation)."""
    lines = [tr("Quality report: {}").format(name), tr("Codes: {}").format(q["codes"]),
             tr("Codes over 8 s (target 0): {}").format(len(q["over8"])) + (f" ({_lst(q['over8'])})" if q["over8"] else ""),
             tr("Codes under 0.8 s: {}").format(len(q["under08"])) + (f" ({_lst(q['under08'])})" if q["under08"] else ""),
             tr("Codes with a '?' inside (a question glued to an answer): {}").format(len(q["glued"])) +
             (f" ({_lst(q['glued'])})" if q["glued"] else "")]
    if q.get("pause_pct") is None:
        lines.append(tr("Borders in a real pause: not measured (no sound)"))
    else:
        lines.append(tr("Borders between codes in a real pause (target 95 % or more, forced cuts not counted): {} % of {}").format(
            f"{q['pause_pct']:g}", q["borders"]))
        if q["in_speech"]:
            lines.append(tr("Borders that fall in speech: {}").format(_lst(q["in_speech"])))
    sep = q.get("sep") or {}
    if sep:
        how = {"sure": tr("sure"), "medium": tr("medium"), "unsure": tr("unsure"), "none": tr("not measured")}
        lines.append(tr("Who speaks, measured from the sound: {} (the two voices {} dB apart, {})").format(
            how.get(sep.get("sure"), sep.get("sure")), sep.get("gap", 0),
            tr("lavalier vs camera mic") if sep.get("ref") else tr("one channel: level")))
        lines.append(tr("Your lines marked [QUESTION] from the sound: {}").format(len(q.get("vid", []))) +
                     (f" ({_lst(q['vid'])})" if q.get("vid") else ""))
        lines.append(tr("Pieces where it is not sure who speaks (the text rule decides): {}").format(
            len(q.get("unsure", []))) + (f" ({_lst(q['unsure'])})" if q.get("unsure") else ""))
    if q.get("forced"):
        lines.append(tr("Forced cuts (no pause: cut at the quietest point between two words): {}").format(len(q["forced"])) +
                     f" ({_lst(q['forced'])})")
    if "removed" in q:
        lines.append(tr("Removed (Whisper inventions in silence or noise, loops): {}").format(len(q["removed"])) +
                     (" (" + " | ".join(f"„{t[:40]}”" for t in q["removed"][:12]) + ")" if q["removed"] else ""))
    if "lost" in q:
        lines.append(tr("Speech found in the sound but without any text (target 0): {}").format(len(q["lost"])) +
                     (f" ({_lst(q['lost'])})" if q["lost"] else ""))
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ files

def _ts(t, comma=True):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d}{',' if comma else '.'}{ms:03d}"


def write_files(path, segs, q=None, tr=lambda t: t):
    """<name>.txt and <name>.srt next to the file (an existing transcript is replaced: it is ours), and with q the
    quality report <name>_raport.txt."""
    p = Path(path)
    if q is not None:
        p.with_name(p.stem + "_raport.txt").write_text(quality_text(p.name, q, tr), encoding="utf-8")
    txt = p.with_suffix(".txt") if p.suffix.lower() != ".txt" else p.with_name(p.name + ".transcript.txt")
    srt = p.with_suffix(".srt")
    spk = list(getattr(segs, "spk", None) or [])
    if len(spk) != len(segs):
        spk = [""] * len(segs)
    tag = {"v": "[QUESTION] ", "?": "(?) "} if any(lab in ("c", "v", "1", "2") for lab in spk) else {}
    txt.write_text("\n".join(f"[{_ts(a, False)[:10]}] {tag.get(lab, '')}{t}" for (a, b, t), lab in zip(segs, spk)),
                   encoding="utf-8")   # [00:00:05.2], the videographer's lines marked
    srt.write_text("\n".join(f"{k}\n{_ts(a)} --> {_ts(b)}\n{t}\n" for k, (a, b, t) in enumerate(segs, 1)), encoding="utf-8")
    return txt, srt


def export_markers(path, segs, out_path, fps=25.0):
    """An XML with the clip and a marker on every sentence (Premiere: File > Import; DaVinci: Import > Timeline)."""
    import sync
    rate_xml, sf = core._rate(fps)
    r, ch = sync.audio_info(path)
    info = None
    try:
        info = core.probe(path)
    except Exception:
        pass
    dur = info.duration if info and getattr(info, "duration", 0) else (segs[-1][1] if segs else 1.0)
    n = round(dur * sf)
    name = escape(Path(path).name)
    has_video = bool(info and getattr(info, "width", 0))
    vfmt = core._sc(rate_xml, info.width, info.height, "none") if has_video else ""
    fx = (f'<file id="file-1"><name>{name}</name><pathurl>{escape(core._url(path))}</pathurl>{rate_xml}<duration>{n}</duration>'
          f'<media>{"<video>" + vfmt + "</video>" if has_video else ""}<audio><samplecharacteristics><depth>16</depth>'
          f'<samplerate>{r}</samplerate></samplecharacteristics><channelcount>{ch}</channelcount></audio></media></file>')
    ref = '<file id="file-1"/>'

    def clip(cid, kind, k, body):
        st = f'<sourcetrack><mediatype>audio</mediatype><trackindex>{k}</trackindex></sourcetrack>' if kind == "audio" else ""
        return (f'<clipitem id="{cid}"><name>{name}</name><duration>{n}</duration>{rate_xml}<start>0</start>'
                f'<end>{n}</end><in>0</in><out>{n}</out>{body}{st}</clipitem>')
    v = f'<track>{clip("clipitem-v", "video", 1, fx)}</track>' if has_video else ""
    a = "".join(f'<track>{clip(f"clipitem-a{k}", "audio", k, fx if (k == 1 and not has_video) else ref)}</track>'
                for k in range(1, min(2, max(1, ch)) + 1))
    mk = "".join(f'<marker><name>{escape(t[:60])}</name><comment>{escape(t)}</comment><in>{round(s * sf)}</in>'
                 f'<out>{round(e * sf)}</out></marker>' for s, e, t in segs)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(Path(path).stem)} - transcript</name><duration>{n}</duration>{rate_xml}{mk}'
           f'<media><video>{"<format>" + vfmt + "</format>" if has_video else ""}{v}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{a}</audio></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return len(segs)
