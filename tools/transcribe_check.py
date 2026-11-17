"""Test of the interview engine (transcribe.py v4) without Whisper: synthetic speech + words with known times.

Checks the general rules (nothing about a particular wedding):
  1. a thinking pause in the middle of a sentence does not cut it;
  2. a sentence longer than 7.5 s is cut, every piece <= 8 s, never after "o / să / într-un...", never before "decât",
     no part under 1.5 s;
  3. a question is always its own piece, even without a pause after it;
  4. a change of speaker (measured regions) cuts, two stray words of the other mic do not;
  5. cleaning: subtitle inventions and words far from speech removed, real words with inexact times (0.5 s off) kept,
     loops removed, a segment's missing last words recovered;
  6. a soft word inside a pause stays with its piece (the border never jumps over it);
  7. a speech region without words is transcribed again (recover);
  8. the quality report has every measure.
    python tools/transcribe_check.py   -> exit code 0 when everything is right
"""
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import transcribe  # noqa: E402

SR = transcribe.SR
rng = np.random.default_rng(3)
probs = []


def check(cond, msg):
    if not cond:
        probs.append(msg)


def audio(words, total, soft=()):
    """Speech-like sound on every word's time span (syllables at ~5 per second), a quiet noise floor elsewhere."""
    x = 0.001 * rng.standard_normal(int(total * SR)).astype(np.float32)
    for k, (a, b, *_rest) in enumerate(words):
        n = int((b - a) * SR)
        t = np.arange(n) / SR
        v = np.sin(2 * np.pi * 180 * t) * (0.6 + 0.4 * np.sin(2 * np.pi * 5 * t) ** 2)
        g = 0.006 if k in soft else 0.3
        x[int(a * SR):int(a * SR) + n] += (g * v).astype(np.float32)
    return x


def W(spec, start=0.5, gap=0.08, dur=0.3, pauses=None):
    """'Word word, word.' -> [(start, end, ' word', prob, False)] one after the other; pauses = {index: extra pause}."""
    out, t = [], start
    for k, w in enumerate(spec.split()):
        t += (pauses or {}).get(k, 0.0)
        out.append((t, t + dur, " " + w, 0.9, False))
        t += dur + gap
    return out


def pieces(words, x, regions=None):
    return transcribe.sentences(words, x, (), "ro", regions)


# 1. thinking pause inside a sentence
ws = W("Sunt sigură că toți oamenii au venit astăzi.", pauses={1: 1.0})
x = audio(ws, ws[-1][1] + 1)
p = pieces(ws, x)
check(len(p) == 1, f"1: a thinking pause cut the sentence: {[s[2] for s in p]}")

# 2. a long sentence (about 14 s), commas, linking words, no full stop until the end
long = ("Am înțeles că doi oameni care nu sunt la fel se pot înțelege foarte bine, și asta mi se pare că e cel mai "
        "mare avantaj al nostru într-un an, că noi chiar ne completăm foarte bine și nu este mai rău decât asta.")
ws = W(long, pauses={21: 0.5})
x = audio(ws, ws[-1][1] + 1)
p = pieces(ws, x)
check(all(b - a <= transcribe.MAX_PIECE + 1e-6 for a, b, _t in p), f"2: a piece over 8 s: {[(round(b - a, 1)) for a, b, _t in p]}")
check(len(p) >= 2, "2: the long sentence was not cut")
for a, b, t in p[:-1]:
    last = transcribe._core(t.split()[-1]).lower()
    check(last not in transcribe.NO_END, f"2: a piece ends with '{last}': {t}")
for a, b, t in p[1:]:
    first = transcribe._core(t.split()[0]).lower()
    check(first not in transcribe.NO_START, f"2: a piece starts with '{first}': {t}")
check(all(b - a >= transcribe.MIN_SPLIT - 0.35 for a, b, _t in p), f"2: a part under 1.5 s: {[(round(b - a, 1)) for a, b, _t in p]}")

# 3. a question glued to its answer, no pause
ws = W("Cum te simți astăzi? Foarte emoționată.")
x = audio(ws, ws[-1][1] + 1)
p = pieces(ws, x)
check(len(p) == 2 and p[0][2].endswith("?"), f"3: question not separate: {[s[2] for s in p]}")

# 4. change of speaker without punctuation; two stray words of the other mic inside an answer
ws = W("ce ai învățat de la el păi cred că acum amândoi învățăm împreună să ne punem pe primul loc")
x = audio(ws, ws[-1][1] + 1)
change = ws[5][1] + 0.04
regions = [(ws[0][0], change, "v"), (change, ws[11][1] + 0.04, "c"), (ws[11][1] + 0.04, ws[12][1] + 0.04, "v"),
           (ws[12][1] + 0.04, ws[-1][1], "c")]
p = pieces(ws, x, regions)
check(any(t.endswith("el") for _a, _b, t in p), f"4: no cut at the change of speaker: {[s[2] for s in p]}")
check(not any(t.strip() in ("împreună", "împreună să") for _a, _b, t in p), f"4: a stray word became a piece: {[s[2] for s in p]}")

