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


def _audio_streams(path):
    """Channel count of every audio stream in the file."""
    r = subprocess.run([core.ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True, text=True, errors="replace", **core._NOWIN)
    out = []
    for m in re.finditer(r"Stream #\d+:\d+.*?: Audio:.*?(\d+) Hz, ([^,\n]+)", r.stderr):
        lay = m.group(2).strip()
        mm = re.match(r"(\d+) channels?", lay)
        mm2 = re.match(r"(\d+)\.(\d+)", lay)
        out.append(1 if lay == "mono" else 2 if lay == "stereo" else int(mm.group(1)) if mm else
                   int(mm2.group(1)) + int(mm2.group(2)) if mm2 else 2)
    if not out and re.search(r"Stream #\d+:\d+.*?: Audio:", r.stderr):
        out = [2]
    return out


def audio_pcm(path, sr=SR):
    """Mono float32 audio at `sr`, taken from the LOUDEST single channel of the file.
    Channels are never mixed together: a mono sound recorded on 2 channels with one channel empty or inverted,
    poly-WAVs from field recorders and Sony MXF with one mono stream per channel all work."""
    exe = core.ffmpeg_exe()
    streams = _audio_streams(path)
    if not streams:
        raise ValueError("No audio stream")
    best, err = None, ""
    if 1 < len(streams) <= 8 and sum(streams) <= 8:
        # several streams (Sony MXF: one mono stream per channel): ONE pass over the file writes every stream to its own
        # small temporary file (a 4K MXF is several GB, reading it once per channel made Sync slow)
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            cmd = [exe, "-v", "error", "-nostdin", "-i", path]
            outs = []
            for i in range(len(streams)):
                o = str(Path(td) / f"a{i}.raw")
                cmd += ["-map", f"0:a:{i}", "-vn", "-ar", str(sr), "-f", "f32le", o]
                outs.append(o)
            r = subprocess.run(cmd, capture_output=True, **core._NOWIN)
            cands = []
            for o, ch in zip(outs, streams):
                try:
                    x = np.fromfile(o, np.float32)
                except Exception:
                    continue
                if len(x) < sr * ch:
                    continue
                x = x[:len(x) // ch * ch].reshape(-1, ch)
                rms = np.sqrt((x.astype(np.float64) ** 2).mean(0))
                k = int(np.argmax(rms))
                cands.append((float(rms[k]), np.ascontiguousarray(x[:, k])))
            if cands:
                best = max(cands, key=lambda c: c[0])
                if best[0] >= 1e-6:
                    return best[1]
            err = (r.stderr.decode(errors="replace").strip().splitlines() or [""])[-1]
            best = None
        # anything unusual -> fall back to reading stream by stream below
    for i, ch in enumerate(streams[:8]):
        base = [exe, "-v", "error", "-nostdin", "-i", path, "-map", f"0:a:{i}", "-vn", "-ar", str(sr)]
        if ch <= 2:   # small enough: read both channels at once and keep the louder one
            r = subprocess.run(base + ["-f", "f32le", "-"], capture_output=True, **core._NOWIN)
            x = np.frombuffer(r.stdout, np.float32)
            if len(x) < sr * ch:
                err = (r.stderr.decode(errors="replace").strip().splitlines() or [""])[-1]
                continue
            x = x[:len(x) // ch * ch].reshape(-1, ch)
            rms = np.sqrt((x.astype(np.float64) ** 2).mean(0))
            k = int(np.argmax(rms))
            cand = (float(rms[k]), np.ascontiguousarray(x[:, k]))
        else:         # many channels (poly WAV): measure every channel while streaming, then extract only the best
            p = subprocess.Popen(base + ["-f", "f32le", "-"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, **core._NOWIN)
            acc, n = np.zeros(ch), 0
            while True:
                buf = p.stdout.read(sr * ch * 4 * 10)
                if not buf:
                    break
                y = np.frombuffer(buf[:len(buf) // (4 * ch) * 4 * ch], np.float32).reshape(-1, ch).astype(np.float64)
                acc += (y ** 2).sum(0)
                n += len(y)
            p.wait()
            if n < sr:
                err = (p.stderr.read().decode(errors="replace").strip().splitlines() or [""])[-1]
                continue
            k = int(np.argmax(acc))
            r = subprocess.run(base + ["-af", f"pan=mono|c0=c{k}", "-f", "f32le", "-"], capture_output=True, **core._NOWIN)
            cand = (float(np.sqrt(acc[k] / n)), np.frombuffer(r.stdout, np.float32))
        if best is None or cand[0] > best[0]:
            best = cand
    if best is None:
        raise ValueError("Could not read the audio" + (f" ({err})" if err else ""))
    if best[0] < 1e-6:
        raise ValueError("The audio is silent on every channel")
    return best[1]


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

    def correlate(self, t, lo=None, hi=None):
        """Returns (lag_samples, z, ratio): best position of window `t` in the master.
        lo/hi (samples) restrict the search to a window around a predicted position (much faster)."""
        wn = len(t)
        lo = -10**12 if lo is None else lo
        hi = 10**12 if hi is None else hi
        T = np.fft.rfft(t, F)
        T = (T / (np.abs(T) + 1e-9)).astype(np.complex64)
        peaks, s1, s2, cnt = [], 0.0, 0.0, 0
        guard = int(0.5 * SR)
        for s, X in self.blocks:
            kmax = min(self.step, self.n - s - wn)
            if kmax < 0 or s + kmax < lo or s > hi:
                continue
            v = np.fft.irfft(X * np.conj(T), F)[:kmax + 1]
            k0 = max(0, lo - s)
            k1 = min(kmax, hi - s)
            if k1 < k0:
                continue
            v = v[k0:k1 + 1]
            s = s + k0
            v64 = v.astype(np.float64)
            s1 += v64.sum()
            s2 += (v64 * v64).sum()
            cnt += len(v)
            k = int(np.argmax(v))
            peaks.append((float(v[k]), s + k))
            g0, g1 = max(0, k - guard), min(len(v), k + guard)
            w = v.copy()
            w[g0:g1] = -1
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
    single = len(cands) == 1          # very short clip: only one window exists
    conf = ("high" if (n >= 3 or (n == 2 and zm >= 12)) else
            "medium" if (n == 2 or (single and zm >= 15)) else "low")   # 1 of several windows agreeing = unsure
    if any(c[2] >= 10 and c not in best for c in good):   # strong windows disagree -> downgrade one level
        conf = {"high": "medium", "medium": "low", "low": "low"}[conf]
    return dict(conf=conf, z=zm, n=n, k=len(cands), offset=float(o0), drift_ppm=float(d * 1e6))


def usable_sound(x, sr=SR):
    """False for clips without real sound (gimbal cameras with the mic off: digital silence or only hiss).
    Such clips would 'stick' to any loud click in the recorder and pile up at one wrong position."""
    if len(x) < sr:
        return False
    hop = sr // 10
    n = len(x) // hop
    e = np.sqrt((x[:n * hop].reshape(n, hop).astype(np.float64) ** 2).mean(1)) + 1e-9
    db = 20 * np.log10(e)
    level = 20 * np.log10(float(np.sqrt((x.astype(np.float64) ** 2).mean())) + 1e-9)
    dynamics = float(np.percentile(db, 95) - np.percentile(db, 10))
    return not (level < -50 and dynamics < 12) and level > -70


def sync_clip(indexes, x, preds=None, win=90.0):
    """preds: {master_index: predicted offset (s)} -> only those masters, only +-win seconds around the prediction."""
    weak = not usable_sound(x)        # very quiet / hiss only: accepted only when every check agrees
    dur = len(x) / SR
    x = _prep(x)
    starts, wn = _pick_windows(x)
    best = None
    for mi, idx in enumerate(indexes):
        if preds is not None and mi not in preds:
            continue
        cands = []
        for st in starts:
            if preds is not None:
                c = (preds[mi] * SR) + st
                lag, z, ratio = idx.correlate(x[st:st + wn], int(c - win * SR), int(c + win * SR))
            else:
                lag, z, ratio = idx.correlate(x[st:st + wn])
            cands.append((st / SR, lag / SR - st / SR, z, ratio))
        r = _decide(cands)
        r["master"] = mi
        rank = ({"fail": 0, "low": 1, "medium": 2, "high": 3}[r["conf"]], r["n"], r["z"])
        if best is None or rank > best[0]:
            best = (rank, r)
    if best is None:
        return dict(conf="fail", z=0.0, n=0, k=0, offset=0.0, drift_ppm=0.0, master=0, dur=dur)
    r = best[1]
    r["dur"] = dur
    if weak and r["conf"] != "high":
        return dict(conf="fail", z=r["z"], n=r["n"], k=r["k"], offset=0.0, drift_ppm=0.0, master=0, dur=dur,
                    error="No usable sound in this clip (camera mic off?)")
    return r


def run_sync(masters, clips, progress=None, cancel=None, clocks=None, groups=None, jobs=2):
    """masters, clips: lists of paths. clocks: {path: time-of-day seconds or None} (timecode / BWF / file dates),
    groups: {clip: camera folder}. Returns (masters_info, {clip_path: result}).

    The first clip of every camera folder is searched in the whole master. Its result teaches the difference between
    that camera's clock and the recorder's clock; the next clips of the same camera are then searched only +-90 s around
    the predicted position (falls back to a full search when that fails)."""
    from concurrent.futures import ThreadPoolExecutor
    clocks, groups = clocks or {}, groups or {}

    def chk():
        if cancel and cancel():
            raise InterruptedError("Cancelled")

    indexes, info = [], []
    for i, m in enumerate(masters):
        chk()
        if progress:
            progress(f"Step 1 · reading recorder file {i + 1} of {len(masters)}", 0.02 * i / max(1, len(masters)))
        x = audio_pcm(m)
        info.append(dict(path=m, duration=len(x) / SR, onsets=onsets(x), clock=clocks.get(m)))
        indexes.append(MasterIndex(x))
    order = sorted(clips, key=lambda c: (groups.get(c, ""), clocks.get(c) if clocks.get(c) is not None else 1e12, c))
    delta, results, full = {}, {}, 0

    def load(c):
        try:
            return audio_pcm(c), None
        except Exception as e:
            return None, str(e)

    with ThreadPoolExecutor(max(1, jobs)) as ex:
        for i, (c, (x, err)) in enumerate(zip(order, ex.map(load, order))):
            chk()
            if progress:
                progress(f"Step 1 · syncing audio: clip {i + 1} of {len(order)} ({Path(c).name})", 0.02 + 0.98 * i / max(1, len(order)))
            if x is None:
                results[c] = dict(conf="fail", z=0.0, n=0, k=0, offset=0.0, drift_ppm=0.0, master=0, dur=0.0, manual=False, error=err)
                continue
            g, ck, r = groups.get(c, ""), clocks.get(c), None
            if g in delta and ck is not None:
                preds = {}
                for mi, m in enumerate(info):
                    if m["clock"] is None:
                        continue
                    d = _tod_diff(ck, m["clock"]) - delta[g]
                    if -120 <= d <= m["duration"] + 120:
                        preds[mi] = d
                if preds:
                    r = sync_clip(indexes, x, preds)
                    if r["conf"] != "high":       # a repeated chorus inside the window must not win: else full search
                        r = None
            if r is None:
                full += 1
                r = sync_clip(indexes, x)
            r["manual"] = False
            try:   # container duration only if it agrees with the real sound length (some MP4 data tracks inflate it)
                pd = core.probe(c).duration
                if pd and abs(pd - r["dur"]) < max(2.0, 0.02 * r["dur"]):
                    r["dur"] = pd
            except Exception:
                pass
            if r["conf"] == "high" and ck is not None and info[r["master"]]["clock"] is not None:
                delta[g] = _tod_diff(ck, info[r["master"]]["clock"]) - r["offset"]   # this camera's clock error
            results[c] = r
    if progress:
        progress(f"Step 1 · sync finished ({full} full searches, {len(order) - full} fast)", 1.0)
    return info, results


def _tod_diff(a, b):
    """a - b for time-of-day seconds, unwrapped across midnight (parties go past 00:00)."""
    d = a - b
    while d > 43200:
        d -= 86400
    while d < -43200:
        d += 86400
    return d


def master_starts(info):
    """Start of every recorder file on ONE common timeline (s). Uses the recorders' clocks when they make sense,
    otherwise lays the files out one after another."""
    if not info:
        return []
    if all(m.get("start") is not None for m in info):     # imported XML: the positions are already known
        return [float(m["start"]) for m in info]
    starts, ok = [0.0], all(m.get("clock") is not None for m in info)
    for k in range(1, len(info)):
        prev = info[k - 1]
        d = _tod_diff(info[k]["clock"], info[0]["clock"]) if ok else None
        lo = starts[-1] + prev["duration"]
        starts.append(d if d is not None and d >= lo - 1 else lo + 5.0)
    return starts


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
    info["clock"] = _clock(t, path, dur)
    for key in ("com.apple.quicktime.model", "product_name", "model", "device_model", "make", "company_name"):
        mm = re.search(rf"^\s*{re.escape(key)}\s*:\s*(.+)$", t, re.M)
        if mm and not mm.group(1).strip().lower().startswith("lavf"):
            info["model"] = mm.group(1).strip()
            break
    return info


def _clock(t, path, dur):
    """Best guess of the recording start as time of day (s): camera timecode, BWF time reference, creation time,
    file date. Only used as a hint to narrow the audio search, never as the final sync."""
    import datetime as _dt
    import os as _os
    m = re.search(r"^\s*timecode\s*:\s*(\d+):(\d+):(\d+)[:;.](\d+)", t, re.M)
    if m:
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
    m = re.search(r"^\s*time_reference\s*:\s*(\d+)", t, re.M)
    r = re.search(r"Audio:.*?(\d+) Hz", t)
    if m and r and int(m.group(1)) > 0:
        return (int(m.group(1)) / int(r.group(1))) % 86400
    m = re.search(r"^\s*creation_time\s*:\s*(\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d)", t, re.M)
    if m:
        utc = _dt.datetime.fromisoformat(m.group(1)).replace(tzinfo=_dt.timezone.utc)
        lt = utc.astimezone()
        return lt.hour * 3600 + lt.minute * 60 + lt.second
    try:
        lt = _dt.datetime.fromtimestamp(_os.path.getmtime(path) - dur)
        return lt.hour * 3600 + lt.minute * 60 + lt.second
    except Exception:
        return None


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
    """Group synced video clips into cameras: same card folder + same model + same file-name pattern.
    Overlapping clips of one group: if both are sure they are two cameras (separate tracks), otherwise the less sure
    one is wrong and goes to the '· check sync' track (its result becomes 'low').
    Names/roles the user edited before are kept for the clips they cover."""
    groups, unsure = {}, {}
    for f in files:
        p = f["path"]
        r = results.get(p)
        if not infos[p]["video"] or not r or r["conf"] == "fail":
            continue
        if r["conf"] == "low" and not r.get("manual"):   # unsure position: never let it explode into extra tracks
            unsure.setdefault(f["group"] or "Camera", []).append(p)
            continue
        i = infos[p]
        # frame rate / resolution are NOT part of the fingerprint: one camera may switch to 50p for slow motion
        key = (f["group"], i["model"], re.sub(r"\d+", "#", Path(p).stem))
        groups.setdefault(key, []).append(p)
    cams = []
    rank = {"high": 2, "medium": 1, "low": 0}
    for key, paths in sorted(groups.items(), key=lambda kv: kv[0]):
        # "A camera cannot film two things at once": the surest clips are placed first; a clip that overlaps an already
        # placed clip of the same camera is wrong unless it is itself sure (then it really is a second camera)
        lanes = []
        for p in sorted(paths, key=lambda q: (-(3 if results[q].get("manual") else rank[results[q]["conf"]]), -results[q].get("z", 0))):
            r = results[p]
            m, a, b = r["master"], r["offset"], r["offset"] + r["dur"]
            lane = next((L for L in lanes if all(mm != m or e <= a + 0.5 or s0 >= b - 0.5 for mm, s0, e, _ in L)), None)
            if lane is not None:
                lane.append((m, a, b, p))
            elif r["conf"] == "high" or r.get("manual") or not lanes:
                lanes.append([(m, a, b, p)])
            else:
                r["conf"] = "low"
                r["error"] = "overlaps another clip of the same camera (position unsure)"
                unsure.setdefault(key[0] or "Camera", []).append(p)
        for k, lane in enumerate(lanes):
            base = key[0] or "Camera"
            cams.append(dict(name=base + (f" {k + 1}" if len(lanes) > 1 else ""), role="Handheld",
                             clips=[x[3] for x in sorted(lane)], user=False))
    for g, paths in sorted(unsure.items()):
        cams.append(dict(name=f"{g} · check sync", role="Handheld", clips=sorted(paths, key=lambda q: results[q]["offset"]),
                         user=False, check=True))
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
