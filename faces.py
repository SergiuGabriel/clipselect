"""Face recognition (local, free): find a person (the vornic; later the bride and groom) in the selections from one good
photo of him / her.

Models: OpenCV Zoo YuNet (face detection, MIT) + SFace (face recognition, Apache 2.0), a few tens of MB, downloaded once
into <data>/ai_model/faces. They run with OpenCV on the processor, nothing is uploaded. SFace's own threshold: cosine
similarity >= 0.363 = the same person.
"""
import ssl
import subprocess
import urllib.request
from pathlib import Path

import numpy as np

import core

BASE = "https://github.com/opencv/opencv_zoo/raw/main/models/"
FILES = {"det": "face_detection_yunet/face_detection_yunet_2023mar.onnx",
         "rec": "face_recognition_sface/face_recognition_sface_2021dec.onnx"}
SAME = 0.363          # SFace: cosine similarity above this = the same person
SCAN_W = 960          # frames are read this wide (faces in a wide shot stay big enough)


def _ctx():
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def ensure_models(base, progress=None):
    d = Path(base) / "ai_model" / "faces"
    d.mkdir(parents=True, exist_ok=True)
    for k, f in FILES.items():
        dest = d / Path(f).name
        if dest.exists() and dest.stat().st_size > 10000:
            continue
        if progress:
            progress("Downloading the face recognition (once)…", 0.0)
        req = urllib.request.Request(BASE + f, headers={"User-Agent": "MoneyMakingMachine"})
        tmp = dest.with_suffix(".part")
        with urllib.request.urlopen(req, timeout=60, context=_ctx()) as r, open(tmp, "wb") as out:
            out.write(r.read())
        if tmp.stat().st_size < 10000:
            raise ValueError("The face recognition model could not be downloaded (needs internet the first time)")
        tmp.replace(dest)
    return d


class Faces:
    def __init__(self, folder):
        import cv2
        self.cv2 = cv2
        folder = Path(folder)
        self.det = cv2.FaceDetectorYN.create(str(folder / Path(FILES["det"]).name), "", (320, 320), 0.8, 0.3, 5000)
        self.rec = cv2.FaceRecognizerSF.create(str(folder / Path(FILES["rec"]).name), "")

    def faces(self, bgr):
        """[(feature, face width in pixels)] of every face in the picture."""
        h, w = bgr.shape[:2]
        self.det.setInputSize((w, h))
        _, found = self.det.detect(bgr)
        out = []
        for f in (found if found is not None else []):
            crop = self.rec.alignCrop(bgr, f)
            feat = self.rec.feature(crop).flatten().astype(np.float32)
            out.append((feat / (np.linalg.norm(feat) + 1e-9), float(f[2])))
        return out

    def person(self, photo_path):
        """The feature of the biggest face in his photo."""
        img = self.cv2.imread(str(photo_path))
        if img is None:
            raise ValueError("The photo could not be read (use a JPG or PNG)")
        if max(img.shape[:2]) > 1600:
            s = 1600 / max(img.shape[:2])
            img = self.cv2.resize(img, (int(img.shape[1] * s), int(img.shape[0] * s)))
        fs = self.faces(img)
        if not fs:
            raise ValueError("No face found in the photo: use a clear photo where the face is well visible")
        return max(fs, key=lambda x: x[1])[0]


def frame_bgr(path, t, w=SCAN_W):
    cmd = [core.ffmpeg_exe(), "-v", "error", "-nostdin", "-ss", f"{max(0.0, t):.3f}", "-i", str(path), "-frames:v", "1",
           "-vf", f"scale={w}:-2", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    p = subprocess.run(cmd, capture_output=True, **core._NOWIN)
    n = len(p.stdout)
    if n < w * 3 * 10:
        return None
    h = n // (w * 3)
    return np.frombuffer(p.stdout[:w * h * 3], np.uint8).reshape(h, w, 3)


def find_people(pieces, refs, model, frames=3, progress=None, cancel=None, label="Looking for the faces"):
    """Every piece read once, every person looked for: {id(piece): {name: (best similarity, face width)}}."""
    out = {}
    for k, p in enumerate(pieces):
        if cancel and cancel():
            raise InterruptedError("Cancelled")
        best = {n: (-1.0, 0.0) for n in refs}
        if Path(p["path"]).exists():
            for f in (0.2, 0.5, 0.8)[:frames]:
                img = frame_bgr(p["path"], p["a"] + (p["b"] - p["a"]) * f)
                if img is None:
                    continue
                for feat, wpx in model.faces(img):
                    for n, ref in refs.items():
                        s_ = float(feat @ ref)
                        if s_ > best[n][0]:
                            best[n] = (s_, wpx)
        out[id(p)] = best
        if progress:
            progress(f"{label}: {k + 1} of {len(pieces)}", (k + 1) / max(1, len(pieces)))
    return out


def find_person(pieces, ref, model, frames=3, progress=None, cancel=None, label="Looking for the vornic"):
    """One person: {id(piece): (best similarity, face width)}."""
    r = find_people(pieces, {"x": ref}, model, frames, progress, cancel, label)
    return {k: v["x"] for k, v in r.items()}
