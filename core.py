"""MoneyMakingMachine core: video analysis (any format FFmpeg can read), 3-level grading, XML export."""
import os
import re
import shutil
import subprocess
import sys
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


HWACCEL = True          # set by the app (Settings > Performance)
_HW = None


def decode_flags():
    """Speed-ups for the analysis decode: skip the in-loop deblocking filter (invisible at 320x180) and, on a Mac,
    use the hardware decoder when this FFmpeg build has it (FFmpeg falls back to software when a codec isn't supported)."""
    global _HW
    flags = ["-skip_loop_filter", "all"]
    if HWACCEL and sys.platform == "darwin":
        if _HW is None:
            try:
                out = subprocess.run([ffmpeg_exe(), "-hide_banner", "-hwaccels"], capture_output=True, text=True).stdout
                _HW = "videotoolbox" in out
            except Exception:
                _HW = False
        if _HW:
            flags = ["-hwaccel", "videotoolbox"] + flags
    return flags


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
    fs: dict = None  # per-sample (8/s) raw measurements: lap, mean, bright, diff, sx, sy (robust shift), gx, gy (global)

    @property
    def duration(self):
        return float(self.t1[-1]) if len(self.t1) else 0.0

    def to_json(self):
        return {"info": asdict(self.info), "t0": self.t0.round(2).tolist(), "t1": self.t1.round(2).tolist(),
                "comp": {k: v.round(3).tolist() for k, v in self.comp.items()},
                "fs": {k: np.asarray(v).round(2).tolist() for k, v in self.fs.items()} if self.fs else None}

    @staticmethod
    def from_json(d):
        return Analysis(Info(**d["info"]), np.array(d["t0"]), np.array(d["t1"]),
                        {k: np.array(v) for k, v in d["comp"].items()},
                        {k: np.array(v, float) for k, v in d["fs"].items()} if d.get("fs") else None)


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


