"""MoneyMakingMachine core: video analysis (any format FFmpeg can read), 3-level grading, XML export."""
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, asdict
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

SAMPLE_FPS = 8
WIN_SEC = 2.0
AW, AH = 320, 180
KEYS = ["contrast", "exposure", "focus", "importance", "stability"]

# Used only when scanning folders. Files picked manually are accepted whatever their extension.
VIDEO_EXT = {
    ".mxf", ".mov", ".mp4", ".m4v", ".mkv", ".avi", ".mts", ".m2ts", ".ts", ".mpg", ".mpeg", ".m2v",
    ".wmv", ".webm", ".flv", ".3gp", ".mj2", ".dv", ".vob", ".ogv", ".gxf", ".r3d", ".braw", ".ari",
    ".mpe", ".divx", ".f4v", ".asf", ".qt", ".dnxhd", ".hevc", ".h264", ".264", ".265", ".insv",
}

_NOWIN = {"creationflags": 0x08000000} if os.name == "nt" else {}


def ffmpeg_exe():
    p = shutil.which("ffmpeg")
    if p:
        return p
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


@dataclass
class Info:
    path: str
    duration: float | None
    fps: float
    width: int
    height: int


@dataclass
class Analysis:
    info: Info
    t0: np.ndarray
    t1: np.ndarray
    comp: dict  # key -> np.ndarray of 0..1 scores, one per window

    @property
    def duration(self):
        return float(self.t1[-1]) if len(self.t1) else 0.0

    def to_json(self):
        return {"info": asdict(self.info), "t0": self.t0.round(2).tolist(), "t1": self.t1.round(2).tolist(),
                "comp": {k: v.round(3).tolist() for k, v in self.comp.items()}}

    @staticmethod
    def from_json(d):
        return Analysis(Info(**d["info"]), np.array(d["t0"]), np.array(d["t1"]),
                        {k: np.array(v) for k, v in d["comp"].items()})


def probe(path):
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True,
                       text=True, errors="replace", **_NOWIN)
    txt = r.stderr
    vline = next((l for l in txt.splitlines() if " Video:" in l and "attached pic" not in l), None)
    if not vline:
        raise ValueError("No video stream found (or format not supported by FFmpeg).")
    body = vline.split("Video:", 1)[1]
    m = re.search(r",\s*(\d{2,5})x(\d{2,5})", body)
    w, h = (int(m.group(1)), int(m.group(2))) if m else (1920, 1080)
    m = re.search(r"([\d.]+)\s*fps", body) or re.search(r"([\d.]+)\s*tbr", body)
    fps = float(m.group(1)) if m else 25.0
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", txt)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else None
    return Info(path, dur, fps, w, h)


def _lap_var(f):
    f = f.astype(np.float32)
    l = f[1:-1, 1:-1] * -4 + f[:-2, 1:-1] + f[2:, 1:-1] + f[1:-1, :-2] + f[1:-1, 2:]
    return float(l.var())


def _shift(a, b):
    fa = np.fft.rfft2(a - a.mean())
    fb = np.fft.rfft2(b - b.mean())
    r = fa * np.conj(fb)
    r /= np.abs(r) + 1e-9
    c = np.fft.irfft2(r, s=a.shape)
    y, x = np.unravel_index(np.argmax(c), c.shape)
    h, w = a.shape
    return (x - w if x > w // 2 else x), (y - h if y > h // 2 else y)


def _focus_score(v):
    return float(np.clip((np.log10(v + 1) - 0.7) / 1.6, 0, 1))


def _contrast_score(s):
    if s < 35:
        return s / 35
    return 1.0 if s <= 85 else max(0.0, 1 - (s - 85) / 60)


def analyze(path, progress=None, cancel=None):
    info = probe(path)
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-i", path, "-map", "0:v:0", "-an", "-sn", "-dn",
           "-vf", f"fps={SAMPLE_FPS},scale={AW}:{AH}:flags=fast_bilinear,format=gray",
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **_NOWIN)
    size = AW * AH
    sharp, csharp, mean, bright, std, diff, shifts = [], [], [], [], [], [], []
    prev = None
    try:
        while True:
            if cancel and cancel():
                raise InterruptedError("Cancelled")
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            f = np.frombuffer(buf, np.uint8).reshape(AH, AW)
            ff = f.astype(np.float32)
            sharp.append(_lap_var(f))
            csharp.append(_lap_var(f[45:135, 80:240]))
            mean.append(float(ff.mean()))
            std.append(float(ff.std()))
            bright.append(float((f > 250).mean()))
            diff.append(float(np.abs(ff - prev).mean()) if prev is not None else 0.0)
            shifts.append(_shift(ff, prev) if prev is not None else (0, 0))
            prev = ff
            if progress and info.duration and len(sharp) % 16 == 0:
                progress(min(0.99, len(sharp) / SAMPLE_FPS / info.duration))
    finally:
        p.kill()
        p.wait()
    n = len(sharp)
    if n == 0:
        raise ValueError("Could not decode any frame (unsupported codec? BRAW/R3D need the vendor SDK).")
    sharp, csharp, mean, std, bright, diff = map(np.array, (sharp, csharp, mean, std, bright, diff))
    sh = np.array(shifts, dtype=np.float32)
    dur = info.duration or n / SAMPLE_FPS
    info.duration = dur

    per = int(WIN_SEC * SAMPLE_FPS)
    idx = list(range(0, n, per))
    if len(idx) > 1 and n - idx[-1] < per // 2:
        idx.pop()
    bounds = idx + [n]
    t0, t1 = [], []
    comp = {k: [] for k in KEYS}
    for a, b in zip(bounds[:-1], bounds[1:]):
        m = float(mean[a:b].mean())
        pen = max(0, (45 - m) / 45, (m - 210) / 45) + max(0, float(bright[a:b].mean()) - 0.15) * 2
        acc = np.linalg.norm(np.diff(sh[a:b], axis=0), axis=1)
        accel = float(acc.mean()) if len(acc) else 0.0
        act = float(np.clip(diff[a:b].mean() / 10, 0, 1))
        comp["focus"].append(_focus_score(float(np.median(sharp[a:b]))))
        comp["contrast"].append(_contrast_score(float(std[a:b].mean())))
        comp["exposure"].append(float(np.clip(1 - pen, 0, 1)))
        comp["stability"].append(float(np.clip(1 - (accel - 1.5) / 8, 0, 1)))
        comp["importance"].append(0.6 * act + 0.4 * _focus_score(float(np.median(csharp[a:b]))))
        t0.append(a / SAMPLE_FPS)
        t1.append(min(b / SAMPLE_FPS, dur))
    if progress:
        progress(1.0)
    return Analysis(info, np.array(t0), np.array(t1), {k: np.array(v) for k, v in comp.items()})


