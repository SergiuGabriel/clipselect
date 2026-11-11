"""AI test v2 (local, free): does SigLIP 2 recognise his shots like his colour labels?

Model: Google SigLIP 2 So400m (Apache 2.0), the ONNX export published by Hugging Face (onnx-community), downloaded
once into <data>/ai_model/siglip2 (a few GB). Runs on the Mac with onnxruntime (Core ML / GPU when it works,
otherwise the processor). Nothing is uploaded.

Better than the first test (CLIP B/32): a much stronger model, 3 frames per selection (the sharpest of each third, the
frames on the floor / in motion do not decide alone), the flat log look corrected (contrast, saturation) before the
model, descriptions written for his weddings, and an "unclear / detail" class so a carpet is not forced into a label.
Only a TEST: it does not change the teaser.
"""
import hashlib
import json
import random
import ssl
import subprocess
import urllib.request
from pathlib import Path

import numpy as np

import core

REPOS = ["onnx-community/siglip2-so400m-patch14-384-ONNX", "onnx-community/siglip2-so400m-patch16-384-ONNX",
         "onnx-community/siglip2-so400m-patch16-512-ONNX", "onnx-community/siglip2-so400m-patch16-256-ONNX"]
API = "https://huggingface.co/api/models/{repo}"
URL = "https://huggingface.co/{repo}/resolve/main/{file}"
# most precise first (full precision, then half, then compressed)
PREF = {"vision": ["onnx/vision_model.onnx", "onnx/vision_model_fp16.onnx", "onnx/vision_model_quantized.onnx",
                   "onnx/vision_model_int8.onnx"],
        "text": ["onnx/text_model.onnx", "onnx/text_model_fp16.onnx", "onnx/text_model_quantized.onnx",
                 "onnx/text_model_int8.onnx"]}
EXTRA = ["tokenizer.json", "preprocessor_config.json"]

UNCLEAR = "unclear"
PROMPTS = {
    "bride": ["a bride getting ready in a white wedding dress", "a woman having her wedding makeup and hair done",
              "a bride putting on her earrings or her veil", "a white wedding dress hanging in a room",
              "bridal shoes, rings and jewellery details"],
    "groom": ["a groom getting ready, buttoning his white shirt", "a man putting on a suit jacket and a tie",
              "a groom fastening his cufflinks or his watch", "a man in an elegant suit in a hotel room"],
    "couple": ["a bride and groom together", "a wedding couple embracing outdoors",
               "a newly married couple walking hand in hand", "a bride and groom posing for a portrait"],
    "church": ["the inside of an orthodox church with golden icons and candles",
               "a priest in vestments during a wedding ceremony", "wedding guests standing inside a church",
               "a church altar with icons and chandeliers"],
    "venue": ["an empty wedding reception hall with decorated tables", "wedding tables with flowers, candles and plates",
              "a crystal chandelier in a banquet hall", "the outside of a wedding venue building in daylight",
              "a garden or terrace prepared for a wedding party"],
    "party": ["people dancing at a wedding party at night", "a crowded dance floor with colourful party lights",
              "wedding guests celebrating, jumping and raising their hands", "a band or a DJ playing at a wedding party"],
    "drone": ["an aerial drone view from high above", "a bird's eye view of a building, trees and fields",
              "aerial footage of a venue seen from the sky"],
    UNCLEAR: ["a blurry, out of focus image", "a close-up of a carpet or a floor", "a ceiling or a plain wall",
              "a dark, underexposed image", "an image smeared by camera motion"],
}
TEMPLATE = "This is a photo of {}."


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def _get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": "MoneyMakingMachine"})
    return urllib.request.urlopen(req, timeout=timeout, context=_ctx())


def model_dir(base):
    d = Path(base) / "ai_model" / "siglip2"
    d.mkdir(parents=True, exist_ok=True)
    return d


def remove_old_clip(base):
    """The first test's CLIP files are not needed any more."""
    old = Path(base) / "ai_model"
    for f in ("vision_model_quantized.onnx", "text_model_quantized.onnx", "tokenizer.json"):
        try:
            (old / f).unlink()
        except OSError:
            pass


def _plan(d):
    """Which repository and files to use: asked from Hugging Face once, then remembered (manifest.json)."""
    man = d / "manifest.json"
    if man.exists():
        try:
            return json.loads(man.read_text("utf-8"))
        except Exception:
            pass
    last = None
    for repo in REPOS:
        try:
            with _get(API.format(repo=repo) + "?blobs=true") as r:
                info = json.loads(r.read().decode("utf-8"))
        except Exception as e:
            last = e
            continue
        sib = {s["rfilename"]: s.get("size") or (s.get("lfs") or {}).get("size") or 0 for s in info.get("siblings", [])}
        pick = {}
        for k, prefs in PREF.items():
            f = next((x for x in prefs if x in sib), None)
            if not f:
                break
            pick[k] = f
        if len(pick) < 2 or any(x not in sib for x in EXTRA):
            continue
        files = []
        for k in ("vision", "text"):
            files.append(pick[k])
            files += [x for x in sib if x.startswith(pick[k]) and x != pick[k]]       # external weights (*.onnx_data)
        files += EXTRA
        plan = dict(repo=repo, vision=pick["vision"], text=pick["text"], files=files,
                    total=int(sum(sib.get(f, 0) for f in files)))
        man.write_text(json.dumps(plan), "utf-8")
        return plan
    raise ValueError(f"Could not find SigLIP 2 on Hugging Face ({last}). The first run needs internet")