def _robust_shift(ff, prev):
    """Whole-frame shift (original estimate) + robust shift = median of whole frame and 4 quadrants.
    The median ignores a moving subject that dominates one region of the frame."""
    h, w = ff.shape
    g = _shift(ff, prev)
    cands = [g]
    for y0, y1, x0, x1 in ((0, h // 2, 0, w // 2), (0, h // 2, w // 2, w), (h // 2, h, 0, w // 2), (h // 2, h, w // 2, w)):
        cands.append(_shift(ff[y0:y1, x0:x1], prev[y0:y1, x0:x1]))
    c = np.array(cands, float)
    return (float(np.median(c[:, 0])), float(np.median(c[:, 1]))), g


def _accel(sh, a, b):
    acc = np.linalg.norm(np.diff(sh[a:b], axis=0), axis=1)
    return float(acc.mean()) if len(acc) else 0.0


def analyze(path, progress=None, cancel=None):
    info = probe(path)
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", *decode_flags(), "-i", path, "-map", "0:v:0", "-an", "-sn", "-dn",
           "-vf", f"fps={SAMPLE_FPS},scale={AW}:{AH}:flags=fast_bilinear,format=gray",
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **_NOWIN)
    size = AW * AH
    sharp, csharp, mean, bright, std, diff, shifts, shifts_g = [], [], [], [], [], [], [], []
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
            if prev is not None:
                r, g = _robust_shift(ff, prev)
            else:
                r = g = (0, 0)
            shifts.append(r)
            shifts_g.append(g)
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
    shg = np.array(shifts_g, dtype=np.float32)
    dur = info.duration or n / SAMPLE_FPS
    info.duration = dur

    per = int(WIN_SEC * SAMPLE_FPS)
    idx = list(range(0, n, per))
    if len(idx) > 1 and n - idx[-1] < per // 2:
        idx.pop()
    bounds = idx + [n]
    t0, t1 = [], []
    comp = {k: [] for k in KEYS + ['stability_v1']}
    for a, b in zip(bounds[:-1], bounds[1:]):
        m = float(mean[a:b].mean())
        pen = max(0, (45 - m) / 45, (m - 210) / 45) + max(0, float(bright[a:b].mean()) - 0.15) * 2
        accel, accel_g = _accel(sh, a, b), _accel(shg, a, b)
        act = float(np.clip(diff[a:b].mean() / 10, 0, 1))
        comp["focus"].append(_focus_score(float(np.median(sharp[a:b]))))
        comp["contrast"].append(_contrast_score(float(std[a:b].mean())))
        comp["exposure"].append(float(np.clip(1 - pen, 0, 1)))
        comp["stability"].append(float(np.clip(1 - (accel - 1.5) / 8, 0, 1)))
        comp["stability_v1"].append(float(np.clip(1 - (accel_g - 1.5) / 8, 0, 1)))
        comp["importance"].append(0.6 * act + 0.4 * _focus_score(float(np.median(csharp[a:b]))))
        t0.append(a / SAMPLE_FPS)
        t1.append(min(b / SAMPLE_FPS, dur))
    if progress:
        progress(1.0)
    fs = dict(lap=sharp, mean=mean, bright=bright, diff=diff, sx=sh[:, 0], sy=sh[:, 1], gx=shg[:, 0], gy=shg[:, 1])
    return Analysis(info, np.array(t0), np.array(t1), {k: np.array(v) for k, v in comp.items()},
                    {k: np.asarray(v, float) for k, v in fs.items()})


# ---------------- Grading: Poor(0) / Fair(1) / Good(2) ----------------

MOVE_PX = 8.0   # robust shift per sample (1/8 s, 320 px wide) above which the camera is "moving" between subjects


def focus_vec(lap):
    return np.clip((np.log10(np.asarray(lap) + 1) - 0.7) / 1.6, 0, 1)


def exposure_vec(mean, bright):
    mean, bright = np.asarray(mean), np.asarray(bright)
    pen = np.maximum.reduce([np.zeros_like(mean), (45 - mean) / 45, (mean - 210) / 45]) + np.maximum(0, bright - 0.15) * 2
    return np.clip(1 - pen, 0, 1)


def jitter_vec(fs):
    """Per-sample change of the global shift (the original stability measure), 0 for the first sample."""
    g = np.stack([fs["gx"], fs["gy"]], 1)
    j = np.zeros(len(g))
    j[1:] = np.linalg.norm(np.diff(g, axis=0), axis=1)
    return j


def moving_mask(fs):
    sp = np.hypot(fs["sx"], fs["sy"])
    if len(sp) >= 3:
        sp = np.median(np.vstack([np.r_[sp[:1], sp[:-1]], sp, np.r_[sp[1:], sp[-1:]]]), axis=0)
    m = sp > MOVE_PX
    df = np.asarray(fs["diff"])            # whip pans alias the shift estimate but change the whole frame at once
    m |= df > max(15.0, 3 * float(np.median(df)) if len(df) else 15.0)
    d = m.copy()
    d[1:] |= m[:-1]
    d[:-1] |= m[1:]
    return d


def _v1_score(fs, a, b, jit):
    F = float(focus_vec([np.median(fs["lap"][a:b])])[0])
    E = float(exposure_vec([np.mean(fs["mean"][a:b])], [np.mean(fs["bright"][a:b])])[0])
    acc = jit[a + 1:b]
    S = float(np.clip(1 - ((acc.mean() if len(acc) else 0.0) - 1.5) / 8, 0, 1))
    return 100 * (0.6 * (0.4 * F + 0.3 * S + 0.3 * E) + 0.4 * min(F, S, E))


def auto_segments(a, thr, min_len, cut_moves=True):
    """AUTO mode (the original algorithm, finer): the clip is split into 'holds' between camera moves; every second of
    a hold is scored like the first version; kept parts (level 2) shorter than min_len are dropped (level 0)."""
    dur = a.duration
    if not a.fs:   # analyses made before per-sample data existed
        lv = np.where(auto_scores(a) >= thr, 2, 0)
        segs = _merge([[float(a.t0[i]), float(a.t1[i]), int(lv[i])] for i in range(len(lv))])
    else:
        fs, sr = a.fs, SAMPLE_FPS
        n = len(fs["lap"])
        mv = moving_mask(fs) if cut_moves else np.zeros(n, bool)
        jit = jitter_vec(fs)
        sel = np.zeros(n, bool)
        i = 0
        while i < n:
            if mv[i]:
                i += 1
                continue
            j = i
            while j < n and not mv[j]:
                j += 1
            b = list(range(i, j, sr))
            if len(b) > 1 and j - b[-1] < sr // 2:
                b.pop()
            b.append(j)
            for x0, x1 in zip(b[:-1], b[1:]):
                if x1 - x0 >= 2 and _v1_score(fs, x0, x1, jit) >= thr:
                    sel[x0:x1] = True
            i = j
        segs = []
        k = 0
        while k < n:
            m = k
            while m < n and sel[m] == sel[k]:
                m += 1
            segs.append([k / sr, min(m / sr, dur), 2 if sel[k] else 0])
            k = m
        if segs:
            segs[-1][1] = dur
    for sg in segs:
        if sg[2] == 2 and sg[1] - sg[0] < min_len - 1e-6:
            sg[2] = 0
    return [tuple(x) for x in _merge(segs)]


def auto_scores(a):
    """AUTO mode = the original algorithm: focus, stability (whole-frame estimate), exposure. Absolute 0-100 score."""
    F, E = a.comp["focus"], a.comp["exposure"]
    S = a.comp.get("stability_v1", a.comp["stability"])
    return 100 * (0.6 * (0.4 * F + 0.3 * S + 0.3 * E) + 0.4 * np.minimum(np.minimum(F, S), E))


def window_scores(a, weights):
    """CUSTOM mode. weights: key -> 0..1 (0 = switched off). Returns 0..100 per window.
    'importance' is a soft criterion: it contributes to the average but never drags the score down as 'worst defect'."""
    w = np.array([weights.get(k, 0) for k in KEYS], float)
    M = np.vstack([a.comp[k] for k in KEYS])
    if w.sum() <= 0:
        return np.full(M.shape[1], 50.0)
    mean = (w[:, None] * M).sum(0) / w.sum()
    defects = [i for i, k in enumerate(KEYS) if w[i] > 0 and k != "importance"]
    mn = M[defects].min(0) if defects else mean
    return 100 * (0.6 * mean + 0.4 * mn)


def _merge(segs):
    out = []
    for s in segs:
        if out and out[-1][2] == s[2]:
            out[-1][1] = s[1]
        else:
            out.append(list(s))
    return out


def apply_min_cut(a, lv, min_len):
    """Merge consecutive windows of the same level, then absorb every segment shorter than min_len into the
    neighbour with the closest level (ties: the longer neighbour). Result: [(t0, t1, level)]"""
    segs = _merge([[float(a.t0[i]), float(a.t1[i]), int(lv[i])] for i in range(len(lv))])
    while len(segs) > 1:
        short = [i for i, s in enumerate(segs) if s[1] - s[0] < min_len - 1e-6]
        if not short:
            break
        i = min(short, key=lambda k: segs[k][1] - segs[k][0])
        cands = [j for j in (i - 1, i + 1) if 0 <= j < len(segs)]
        j = min(cands, key=lambda j: (abs(segs[j][2] - segs[i][2]), -(segs[j][1] - segs[j][0])))
        segs[j][0] = min(segs[j][0], segs[i][0])
        segs[j][1] = max(segs[j][1], segs[i][1])
        del segs[i]
        segs = _merge(segs)
    return [(s[0], s[1], s[2]) for s in segs]


PROTECT_POOR, PROTECT_FAIR = 65, 85   # "Protect good frames": above these scores a window can't be Poor / Fair


def grade_segments(analyses, s):
    """s = project settings. Returns, per analysis, a list of (t0, t1, level)."""
    if not analyses:
        return []
    if s.get("mode", "auto") == "auto":
        return [auto_segments(a, s.get("thr", 60), float(s.get("mincut", 3)), s.get("cutmoves", True)) for a in analyses]
    else:
        on = s.get("on", {})
        weights = {k: (s.get(k, 50) / 100 if on.get(k, True) else 0) for k in KEYS}
        scores = [window_scores(a, weights) for a in analyses]
        lo, hi = np.percentile(np.concatenate(scores), [s.get("p1", 25), s.get("p2", 65)])
        if s.get("protect", True):
            lo, hi = min(lo, PROTECT_POOR), min(hi, PROTECT_FAIR)
        lvs = [np.where(sc < lo, 0, np.where(sc < hi, 1, 2)) for sc in scores]
    mc = float(s.get("mincut", 3))
    return [apply_min_cut(a, lv, mc) for a, lv in zip(analyses, lvs)]


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
FIELDS = {"lower": "lower", "upper": "upper"}


def _sc(rate, w, h, fields):
    # pixelaspectratio MUST be explicit: without it Premiere guesses a PAL 4:3 pixel aspect (1.094) -> "Scale Width 109.4".
    return (f"<samplecharacteristics>{rate}<width>{w}</width><height>{h}</height><anamorphic>FALSE</anamorphic>"
            f"<pixelaspectratio>square</pixelaspectratio><fielddominance>{fields}</fielddominance></samplecharacteristics>")


def export_xmeml(items, out_path, name="MoneyMakingMachine", seq=None, single=False):
    """items = [(Analysis, [(t0, t1, level), ...]), ...]

    One sequence, THREE video tracks: V1 = Poor, V2 = Fair, V3 = Good (Good on top, like the preview).
    Every segment keeps its original position in the footage timeline (clips follow each other).
    seq = {"width": int|None, "height": int|None, "fps": float|None, "fields": "lower"|"upper"|"none"}
    """
    seq = seq or {}
    items = [i for i in items if i[1]]
    if not items:
        raise ValueError("Nothing to export.")
    first = items[0][0].info
    sw, sh = seq.get("width") or first.width, seq.get("height") or first.height
    seq_rate, seq_fps = _rate(seq.get("fps") or first.fps)
    fd = FIELDS.get(seq.get("fields", "lower"), "none")

    entries, offset, files = [], 0, {}
    if single:   # AUTO: only the kept shots, back to back on one track (like the first version)
        for fi, (a, segs) in enumerate(items, 1):
            inf = a.info
            frate, ffps = _rate(inf.fps)
            fdur = int(inf.duration * ffps)
            files[fi] = (inf, frate, fdur)
            for s, e, lvl in segs:
                if lvl != 2:
                    continue
                sdur = max(1, int(round(inf.duration * seq_fps)))
                fin = max(0, round(s * seq_fps))
                fout = min(sdur, fin + max(1, round((e - s) * seq_fps)))
                entries.append((2, offset, offset + (fout - fin), fin, fout, fi))
                offset += fout - fin
        items = []
    for fi, (a, segs) in enumerate(items, 1):
        inf = a.info
        frate, ffps = _rate(inf.fps)
        fdur = int(inf.duration * ffps)
        files[fi] = (inf, frate, fdur)
        sdur = max(1, int(round(inf.duration * seq_fps)))
        for s, e, lvl in segs:
            st = offset + round(s * seq_fps)
            fin = max(0, round(s * seq_fps))
            fout = min(sdur, fin + max(1, round((e - s) * seq_fps)))
            entries.append((lvl, st, st + (fout - fin), fin, fout, fi))
        offset += round(a.duration * seq_fps)
    total = offset

    # ---- every cut gets its own sound, LINKED to the picture (moves / trims together in Premiere)
    lay = {fi: audio_layout(files[fi][0].path) for fi in files}          # (sample rate, total channels)
    levels = (2,) if single else (0, 1, 2)
    vt = {lvl: sorted((e for e in entries if e[0] == lvl), key=lambda e: e[1]) for lvl in levels}
    # stereo files -> A1 + A2; files with more than 2 channels (Sony MXF: 4 mono channels) -> channel 1 only, mono
    use = {fi: (1 if ch > 2 else ch) for fi, (_, ch) in lay.items()}
    nach = max(list(use.values()) + [0])
    at = {k: sorted((e for e in entries if use[e[5]] >= k), key=lambda e: e[1]) for k in range(1, nach + 1)}
    ids, n = {}, 0
    for t_i, lvl in enumerate(levels, 1):
        for c_i, e in enumerate(vt[lvl], 1):
            n += 1
            ids[("v", id(e))] = (f"clipitem-{n}", t_i, c_i)
    for k in range(1, nach + 1):
        for c_i, e in enumerate(at[k], 1):
            n += 1
            ids[("a", k, id(e))] = (f"clipitem-{n}", k, c_i)

    def links(e):
        out = []
        v = ids[("v", id(e))]
        out.append(f"<link><linkclipref>{v[0]}</linkclipref><mediatype>video</mediatype><trackindex>{v[1]}</trackindex>"
                   f"<clipindex>{v[2]}</clipindex></link>")
        for k in range(1, nach + 1):
            a = ids.get(("a", k, id(e)))
            if a:
                out.append(f"<link><linkclipref>{a[0]}</linkclipref><mediatype>audio</mediatype><trackindex>{a[1]}</trackindex>"
                           f"<clipindex>{a[2]}</clipindex><groupindex>1</groupindex></link>")
        return "".join(out) if len(out) > 1 else ""

    defined, tracks = set(), []

    def fxml(fi):
        inf, frate, fdur = files[fi]
        if fi in defined:
            return f'<file id="file-{fi}"/>'
        defined.add(fi)
        rate, ch = lay[fi]
        aud = (f'<audio><samplecharacteristics><depth>16</depth><samplerate>{rate}</samplerate></samplecharacteristics>'
               f'<channelcount>{ch}</channelcount></audio>') if ch else ""
        return (f'<file id="file-{fi}"><name>{escape(Path(inf.path).name)}</name>'
                f'<pathurl>{escape(_url(inf.path))}</pathurl>{frate}<duration>{fdur}</duration>'
                f'<media><video>{_sc(frate, inf.width, inf.height, "none")}</video>{aud}</media></file>')

    def head(e, cid):
        lvl, st, en, fin, fout, fi = e
        inf = files[fi][0]
        return (f'<clipitem id="{cid}"><name>{escape(Path(inf.path).name)}</name>'
                f'<duration>{max(1, int(round(inf.duration * seq_fps)))}</duration>{seq_rate}<start>{st}</start><end>{en}</end>'
                f'<in>{fin}</in><out>{fout}</out><labels><label2>{LABELS[lvl]}</label2></labels>')

    for lvl in levels:
        out = [head(e, ids[("v", id(e))][0]) + fxml(e[5]) + links(e) + "</clipitem>" for e in vt[lvl]]
        tracks.append(f'<track>{"".join(out)}<enabled>TRUE</enabled><locked>FALSE</locked></track>')
    atracks = []
    for k in range(1, nach + 1):
        out = [head(e, ids[("a", k, id(e))][0]) + fxml(e[5]) +
               f'<sourcetrack><mediatype>audio</mediatype><trackindex>{k}</trackindex></sourcetrack>' + links(e) + "</clipitem>"
               for e in at[k]]
        atracks.append(f'<track>{"".join(out)}<enabled>TRUE</enabled><locked>FALSE</locked></track>')
    arate = next((r for r, ch in lay.values() if ch), 48000)
    audio = (f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
             f'<samplerate>{arate}</samplerate></samplecharacteristics></format>{"".join(atracks)}</audio>') if atracks else ""
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">'
           f'<sequence id="sequence-1"><name>{escape(name)}</name><duration>{total}</duration>{seq_rate}'
           f'<media><video><format>{_sc(seq_rate, sw, sh, fd)}</format>{"".join(tracks)}</video>{audio}</media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return len(entries)


def audio_layout(path):
    """(sample rate, total number of audio channels) of a file. Sony MXF stores one mono stream per channel."""
    r = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace", **_NOWIN)
    total, rate = 0, 48000
    for m in re.finditer(r"Stream #\d+:\d+.*?: Audio:.*?(\d+) Hz, ([^,\n]+)", r.stderr):
        rate = int(m.group(1))
        lay = m.group(2).strip()
        mm = re.match(r"(\d+) channels?", lay)
        total += 1 if lay == "mono" else 2 if lay == "stereo" else int(mm.group(1)) if mm else 6 if lay.startswith("5.1") else 2
    return rate, total


def analyze_range(path, a, b, fps=4):
    """Quick look at one selection only (from a to b seconds): per sample (fps per second) a quality score 0..1
    (sharpness, steadiness, exposure) and the amount of movement 0..1. Used by Teaser Studio to pick the best part of
    each selection. Returns (times relative to a, quality, motion) or None."""
    dur = max(0.0, b - a)
    if dur < 0.3:
        return None
    cmd = [ffmpeg_exe(), "-v", "error", "-nostdin", *decode_flags(), "-ss", f"{a:.3f}", "-t", f"{dur:.3f}", "-i", path,
           "-map", "0:v:0", "-an", "-sn", "-dn", "-vf", f"fps={fps},scale={AW}:{AH}:flags=fast_bilinear,format=gray",
           "-f", "rawvideo", "-"]
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, **_NOWIN)
    size = AW * AH
    lap, mean, bright, diff, jit = [], [], [], [], []
    prev, prev_shift = None, (0, 0)
    try:
        while True:
            buf = p.stdout.read(size)
            if len(buf) < size:
                break
            f = np.frombuffer(buf, np.uint8).reshape(AH, AW)
            ff = f.astype(np.float32)
            lap.append(_lap_var(f))
            mean.append(float(ff.mean()))
            bright.append(float((f > 250).mean()))
            if prev is None:
                diff.append(0.0)
                jit.append(0.0)
            else:
                diff.append(float(np.abs(ff - prev).mean()))
                sh = _shift(ff, prev)
                jit.append(float(np.hypot(sh[0] - prev_shift[0], sh[1] - prev_shift[1])))
                prev_shift = sh
            prev = ff
    finally:
        p.kill()
        p.wait()
    if not lap:
        return None
    F = focus_vec(lap)
    E = exposure_vec(mean, bright)
    j = np.convolve(np.asarray(jit), np.ones(3) / 3, "same")
    S = np.clip(1 - (j - 1.5 * 2) / 16, 0, 1)        # 4 samples/s: shifts are ~2x larger than at 8/s
    q = 0.45 * F + 0.35 * S + 0.2 * E
    m = np.clip(np.asarray(diff) / 12, 0, 1)
    t = np.arange(len(q)) / fps
    return t.round(3).tolist(), q.round(3).tolist(), m.round(3).tolist()
