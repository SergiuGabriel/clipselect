"""What a clip shows, seen by the AI (SigLIP 2, the model of the AI test): getting ready, church, couple, venue, party,
drone, a speech. Used by the automatic mode of Long Film v2 (daymap) next to the clock, the sound and the faces, so the
church / drone / vornic do not depend on how long the videographer's clips are (every videographer films differently).

Three frames per clip (20 / 50 / 80 %), the log look undone (ai.ungrade), one probability per scene = the mean of the
frames' probabilities. Cached per clip (path + range + size + date) in the project's analysis cache."""
from pathlib import Path

import numpy as np

import ai

UNCLEAR = "unclear"
SCENES = {
    "ready": ["a bride getting ready in a white wedding dress", "a woman having her makeup and hair done",
              "a groom buttoning his white shirt", "a man putting on a suit jacket and a tie",
              "wedding rings, shoes and jewellery details", "people in a living room at home"],
    "church": ["the inside of an orthodox church with golden icons and candles",
               "a priest in vestments during a wedding ceremony", "wedding guests standing inside a church",
               "a church altar with icons and chandeliers"],
    "couple": ["a bride and groom posing together outdoors", "a wedding couple embracing in nature",
               "a bride and groom walking hand in hand in a park"],
    "venue": ["an empty wedding reception hall with decorated tables", "wedding tables with flowers, candles and plates",
              "a crystal chandelier in a banquet hall", "the outside of a wedding venue building"],
    "party": ["people dancing at a wedding party at night", "a crowded dance floor with colourful lights",
              "wedding guests sitting at tables in a restaurant", "a band or a DJ playing at a wedding party"],
    "drone": ["an aerial drone view from high above", "a bird's eye view of buildings, trees and fields"],
    "speech": ["a man giving a speech to a group of people in a house", "a man speaking to guests in a courtyard",
               "an older man talking while people listen"],
    UNCLEAR: ["a blurry, out of focus image", "a dark, underexposed image", "a ceiling or a plain wall"],
}
CATS = list(SCENES)
# WHO is in the picture (a second, separate judgement on the same frames): the bride (white dress, veil), the groom
# (suit), both, or nobody of the couple (details, rooms, decorations, buildings, guests). Used by daymap to tell the
# groom from the bride whatever the order of the day (28 August: the decorators of the venue were filmed first and the
# old "first scene = groom" rule made the groom pink).
WHO = {
    "bride": ["a bride in a white wedding dress", "a woman in a white wedding dress with a long veil",
              "a bride having her hair and makeup done", "a woman putting on a white wedding gown"],
    "groom": ["a groom in a suit and a bow tie", "a man in a white tuxedo jacket", "a man buttoning his shirt",
              "a man putting on a suit jacket"],
    "both": ["a bride and a groom together", "a man in a suit kissing a woman in a white wedding dress",
             "a wedding couple holding hands"],
    "none": ["an empty room", "wedding rings, shoes, perfume and an invitation on a table", "the outside of a building with trees",
             "tables decorated for a wedding", "a group of wedding guests", "a woman arranging flowers", "a church interior"],
}
WHO_CATS = list(WHO)


def load(base, progress=None, cancel=None):
    """The SigLIP 2 model (downloaded once, the same files as the AI test)."""
    d, plan = ai.ensure_model(base, progress, cancel)
    return ai.Siglip(d, plan)


class Judge:
    def __init__(self, model):
        self.m = model
        prompts, owner = [], []
        for i, c in enumerate(CATS):
            for p in SCENES[c]:
                prompts.append(ai.TEMPLATE.format(p))
                owner.append(i)
        self.owner = np.array(owner)
        wp, wo = [], []
        for i, c in enumerate(WHO_CATS):
            for p in WHO[c]:
                wp.append(ai.TEMPLATE.format(p))
                wo.append(i)
        self.wowner = np.array(wo)
        self.T = model.text(prompts + wp)
        self.TW, self.T = self.T[len(prompts):], self.T[:len(prompts)]
        self.scale = float(getattr(model, "scale", 50.0))

    def probs(self, E):
        """Frame embeddings -> {scene: probability} (mean over the frames that are not unclear)."""
        s = E @ self.T.T
        sc = np.stack([s[:, self.owner == i].max(axis=1) for i in range(len(CATS))], axis=1)
        z = np.exp(self.scale * (sc - sc.max(axis=1, keepdims=True)))
        pr = z / z.sum(axis=1, keepdims=True)
        ui = CATS.index(UNCLEAR)
        clear = pr[pr.argmax(axis=1) != ui]
        use = clear if len(clear) else pr
        m = use.mean(axis=0)
        m[ui] = 0.0
        tot = float(m.sum()) or 1.0
        out = {c: round(float(m[i] / tot), 4) for i, c in enumerate(CATS) if c != UNCLEAR}
        out["_frames"] = [CATS[int(i)] for i in pr.argmax(axis=1)]
        w = E @ self.TW.T
        wc = np.stack([w[:, self.wowner == i].max(axis=1) for i in range(len(WHO_CATS))], axis=1)
        z = np.exp(self.scale * (wc - wc.max(axis=1, keepdims=True)))
        wm = (z / z.sum(axis=1, keepdims=True)).mean(axis=0)
        out["_who"] = {c: round(float(wm[i]), 4) for i, c in enumerate(WHO_CATS)}
        return out

    def clip(self, path, a, b):
        frames = [f for f in (ai.frame_rgb(path, a + (b - a) * x, self.m.w, self.m.h) for x in (0.2, 0.5, 0.8))
                  if f is not None]
        if not frames:
            return None
        return self.probs(self.m.image(np.stack([ai.ungrade(f) for f in frames])))


def top(sc):
    """The scene with the highest probability ('' without a judgement)."""
    if not sc:
        return ""
    return max((c for c in sc if not c.startswith("_")), key=lambda c: sc[c])


def who(sc):
    """{bride, groom, both, none} of a judgement ({} for an old one without it)."""
    return (sc or {}).get("_who") or {}


def cache_key(path, a, b, stamp):
    return f"scene2|{Path(path).name}|{a:.2f}|{b:.2f}|{stamp}"     # scene2: with the WHO judgement (v4.3.0)