def ensure_model(base, progress=None, cancel=None):
    """Download every file once; a broken download continues where it stopped."""
    d = model_dir(base)
    plan = _plan(d)
    done_b = 0
    total = max(1, plan.get("total", 0))
    for f in plan["files"]:
        dest = d / f
        dest.parent.mkdir(parents=True, exist_ok=True)
        ok = dest.with_suffix(dest.suffix + ".ok")
        if dest.exists() and ok.exists():
            done_b += dest.stat().st_size
            continue
        tmp = dest.with_suffix(dest.suffix + ".part")
        have = tmp.stat().st_size if tmp.exists() else 0
        req = urllib.request.Request(URL.format(repo=plan["repo"], file=f),
                                     headers={"User-Agent": "MoneyMakingMachine", **({"Range": f"bytes={have}-"} if have else {})})
        with urllib.request.urlopen(req, timeout=60, context=_ctx()) as r, open(tmp, "ab" if have and r.status == 206 else "wb") as out:
            if r.status != 206:
                have = 0
            got = have
            while True:
                if cancel and cancel():
                    raise InterruptedError("Cancelled")
                chunk = r.read(4 << 20)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if progress:
                    if total > 1:
                        progress(f"Downloading SigLIP 2 (once): {(done_b + got) >> 20} of {total >> 20} MB",
                                 min(0.99, (done_b + got) / total))
                    else:
                        progress(f"Downloading SigLIP 2 (once): {(done_b + got) >> 20} MB", 0.5)
        tmp.replace(dest)
        ok.write_text("ok")
        done_b += dest.stat().st_size
    return d, plan


class Siglip:
    def __init__(self, folder, plan):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        folder = Path(folder)
        prov = ort.get_available_providers()
        tries = ([["CoreMLExecutionProvider", "CPUExecutionProvider"]] if "CoreMLExecutionProvider" in prov else []) + \
                [["CPUExecutionProvider"]]
        self.vis = self.txt = None
        for p in tries:
            try:
                self.vis = ort.InferenceSession(str(folder / plan["vision"]), providers=p)
                break
            except Exception:
                continue
        self.txt = ort.InferenceSession(str(folder / plan["text"]), providers=["CPUExecutionProvider"])
        pc = json.loads((folder / "preprocessor_config.json").read_text("utf-8"))
        sz = pc.get("size", {})
        self.h = int(sz.get("height") or sz.get("shortest_edge") or 384)
        self.w = int(sz.get("width") or sz.get("shortest_edge") or 384)
        self.mean = np.array(pc.get("image_mean", [0.5, 0.5, 0.5]), np.float32)
        self.std = np.array(pc.get("image_std", [0.5, 0.5, 0.5]), np.float32)
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        pad = self.tok.token_to_id("<pad>")
        self.tok.enable_padding(length=64, pad_id=0 if pad is None else pad, pad_token="<pad>")
        self.tok.enable_truncation(64)

    @staticmethod
    def _pick(outputs, names):
        for key in ("embeds", "pooler"):
            for i, n in enumerate(names):
                if key in n:
                    return outputs[i]
        return outputs[0]

    def text(self, prompts):
        enc = self.tok.encode_batch(prompts)
        ids = np.array([e.ids for e in enc], np.int64)
        feed = {}
        for i in self.txt.get_inputs():
            feed[i.name] = np.array([e.attention_mask for e in enc], np.int64) if "mask" in i.name else ids
        out = self.txt.run(None, feed)
        e = np.asarray(self._pick(out, [o.name for o in self.txt.get_outputs()]), np.float32)
        if e.ndim == 3:
            e = e[:, -1]
        return e / np.linalg.norm(e, axis=1, keepdims=True)

    def image(self, rgb):
        x = (rgb.astype(np.float32) / 255.0 - self.mean) / self.std
        x = np.ascontiguousarray(x.transpose(0, 3, 1, 2))
        inp = self.vis.get_inputs()[0]
        if "16" in (inp.type or ""):
            x = x.astype(np.float16)
        out = self.vis.run(None, {inp.name: x})
        e = np.asarray(self._pick(out, [o.name for o in self.vis.get_outputs()]), np.float32)
        if e.ndim == 3:
            e = e[:, 0]
        return e / np.linalg.norm(e, axis=1, keepdims=True)


