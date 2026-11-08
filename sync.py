"""Audio sync: align camera clips to a master audio recording (mixer recorder).

Method: GCC-PHAT cross-correlation (robust to reverb, music and unequal levels) between several loud windows of each
clip and the whole master. Windows that agree on the same offset give a high-confidence result and a drift estimate.
"""
import re
import subprocess
from pathlib import Path
from xml.sax.saxutils import escape

import numpy as np

import core

SR = 4000                 # analysis sample rate (resolution 0.25 ms, far below one video frame)
WIN = 15.0                # seconds per correlation window
K = 5                     # windows per clip
F = 1 << 19               # FFT block size over the master
Z_MIN = 7.0               # minimum z-score for a window to count as a match

AUDIO_EXT = {".wav", ".bwf", ".w64", ".mp3", ".flac", ".aif", ".aiff", ".m4a", ".aac", ".ogg", ".opus", ".wma", ".mka"}


def audio_pcm(path, sr=SR):
    """Mono float32 audio at `sr`. All audio streams of the file are mixed (FX6 MXF has one stream per channel)."""
    exe = core.ffmpeg_exe()
    r = subprocess.run([exe, "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace", **core._NOWIN)
    n = len(re.findall(r"Stream #\d+:\d+.*?: Audio:", r.stderr))
    if n == 0:
        raise ValueError("No audio stream")
    n = min(n, 8)
    if n == 1:
        args = ["-map", "0:a:0", "-ac", "1"]
    else:
        ins = "".join(f"[0:a:{i}]" for i in range(n))
        args = ["-filter_complex", f"{ins}amix=inputs={n}[a]", "-map", "[a]", "-ac", "1"]
    cmd = [exe, "-v", "error", "-nostdin", "-i", path, *args, "-vn", "-ar", str(sr), "-f", "f32le", "-"]
    out = subprocess.run(cmd, capture_output=True, **core._NOWIN).stdout
    x = np.frombuffer(out, np.float32)
    if len(x) < sr:
        raise ValueError("Audio too short or unreadable")
    return x


def audio_info(path):
    """(sample_rate, channels) of the first audio stream, for the XML export."""
    r = subprocess.run([core.ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True, text=True,
                       errors="replace", **core._NOWIN)
    m = re.search(r"Audio:.*?(\d+) Hz, ([^,\n]+)", r.stderr)
    if not m:
        return 48000, 2
    rate, lay = int(m.group(1)), m.group(2).strip()
    mm = re.match(r"(\d+) channels?", lay)
    ch = 1 if lay == "mono" else 2 if lay == "stereo" else int(mm.group(1)) if mm else 6 if lay.startswith("5.1") else 2
    return rate, ch


def _prep(x):
    x = x.astype(np.float32)
    x = x - x.mean()
    y = np.empty_like(x)
    y[0] = 0
    y[1:] = x[1:] - 0.95 * x[:-1]       # pre-emphasis: more weight on the information-rich upper band
    return y


class MasterIndex:
    """Whitened block spectra of the master, computed once and reused for every clip window."""

    def __init__(self, x):
        x = _prep(x)
        self.n = len(x)
        self.step = F - int(WIN * SR)
        self.blocks = []
        s = 0
        while True:
            seg = x[s:s + F]
            X = np.fft.rfft(seg, F)
            X = (X / (np.abs(X) + 1e-9)).astype(np.complex64)
            self.blocks.append((s, X))
            if s + F >= self.n:
                break
            s += self.step

    def correlate(self, t):
        """Returns (lag_samples, z, ratio): best position of window `t` in the master."""
        wn = len(t)
        T = np.fft.rfft(t, F)
        T = (T / (np.abs(T) + 1e-9)).astype(np.complex64)
        peaks, s1, s2, cnt = [], 0.0, 0.0, 0
        guard = int(0.5 * SR)
        for s, X in self.blocks:
            kmax = min(self.step, self.n - s - wn)
            if kmax < 0:
                continue
            v = np.fft.irfft(X * np.conj(T), F)[:kmax + 1]
            v64 = v.astype(np.float64)
            s1 += v64.sum()
            s2 += (v64 * v64).sum()
            cnt += len(v)
            k = int(np.argmax(v))
            peaks.append((float(v[k]), s + k))
            lo, hi = max(0, k - guard), min(len(v), k + guard)
            w = v.copy()
            w[lo:hi] = -1
            k2 = int(np.argmax(w))
            if w[k2] > -1:
                peaks.append((float(w[k2]), s + k2))
        if not peaks:
            return 0, 0.0, 1.0
        mu = s1 / cnt
        sd = max(1e-12, (s2 / cnt - mu * mu) ** 0.5)
        peaks.sort(reverse=True)
        top = peaks[0]
        second = next((p for p in peaks[1:] if abs(p[1] - top[1]) > guard), None)
        z = (top[0] - mu) / sd
        ratio = (top[0] - mu) / max(1e-12, (second[0] - mu)) if second else 99.0
        return top[1], z, ratio


def _pick_windows(x):
    n, wn = len(x), min(int(WIN * SR), len(x))
    if n <= wn * 1.2:
        return [0], wn
    c = np.concatenate([[0.0], np.cumsum(x.astype(np.float64) ** 2)])
    hop = int(2.5 * SR)
    cands = np.arange(0, n - wn + 1, hop)
    energy = c[cands + wn] - c[cands]
    parts = np.array_split(np.arange(len(cands)), min(K, len(cands)))
    starts = sorted({int(cands[p[np.argmax(energy[p])]]) for p in parts if len(p)})
    return starts, wn


def _decide(cands):
    """cands: [(t_clip, offset, z, ratio)] for one master -> dict or None."""
    good = [c for c in cands if c[2] >= Z_MIN]
    if not good:
        return dict(conf="fail", z=max((c[2] for c in cands), default=0.0), n=0, k=len(cands), offset=0.0, drift_ppm=0.0)
    best = []
    for s in good:
        inl = [c for c in good if abs(c[1] - s[1]) <= 0.05 + 300e-6 * abs(c[0] - s[0])]
        if len(inl) > len(best) or (len(inl) == len(best) and sum(c[2] for c in inl) > sum(c[2] for c in best)):
            best = inl
    if len(best) >= 3:
        t = np.array([c[0] for c in best])
        o = np.array([c[1] for c in best])
        d, o0 = np.polyfit(t, o, 1)
    else:
        o0, d = float(np.median([c[1] for c in best])), 0.0
    zm = float(np.mean([c[2] for c in best]))
    n = len(best)
    conf = "high" if (n >= 3 or (n == 2 and zm >= 12)) else "medium" if (n == 2 or zm >= 15) else "low"
    if any(c[2] >= 10 and c not in best for c in good):   # strong windows disagree -> downgrade one level
        conf = {"high": "medium", "medium": "low", "low": "low"}[conf]
    return dict(conf=conf, z=zm, n=n, k=len(cands), offset=float(o0), drift_ppm=float(d * 1e6))


def sync_clip(indexes, x):
    x = _prep(x)
    starts, wn = _pick_windows(x)
    best = None
    for mi, idx in enumerate(indexes):
        cands = []
        for st in starts:
            lag, z, ratio = idx.correlate(x[st:st + wn])
            cands.append((st / SR, lag / SR - st / SR, z, ratio))
        r = _decide(cands)
        r["master"] = mi
        rank = ({"fail": 0, "low": 1, "medium": 2, "high": 3}[r["conf"]], r["n"], r["z"])
        if best is None or rank > best[0]:
            best = (rank, r)
    r = best[1]
    r["dur"] = len(x) / SR
    return r


def run_sync(masters, clips, progress=None, cancel=None):
    """masters, clips: lists of paths. Returns (masters_info, {clip_path: result})."""
    def chk():
        if cancel and cancel():
            raise InterruptedError("Cancelled")

    indexes, info = [], []
    for i, m in enumerate(masters):
        chk()
        if progress:
            progress(f"Reading master {i + 1} of {len(masters)}", 0.0)
        x = audio_pcm(m)
        info.append(dict(path=m, duration=len(x) / SR, onsets=onsets(x)))
        indexes.append(MasterIndex(x))
    results = {}
    for i, c in enumerate(clips):
        chk()
        if progress:
            progress(f"Syncing {Path(c).name}", i / max(1, len(clips)))
        try:
            r = sync_clip(indexes, audio_pcm(c))
            r["manual"] = False
        except Exception as e:
            r = dict(conf="fail", z=0.0, n=0, k=0, offset=0.0, drift_ppm=0.0, master=0, dur=0.0, manual=False, error=str(e))
        try:
            r["dur"] = core.probe(c).duration or r["dur"]
        except Exception:
            pass
        results[c] = r
    if progress:
        progress("Done", 1.0)
    return info, results


# ---------------- verification XML: master audio on A1/A2, one video track per camera, at synced positions -------------

CAM_LABELS = ["Violet", "Caribbean", "Mango", "Forest", "Iris", "Rose", "Cerulean", "Lavender"]


def export_sync_xml(masters, cams, results, out_path, name="Sync"):
    """One sequence per master. cams = [{"name", "role", "clips": [paths]}]. Clips that failed to sync are skipped."""
    seqs, fid, cid, defined = [], 0, 0, {}
    infos = {}
    for mi, m in enumerate(masters):
        placed = []   # (cam_index, path, offset, info)
        for ci, cam in enumerate(cams):
            for p in cam["clips"]:
                r = results.get(p)
                if r and r["conf"] != "fail" and r.get("master", 0) == mi:
                    infos.setdefault(p, core.probe(p))
                    placed.append((ci, p, r["offset"], infos[p], r))
        if not placed:
            continue
        first = placed[0][3]
        rate_xml, fps = core._rate(first.fps)
        t0 = min(0.0, min(o for _, _, o, _, _ in placed))
        mdur = int(np.ceil(m["duration"] * fps))
        arate, ach = audio_info(m["path"])
        ach = max(1, min(2, ach))
        mfile_id = f"file-m{mi}"
        afile = (f'<file id="{mfile_id}"><name>{escape(Path(m["path"]).name)}</name><pathurl>{escape(core._url(m["path"]))}</pathurl>'
                 f'{rate_xml}<duration>{mdur}</duration><media><audio><samplecharacteristics><depth>16</depth>'
                 f'<samplerate>{arate}</samplerate></samplecharacteristics><channelcount>{ach}</channelcount></audio></media></file>')
        a_tracks = []
        ms = round(-t0 * fps)
        for ch in range(1, ach + 1):
            cid += 1
            body = afile if (ch == 1) else f'<file id="{mfile_id}"/>'
            a_tracks.append(
                f'<track><clipitem id="clipitem-{cid}"><name>{escape(Path(m["path"]).name)}</name><duration>{mdur}</duration>{rate_xml}'
                f'<start>{ms}</start><end>{ms + mdur}</end><in>0</in><out>{mdur}</out>{body}'
                f'<sourcetrack><mediatype>audio</mediatype><trackindex>{ch}</trackindex></sourcetrack></clipitem>'
                f'<enabled>TRUE</enabled><locked>FALSE</locked></track>')
        v_tracks = []
        for ci, cam in enumerate(cams):
            items = sorted((x for x in placed if x[0] == ci), key=lambda x: x[2])
            if not items:
                continue
            out = []
            for _, p, off, inf, r in items:
                frate, ffps = core._rate(inf.fps)
                fdur = int((inf.duration or r.get("dur", 0)) * ffps)
                st = round((off - t0) * fps)
                ln = max(1, round(fdur / ffps * fps))
                cid += 1
                if p in defined:
                    fx = f'<file id="{defined[p]}"/>'
                else:
                    fid += 1
                    defined[p] = f"file-{fid}"
                    fx = (f'<file id="file-{fid}"><name>{escape(Path(p).name)}</name><pathurl>{escape(core._url(p))}</pathurl>{frate}'
                          f'<duration>{fdur}</duration><media><video>{core._sc(frate, inf.width, inf.height, "none")}</video></media></file>')
                flag = " [CHECK SYNC]" if r["conf"] == "low" else ""
                out.append(f'<clipitem id="clipitem-{cid}"><name>{escape(Path(p).stem + flag)}</name><duration>{fdur}</duration>{frate}'
                           f'<start>{st}</start><end>{st + ln}</end><in>0</in><out>{fdur}</out>'
                           f'<labels><label2>{CAM_LABELS[ci % len(CAM_LABELS)]}</label2></labels>{fx}</clipitem>')
            v_tracks.append(f'<track>{"".join(out)}<enabled>TRUE</enabled><locked>FALSE</locked></track>')
        total = max(round((o - t0) * fps) + int(i.duration * fps) for _, _, o, i, _ in placed)
        total = max(total, ms + mdur)
        sc = core._sc(rate_xml, first.width, first.height, "none")
        seqs.append(
            f'<sequence id="sequence-{mi + 1}"><name>{escape(name)} - {escape(Path(m["path"]).stem)}</name><duration>{total}</duration>{rate_xml}'
            f'<media><video><format>{sc}</format>{"".join(v_tracks)}</video>'
            f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth><samplerate>{arate}</samplerate>'
            f'</samplecharacteristics></format>{"".join(a_tracks)}</audio></media></sequence>')
    if not seqs:
        raise ValueError("Nothing to export: no clip was synced.")
    Path(out_path).write_text('<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4">' + "".join(seqs) + "</xmeml>",
                              encoding="utf-8")
    return len(seqs)


# ---------------- automatic ingest: "dump everything" ----------------

def media_info(path):
    """What is this file? video/audio presence, duration, format fingerprint and camera model tags."""
    r = subprocess.run([core.ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True, text=True,
                       errors="replace", **core._NOWIN)
    t = r.stderr
    vline = next((l for l in t.splitlines() if " Video:" in l and "attached pic" not in l), None)
    has_a = bool(re.search(r"Stream #\d+:\d+.*?: Audio:", t))
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", t)
    dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3)) if m else 0.0
    info = dict(video=vline is not None, audio=has_a, duration=dur, codec="", size="", fps=0.0, model="")
    if vline:
        body = vline.split("Video:", 1)[1]
        info["codec"] = body.strip().split()[0].strip(",")
        mm = re.search(r",\s*(\d{2,5})x(\d{2,5})", body)
        info["size"] = f"{mm.group(1)}x{mm.group(2)}" if mm else ""
        mm = re.search(r"([\d.]+)\s*fps", body)
        info["fps"] = round(float(mm.group(1)), 2) if mm else 0.0
    for key in ("com.apple.quicktime.model", "product_name", "model", "device_model", "make", "company_name"):
        mm = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.+)$", t, re.M)
        if mm and not mm.group(1).strip().lower().startswith("lavf"):
            info["model"] = mm.group(1).strip()
            break
    return info


