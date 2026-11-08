"""ClipSelect core: analiză video (orice format citit de FFmpeg) + export XML (xmeml) pentru Premiere Pro."""
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

SAMPLE_FPS = 8          # câte cadre/secundă analizăm
WIN_SEC = 2.0           # lungimea unei ferestre de scorare
AW, AH = 320, 180       # rezoluția de analiză (cadrele sunt redimensionate)

# Extensii folosite doar la scanarea folderelor. Fișierele adăugate manual sunt acceptate ORICARE ar fi.
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
    sharp: np.ndarray    # 0-100
    stab: np.ndarray     # 0-100
    expo: np.ndarray     # 0-100
    total: np.ndarray    # 0-100

    @property
    def duration(self):
        return float(self.t1[-1]) if len(self.t1) else 0.0

    @property
    def score(self):
        w = self.t1 - self.t0
        return float((self.total * w).sum() / max(w.sum(), 1e-6)) if len(w) else 0.0

    def mean(self, arr):
        w = self.t1 - self.t0
        return float((arr * w).sum() / max(w.sum(), 1e-6)) if len(w) else 0.0


def probe(path):
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True,
                       text=True, errors="replace", **_NOWIN)
    txt = r.stderr
    vline = next((l for l in txt.splitlines() if " Video:" in l and "attached pic" not in l), None)
    if not vline:
        raise ValueError("Fișierul nu conține flux video (sau formatul nu e suportat de FFmpeg).")
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


def analyze(path, progress=None, cancel=None):
    info = probe(path)
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-i", path, "-map", "0:v:0", "-an", "-sn", "-dn",
           "-vf", f"fps={SAMPLE_FPS},scale={AW}:{AH}:flags=fast_bilinear,format=gray",
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **_NOWIN)
    size = AW * AH
    sharp, mean, bright, shifts = [], [], [], []
    prev = None
    try:
        while True:
            if cancel and cancel():
                raise InterruptedError("Anulat")
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            f = np.frombuffer(buf, np.uint8).reshape(AH, AW)
            sharp.append(_lap_var(f))
            mean.append(float(f.mean()))
            bright.append(float((f > 250).mean()))
            shifts.append(_shift(f.astype(np.float32), prev) if prev is not None else (0, 0))
            prev = f.astype(np.float32)
            if progress and info.duration and len(sharp) % 16 == 0:
                progress(min(0.99, len(sharp) / SAMPLE_FPS / info.duration))
    finally:
        p.kill()
        p.wait()
    n = len(sharp)
    if n == 0:
        raise ValueError("Nu s-a putut decoda niciun cadru (codec nesuportat? ex. BRAW/R3D cer SDK propriu).")

    sharp, mean, bright = np.array(sharp), np.array(mean), np.array(bright)
    sh = np.array(shifts, dtype=np.float32)
    dur = info.duration or n / SAMPLE_FPS
    info.duration = dur

    per = int(WIN_SEC * SAMPLE_FPS)
    idx = list(range(0, n, per))
    if len(idx) > 1 and n - idx[-1] < per // 2:
        idx.pop()
    bounds = idx + [n]
    t0, t1, S, T, E = [], [], [], [], []
    for a, b in zip(bounds[:-1], bounds[1:]):
        v = float(np.median(sharp[a:b]))
        s_sharp = np.clip((np.log10(v + 1) - 0.7) / 1.6, 0, 1)
        m = float(mean[a:b].mean())
        pen = max(0, (45 - m) / 45, (m - 210) / 45) + max(0, float(bright[a:b].mean()) - 0.15) * 2
        s_exp = float(np.clip(1 - pen, 0, 1))
        acc = np.linalg.norm(np.diff(sh[a:b], axis=0), axis=1)
        accel = float(acc.mean()) if len(acc) else 0.0
        s_stab = float(np.clip(1 - (accel - 1.5) / 8, 0, 1))
        t0.append(a / SAMPLE_FPS)
        t1.append(min(b / SAMPLE_FPS, dur))
        S.append(s_sharp * 100); T.append(s_stab * 100); E.append(s_exp * 100)
    S, T, E = map(np.array, (S, T, E))
    total = 0.6 * (0.4 * S + 0.3 * T + 0.3 * E) + 0.4 * np.minimum(np.minimum(S, T), E)
    if progress:
        progress(1.0)
    return Analysis(info, np.array(t0), np.array(t1), S, T, E, total)


