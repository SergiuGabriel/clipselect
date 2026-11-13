"""Speech transcription (local, free): interviews, speeches, the vornic, the priest's sermon.

Engine: faster-whisper (OpenAI Whisper on CTranslate2), running on this computer; the model is downloaded once into
<data>/ai_model/whisper. "best" = large-v3 (the most precise, slower), "fast" = large-v3-turbo (several times faster,
almost as good). Nothing is uploaded.
Results, next to the file: <name>.txt (text with times), <name>.srt (subtitles); and on request an XML for Premiere /
DaVinci: the clip with a marker on every sentence, the sentence in the marker.
"""
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


def load_model(base, quality="fast", progress=None):
    from faster_whisper import WhisperModel
    folder = Path(base) / "ai_model" / "whisper"
    folder.mkdir(parents=True, exist_ok=True)
    if progress:
        progress("Loading the speech model (the first time it is downloaded once, about 1.5-3 GB)…", 0.0)
    try:
        return WhisperModel(MODELS.get(quality, MODELS["fast"]), device="auto", compute_type="int8", download_root=str(folder))
    except Exception:
        return WhisperModel(MODELS.get(quality, MODELS["fast"]), device="cpu", compute_type="int8", download_root=str(folder))


def read_audio(path):
    """The sound of a file (audio or video), mono 16 kHz."""
    cmd = [core.ffmpeg_exe(), "-v", "error", "-nostdin", "-i", str(path), "-vn", "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True, **core._NOWIN).stdout
    x = np.frombuffer(out, np.float32).copy()
    if len(x) < SR // 2:
        raise ValueError("No sound in this file")
    return x


def transcribe(path, model, lang="ro", progress=None, cancel=None):
    """[(start s, end s, text)] of one file."""
    x = read_audio(path)
    dur = len(x) / SR
    segs, info = model.transcribe(x, language=LANGS.get(lang, lang), vad_filter=True, beam_size=5,
                                  condition_on_previous_text=False)
    out = []
    for s in segs:                                   # a generator: the work happens while reading it
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        t = s.text.strip()
        if t:
            out.append((float(s.start), float(s.end), t))
        if progress:
            progress(f"{Path(path).name}: {int(s.end // 60)}:{int(s.end % 60):02d} of {int(dur // 60)}:{int(dur % 60):02d}",
                     min(1.0, s.end / max(1.0, dur)))
    return out


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
