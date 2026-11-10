"""AI test (local, free): does an image model recognise what is in his shots as well as his colour labels?

Model: CLIP ViT-B/32 (OpenAI, MIT licence) as ONNX files from the Hugging Face repo Xenova/clip-vit-base-patch32
(quantized, ~150 MB in total), downloaded once into the app's data folder. Runs on the Mac with onnxruntime,
no internet needed after the download, the frames never leave the computer.

For every labelled selection one frame (middle of the selection) is shown to the model together with a few
descriptions per category; the category whose descriptions match best is the model's guess.
"""
import json
import subprocess
import urllib.request
from pathlib import Path

import numpy as np

import core

REPO = "Xenova/clip-vit-base-patch32"
FILES = {"vision": "onnx/vision_model_quantized.onnx", "text": "onnx/text_model_quantized.onnx", "tokenizer": "tokenizer.json"}
URL = "https://huggingface.co/{repo}/resolve/main/{file}"
SIZE = 224
MEAN = np.array([0.48145466, 0.4578275, 0.40821073], np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], np.float32)

PROMPTS = {
    "bride": ["a photo of a bride getting ready", "a bride in a white wedding dress", "a woman having her wedding makeup done",
              "a bride with a veil and wedding hairstyle"],
    "groom": ["a photo of a groom getting ready", "a man in a suit putting on a tie", "a groom buttoning his shirt",
              "a man in a wedding suit"],
    "couple": ["a bride and groom together", "a wedding couple portrait", "a newly married couple hugging",
               "a bride and groom holding hands outdoors"],
    "church": ["the inside of an orthodox church during a wedding ceremony", "a priest during a wedding in a church",
               "guests standing inside a church", "church icons and candles"],
    "venue": ["an empty decorated wedding reception hall", "wedding tables with flowers and candles",
              "a wedding venue decoration", "a festive banquet hall before the guests arrive"],
    "party": ["people dancing at a wedding party", "a crowded dance floor with party lights",
              "guests celebrating and jumping at night", "a dj party with colourful lights"],
    "drone": ["an aerial drone view from above", "a bird's eye view of a building and landscape",
              "aerial footage of a church from the sky", "a drone shot of a venue from above"],
}


def model_dir(base):
    d = Path(base) / "ai_model"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_model(base, progress=None, cancel=None):
    """Download the model files once (resumes nothing: a broken file is downloaded again)."""
    d = model_dir(base)
    for k, f in FILES.items():
        dest = d / Path(f).name
        if dest.exists() and dest.stat().st_size > 1000:
            continue
        req = urllib.request.Request(URL.format(repo=REPO, file=f), headers={"User-Agent": "MoneyMakingMachine"})
        tmp = dest.with_suffix(dest.suffix + ".part")
        try:
            import ssl
            import certifi
            ctx = ssl.create_default_context(cafile=certifi.where())
        except Exception:
            ctx = None
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r, open(tmp, "wb") as out:
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                if cancel and cancel():
                    raise InterruptedError("Cancelled")
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                out.write(chunk)
                got += len(chunk)
                if progress and total:
                    progress(f"Downloading the AI model ({k}): {got >> 20} of {total >> 20} MB", got / total)
        tmp.replace(dest)
    return d


class Clip:
    def __init__(self, folder):
        import onnxruntime as ort
        from tokenizers import Tokenizer
        folder = Path(folder)
        opts = ort.SessionOptions()
        self.vis = ort.InferenceSession(str(folder / "vision_model_quantized.onnx"), opts, providers=["CPUExecutionProvider"])
        self.txt = ort.InferenceSession(str(folder / "text_model_quantized.onnx"), opts, providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        eot = self.tok.token_to_id("<|endoftext|>")
        self.tok.enable_padding(length=77, pad_id=eot if eot is not None else 49407, pad_token="<|endoftext|>")
        self.tok.enable_truncation(77)

    @staticmethod
    def _pick(outputs, names):
        for i, n in enumerate(names):
            if "embeds" in n:
                return outputs[i]
        return outputs[0]

    def text(self, prompts):
        enc = self.tok.encode_batch(prompts)
        ids = np.array([e.ids for e in enc], np.int64)
        mask = np.array([e.attention_mask for e in enc], np.int64)
        feed = {}
        for i in self.txt.get_inputs():
            feed[i.name] = mask if "mask" in i.name else ids
        out = self.txt.run(None, feed)
        e = np.asarray(self._pick(out, [o.name for o in self.txt.get_outputs()]), np.float32)
        if e.ndim == 3:            # no projection output: take the end-of-text token
            e = e[np.arange(len(ids)), ids.argmax(1)]
        return e / np.linalg.norm(e, axis=1, keepdims=True)

    def image(self, rgb):
        """rgb: N x 224 x 224 x 3 uint8."""
        x = (rgb.astype(np.float32) / 255.0 - MEAN) / STD
        x = np.ascontiguousarray(x.transpose(0, 3, 1, 2))
        name = self.vis.get_inputs()[0].name
        out = self.vis.run(None, {name: x})
        e = np.asarray(self._pick(out, [o.name for o in self.vis.get_outputs()]), np.float32)
        if e.ndim == 3:
            e = e[:, 0]
        return e / np.linalg.norm(e, axis=1, keepdims=True)


def frame_rgb(path, t):
    """One frame, 224 x 224 RGB (centre crop), read with FFmpeg."""
    cmd = [core.ffmpeg_exe(), "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", path, "-frames:v", "1",
           "-vf", f"scale={SIZE}:{SIZE}:force_original_aspect_ratio=increase,crop={SIZE}:{SIZE}",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
    out = subprocess.run(cmd, capture_output=True, **core._NOWIN).stdout
    if len(out) < SIZE * SIZE * 3:
        return None
    return np.frombuffer(out[:SIZE * SIZE * 3], np.uint8).reshape(SIZE, SIZE, 3)


def run_test(pieces, base, per_cat=25, progress=None, cancel=None, seed=1):
    """Returns dict(rows=[(piece, frame rgb, his category, ai category, confidence)], acc={cat: (right, total)})."""
    import random
    rng = random.Random(seed)
    folder = ensure_model(base, progress, cancel)
    if progress:
        progress("Loading the AI model…", 0.0)
    clip = Clip(folder)
    cats = list(PROMPTS)
    allp = [p for c in cats for p in PROMPTS[c]]
    T = clip.text(allp)
    owner = np.array([cats.index(c) for c in cats for _ in PROMPTS[c]])
    sample = []
    for c in cats:
        ps = [p for p in pieces if p["cat"] == c]
        rng.shuffle(ps)
        sample += ps[:per_cat]
    rows = []
    for k, p in enumerate(sample):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        img = frame_rgb(p["path"], (p["a"] + p["b"]) / 2)
        if img is None:
            continue
        e = clip.image(img[None])[0]
        sim = T @ e
        score = np.array([sim[owner == i].mean() for i in range(len(cats))])
        prob = np.exp(100 * (score - score.max()))
        prob /= prob.sum()
        g = int(np.argmax(score))
        rows.append((p, img, p["cat"], cats[g], float(prob[g])))
        if progress:
            progress(f"The AI is looking at your shots: {k + 1} of {len(sample)}", (k + 1) / max(1, len(sample)))
    acc = {}
    for _, _, his, ai_, _ in rows:
        r, t = acc.get(his, (0, 0))
        acc[his] = (r + (his == ai_), t + 1)
    return dict(rows=rows, acc=acc)
