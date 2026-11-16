"""The story of the interviews, written by Claude through the owner's own subscription (no API key, no cost).

1. prompt(): the transcripts with a code on every sentence (A1, A2... for the first interview, B1... for the second),
   who speaks, no length limit (as long as the story needs: the owner does not want it shortened by force), and the
   rules (whole sentences exactly as said, the two of them telling ONE story
   together, answer between STORY_START / STORY_END). The app copies it and opens a new Claude chat; he pastes it.
2. parse(): Claude's answer (copied back) -> the pieces in film order, each = a run of sentences of one interview.
3. export_xml(): the pieces back to back on a 25 fps timeline, picture + all sound channels linked, a marker on every
   piece with its text. Imported into Premiere like every other XML of the app.
"""
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

import core

SEQ_FPS = 25.0
LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
PAD_IN, PAD_OUT = 0.15, 0.30          # breath before / after a piece (never into the next sentence)
WHO_RO = {"bride": "mireasa", "groom": "mirele", "both": "mirii împreună", "other": "altcineva", "": "nu știu cine"}
WHO_EN = {"bride": "the bride", "groom": "the groom", "both": "the couple together", "other": "someone else", "": "unknown"}


def is_question(text):
    """The interviewer's questions end with '?' (Whisper writes the punctuation). Claude also gets the rule to skip his
    other lines (Perfect!, Bravo!, Mulțumesc!), which it recognises from the context."""
    return str(text).strip().rstrip('"\'»”').endswith("?")


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


