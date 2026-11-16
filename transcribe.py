"""Speech transcription (local, free): interviews, speeches, the vornic, the priest's sermon.

Engine: faster-whisper (OpenAI Whisper on CTranslate2), running on this computer; the model is downloaded once into
<data>/ai_model/whisper. "best" = large-v3 (the most precise, slower), "fast" = large-v3-turbo (several times faster,
almost as good). Nothing is uploaded.
Results, next to the file: <name>.txt (text with times), <name>.srt (subtitles); and on request an XML for Premiere /
DaVinci: the clip with a marker on every sentence, the sentence in the marker.
"""
import logging
import sys
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core

SR = 16000
MODELS = {"fast": "large-v3-turbo", "best": "large-v3"}
LANGS = {"ro": "ro", "en": "en", "auto": None}


def available():
    """'' when the engine is in this build, else the reason."""
    try:
        import faster_whisper
        return "" if faster_whisper else "missing"
    except Exception as e:
        return str(e)


MLX_MODELS = {"fast": "mlx-community/whisper-large-v3-turbo", "best": "mlx-community/whisper-large-v3-mlx"}


def mlx_ok():
    """Whisper on the Mac's graphics chip (Apple MLX): several times faster. Only on Apple Silicon, only when the app was
    built with it; anything wrong -> faster-whisper on the processor (the old way)."""
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


def _channels(path):
    """Every audio channel of the file as mono 16 kHz arrays (Sony MXF: one stream per channel, read in ONE pass)."""
    import sync
    import tempfile
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
    """How clearly speech stands out on a channel: loud parts (p90) above the quiet floor (p20), in dB. The
    lavalier (close to the mouth) scores higher than the camera microphone (room sound)."""
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
    """The sound of a file (audio or video), mono 16 kHz, from its CLEAREST channel. Never a mix: on FX6 the camera
    microphone and the lavalier are on different channels, and the mix made Whisper mishear words."""
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


MAX_PIECE = 8.0        # owner: a piece ideally lasts at most ~8 s (Claude can only cut between codes)
PAUSE = 0.6            # owner's final spec: a pause longer than this between two words ends a piece
MIN_PIECE = 0.8        # shorter pieces are joined to a neighbour, unless they are a complete short line ("Te iubesc.")
LINKS = ("și", "si", "dar", "așa", "asa", "pentru", "deci", "iar", "and", "but", "so", "because")
FILLERS = {"da", "păi", "pai", "nu știu", "nu stiu", "deci", "adică", "adica", "ăă", "ăăă", "mm", "ok", "bine", "yes", "well"}


def _norm(t):
    return re.sub(r"[^\w]+", " ", str(t).lower()).strip()


VERSION = 8            # transcripts made before (no "tv" or lower) use older pieces: Transcribe redoes them


SIL_DB, SIL_MIN, SNAP = -38.0, 0.15, 0.6       # a real pause: under about -38 dB for 0.15 s, looked for within +-0.6 s


def _core(t):
    return re.sub(r"[^\w\-]", "", str(t)).strip("-")


NO_END = {"de", "la", "cu", "pe", "în", "in", "din", "pentru", "lui", "că", "ca", "și", "si", "sau", "dar", "a", "al", "ale",
          "ai", "o", "un", "unei", "unui", "spre", "despre", "după", "dupa", "fără", "fara", "prin", "către", "catre", "între",
          "intre", "sub", "peste", "să", "sa", "mai", "foarte", "cel", "cea", "cei", "cele", "lu", "the", "a", "an", "of", "to",
          "with", "and", "for", "on", "at", "my", "your", "his", "her", "our", "their", "from", "by", "about"}
# words that cannot end a sentence (a preposition, an article, "și"...): "vorbeam cu Maria" never splits before "Maria"