def classify(files, infos):
    """files: [{"path","group"}]. Masters = audio-only files; if there are none, the longest file with sound.
    Returns (masters, video_clips, note)."""
    audio_only = [f["path"] for f in files if infos[f["path"]]["audio"] and not infos[f["path"]]["video"]]
    videos = [f["path"] for f in files if infos[f["path"]]["video"]]
    if audio_only:
        return sorted(audio_only), videos, ""
    with_sound = [p for p in videos if infos[p]["audio"]]
    if not with_sound:
        return [], videos, "No file with sound was found, so nothing can be synced."
    longest = max(with_sound, key=lambda p: infos[p]["duration"])
    return [longest], videos, f"No recorder file found: using the longest clip ({Path(longest).name}) as the audio master."


def auto_cameras(files, infos, results, old_cams=None):
    """Group synced video clips into cameras: same card folder + same format fingerprint + same file-name pattern.
    Clips of one group that overlap in time cannot be one camera, so they are split into separate cameras.
    Names/roles the user edited before are kept for the clips they cover."""
    groups = {}
    for f in files:
        p = f["path"]
        r = results.get(p)
        if not infos[p]["video"] or not r or r["conf"] == "fail":
            continue
        i = infos[p]
        key = (f["group"], i["model"], i["codec"], i["size"], i["fps"], re.sub(r"\d+", "#", Path(p).stem))
        groups.setdefault(key, []).append(p)
    cams = []
    for key, paths in sorted(groups.items(), key=lambda kv: kv[0]):
        lanes = []   # [(master, end), [paths]]
        for p in sorted(paths, key=lambda q: (results[q]["master"], results[q]["offset"])):
            r = results[p]
            for lane in lanes:
                if lane[0][0] != r["master"] or lane[0][1] <= r["offset"] + 0.5:
                    lane[0] = (r["master"], r["offset"] + r["dur"])
                    lane[1].append(p)
                    break
            else:
                lanes.append([(r["master"], r["offset"] + r["dur"]), [p]])
        for k, lane in enumerate(lanes):
            base = key[0] or "Camera"
            cams.append(dict(name=base + (f" {k + 1}" if len(lanes) > 1 else ""), role="Handheld", clips=lane[1], user=False))
    seen = {}
    for c in cams:   # unique names
        n = seen.get(c["name"], 0)
        seen[c["name"]] = n + 1
        if n:
            c["name"] = f"{c['name']} ({n + 1})"
    if old_cams:     # keep what the user edited
        owner = {p: oc for oc in old_cams if oc.get("user") for p in oc["clips"]}
        for c in cams:
            hits = [owner[p] for p in c["clips"] if p in owner]
            if hits:
                oc = max(set(map(id, hits)), key=lambda i: sum(id(h) == i for h in hits))
                oc = next(h for h in hits if id(h) == oc)
                c.update(name=oc["name"], role=oc["role"], user=True)
    return cams


def onsets(x, sr=SR):
    """Times (s) of musical/sound onsets in the master, used to put cuts on the beat."""
    hop = sr // 100
    n = len(x) // hop
    if n < 10:
        return []
    e = np.log1p(100 * np.sqrt((x[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1)))
    flux = np.maximum(0, np.diff(e, prepend=e[0]))
    k = np.ones(101) / 101
    thr = np.convolve(flux, k, "same") + 1.5 * np.sqrt(np.convolve((flux - flux.mean()) ** 2, k, "same")) + 0.02
    loc = np.maximum.reduce([np.r_[flux[i:], np.zeros(i)] for i in range(0, 6)] + [np.r_[np.zeros(i), flux[:-i]] for i in range(1, 6)])
    idx = np.where((flux > thr) & (flux >= loc))[0]
    return (idx * hop / sr).round(3).tolist()