def prompt(files, lang="ro"):
    """files = [dict(path, segs=[[start, end, text]], who)] in the order of the list. Returns the text for Claude."""
    ro = lang == "ro"
    who = WHO_RO if ro else WHO_EN
    head = []
    body = []
    for k, f in enumerate(files):
        L = LETTERS[k]
        head.append(f"- {'Interviul' if ro else 'Interview'} {L}: {who.get(f.get('who') or '', who[''])} "
                    f"({Path(f['path']).name})")
        body.append(f"\n=== {'INTERVIUL' if ro else 'INTERVIEW'} {L} ===")
        for i, (a, b, t) in enumerate(f["segs"], 1):
            q = (" [ÎNTREBARE]" if ro else " [QUESTION]") if is_question(t) else ""
            body.append(f"{L}{i} ({b - a:.1f} s){q} {t}")
    if ro:
        intro = (
            "Ești editorul unui film de nuntă. Mai jos sunt interviurile transcrise, fiecare frază are un cod "
            "(A1, A2… pentru primul interviu, B1, B2… pentru al doilea) și durata ei în secunde.\n\n"
            + "\n".join(head) + "\n\n"
            "Interviurile sunt de tipul: eu (cameramanul) întreb, mirii răspund. ÎNTREBĂRILE MELE ȘI REPLICILE MELE NU INTRĂ "
            "NICIODATĂ ÎN POVESTE: cele marcate [ÎNTREBARE], dar și replicile mele scurte (de ex. „Perfect!”, „Bravo!”, "
            "„Mulțumesc!”, „A fost perfect!”) și glumele de la final. Folosește doar răspunsurile mirilor.\n\n"
            "Ce vreau:\n"
            "1. Găsește povestea lor: ce îi leagă, cum s-au cunoscut, momentele importante, ce simt unul pentru altul.\n"
            + ("2. Construiește O SINGURĂ POVESTE în care povestesc ÎMPREUNĂ. Pe amândoi îi întreb aceleași lucruri (cum s-au "
               "cunoscut, cum e celălalt, ce iubește la el / ea, ce își doresc, un mesaj pentru celălalt), deci pe fiecare "
               "temă ai versiunea ei și versiunea lui. Împletește-le pe teme: pe aceeași temă tai de la unul la celălalt, "
               "des, în bucăți scurte (una-trei fraze), ca și cum unul ar continua ideea celuilalt (de ex. el spune ce iubește "
               "la ea, apoi tai la ea care spune ce iubește la el; ea începe cum s-au cunoscut, el continuă). Ordinea "
               "temelor: cum s-au cunoscut, apoi cum se văd unul pe altul, ce îi leagă, viitorul, iar la final mesajele "
               "lor unul pentru celălalt (finalul emoționant). Fiecare temă să aibă ambele voci, iar povestea să fie un "
               "întreg, cu început, mijloc și final.\n" if len(files) > 1 else
               "2. Construiește din răspunsuri o poveste curgătoare, ca și cum ar povesti fără întrebări, cu început, mijloc "
               "și un final emoționant.\n") +
            "3. Durata: cât are nevoie povestea. Nu o scurta forțat și nu o lungi: păstrează tot ce e bun și spune "
            "povestea, lasă afară ce nu adaugă nimic.\n"
            "4. Folosește DOAR fraze care există, întregi, exact cum sunt. Nu inventa, nu rescrie, nu tăia o frază la "
            "jumătate. Poți lua mai multe fraze la rând (de ex. A12-A14). Evită ezitările, repetițiile, frazele "
            "neterminate și ce nu se înțelege fără întrebarea mea.\n\n"
            "Răspunsul tău: întâi 1-2 propoziții cu povestea pe scurt, apoi lista, exact între rândurile STORY_START și "
            "STORY_END, un rând pe bucată, în ordinea din film: codul (A12) sau codurile la rând (A12-A14), apoi \" | \" și "
            "începutul textului. Exemplu:\n"
            "STORY_START\nB3 | Prima dată când am văzut-o…\nA7-A8 | Eu nu credeam că…\nSTORY_END\n"
        )
    else:
        intro = (
            "You are the editor of a wedding film. Below are the transcribed interviews; every sentence has a code "
            "(A1, A2… for the first interview, B1, B2… for the second) and its length in seconds.\n\n"
            + "\n".join(head) + "\n\n"
            "The interviews go like this: I (the videographer) ask, the couple answers. MY QUESTIONS AND MY LINES NEVER GO "
            "INTO THE STORY: the ones marked [QUESTION], and also my short lines (e.g. \"Perfect!\", \"Bravo!\", "
            "\"Thank you!\") and the jokes at the end. Use only the couple's answers.\n\n"
            "What I want:\n"
            "1. Find their story: what binds them, how they met, the important moments, what they feel for each other.\n"
            + ("2. Build ONE STORY that they tell TOGETHER. I ask both of them the same things (how they met, what the "
               "other is like, what they love about him / her, what they wish for, a message to the other), so on every "
               "theme you have her version and his. Weave them by theme: on the same theme cut from one to the other, "
               "often, in short pieces (one to three sentences), as if one continued the other's thought (e.g. he says "
               "what he loves about her, then cut to her saying what she loves about him; she starts how they met, he "
               "goes on). Order of the themes: how they met, then how they see each other, what binds them, the future, "
               "and at the end their messages to each other (the emotional ending). Every theme with both voices, and "
               "the story a whole, with a beginning, a middle and an ending.\n" if len(files) > 1 else
               "2. Build a flowing story from the answers, as if told without questions, with a beginning, a middle and "
               "an emotional ending.\n") +
            "3. Length: as long as the story needs. Do not shorten it by force and do not stretch it: keep everything "
            "that is good and tells the story, leave out what adds nothing.\n"
            "4. Use ONLY sentences that exist, whole, exactly as they are. Do not invent, rewrite or cut a sentence in "
            "half. You may take several sentences in a row (e.g. A12-A14). Avoid hesitations, repetitions, unfinished "
            "sentences and anything that needs my question to make sense.\n\n"
            "Your answer: first 1-2 sentences with the story in short, then the list, exactly between the lines "
            "STORY_START and STORY_END, one line per piece, in film order: the code (A12) or the codes in a row (A12-A14), "
            "then \" | \" and the beginning of the text. Example:\n"
            "STORY_START\nB3 | The first time I saw her…\nA7-A8 | I never thought…\nSTORY_END\n"
        )
    return intro + "\n".join(body) + "\n"


_LINE = re.compile(r"^\W*([A-Z])\s*(\d+)(?:\s*[-–—]\s*([A-Z])?\s*(\d+))?\b")