def frame_rgb(path, t, w, h):
    """One frame squashed to the model's size (as its own preprocessing does), RGB."""
    cmd = [core.ffmpeg_exe(), "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", path, "-frames:v", "1",
           "-vf", f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    out = subprocess.run(cmd, capture_output=True, **core._NOWIN).stdout
    if len(out) < w * h * 3:
        return None
    return np.frombuffer(out[:w * h * 3], np.uint8).reshape(h, w, 3)


def ungrade(img):
    """Flat log footage -> a normal looking picture: stretch the levels and bring the colour back."""
    x = img.astype(np.float32)
    lo = np.percentile(x, 1, axis=(0, 1))
    hi = np.percentile(x, 99, axis=(0, 1))
    x = (x - lo) / np.maximum(1.0, hi - lo) * 255
    g = x.mean(axis=2, keepdims=True)
    x = g + (x - g) * 1.35
    return np.clip(x, 0, 255).astype(np.uint8)


def pick_times(p, n=3):
    """The sharpest moment of each third of the selection (from the quality analysis), else 20 / 50 / 80 %."""
    a, b = p["a"], p["b"]
    qa = p.get("qa")
    if qa:
        t, q = np.asarray(qa[0], float) + a, np.asarray(qa[1], float)
        out = []
        for k in range(n):
            lo, hi = a + (b - a) * k / n, a + (b - a) * (k + 1) / n
            m = (t >= lo) & (t < hi)
            out.append(float(t[m][np.argmax(q[m])]) if m.any() else (lo + hi) / 2)
        return out
    return [a + (b - a) * f for f in (0.2, 0.5, 0.8)]


def run_test(pieces, base, per_cat=25, progress=None, cancel=None, seed=1):
    """rows = [(piece, shown frame, his category, AI category or 'unclear', confidence)], acc = {cat: (right, judged)},
    unclear = {cat: n}."""
    rng = random.Random(seed)
    remove_old_clip(base)
    folder, plan = ensure_model(base, progress, cancel)
    if progress:
        progress("Loading SigLIP 2…", 0.0)
    m = Siglip(folder, plan)
    cats = list(PROMPTS)
    allp = [TEMPLATE.format(x) for c in cats for x in PROMPTS[c]]
    key = hashlib.sha1(("|".join(allp) + plan["text"]).encode()).hexdigest()[:12]
    cache = folder / f"text_{key}.npy"
    if cache.exists():
        T = np.load(cache)
    else:
        T = m.text(allp)
        np.save(cache, T)
    owner = np.array([cats.index(c) for c in cats for _ in PROMPTS[c]])
    sample = []
    for c in cats:
        if c == UNCLEAR:
            continue
        ps = [p for p in pieces if p["cat"] == c]
        rng.shuffle(ps)
        sample += ps[:per_cat]
    rows, missing, unread = [], [], []
    for k, p in enumerate(sample):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        if not Path(p["path"]).exists():
            missing.append(p["path"])
            continue
        frames = [f for f in (frame_rgb(p["path"], t, m.w, m.h) for t in pick_times(p)) if f is not None]
        if not frames:
            unread.append(p["path"])
            continue
        E = m.image(np.stack([ungrade(f) for f in frames]))
        sims = E @ T.T                                           # frames x prompts
        score = np.stack([sims[:, owner == i].max(axis=1) for i in range(len(cats))], axis=1)   # frames x classes
        ui = cats.index(UNCLEAR)
        clear = [i for i in range(len(frames)) if int(np.argmax(score[i])) != ui]
        if clear:
            s = score[clear].mean(axis=0)
            s[ui] = -1e9
            best = clear[int(np.argmax(score[clear].max(axis=1)))]
        else:
            s, best = score.mean(axis=0), len(frames) // 2
        g = int(np.argmax(s))
        z = np.exp(50 * (s - s.max()))
        rows.append((p, frames[best], p["cat"], cats[g], float(z[g] / z.sum())))
        if progress:
            progress(f"SigLIP 2 is looking at your shots: {k + 1} of {len(sample)}", (k + 1) / max(1, len(sample)))
    if not rows:
        if missing:
            raise ValueError(f"{len(missing)} clips were not found on this computer (e.g. {missing[0]}): connect the "
                             f"disk with the footage and run the test again")
        raise ValueError(f"No frame could be read from the clips (e.g. {unread[0] if unread else '?'}). Send the error "
                         f"report to Claude")
    acc, unclear = {}, {}
    for _, _, his, ai_, _ in rows:
        if ai_ == UNCLEAR:
            unclear[his] = unclear.get(his, 0) + 1
            continue
        r, t = acc.get(his, (0, 0))
        acc[his] = (r + (his == ai_), t + 1)
    return dict(rows=rows, acc=acc, unclear=unclear, missing=len(missing), unread=len(unread), model=plan["repo"])
