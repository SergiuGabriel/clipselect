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
# v4.6.0: the MOMENT of every clip, finer (the day model of daymap.classify_ai reads these): measured with the real
# SigLIP 2 on his 28 / 29 August and 4 September weddings (3 frames per clip). "civil" = the officer with the tricolour
# sash (a sure frame scores ~1.0, nothing else above 0.5); "church" also covers ceremonies outdoors under an arch.
MOMENTS = {
    'groom': [
        'a groom getting dressed in a white shirt in a room',
        'a man in a suit and bow tie getting ready for his wedding',
        'a groom with his parents in a living room before the wedding',
        'groomsmen helping a man put on his jacket',
        'a man buttoning the cuffs of his shirt',
        'a man adjusting his bow tie in front of a window',
    ],
    'bride': [
        'a bride having her makeup and hair done',
        'a bride in a white wedding dress and long veil getting ready in a room',
        'a woman helping a bride lace up her wedding dress',
        'a bride posing alone in a white gown in an elegant room',
        'the long train of a white wedding dress on a wooden floor',
        'a bride putting on her earrings',
    ],
    'details': [
        'wedding rings on an invitation card',
        'a perfume bottle, watch and cufflinks on a table',
        'a white suit jacket hanging on a bookshelf',
        'wedding shoes and jewellery details',
        'a box of cigars and a bottle of whisky',
    ],
    'firstlook': [
        'a groom seeing his bride for the first time and crying',
        'a bride and groom meeting emotionally in a room with photographers around',
        'family members hugging the bride and groom inside a house',
        'a groom wiping tears with a handkerchief',
    ],
    'couple': [
        'a bride and groom posing together for photos in a garden',
        'a wedding couple walking hand in hand outdoors',
        'a bride and groom embracing in front of a mansion',
        'a wedding couple kissing in a park at sunset',
        'a bride and groom portrait in an elegant room',
        'a bride and groom showing their wedding rings',
    ],
    'civil': [
        'a woman wearing a red yellow and blue tricolor sash reading from a register',
        'a civil wedding officer with a tricolour sash officiating outdoors',
        'a civil servant with a tricolour sash marrying a couple at a table',
        'a bride and groom signing a marriage register at a civil ceremony',
    ],
    'church': [
        'the inside of an orthodox church with golden icons and chandeliers',
        'a priest in golden vestments during a wedding ceremony',
        'a bride and groom wearing crowns in an orthodox church',
        'wedding guests standing inside a church',
        'newlyweds walking out of a church while guests throw rice and petals',
        'a wedding ceremony outdoors under a white floral arch',
        'a priest officiating a wedding in a garden',
        'a bride and groom standing at an altar outdoors in front of seated guests',
        'a catholic priest in white vestments blessing a couple',
    ],
    'venue': [
        'long tables decorated for a wedding reception outdoors',
        'an empty banquet hall with a crystal chandelier',
        'the outside of an elegant mansion with trees',
        'a woman arranging flowers and setting wedding tables',
        'white chairs and table settings with plates and glasses',
        'an empty room with paintings and antique furniture',
        'a decorated wedding tent with chandeliers and empty round tables',
        'a welcome sign with flowers at a wedding venue',
        'a dessert table with cakes and sweets at a wedding',
        'an empty outdoor ceremony area with white chairs and a floral arch',
        'a seating plan board with flowers',
    ],
    'party': [
        'people dancing at a wedding party at night',
        'a DJ playing music at a wedding party',
        'a crowded dance floor with lights',
        'wedding guests sitting at long tables in a garden in the evening',
        'guests chatting outdoors at a wedding reception',
        'a bride and groom cutting a wedding cake at night',
        'wedding guests dancing in a tent with colourful stage lights',
    ],
    'drone': [
        'an aerial drone view from high above',
        "a bird's eye view of buildings, trees and fields",
    ],
    'interview': [
        'a man talking to the camera in an interview at night',
        'an older couple speaking to the camera',
    ],
    'speech': [
        'a man giving a speech to a group of people in a house',
        'a man speaking to guests in a courtyard',
        'an older man talking while people listen',
    ],
    UNCLEAR: [
        'a blurry, out of focus image',
        'a dark, underexposed image',
        'a ceiling or a plain wall',
        'a floor',
    ],
}
MOMENT_CATS = list(MOMENTS)


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
        mp, mo = [], []
        for i, c in enumerate(MOMENT_CATS):
            for p in MOMENTS[c]:
                mp.append(ai.TEMPLATE.format(p))
                mo.append(i)
        self.mowner = np.array(mo)
        self.TM = model.text(mp)
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
        out["_p"], out["_civil"] = moment_probs(E, self.TM, self.mowner, self.scale)
        return out

    def clip(self, path, a, b):
        frames = [f for f in (ai.frame_rgb(path, a + (b - a) * x, self.m.w, self.m.h) for x in (0.2, 0.5, 0.8))
                  if f is not None]
        if not frames:
            return None
        return self.probs(self.m.image(np.stack([ai.ungrade(f) for f in frames])))


def moment_probs(E, TM, owner, scale=50.0):
    """Frame embeddings -> ({moment: probability}, the highest 'civil' of one frame). Per frame: the best prompt of
    every moment, a softmax; the clip = the mean of its clear frames (blurred / dark / ceiling frames left out)."""
    s = E @ TM.T
    sc = np.stack([s[:, owner == i].max(axis=1) for i in range(len(MOMENT_CATS))], axis=1)
    z = np.exp(scale * (sc - sc.max(axis=1, keepdims=True)))
    pr = z / z.sum(axis=1, keepdims=True)
    ui = MOMENT_CATS.index(UNCLEAR)
    clear = pr[pr.argmax(axis=1) != ui]
    m = (clear if len(clear) else pr).mean(axis=0)
    m[ui] = 0.0
    m = m / (float(m.sum()) or 1.0)
    civ = float(pr[:, MOMENT_CATS.index("civil")].max())
    return {c: round(float(m[i]), 4) for i, c in enumerate(MOMENT_CATS) if c != UNCLEAR}, round(civ, 4)


def top(sc):
    """The scene with the highest probability ('' without a judgement)."""
    if not sc:
        return ""
    return max((c for c in sc if not c.startswith("_")), key=lambda c: sc[c])


def who(sc):
    """{bride, groom, both, none} of a judgement ({} for an old one without it)."""
    return (sc or {}).get("_who") or {}


def cache_key(path, a, b, stamp):
    return f"scene3|{Path(path).name}|{a:.2f}|{b:.2f}|{stamp}"     # scene3: with the moments of the day model (v4.6.0)
