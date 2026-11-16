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


VERSION = 4            # transcripts made before (no "tv" or lower) use older pieces: Transcribe redoes them


def _split_long(ws):
    """A piece longer than MAX_PIECE is cut at its longest inner pause, preferably after a comma or before "și", "dar",
    "așa că", "pentru că" (owner's final spec, rule 3), again and again until every part is <= MAX_PIECE; parts are
    never shorter than MIN_PIECE when it can be helped."""
    if len(ws) < 2 or ws[-1][1] - ws[0][0] <= MAX_PIECE:
        return [ws]
    best, bk = None, None
    for k in range(1, len(ws)):
        left, right = ws[k - 1][1] - ws[0][0], ws[-1][1] - ws[k][0]
        if min(left, right) < MIN_PIECE and len(ws) > 2:
            continue
        gap = ws[k][0] - ws[k - 1][1]
        nice = ws[k - 1][2].strip().endswith((",", ";", ":", "—", "-")) or \
            ws[k][2].strip().lower().strip(",.").startswith(LINKS)
        score = 3.0 * gap + (0.5 if nice else 0.0) - 0.03 * abs(left - right)
        if best is None or score > best:
            best, bk = score, k
    if bk is None:
        bk = len(ws) // 2
    return _split_long(ws[:bk]) + _split_long(ws[bk:])


def _text(ws):
    return "".join(w[2] for w in ws).strip()


def _is_filler(ws):
    t = re.sub(r"[^\w\s]", "", _text(ws).lower()).strip()
    return t in FILLERS or not t


def _complete(ws):
    """A complete short line that may stay on its own ("Te iubesc.", "Mulțumesc!")."""
    t = _text(ws)
    return t.endswith((".", "!", "?", "…")) and not _is_filler(ws)


def _join_short(parts):
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


def sentences(words):
    """Words [(start, end, text)] -> pieces (owner's final spec): cut after every word ending in . ? ! and at every
    pause > 0.6 s; a piece > 8 s is cut again at its longest pause (comma / "și" / "dar"...) until <= 8 s; pieces under
    0.8 s are joined to a neighbour unless they are a complete short line; fillers ("Da.", "Păi") are joined too. Every
    piece keeps the exact time of its first and last word (seconds from the start of the media file)."""
    groups, cur = [], []
    for w in words:
        if cur:
            last = cur[-1][2].strip()
            if last.endswith((".", "?", "!", "…")) or w[0] - cur[-1][1] > PAUSE:
                groups.append(cur)
                cur = []
        cur.append(w)
    if cur:
        groups.append(cur)
    parts = []
    for g in groups:
        parts += _split_long(g)
    out = []
    for part in _join_short(parts):
        txt = _text(part)
        if txt:
            out.append((float(part[0][0]), max(float(part[-1][1]), float(part[0][0]) + 0.1), txt))
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


def transcribe(path, model, lang="ro", progress=None, cancel=None):
    """[(start s, end s, text)] of one file: one entry per SENTENCE, times from its first and last word."""
    x = read_audio(path)
    dur = len(x) / SR
    opts = dict(language=LANGS.get(lang, lang), condition_on_previous_text=False, word_timestamps=True,
                initial_prompt=hint(path, lang))
    if isinstance(model, dict) and model.get("engine") == "mlx":
        try:
            return _transcribe_mlx(x, model, opts, path, progress)
        except InterruptedError:
            raise
        except Exception:
            logging.exception("mlx whisper failed: faster-whisper from now on")
            folder = Path(model["base"]) / "ai_model" / "whisper"
            (folder / "mlx_failed").write_text("mlx failed, see app.log")
            model = _fw_model(folder, model["quality"])
    segs, info = model.transcribe(x, vad_filter=True, beam_size=5, hallucination_silence_threshold=2.0, **opts)
    kept = []
    for s in segs:                                   # a generator: the work happens while reading it
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        if s.text.strip():
            kept.append(s)
        if progress:
            progress(f"{Path(path).name}: {int(s.end // 60)}:{int(s.end % 60):02d} of {int(dur // 60)}:{int(dur % 60):02d}",
                     min(1.0, s.end / max(1.0, dur)))
    words = []
    for s in _dedupe([dict(text=s.text, seg=s) for s in kept]):
        ws = [w for w in (s["seg"].words or []) if w.end > w.start]
        words += [(w.start, w.end, w.word) for w in ws] or [(s["seg"].start, s["seg"].end, " " + s["seg"].text.strip())]
    return sentences(words)


def _transcribe_mlx(x, model, opts, path, progress):
    import mlx_whisper
    if progress:
        progress(f"{Path(path).name}: transcribing on the graphics chip…", 0.3)
    r = mlx_whisper.transcribe(x, path_or_hf_repo=model["path"], verbose=None, hallucination_silence_threshold=2.0,
                               **opts)
    words = []
    for s in _dedupe([seg for seg in r.get("segments", []) if str(seg.get("text", "")).strip()]):
        ws = [w for w in s.get("words", []) if w.get("end", 0) > w.get("start", 0)]
        words += [(w["start"], w["end"], w["word"]) for w in ws] or [(s["start"], s["end"], " " + s["text"].strip())]
    if progress:
        progress(f"{Path(path).name}: done", 1.0)
    return sentences(words)


def _ts(t, comma=True):
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    sec, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{sec:02d}{',' if comma else '.'}{ms:03d}"


def write_files(path, segs):
    """<name>.txt and <name>.srt next to the file (an existing transcript is replaced: it is ours)."""
    p = Path(path)
    txt = p.with_suffix(".txt") if p.suffix.lower() != ".txt" else p.with_name(p.name + ".transcript.txt")
    srt = p.with_suffix(".srt")
    txt.write_text("\n".join(f"[{_ts(a, False)[:8]}] {t}" for a, b, t in segs), encoding="utf-8")
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