def segments(a, thr, min_len):
    segs, cur = [], None
    for i in range(len(a.total)):
        if a.total[i] >= thr:
            cur = [a.t0[i], a.t1[i]] if cur is None else [cur[0], a.t1[i]]
        elif cur:
            segs.append(tuple(cur)); cur = None
    if cur:
        segs.append(tuple(cur))
    return [s for s in segs if s[1] - s[0] >= min_len]


def rating(score, thr):
    return "green" if score >= thr + 10 else "yellow" if score >= thr - 10 else "red"


def frame_jpeg(path, t, width=640):
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1",
           "-vf", f"scale={width}:-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-"]
    return subprocess.run(cmd, capture_output=True, **_NOWIN).stdout


# ---------------- Export xmeml (Final Cut Pro XML v4 - se importă în Premiere: File > Import) ----------------

def _rate(fps):
    tb = round(fps)
    ntsc = abs(fps - tb) > 0.01
    return f"<rate><timebase>{tb}</timebase><ntsc>{'TRUE' if ntsc else 'FALSE'}</ntsc></rate>", (tb * 1000 / 1001 if ntsc else tb)


def _url(p):
    return Path(p).resolve().as_uri().replace("file:///", "file://localhost/", 1)


LABELS = {"green": "Forest", "yellow": "Mango", "red": "Rose"}


def export_xmeml(items, out_path, name="ClipSelect"):
    """items = [(Analysis, [(t0,t1),...], 'green'|'yellow'|'red'), ...]"""
    items = [i for i in items if i[1]]
    if not items:
        raise ValueError("Nicio selecție de exportat.")
    seq_rate, seq_fps = _rate(items[0][0].info.fps)
    w0, h0 = items[0][0].info.width, items[0][0].info.height
    out, cursor, nclip = [], 0, 0
    for fi, (a, segs, rate_name) in enumerate(items, 1):
        inf = a.info
        frate, ffps = _rate(inf.fps)
        fdur = int(inf.duration * ffps)
        file_full = (f'<file id="file-{fi}"><name>{escape(Path(inf.path).name)}</name>'
                     f'<pathurl>{escape(_url(inf.path))}</pathurl>{frate}<duration>{fdur}</duration>'
                     f'<media><video><samplecharacteristics><width>{inf.width}</width><height>{inf.height}</height>'
                     f'</samplecharacteristics></video></media></file>')
        for k, (s, e) in enumerate(segs):
            nclip += 1
            fin = max(0, round(s * ffps))
            fout = min(fdur, round(e * ffps))
            ln = max(1, round((fout - fin) / ffps * seq_fps))
            file_xml = file_full if k == 0 else f'<file id="file-{fi}"/>'
            out.append(
                f'<clipitem id="clipitem-{nclip}"><name>{escape(Path(inf.path).stem)}</name>'
                f'<duration>{fdur}</duration>{frate}<start>{cursor}</start><end>{cursor + ln}</end>'
                f'<in>{fin}</in><out>{fout}</out><labels><label2>{LABELS[rate_name]}</label2></labels>'
                f'{file_xml}</clipitem>')
            cursor += ln
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">'
           f'<sequence id="sequence-1"><name>{escape(name)}</name><duration>{cursor}</duration>{seq_rate}'
           f'<media><video><format><samplecharacteristics>{seq_rate}<width>{w0}</width><height>{h0}</height>'
           f'</samplecharacteristics></format><track>{"".join(out)}</track></video></media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return nclip