# ---------------- Grading: Poor(0) / Fair(1) / Good(2) ----------------

def window_scores(a, weights):
    """weights: dict key -> 0..1. Returns 0..100 score per window."""
    w = np.array([weights.get(k, 0) for k in KEYS], float)
    M = np.vstack([a.comp[k] for k in KEYS])
    if w.sum() <= 0:
        return np.full(M.shape[1], 50.0)
    mean = (w[:, None] * M).sum(0) / w.sum()
    return 100 * (0.6 * mean + 0.4 * M[w > 0].min(0))


def grade(analyses, weights, p_poor, p_good):
    """Lowest p_poor% of all windows -> Poor, up to p_good% -> Fair, the rest -> Good.
    Returns one int array (0/1/2) per analysis."""
    scores = [window_scores(a, weights) for a in analyses]
    if not scores:
        return []
    allv = np.concatenate(scores)
    lo, hi = np.percentile(allv, [p_poor, p_good])
    return [np.where(s < lo, 0, np.where(s < hi, 1, 2)) for s in scores]


def level_segments(a, lv):
    """Merge consecutive windows with the same level -> [(t0, t1, level)]"""
    out = []
    for i in range(len(lv)):
        if out and out[-1][2] == lv[i]:
            out[-1] = (out[-1][0], float(a.t1[i]), int(lv[i]))
        else:
            out.append((float(a.t0[i]), float(a.t1[i]), int(lv[i])))
    return out


def frame_jpeg(path, t, width=640):
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
           "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    return subprocess.run(cmd, capture_output=True, **_NOWIN).stdout


def thumb_jpeg(path, t=1.0, height=120):
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
           "-vf", f"scale=-2:{height}", "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    out = subprocess.run(cmd, capture_output=True, **_NOWIN).stdout
    if not out and t > 0:
        return thumb_jpeg(path, 0, height)
    return out


# ---------------- Export (xmeml / FCP7 XML: imported by Premiere Pro and DaVinci Resolve) ----------------

def _rate(fps):
    tb = round(fps)
    ntsc = abs(fps - tb) > 0.01
    return f"<rate><timebase>{tb}</timebase><ntsc>{'TRUE' if ntsc else 'FALSE'}</ntsc></rate>", (tb * 1000 / 1001 if ntsc else tb)


def _url(p):
    return Path(p).resolve().as_uri().replace("file:///", "file://localhost/", 1)


LABELS = {0: "Rose", 1: "Yellow", 2: "Forest"}   # Poor / Fair / Good


def export_xmeml(items, out_path, name="MoneyMakingMachine"):
    """items = [(Analysis, [(t0, t1, level), ...]), ...]  -> one timeline with every segment, colour-labelled."""
    items = [i for i in items if i[1]]
    if not items:
        raise ValueError("Nothing to export.")
    seq_rate, seq_fps = _rate(items[0][0].info.fps)
    w0, h0 = items[0][0].info.width, items[0][0].info.height
    out, cursor, nclip = [], 0, 0
    for fi, (a, segs) in enumerate(items, 1):
        inf = a.info
        frate, ffps = _rate(inf.fps)
        fdur = int(inf.duration * ffps)
        file_full = (f'<file id="file-{fi}"><name>{escape(Path(inf.path).name)}</name>'
                     f'<pathurl>{escape(_url(inf.path))}</pathurl>{frate}<duration>{fdur}</duration>'
                     f'<media><video><samplecharacteristics><width>{inf.width}</width><height>{inf.height}</height>'
                     f'</samplecharacteristics></video></media></file>')
        for k, (s, e, lvl) in enumerate(segs):
            nclip += 1
            fin = max(0, round(s * ffps))
            fout = min(fdur, round(e * ffps))
            ln = max(1, round((fout - fin) / ffps * seq_fps))
            file_xml = file_full if k == 0 else f'<file id="file-{fi}"/>'
            out.append(
                f'<clipitem id="clipitem-{nclip}"><name>{escape(Path(inf.path).stem)}</name>'
                f'<duration>{fdur}</duration>{frate}<start>{cursor}</start><end>{cursor + ln}</end>'
                f'<in>{fin}</in><out>{fout}</out><labels><label2>{LABELS[lvl]}</label2></labels>'
                f'{file_xml}</clipitem>')
            cursor += ln
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">'
           f'<sequence id="sequence-1"><name>{escape(name)}</name><duration>{cursor}</duration>{seq_rate}'
           f'<media><video><format><samplecharacteristics>{seq_rate}<width>{w0}</width><height>{h0}</height>'
           f'</samplecharacteristics></format><track>{"".join(out)}</track></video></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return nclip