def parse(answer, files):
    """Claude's answer -> ([(file index, first sentence, last sentence)] in order (0-based, inclusive), [bad lines])."""
    text = answer.replace("\r", "")
    m = re.search(r"STORY_START(.*?)(STORY_END|$)", text, re.S)
    block = m.group(1) if m else text
    pieces, bad = [], []
    for line in block.split("\n"):
        s = line.strip().strip("`*")
        if not s:
            continue
        mm = _LINE.match(s)
        if not mm:
            if m:                                     # inside the block every line should be a piece
                bad.append(s[:60])
            continue
        L, a, L2, b = mm.group(1), int(mm.group(2)), mm.group(3), mm.group(4)
        fi = LETTERS.find(L)
        b = int(b) if b else a
        if (L2 and L2 != L) or fi < 0 or fi >= len(files) or not (1 <= a <= b <= len(files[fi]["segs"])):
            bad.append(s[:60])
            continue
        run = []                                        # a range never carries a question inside it
        for k in range(a - 1, b):
            if is_question(files[fi]["segs"][k][2]):
                if run:
                    pieces.append((fi, run[0], run[-1]))
                run = []
            else:
                run.append(k)
        if run:
            pieces.append((fi, run[0], run[-1]))
    return pieces, bad


def ranges(pieces, files, durs):
    """Pieces -> [(file index, t0, t1, text)]: from the first sentence's start to the last one's end, with a breath on
    both sides that never reaches into the sentence before / after."""
    out = []
    for fi, a, b in pieces:
        segs = files[fi]["segs"]
        t0, t1 = float(segs[a][0]), float(segs[b][1])
        lo = float(segs[a - 1][1]) if a > 0 else 0.0
        hi = float(segs[b + 1][0]) if b + 1 < len(segs) else durs[fi]
        t0 = max(lo, 0.0, t0 - PAD_IN)
        t1 = min(hi, durs[fi], t1 + PAD_OUT)
        if t1 - t0 >= 0.2:
            out.append((fi, t0, t1, " ".join(str(s[2]) for s in segs[a:b + 1])))
    return out


def export_xml(cuts, files, infos, out_path, name, labels=None):
    """cuts = ranges(); infos = projectsetup.probe() per file path. One 25 fps sequence: the pieces back to back on V1
    (video files) with every sound channel on A1..An (source channel k on Ak), linked; a marker per piece."""
    rate_xml, sf = core._rate(SEQ_FPS)
    clips, pos = [], 0
    for fi, t0, t1, text in cuts:
        f = files[fi]["path"]
        i0, i1 = int(round(t0 * sf)), int(round(t1 * sf))
        if i1 <= i0:
            continue
        clips.append(dict(f=f, st=pos, n=i1 - i0, src=i0, text=text, fi=fi))
        pos += i1 - i0
    if not clips:
        raise ValueError("No pieces to put on the timeline.")
    vid = lambda c: infos[c["f"]].get("video")
    ach = lambda c: infos[c["f"]].get("ach", 0)
    nach = max(ach(c) for c in clips)
    n = 0
    vpos = 0
    for c in clips:
        if vid(c):
            n += 1
            vpos += 1
            c["v"] = (f"clipitem-{n}", 1, vpos)
    for k in range(1, nach + 1):
        p = 0
        for c in clips:
            if ach(c) >= k:
                n += 1
                p += 1
                c[f"a{k}"] = (f"clipitem-{n}", k, p)
    fids = {}

    def file_xml(f):
        if f in fids:
            return f'<file id="{fids[f]}"/>'
        fids[f] = f"file-{len(fids) + 1}"
        i = infos[f]
        frate, ffps = core._rate(i.get("fps", 25.0))
        v = f'<video>{core._sc(frate, i["w"], i["h"], "none")}</video>' if i.get("video") else ""
        a = (f'<audio><samplecharacteristics><depth>16</depth><samplerate>{i.get("arate", 48000)}</samplerate>'
             f'</samplecharacteristics><channelcount>{i["ach"]}</channelcount></audio>') if i.get("ach") else ""
        return (f'<file id="{fids[f]}"><name>{escape(Path(f).name)}</name><pathurl>{escape(core._url(f))}</pathurl>'
                f'{frate}<duration>{int(i["dur"] * ffps)}</duration><media>{v}{a}</media></file>')

    def links(c):
        refs = ([("video", c["v"])] if "v" in c else []) + [("audio", c[f"a{k}"]) for k in range(1, ach(c) + 1)]
        if len(refs) < 2:
            return ""
        return "".join(f'<link><linkclipref>{r[0]}</linkclipref><mediatype>{mt}</mediatype><trackindex>{r[1]}</trackindex>'
                       f'<clipindex>{r[2]}</clipindex>' + ("<groupindex>1</groupindex>" if mt == "audio" else "") + "</link>"
                       for mt, r in refs)

    def item(c, ref, extra=""):
        return (f'<clipitem id="{ref[0]}"><name>{escape(Path(c["f"]).name)}</name><duration>{c["n"]}</duration>{rate_xml}'
                f'<start>{c["st"]}</start><end>{c["st"] + c["n"]}</end><in>{c["src"]}</in><out>{c["src"] + c["n"]}</out>'
                f'{file_xml(c["f"])}{extra}{links(c)}</clipitem>')

    trk = lambda its: f'<track>{"".join(its)}<enabled>TRUE</enabled><locked>FALSE</locked></track>'
    vitems = [item(c, c["v"]) for c in clips if "v" in c]
    aitems = [[item(c, c[f"a{k}"], f'<sourcetrack><mediatype>audio</mediatype><trackindex>{k}</trackindex></sourcetrack>')
               for c in clips if ach(c) >= k] for k in range(1, nach + 1)]
    vf = next((infos[c["f"]] for c in clips if vid(c)), None)
    fmt = f'<format>{core._sc(rate_xml, vf["w"], vf["h"], "none")}</format>' if vf else \
        f'<format>{core._sc(rate_xml, 1920, 1080, "none")}</format>'
    labels = labels or {}
    mk = "".join(f'<marker><name>{escape((labels.get(c["fi"], "") + ": " if labels.get(c["fi"]) else "") + c["text"][:50])}'
                 f'</name><comment>{escape(c["text"])}</comment><in>{c["st"]}</in><out>{c["st"] + c["n"]}</out></marker>'
                 for c in clips)
    arate = next((infos[c["f"]].get("arate", 48000) for c in clips if ach(c)), 48000)
    xml = (f'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n<xmeml version="4"><sequence id="sequence-1">'
           f'<name>{escape(name)}</name><duration>{pos}</duration>{rate_xml}{mk}'
           f'<media><video>{fmt}{trk(vitems) if vitems else ""}</video>'
           f'<audio><numOutputChannels>2</numOutputChannels><format><samplecharacteristics><depth>16</depth>'
           f'<samplerate>{arate}</samplerate></samplecharacteristics></format>{"".join(trk(a) for a in aitems)}</audio>'
           f'</media></sequence></xmeml>')
    Path(out_path).write_text(xml, encoding="utf-8")
    return dict(pieces=len(clips), seconds=pos / sf)