# 5. cleaning
reg = [(1.0, 4.0, "c"), (6.0, 9.0, "c")]
segs = [
    dict(start=1.0, end=3.0, text=" Mi-a scris pe Instagram.", nsp=0.0, logp=-0.2, comp=1.2,
         words=[(1.0, 1.3, " Mi-a", 0.9), (1.35, 1.7, " scris", 0.9), (1.75, 1.9, " pe", 0.9), (1.95, 2.6, " Instagram.", 0.9)]),
    dict(start=4.3, end=4.9, text=" frumos", nsp=0.0, logp=-0.3, comp=1.0, words=[(4.35, 4.85, " frumos", 0.8)]),    # 0.5 s off
    dict(start=5.0, end=5.5, text=" Nu uitați să dați like!", nsp=0.0, logp=-0.5, comp=1.0,
         words=[(5.0, 5.1, " Nu", 0.5), (5.1, 5.2, " uitați", 0.5), (5.2, 5.3, " să", 0.5), (5.3, 5.4, " dați", 0.5), (5.4, 5.5, " like!", 0.5)]),
    dict(start=11.0, end=11.6, text=" La revedere.", nsp=0.0, logp=-0.9, comp=1.0, words=[(11.0, 11.3, " La", 0.6), (11.3, 11.6, " revedere.", 0.6)]),
    dict(start=6.0, end=8.0, text=" Și am zis da da da da da da da da da da da da.", nsp=0.0, logp=-0.4, comp=3.0, words=[]),
    dict(start=6.2, end=8.0, text=" Am ieșit la primul date și la al doilea.", nsp=0.0, logp=-0.2, comp=1.1,
         words=[(6.2, 6.4, " Am", 0.9), (6.4, 6.7, " ieșit", 0.9), (6.7, 6.8, " la", 0.9), (6.8, 7.2, " primul", 0.9)]),
]
words, removed = transcribe.clean(segs, reg)
txt = " ".join(w[2].strip() for w in words)
check("frumos" in txt, "5: a real word 0.5 s outside the speech was removed")
check("uitați" not in txt, "5: a subtitle invention was kept")
check("revedere" not in txt, "5: a word far from any speech was kept")
check("da da da" not in txt, "5: a loop was kept")
check("doilea." in txt, f"5: the segment's missing last words were not recovered: {txt}")

# 6. a soft word inside a pause stays with its piece: border between "mult" and a softly said "că" that sits inside
# what the sound measures as a pause (its word times also a little early, like on real interviews)
ws = W("Acum apreciez foarte mult că s-au așezat toate lucrurile.", pauses={4: 0.6})
x = audio(ws, ws[-1][1] + 1, soft={4})
early = [(w[0] - 0.15, w[1] - 0.15) + tuple(w[2:]) if k >= 4 else w for k, w in enumerate(ws)]
times = transcribe._snap_borders([early[:4], early[4:]], x, set())
check(times[1][0] <= ws[4][0] + 0.05, f"6: the soft word 'că' ({ws[4][0]:.2f}) was cut off: next piece starts {times[1][0]:.2f}")
check(times[0][1] >= ws[3][1] - 0.05, f"6: 'mult' ({ws[3][1]:.2f}) was cut off: piece ends {times[0][1]:.2f}")

# 7. recover: a speech region without words is transcribed again
calls = []


def fake_run(y):
    calls.append(len(y) / SR)
    return [dict(start=1.0, end=1.5, text=" Superb!", nsp=0.0, logp=-0.1, comp=1.0, words=[(1.0, 1.5, " Superb!", 0.95)])]


words = [(0.5, 0.9, " Bun.", 0.9, False), (3.0, 3.4, " Sunt", 0.9, False)]
xx = np.zeros(5 * SR, np.float32)
out, lost = transcribe.recover(words, [(0.5, 0.9, "c"), (1.6, 2.3, "c"), (3.0, 3.4, "c")], xx, fake_run)
check(len(calls) == 1, f"7: expected one new transcription, got {len(calls)}")
check(any("Superb" in w[2] for w in out) and not lost, "7: the word of the silent region was not recovered")

# 8. quality report
ws = W("Cum te simți astăzi? Foarte emoționată, nu așteptam să am așa mari emoții.")
x = audio(ws, ws[-1][1] + 1)
p = pieces(ws, x)
p.removed, p.lost = ["Nu uitați să dați like!"], [(1.0, 1.5)]
q = transcribe.quality(p, x, "A")
for key in ("codes", "over8", "under08", "glued", "pause_pct", "forced", "removed", "lost"):
    check(key in q, f"8: report without '{key}'")
check("1 stretches" in transcribe.quality_line(q), "8: the quality line does not show the speech without text")

for m in probs:
    print("WRONG:", m)
print("interview engine:", "OK" if not probs else f"{len(probs)} problem(s)")
sys.exit(1 if probs else 0)