def vocabulary(words, names=(), lang="ro"):
    """What the transcript itself says about its words (no list of names): the words seen with a small letter, how many
    times each word appears, the names chosen in the program (the couple from the folder, the first names typed in the
    list) and the common words of the interview language (wordfreq, the first 5000)."""
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
    common word ("Mamaia", "TikTok", the godfather's name), plus the names chosen in the program."""
    v = vocabulary(words, names, lang)
    return {k for k in v["count"] if k not in v["small"] and (v["count"][k] > 1 or k not in v["common"])} | v["names"]


def _cap_start(prev, w, voc):
    """Whisper forgot the full stop (owner's final spec, point 2): a word with a capital letter in the middle of a line,
    after a word without punctuation, starts a new sentence when the transcript shows it is an ordinary word: it also
    appears with a small letter, or it appears only this once and is one of the language's common words ("Asta",
    "Mi-a"). Never before a name chosen in the program, never after a word that cannot end a sentence ("cu", "pe",
    "și"...), never for the English "I" or an acronym (OK, DJ)."""
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


def _ends(t):
    return str(t).strip().rstrip('"\'»”)').endswith((".", "?", "!", "…"))


def _db(x):
    import numpy as np
    n = int(SR * 0.01)
    k = len(x) // n
    if k == 0:
        return np.zeros(0)
    e = (x[:k * n].astype("float64").reshape(k, n) ** 2).mean(axis=1)
    return 10 * np.log10(e + 1e-12)


def _thr(d):
    """The pause threshold of this stretch of sound: about -38 dB on a clean recording, but always relative to it: 18 dB
    under the speaker's loud parts on a quiet recording, and close to the noise floor on a noisy one (wind, outside),
    where nothing is ever under -38 dB."""
    import numpy as np
    floor, loud = float(np.percentile(d, 15)), float(np.percentile(d, 90))
    return max(min(SIL_DB, loud - 18.0), floor + 0.3 * (loud - floor))


def pauses(x, a, b):
    """Real pauses in the audio between a and b seconds: [(start, end)], under about -38 dB for at least 0.15 s (the
    threshold follows the speaker when the recording is quiet)."""
    if x is None:
        return []
    lo, hi = max(0, int((a - 3.0) * SR)), min(len(x), int((b + 3.0) * SR))
    d = _db(x[lo:hi])
    if not len(d):
        return []
    thr = _thr(d)
    quiet = d < thr
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
    """The nearest real pause to an estimated cut point t (within +-0.6 s and inside [lo, hi]): (pause start, pause end),
    or None when there is no pause (the estimate is kept)."""
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
    """MEASURED from the sound: is the moment t in a real pause (the 10 ms frames around it under the pause threshold:
    about -38 dB, or 18 dB under the speaker's loud parts on a quiet recording)?"""
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
    """MEASURED: is there a real pause (at least 0.08 s under the pause threshold) between the end of one piece (a) and
    the start of the next (b)? Then the cut can go there. None without sound."""
    if x is None:
        return None
    lo, hi = min(a, b) - 0.05, max(a, b) + 0.05
    return any(min(p1, hi) - max(p0, lo) >= 0.08 for p0, p1 in pauses(x, lo, hi))


def _at(t):
    return f"{int(t // 60)}:{t % 60:04.1f}"


def quality(segs, x=None, letter=""):
    """The automatic quality report of one transcript (measured, nothing assumed): codes over 8 s and under 0.8 s, codes
    with a '?' INSIDE (a question glued to an answer), and how many borders between codes fall in a real pause of the
    sound (target >= 95 %), with the list of those that fall in speech."""
    code = lambda i: f"{letter}{i + 1}"
    over = [code(i) for i, s in enumerate(segs) if s[1] - s[0] > MAX_PIECE]
    under = [code(i) for i, s in enumerate(segs) if s[1] - s[0] < MIN_PIECE]
    glued = [code(i) for i, s in enumerate(segs) if re.search(r"\?\s*[\w„\"]", str(s[2]).strip())]
    speech, n = [], 0
    if x is not None:
        forced_k = set(getattr(segs, "forced", ()) or ())
        for i in range(len(segs) - 1):
            if i in forced_k:
                continue                              # forced cuts are counted on their own line
            t = (float(segs[i][1]) + float(segs[i + 1][0])) / 2
            r = pause_between(x, float(segs[i][1]), float(segs[i + 1][0]))
            if r is None:
                continue
            n += 1
            if not r:
                speech.append(f"{code(i)}/{code(i + 1)} ({_at(t)})")
    pct = round(100.0 * (n - len(speech)) / n, 1) if n else None
    forced = [f"{code(k)}/{code(k + 1)} ({_at((float(segs[k][1]) + float(segs[k + 1][0])) / 2)})"
              for k in getattr(segs, "forced", ()) if k + 1 < len(segs)]
    spk = list(getattr(segs, "spk", None) or [])
    vid = [code(i) for i, lab in enumerate(spk) if lab == "v"]
    unsure = [code(i) for i, lab in enumerate(spk) if lab == "?"]
    return dict(codes=len(segs), over8=over, under08=under, glued=glued, borders=n, in_speech=speech, pause_pct=pct,
                forced=forced, vid=vid, unsure=unsure, sep=dict(getattr(segs, "sep", None) or {}))


def _lst(xs, n=40):
    return ", ".join(xs[:n]) + (" …" if len(xs) > n else "")


def quality_line(q, tr=lambda t: t):
    """One line for the app: '0 over 8 s · 2 under 0.8 s · 0 questions glued · 97 % of borders in a pause'."""
    pct = "—" if q.get("pause_pct") is None else f"{q['pause_pct']:g} %"
    return tr("{} over 8 s · {} under 0.8 s · {} questions glued · {} of borders in a pause").format(
        len(q["over8"]), len(q["under08"]), len(q["glued"]), pct)


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
        lines.append(tr("Forced cuts (no pause: cut at the quietest point between 5 and 8 s): {}").format(len(q["forced"])) +
                     f" ({_lst(q['forced'])})")
    return "\n".join(lines) + "\n"


def estimate_words(a, b, text):
    """A segment Whisper gave without word times: its words get times by their number of letters (an ESTIMATE, marked
    so the cut points are moved to a real pause in the audio afterwards)."""
    toks = [t for t in re.findall(r"\S+", str(text))]
    if not toks:
        return []
    weights = [len(_core(t)) + 1 for t in toks]
    tot, out, pos = float(sum(weights)), [], a
    for t, wgt in zip(toks, weights):
        d = (b - a) * wgt / tot
        out.append((pos, pos + d, " " + t, True))
        pos += d
    return out


FORCE_FROM = 5.0       # no pause at all: the cut goes to the quietest point between 5 s and 8 s


def _quietest(x, a, b):
    """The moment with the least energy in the sound between a and b (50 ms smoothing)."""
    import numpy as np
    lo, hi = max(0, int(a * SR)), min(len(x), int(b * SR))
    d = _db(x[lo:hi])
    if len(d) < 3:
        return (a + b) / 2
    d = np.convolve(d, np.ones(5) / 5, mode="same")
    return lo / SR + (int(np.argmin(d)) + 0.5) * 0.01


def _split_long(ws, audio=None, forced=None):
    """A piece longer than MAX_PIECE is cut at its best inner pause (a real pause in the sound, a long gap between words,
    preferably after a comma or before "și", "dar", "așa că", "pentru că"), again and again until every part is <=
    MAX_PIECE; parts are never shorter than MIN_PIECE when it can be helped. When there is NO pause at all, the cut is
    FORCED: at the quietest point of the sound between 5 s and 8 s (owner), and it is listed in the quality report."""
    if len(ws) < 2 or ws[-1][1] - ws[0][0] <= MAX_PIECE:
        return [ws]
    t0, dur = ws[0][0], ws[-1][1] - ws[0][0]
    cands = [k for k in range(1, len(ws)) if min(ws[k - 1][1] - t0, ws[-1][1] - ws[k][0]) >= MIN_PIECE or len(ws) == 2]
    cands = cands or list(range(1, len(ws)))

    def real_pause(k):
        if audio is not None:                          # the sound decides (word times are not exact)
            return _pause_between(audio, ws[k - 1], ws[k])
        return ws[k][0] - ws[k - 1][1] >= SIL_MIN and len(ws[k]) <= 3
    def nice(k):
        return ws[k - 1][2].strip().endswith((",", ";", ":", "—", "-")) or \
            ws[k][2].strip().lower().strip(",.").startswith(LINKS)
    est = any(len(w) > 3 for w in ws)
    if est and audio is not None:                     # estimated word times: the real pauses of the SOUND decide
        best = None
        for p0, p1 in pauses(audio, t0 + MIN_PIECE, ws[-1][1] - MIN_PIECE):
            c = (p0 + p1) / 2
            if not t0 + MIN_PIECE < c < ws[-1][1] - MIN_PIECE:
                continue
            near = [k for k in cands if abs((ws[k - 1][1] + ws[k][0]) / 2 - c) <= SNAP]
            if not near:
                continue
            k = min(near, key=lambda k: (not nice(k), abs((ws[k - 1][1] + ws[k][0]) / 2 - c)))
            left, right = c - t0, ws[-1][1] - c
            score = 3.0 * min(p1 - p0, 0.6) + (0.5 if nice(k) else 0.0) - 0.03 * abs(left - right)
            if best is None or score > best[0]:
                best = (score, k, p0, p1)
        if best:
            _, bk, p0, p1 = best
            ws = list(ws)
            ws[bk - 1] = (ws[bk - 1][0], max(ws[bk - 1][0] + 0.05, p0 + 0.05)) + tuple(ws[bk - 1][2:])
            ws[bk] = (min(ws[bk][1] - 0.05, p1 - 0.05), ws[bk][1]) + tuple(ws[bk][2:])
            return _split_long(ws[:bk], audio, forced) + _split_long(ws[bk:], audio, forced)
        paused = set()
    else:
        paused = {k for k in cands if real_pause(k)}
    if paused:
        best, bk = None, None
        for k in paused:
            left, right = ws[k - 1][1] - t0, ws[-1][1] - ws[k][0]
            gap = ws[k][0] - ws[k - 1][1]
            nice = ws[k - 1][2].strip().endswith((",", ";", ":", "—", "-")) or \
                ws[k][2].strip().lower().strip(",.").startswith(LINKS)
            score = 3.0 * gap + (0.5 if nice else 0.0) - 0.03 * abs(left - right)
            if best is None or score > best:
                best, bk = score, k
        return _split_long(ws[:bk], audio, forced) + _split_long(ws[bk:], audio, forced)
    # forced: no pause anywhere in it
    hi = min(MAX_PIECE, dur - MIN_PIECE)
    lo = min(FORCE_FROM, hi)
    inwin = [k for k in cands if lo <= ws[k - 1][1] - t0 <= hi] or cands
    ws = list(ws)
    if audio is not None:                             # the quietest moment, then the nearest word border
        tm = _quietest(audio, t0 + lo, t0 + hi)
        bk = min(inwin, key=lambda k: abs((ws[k - 1][1] + ws[k][0]) / 2 - tm))
        if len(ws[bk]) > 3 and ws[bk - 1][0] < tm < ws[bk][1]:     # estimated times: the border moves to that moment
            ws[bk - 1] = (ws[bk - 1][0], tm) + tuple(ws[bk - 1][2:])
            ws[bk] = (tm, ws[bk][1]) + tuple(ws[bk][2:])
    else:                                             # no sound to measure: a comma / "și" / "dar" in the window
        bk = min(inwin, key=lambda k: (not nice(k), abs(ws[k - 1][1] - t0 - 6.5)))
    if forced is not None:
        forced.add(id(ws[bk]))
    return _split_long(ws[:bk], audio, forced) + _split_long(ws[bk:], audio, forced)


class Segs(list):
    """The pieces of a transcript; .forced = the borders (after piece k) that were forced cuts (no pause)."""
    forced = ()


def _text(ws):
    return "".join(w[2] for w in ws).strip()


def _is_filler(ws):
    t = re.sub(r"[^\w\s]", "", _text(ws).lower()).strip()
    return t in FILLERS or not t


def _complete(ws):
    """A complete short line that may stay on its own ("Te iubesc.", "Mulțumesc!")."""
    t = _text(ws)
    first = next((ch for ch in t if ch.isalpha()), "")
    return _ends(t) and first.isupper() and not _is_filler(ws)     # "frumos." alone is the end of a sentence, not one


def _join_short(parts, hard=frozenset()):
    """Pieces under MIN_PIECE (and isolated fillers like "Da.", "Păi") are joined to the closer neighbour, unless they
    are a complete short line; the joined piece may not grow past MAX_PIECE."""
    out = [list(p) for p in parts]
    k = 0
    while k < len(out):
        p = out[k]
        short = p[-1][1] - p[0][0] < MIN_PIECE
        if (short and not _complete(p)) or (_is_filler(p) and len(out) > 1):
            gl = p[0][0] - out[k - 1][-1][1] if k > 0 else 1e9
            gr = out[k + 1][0][0] - p[-1][1] if k + 1 < len(out) else 1e9
            for side in sorted(((gl, -1), (gr, 1))):
                j = k + side[1]
                if side[0] < 1e8 and 0 <= j < len(out):
                    first, second = (out[j], p) if side[1] < 0 else (p, out[j])
                    if id(second[0]) in hard:
                        continue     # never across a change of speaker
                    if _ends(_text(first)) or _text(out[j]).rstrip().endswith("?") or _text(p).rstrip().endswith("?"):
                        continue     # never across a finished sentence, never into / out of a question (owner: "Iubitor,")
                    merged = out[j] + p if side[1] < 0 else p + out[j]
                    if merged[-1][1] - merged[0][0] <= MAX_PIECE:
                        lo = min(j, k)
                        out[lo:lo + 2] = [merged]
                        k = max(0, lo - 1)
                        break
            else:
                k += 1
            continue
        k += 1
    return out


def _pause_between(x, w1, w2):
    """Is there a real pause between two words (searched between their middles: word times are not exact)?"""
    lo, hi = (w1[0] + w1[1]) / 2, (w2[0] + w2[1]) / 2
    return snap(x, (w1[1] + w2[0]) / 2, lo, hi) is not None


def sentences(words, audio=None, names=(), lang="ro", hard=frozenset()):
    """Words [(start, end, text)] -> pieces (owner's final spec): cut after every word ending in . ? ! and at every
    pause > 0.6 s; a piece > 8 s is cut again at its longest pause (comma / "și" / "dar"...) until <= 8 s; pieces under
    0.8 s are joined to a neighbour unless they are a complete short line; fillers ("Da.", "Păi") are joined too. Every
    piece keeps the exact time of its first and last word (seconds from the start of the media file)."""
    voc = vocabulary(words, names, lang)
    groups, cur = [], []
    for w in words:
        if cur:
            last = cur[-1][2].strip()
            want = _ends(last) or _cap_start(last, w[2], voc)
            asked = last.rstrip('"\'»”)').endswith("?")      # a question never stays glued to its answer
            if id(w) in hard or asked or w[0] - cur[-1][1] > PAUSE or \
                    (want and (audio is None or _pause_between(audio, cur[-1], w))):
                groups.append(cur)        # punctuation only chooses among REAL pauses (v3.10.0)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    parts, forced = [], set()
    for g in groups:
        parts += _split_long(g, audio, forced)
    joined = [p for p in _join_short(parts, hard) if _text(p)]
    times = [[float(p[0][0]), float(p[-1][1])] for p in joined]
    fk = [k for k in range(len(joined) - 1) if id(joined[k + 1][0]) in forced]
    for k in range(len(joined) - 1):                 # an estimated cut point goes to the nearest real pause (point 4)
        if k not in fk and audio is not None and not in_pause(audio, (times[k][1] + times[k + 1][0]) / 2):
            # the pause is looked for around the border, never past the middle of the last / first word
            lo = max(times[k][0] + 0.2, (joined[k][-1][0] + joined[k][-1][1]) / 2, times[k][1] - 0.3)
            hi = min(times[k + 1][1] - 0.2, (joined[k + 1][0][0] + joined[k + 1][0][1]) / 2, times[k + 1][0] + 0.3)
            sp = snap(audio, times[k][1], lo, hi)
            if sp:
                e = min(sp[1], sp[0] + 0.05)
                b = max(e, sp[1] - 0.05)
                # a piece may grow by at most 0.3 s past its words (never by seconds into noise)
                if e <= times[k][1] + 0.3 and b >= times[k + 1][0] - 0.3:
                    times[k][1], times[k + 1][0] = e, b
    out = Segs()
    for part, (a, b) in zip(joined, times):
        out.append((a, max(b, a + 0.1), _text(part)))
    out.forced = fk
    return out


def _dedupe(segs):
    """Whisper sometimes loops on one sentence ("Nu i-am răspuns la mesaj…" again and again): a segment equal to one of
    the last two is dropped."""
    out = []
    for seg in segs:
        n = _norm(seg[-1] if isinstance(seg, tuple) else seg["text"])
        if n and any(_norm(o[-1] if isinstance(o, tuple) else o["text"]) == n for o in out[-2:]):
            continue
        out.append(seg)
    return out


CHUNK_MAX = 24.0       # Whisper hears at most this much at once: chunks end at real pauses and at every change of speaker


def chunks(regions):
    """The speech regions (VAD, with who speaks) -> chunks to transcribe one by one: [(start, end, label, hard)].
    A chunk never crosses a change of speaker (videographer / couple / interviewee 1 / 2) nor a pause over 2 s, and
    stays under CHUNK_MAX. hard = it starts with another speaker than the chunk before (a border no rule may undo)."""
    out = []
    for a, b, lab in regions:
        if out:
            ca, cb, clab, hard = out[-1]
            change = lab != "?" and clab != "?" and lab != clab
            if not change and a - cb <= 2.0 and b - ca <= CHUNK_MAX:
                out[-1] = (ca, b, clab if clab != "?" else lab, hard)
                continue
            out.append((a, b, lab, change))
        else:
            out.append((a, b, lab, False))
    return out


def _fragments(segs, regions, label_of):
    """A word or two left alone on a border between speakers (under 0.6 s, no sentence of its own, e.g. "Ce" + "mai prost
    e?") joins the piece it belongs to: forward when it does not end a sentence and the next piece is close, backward
    when it starts with a small letter. Never past 8 s, never into a piece of a DEFINITE other speaker than its own."""
    out = [list(sg) for sg in segs]
    forced = {round(float(segs[k][1]), 3) for k in getattr(segs, "forced", ()) if k < len(segs)}
    k = 0
    while k < len(out):
        a, b, t = out[k]
        words = t.split()
        lab = label_of(a, b, regions) if b - a >= 0.5 else "?"     # half a second cannot be measured
        small = b - a < 0.6 and len(words) <= 2 and not (_ends(t) and t[:1].isupper() and len(_core(t)) > 3)
        merged = False
        if small:
            nxt = out[k + 1] if k + 1 < len(out) else None
            prv = out[k - 1] if k else None
            if nxt and not _ends(t) and nxt[0] - b < 0.5 and nxt[1] - a <= MAX_PIECE and \
                    (lab == "?" or label_of(*nxt[:2], regions) in (lab, "?")):
                out[k:k + 2] = [[a, nxt[1], t + " " + nxt[2]]]
                merged = True
            elif prv and t[:1].islower() and a - prv[1] < 0.5 and b - prv[0] <= MAX_PIECE and \
                    not str(prv[2]).rstrip().endswith("?") and (lab == "?" or label_of(*prv[:2], regions) in (lab, "?")):
                out[k - 1:k + 1] = [[prv[0], b, prv[2] + " " + t]]
                k -= 1
                merged = True
        if not merged:
            k += 1
    # the other speaker started without any pause: his first word or two stayed at the end of this piece
    # ("…facem asta. Cum va" + "decurge ziua de astăzi…?"): they move to the next piece
    for k in range(len(out) - 1):
        a, b, t = out[k]
        na, nb, nt = out[k + 1]
        m = re.search(r"[.!?…][\"'»”)]?\s+(\S+(?:\s+\S+)?)\s*$", t)
        if not m or not m.group(1)[:1].isupper() or _ends(m.group(1)) or na - b > 1.2:
            continue
        mine, theirs = label_of(a, b, regions), label_of(na, nb, regions)
        if not ({mine, theirs} == {"c", "v"} or str(nt).rstrip().endswith("?")):
            continue
        cut = a + (b - a) * len(t[:m.start(1)]) / max(1, len(t))
        out[k] = [a, cut, t[:m.start(1)].rstrip()]
        out[k + 1] = [cut, nb, m.group(1) + " " + nt]
    res = Segs((a, b, t) for a, b, t in out)
    res.forced = [i for i, sg in enumerate(res) if round(float(sg[1]), 3) in forced and i + 1 < len(res)]
    return res


def _engine(model, opts):
    """One function for both engines: (sound) -> segments [dict(start, end, text, words=[(s, e, w)], bad)]."""
    if isinstance(model, dict) and model.get("engine") == "mlx":
        import mlx_whisper

        def run(y):
            r = mlx_whisper.transcribe(y, path_or_hf_repo=model["path"], verbose=None, **opts)
            return [dict(start=sg["start"], end=sg["end"], text=str(sg.get("text", "")),
                         words=[(w["start"], w["end"], w["word"]) for w in sg.get("words", []) if w.get("end", 0) > w.get("start", 0)],
                         bad=sg.get("no_speech_prob", 0) > 0.6 and sg.get("avg_logprob", 0) < -1.0)
                    for sg in r.get("segments", [])]
        return run

    def run(y):
        segs, _info = model.transcribe(y, vad_filter=False, beam_size=5, **opts)
        return [dict(start=sg.start, end=sg.end, text=sg.text,
                     words=[(w.start, w.end, w.word) for w in (sg.words or []) if w.end > w.start],
                     bad=getattr(sg, "no_speech_prob", 0) > 0.6 and getattr(sg, "avg_logprob", 0) < -1.0)
                for sg in segs]
    return run


def transcribe(path, model, lang="ro", progress=None, cancel=None, names=(), keep=None):
    """[(start s, end s, text)] of one file: one entry per SENTENCE, times from its first and last word (v3.10.0):
    1. who speaks when, measured from the sound (speakers.analyse: VAD regions + lavalier / camera mic levels);
    2. every chunk between real pauses, with one speaker, is transcribed on its own (always with word times);
    3. the words become sentences, cut only at real pauses (punctuation only chooses among them), never across a
       change of speaker. The result carries .spk (who speaks every sentence), .forced and .sep (how sure)."""
    import speakers
    chans = _channels(path)
    an = speakers.analyse(chans)
    x = an["x"]
    if keep is not None:
        keep[path] = x
    names = list(names) + couple_names(path)
    dur = len(x) / SR
    opts = dict(language=LANGS.get(lang, lang), condition_on_previous_text=False, word_timestamps=True,
                initial_prompt=hint(path, lang))
    run = _engine(model, opts)
    if isinstance(model, dict) and model.get("engine") == "mlx":
        try:
            run(np.zeros(SR, dtype=np.float32))          # the graphics chip engine answers at all?
        except Exception:
            logging.exception("mlx whisper failed: faster-whisper from now on")
            folder = Path(model["base"]) / "ai_model" / "whisper"
            (folder / "mlx_failed").write_text("mlx failed, see app.log")
            run = _engine(_fw_model(folder, model["quality"]), opts)
    ch = chunks(an["regions"])
    words, hard = [], set()
    for n, (a, b, lab, is_hard) in enumerate(ch):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        prev_end = ch[n - 1][1] if n else 0.0
        next_start = ch[n + 1][0] if n + 1 < len(ch) else dur
        lo = max(0.0, a - min(0.2, (a - prev_end) / 2))
        hi = min(dur, b + min(0.2, (next_start - b) / 2))
        y = np.ascontiguousarray(x[int(lo * SR):int(hi * SR)], dtype=np.float32)
        if len(y) < SR // 5:
            continue
        try:
            segs = run(y)
        except Exception:
            logging.exception("chunk %.1f-%.1f failed", a, b)
            continue
        got = []
        for sg in _dedupe([sg for sg in segs if str(sg["text"]).strip() and not sg["bad"]]):
            ws = [(lo + w0, lo + w1, t) for w0, w1, t in sg["words"]]
            got += ws or estimate_words(lo + sg["start"], lo + min(sg["end"], hi - lo), sg["text"])
        if got and is_hard:
            hard.add(id(got[0]))
        words += got
        if progress:
            progress(f"{Path(path).name}: {int(b // 60)}:{int(b % 60):02d} of {int(dur // 60)}:{int(dur % 60):02d}",
                     min(1.0, b / max(1.0, dur)))
    if not words and dur > 1.0:                        # nothing came out of the chunks: the whole file at once
        logging.warning("no words from the chunks of %s: whole file", path)
        for sg in _dedupe([sg for sg in run(np.ascontiguousarray(x, dtype=np.float32))
                           if str(sg["text"]).strip() and not sg["bad"]]):
            words += sg["words"] or estimate_words(sg["start"], sg["end"], sg["text"])
    out = _fragments(sentences(words, x, names, lang, hard), an["regions"], speakers.label_of)
    out.spk = [speakers.label_of(sa, sb, an["regions"]) for sa, sb, _t in out]
    out.sep = dict(method=an["method"], sure=an["sure"], gap=an["gap"], ref=an["ref"], two=an["two"])
    return out


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
    clip = lambda cid, kind, k, body: (f'<clipitem id="{cid}"><name>{name}</name><duration>{n}</duration>{rate_xml}<start>0</start>'
                                       f'<end>{n}</end><in>0</in><out>{n}</out>{body}'
                                       + (f'<sourcetrack><mediatype>audio</mediatype><trackindex>{k}</trackindex></sourcetrack>' if kind == "audio" else "")
                                       + '</clipitem>')
    v = f'<track>{clip("clipitem-v", "video", 1, fx)}</track>' if has_video else ""
    a = "".join(f'<track>{clip(f"clipitem-a{k}", "audio", k, fx if (k == 1 and not has_video) else chr(60) + "file id=" + chr(34) + "file-1" + chr(34) + "/" + chr(62))}</track>'
                for k in range(1, min(2, max(1, ch)) + 1))
    mk = "".join(f'<marker><name>{escape(t[:60])}</name><comment>{escape(t)}</comment><in>{round(s * sf)}</in>'
                 f'<out>{round(e * sf)}</out></marker>' for s, e, t in segs)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(Path(path).stem)} - transcript</name><duration>{n}</duration>{rate_xml}{mk}'
           f'<media><video>{"<format>" + vfmt.replace("<samplecharacteristics>", "<samplecharacteristics>") + "</format>" if has_video else ""}{v}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels>{a}</audio></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return len(segs)