# ---- automatic: straight to Claude with his own API key (optional; without a key the copy / paste way is used)
MODELS = ["claude-sonnet-5-5", "claude-opus-5-5"]       # the first one that answers


def ask_claude(text, key, cancel=None):
    """Sends the prompt to the Claude API and returns the answer's text. Raises RuntimeError(short reason)."""
    import updater
    last = "no answer"
    for model in MODELS:
        body = json.dumps({"model": model, "max_tokens": 8000,
                           "messages": [{"role": "user", "content": text}]}).encode("utf-8")
        req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=body, method="POST", headers={
            "x-api-key": key.strip(), "anthropic-version": "2023-06-01", "content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=600, context=updater._ctx()) as r:
                d = json.loads(r.read().decode("utf-8"))
            out = "".join(b.get("text", "") for b in d.get("content", []) if b.get("type") == "text")
            if out.strip():
                return out
            last = "empty answer"
        except urllib.error.HTTPError as e:
            try:
                msg = json.loads(e.read().decode("utf-8")).get("error", {}).get("message", "")
            except Exception:
                msg = ""
            low = msg.lower()
            if e.code == 401:
                raise RuntimeError("the Claude API key is not valid") from None
            if "credit" in low or "billing" in low:
                raise RuntimeError("the Claude API account has no credit (add credit at console.anthropic.com)") from None
            if e.code == 429:
                raise RuntimeError("Claude's limit was reached for now, try again in a few minutes") from None
            if e.code in (500, 529):
                raise RuntimeError("Claude is overloaded right now, try again in a few minutes") from None
            if e.code == 404 or "model" in low:
                last = f"model {model} not available"
                continue                                # try the next model
            raise RuntimeError(f"Claude refused the request (HTTP {e.code}{': ' + msg[:80] if msg else ''})") from None
        except urllib.error.URLError:
            raise RuntimeError("no internet connection") from None
    raise RuntimeError(last)
