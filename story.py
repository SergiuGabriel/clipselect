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
PAD_IN, PAD_OUT = 0.12, 0.20          # breath before / after a piece (owner: -0.12 s / +0.2 s, never into the next sentence)
WHO_RO = {"bride": "mireasa", "groom": "mirele", "both": "mirii împreună", "other": "altcineva", "": "nu știu cine"}
WHO_EN = {"bride": "the bride", "groom": "the groom", "both": "the couple together", "other": "someone else", "": "unknown"}


INTERVIEWER = {"perfect", "bravo", "multumesc", "mulțumesc", "bun", "super", "foarte bine", "gata", "excelent",
               "good", "great", "thank you", "thanks", "perfect perfect", "bravo bravo"}


def is_question(text):
    """[QUESTION] = what can be detected of the videographer (owner's final spec): a question (ends with '?') or one of
    his very short lines ("Perfect!", "Bravo!", "Mulțumesc!", "Bun!"). Not perfect on purpose: the prompt tells Claude to
    recognise his unmarked lines too."""
    t = str(text).strip().rstrip('"\'»”')
    if t.endswith("?"):
        return True
    return re.sub(r"[^\w\s]", "", t.lower()).strip() in INTERVIEWER


def qflags(f):
    """[True when the piece is the videographer's] for every piece of an interview (v3.10.0): measured from the sound
    when the transcript has it (f["spk"]: 'v' = the videographer, 'c' / '1' / '2' = the couple); only where it is not
    sure who speaks ('?') or there is no measurement does the text rule decide ('?' at the end, his short lines)."""
    segs = f["segs"]
    spk = f.get("spk") or []
    if len(spk) != len(segs):
        spk = [None] * len(segs)
    return [lab == "v" or (lab not in ("c", "1", "2") and is_question(sg[2])) for sg, lab in zip(segs, spk)]


def _mmss(t):
    return f"{int(t // 60)}:{int(t % 60):02d}"


WHO_PROMPT = {"groom": "THE GROOM", "bride": "THE BRIDE", "both": "BOTH OF THEM", "other": "SOMEONE ELSE"}


def prompt(files, lang="ro"):
    """The owner's final prompt (MODIFICARE_FINALA_program.md, section 3), always in English; only the <...> fields are
    filled. files = [dict(path, segs=[[start, end, text]], who, name)] in the order of the list."""
    import transcribe
    head, body = [], []
    unknown = [LETTERS[k] for k, f in enumerate(files) if not f.get("who")]
    names = next((transcribe.couple_names(f["path"]) for f in files if transcribe.couple_names(f["path"])), [])
    for k, f in enumerate(files):
        L = LETTERS[k]
        who = WHO_PROMPT.get(f.get("who") or "", "UNKNOWN")
        nm = (f.get("name") or "").strip()
        head.append(f"- Interview {L}: {who}{', ' + nm if nm else ''} ({Path(f['path']).name})")
        body.append(f"\n=== INTERVIEW {L} ===")
        qs = qflags(f)
        spk = f.get("spk") or []
        two = len(spk) == len(f["segs"]) and any(lab in ("1", "2") for lab in spk)
        if two:
            body.append(f"(Interview {L} has two people, each with a lavalier: [S1] = the person on the first "
                        "lavalier, [S2] = on the second, measured from the sound; find out from what they say who is who.)")
        for i, (a, b, t) in enumerate(f["segs"], 1):
            q = " [QUESTION]" if qs[i - 1] else ""
            sp = f" [S{spk[i - 1]}]" if two and spk[i - 1] in ("1", "2") and not qs[i - 1] else ""
            body.append(f"{L}{i} ({b - a:.1f} s){q}{sp} {t}")
    extra = ""
    if unknown:
        extra = ((f"The couple: {names[0]} and {names[1]}.\n" if names else "") +
                 f"For interview(s) {', '.join(unknown)} (UNKNOWN): find out from what they say whether it is THE GROOM, "
                 "THE BRIDE or BOTH OF THEM, and write it on a line before STORY_START, e.g. WHO: A=GROOM, B=BRIDE.\n")
    intro = (
        "You are the editor of a wedding film. Below are the transcribed interviews; every piece has a code (A1, A2… for "
        "the first interview, B1, B2… for the second, C1… for a third) and its length in seconds.\n\n"
        + "\n".join(head) + "\n" + extra + "\n"
        "The interviews go like this: I (the videographer) ask, they answer. MY QUESTIONS AND MY LINES NEVER GO INTO THE "
        "STORY: the ones marked [QUESTION], my short lines (e.g. \"Perfect!\", \"Bravo!\", \"Thank you!\", \"Good!\"), my "
        "instructions to them even when NOT marked (e.g. \"you have to tell me what day it is today\", \"say it to her in "
        "the second person\", \"say it as if you were talking to her\"), the small talk before the interview starts, and "
        "the jokes at the end. Use only the couple's answers.\n\n"
        "What I want:\n"
        "1. Find their story: what binds them, how they met, the important moments, what they feel for each other.\n"
        "2. Build ONE STORY that they tell TOGETHER. I ask both of them the same things, so on every theme you have her "
        "version and his. Weave them by theme: cut from one to the other OFTEN, in short pieces (ideally one to three "
        "sentences), as if one continued the other's thought. When one of them tells part of an event and the other tells "
        "the next part, alternate between them.\n"
        "3. Look for ECHOES: a sentence of one that answers or mirrors a sentence of the other (e.g. she says what they are "
        "learning, he says the same thing about her). Put them next to each other.\n"
        "4. Order: open strong (the day, the emotion; if one of them mentions something difficult that happened before the "
        "wedding, use it here and let the other answer it), then how they met, how they see each other, what binds them, "
        "what they learned / the future, and at the end their messages to each other (the emotional ending, maybe with a "
        "smile). Every theme with both voices where both talked about it.\n"
        "5. Length: as long as the story needs. Do not shorten it by force and do not stretch it: keep everything that is "
        "good and tells the story, leave out what adds nothing.\n"
        "6. Use ONLY pieces that exist, whole, exactly as they are. You may take several pieces in a row (e.g. A12-A14). "
        "Never use part of a piece.\n"
        "7. Avoid: hesitations, repetitions, unfinished sentences, and anything that needs my question to make sense (e.g. "
        "a bare \"On Instagram, the first time.\" or \"Full of emotion.\" as an answer).\n"
        "8. A piece that starts with a linking word (\"And\", \"But\", \"So\", \"Și\", \"Dar\", \"Așa că\", \"Pentru că\") "
        "must make sense after the piece you put BEFORE it in the story. If it only makes sense after the piece that came "
        "before it in the interview, take that piece too (e.g. B23-B24) or choose another.\n"
        "9. Do not repeat the same information in two voices back to back unless the second one adds something (e.g. both "
        "saying the date: keep the stronger one).\n"
        "10. Swearing is allowed (I remove it myself in the edit). Keep jokes WHOLE: if you use the setup of a joke, put its "
        "punchline right after it; otherwise leave both out.\n\n"
        "The automatic transcript misspells some words: understand them from the context.\n\n"
        "Your answer: first 1-2 sentences with the story in short, then the list, exactly between the lines STORY_START and "
        "STORY_END, one line per piece, in film order: the code (A12) or the codes in a row (A12-A14), then \" | \" and the "
        "text of those pieces written correctly (misheard words fixed, without changing what they said). Use only codes "
        "that exist. Example:\n"
        "STORY_START\nB3 | The first time I saw her…\nA7-A8 | I never thought…\nSTORY_END\n"
    )
    return intro + "\n".join(body) + "\n"


def parse_who(answer, n):
    """The WHO line of Claude's answer -> {interview index: 'groom' / 'bride'}."""
    m = re.search(r"WHO\s*:\s*(.+)", answer)
    out = {}
    if not m:
        return out
    for L, w in re.findall(r"\b([A-Z])\s*[=:]\s*\**\s*([A-Za-zĂÂÎȘȚăâîșț]+)", m.group(1)):
        k = LETTERS.find(L)
        w = w.lower()
        if 0 <= k < n:
            if w.startswith(("groom", "mire")) and not w.startswith("mireas"):
                out[k] = "groom"
            elif w.startswith(("bride", "mireas")):
                out[k] = "bride"
    return out


_LINE = re.compile(r"^\W*([A-Z])\s*(\d+)(?:\s*[-–—]\s*([A-Z])?\s*(\d+))?\b")


def parse_checked(answer, files):
    """Claude's answer -> (pieces, errors, warnings). pieces = [(file index, first, last, corrected text)] (0-based,
    inclusive) in film order. Only the lines between STORY_START and STORY_END count. ERRORS (no XML): no list, a code
    that does not exist, a range across two interviews or backwards, a [QUESTION] code, a code used twice. A question
    inside a range is cut out of it (warning)."""
    text = answer.replace("\r", "")
    m = re.search(r"STORY_START(.*?)STORY_END", text, re.S) or re.search(r"STORY_START(.*)$", text, re.S)
    errors, warnings, pieces, used = [], [], [], {}
    if not m:
        return [], ["The answer has no STORY_START / STORY_END list."], []
    for line in m.group(1).split("\n"):
        s = line.strip().strip("`*").strip()
        if not s:
            continue
        mm = _LINE.match(s)
        if not mm:
            warnings.append(f"Line ignored (no code): {s[:50]}")
            continue
        L, a, L2, b = mm.group(1), int(mm.group(2)), mm.group(3), mm.group(4)
        code = f"{L}{a}" + (f"-{L2 or L}{b}" if b else "")
        fi = LETTERS.find(L)
        b = int(b) if b else a
        if L2 and L2 != L:
            errors.append(f"{code}: a range across two interviews.")
            continue
        if fi < 0 or fi >= len(files) or not (1 <= a <= len(files[fi]["segs"])) or not (1 <= b <= len(files[fi]["segs"])):
            errors.append(f"{code}: this code does not exist.")
            continue
        if b < a:
            errors.append(f"{code}: the range goes backwards.")
            continue
        qs = qflags(files[fi])
        if qs[a - 1] or qs[b - 1]:
            errors.append(f"{code}: a [QUESTION] (the videographer) is used.")
            continue
        for k in range(a - 1, b):
            if k in used.setdefault(fi, set()):
                errors.append(f"{L}{k + 1} is used twice.")
            used[fi].add(k)
        txt = s.split("|", 1)[1].strip().strip("`*").strip() if "|" in s else None
        run, runs = [], []
        for k in range(a - 1, b):
            if qs[k]:
                warnings.append(f"{code}: the [QUESTION] {L}{k + 1} inside it was left out.")
                if run:
                    runs.append(run)
                run = []
            else:
                run.append(k)
        if run:
            runs.append(run)
        for r in runs:
            pieces.append((fi, r[0], r[-1], txt if len(runs) == 1 else None))
    if not pieces and not errors:
        errors.append("The list between STORY_START and STORY_END is empty.")
    return pieces, errors, warnings


def parse(answer, files):
    """Old interface: (pieces, bad lines)."""
    pieces, errors, warnings = parse_checked(answer, files)
    return pieces, errors + [w for w in warnings if w.startswith("Line ignored")]


def cut_times(pieces, files, durs, fps=25.0, audio=None):
    """Owner's final spec, section 4: in = start of the first code - 0.12 s, never earlier than the end of the previous
    code of the INTERVIEW + 0.02 s; out = end of the last code + 0.20 s, never later than the start of the next code of
    the interview - 0.02 s; then, per media file, cuts sorted by in: when one's out passes the next one's in (even if
    they are far apart in the story), both move to the middle. No audio frame is heard twice."""
    cuts = []
    for p in pieces:
        fi, a, b = p[:3]
        fixed = p[3] if len(p) > 3 else None
        segs, dur = files[fi]["segs"], durs[fi]
        t0 = float(segs[a][0]) - PAD_IN
        if a > 0:
            t0 = max(t0, float(segs[a - 1][1]) + 0.02)
        t1 = float(segs[b][1]) + PAD_OUT
        if b + 1 < len(segs):
            t1 = min(t1, float(segs[b + 1][0]) - 0.02)
        t0 = max(0.0, min(t0, float(segs[a][0])))      # never after the first word (words that touch)
        t1 = min(dur, t1)
        x = (audio or {}).get(fi)
        if x is not None:                                # point 4: the cut goes into a real pause when one is close
            import transcribe
            lo = float(segs[a - 1][1]) + 0.02 if a > 0 else 0.0
            sp = transcribe.snap(x, t0, lo, float(segs[a][0]))
            if sp and not sp[0] <= t0 <= sp[1]:
                t0 = min(max(t0, sp[0] + 0.02), sp[1] - 0.02)
            hi = float(segs[b + 1][0]) - 0.02 if b + 1 < len(segs) else dur
            sp = transcribe.snap(x, t1, float(segs[b][1]), hi)
            if sp and not sp[0] <= t1 <= sp[1]:
                t1 = min(max(t1, sp[0] + 0.02), sp[1] - 0.02)
        cuts.append([fi, t0, t1, fixed or " ".join(str(x[2]) for x in segs[a:b + 1])])
    for fi in {c[0] for c in cuts}:
        mine = sorted((c for c in cuts if c[0] == fi), key=lambda c: c[1])
        for x, y in zip(mine, mine[1:]):
            if x[2] > y[1]:
                mid = (x[2] + y[1]) / 2
                x[2] = y[1] = mid
    return [tuple(c) for c in cuts]


def ranges(pieces, files, durs):
    return cut_times(pieces, files, durs)


LINKING = ("și ", "si ", "dar ", "așa că", "asa ca", "pentru că", "pentru ca", "and ", "but ", "so ")


def check_cuts(cuts, pieces, files, durs, fps=25.0):
    """Errors / warnings on the cuts themselves (owner's final spec, section 6)."""
    errors, warnings = [], []
    frames = {}
    for n, (fi, t0, t1, _) in enumerate(cuts, 1):
        f0, f1 = int(round(t0 * fps)), int(round(t1 * fps))
        if f1 <= f0:
            errors.append(f"Piece {n}: its length is 0.")
        if t1 > durs[fi] + 1.0 / fps:
            errors.append(f"Piece {n}: it ends after the end of {Path(files[fi]['path']).name}.")
        frames.setdefault(fi, []).append((f0, f1, n))
    for fi, lst in frames.items():
        lst.sort()
        for (a0, a1, n1), (b0, b1, n2) in zip(lst, lst[1:]):
            if a1 > b0:
                errors.append(f"Pieces {n1} and {n2} overlap ({a1 - b0} frames of the same file).")
    for k, f in enumerate(files):
        longs = [f"{LETTERS[k]}{i}" for i, sg in enumerate(f["segs"], 1) if sg[1] - sg[0] > 8.0]
        if longs:
            warnings.append(f"Transcript pieces longer than 8 s: {', '.join(longs[:8])}{' …' if len(longs) > 8 else ''}.")
    for n, p in enumerate(pieces):
        fi, a = p[0], p[1]
        t = str(files[fi]["segs"][a][2]).strip().lower()
        if t.startswith(LINKING) and a > 0:
            prev = pieces[n - 1] if n else None
            if not (prev and prev[0] == fi and prev[2] == a - 1):
                warnings.append(f"Piece {n + 1} ({LETTERS[fi]}{a + 1}) starts with a linking word without "
                                f"{LETTERS[fi]}{a} before it.")
    run = 1
    for n in range(1, len(pieces)):
        run = run + 1 if pieces[n][0] == pieces[n - 1][0] else 1
        if run == 4:
            warnings.append(f"The same speaker more than 3 times in a row (from piece {n - 2}).")
    return errors, warnings


def check_xml(xml_path):
    """Errors in the written XML: links (clip exists, trackindex, clipindex), pproTicks = in x ticks per frame, every
    file complete the first time it appears (document order)."""
    import xml.etree.ElementTree as ET
    errors = []
    seq = ET.parse(xml_path).getroot().find("sequence")
    fps = float(seq.findtext("rate/timebase") or 25)
    tpf = TICKS_PER_SEC // int(round(fps))
    where, seen = {}, set()
    for kind in ("video", "audio"):
        sect = seq.find("media").find(kind)
        for ti, t in enumerate(sect.findall("track") if sect is not None else [], 1):
            for ci, c in enumerate([c for c in t if c.tag in ("clipitem", "generatoritem")], 1):
                where[c.get("id")] = (kind, str(ti), str(ci))
                f = c.find("file")
                if f is not None and f.get("id"):
                    if f.get("id") not in seen and not len(f):
                        errors.append(f"{c.findtext('name')}: the file is not complete the first time it appears.")
                    seen.add(f.get("id"))
                if c.tag == "clipitem" and c.find("pproTicksIn") is not None:
                    if int(c.findtext("pproTicksIn")) != int(c.findtext("in")) * tpf:
                        errors.append(f"{c.findtext('name')}: pproTicksIn does not match in.")
    for c in seq.iter("clipitem"):
        for l in c.findall("link"):
            ref = l.findtext("linkclipref")
            if ref not in where:
                errors.append(f"A link points to a clip that does not exist ({ref}).")
            elif where[ref] != (l.findtext("mediatype"), l.findtext("trackindex"), l.findtext("clipindex")):
                errors.append(f"A link with a wrong track / clip index ({ref}).")
    return errors


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



# ---- the story from HIS sequence (owner's make_story_xml.py principle): the clips are copied EXACTLY from the sequence
# he exported from Premiere (multichannel FX6 description, exploded stereo tracks, lavalier, Color Matte...) and only
# times, ids and links change. Premiere is very sensitive to how a multichannel file is described: copying is the only
# way the sound comes out exactly as he laid it out (mic and lavalier on their own tracks).
TICKS_PER_SEC = 254016000000


def export_from_source(cuts, files, src_xml, out_path, name, labels=None):
    import copy
    import xml.etree.ElementTree as ET
    import xmlimport
    tree, seq, fps, groups = xmlimport.source_groups(src_xml)
    tpf = TICKS_PER_SEC // int(round(fps))
    media = seq.find("media")
    vtr = media.find("video").findall("track") if media.find("video") is not None else []
    atr = media.find("audio").findall("track") if media.find("audio") is not None else []
    full = {f.get("id"): f for f in seq.iter("file") if len(f)}

    def group_for(path, fin):
        cands = [g for g in groups if path in g["paths"]]
        for g in cands:                              # the segment whose source range holds this moment
            ref = g["paths"][path]
            if ref <= fin < ref + (g["key"][1] - g["key"][0]):
                return g
        return cands[0] if cands else None

    plan, pos = [], 0
    for fi, t0, t1, text in cuts:
        path = files[fi]["path"]
        fin, fout = int(round(t0 * fps)), int(round(t1 * fps))
        g = group_for(path, fin)
        if g is None or fout <= fin:
            raise ValueError(f"{Path(path).name} is not in the imported sequence")
        plan.append((g, path, fin, fout - fin, text, fi))
    for t in vtr + atr:                              # empty every track (keeps the track settings)
        for it in [c for c in t if c.tag in xmlimport.ITEM_TAGS + ("transitionitem",)]:
            t.remove(it)
    for m in seq.findall("marker"):
        seq.remove(m)
    written, n, markers = set(), 0, []
    for g, path, fin, dur, text, fi in plan:
        shift = fin - g["paths"][path]               # how far into the segment this cut starts
        idmap, clones = {}, []
        for kind, ti, it in g["items"]:
            c = copy.deepcopy(it)
            n += 1
            idmap[it.get("id")] = f"clipitem-{n}"
            c.set("id", f"clipitem-{n}")
            clones.append((kind, ti, it, c))
        for kind, ti, orig, c in clones:
            c.find("start").text = str(pos)
            c.find("end").text = str(pos + dur)
            oin = int(orig.findtext("in") or 0)
            nin = max(0, oin + shift) if c.tag != "generatoritem" else oin
            c.find("in").text = str(nin)
            c.find("out").text = str(nin + dur)
            if c.find("pproTicksIn") is not None:
                c.find("pproTicksIn").text = str(nin * tpf)
            if c.find("pproTicksOut") is not None:
                c.find("pproTicksOut").text = str((nin + dur) * tpf)
            f = c.find("file")
            if f is not None and f.get("id"):
                for ch in list(f):
                    f.remove(ch)
                if f.get("id") not in written and f.get("id") in full:
                    for ch in full[f.get("id")]:
                        f.append(copy.deepcopy(ch))
                    written.add(f.get("id"))
            for link in c.findall("link"):
                ref = link.findtext("linkclipref")
                if ref in idmap:
                    link.find("linkclipref").text = idmap[ref]
                else:
                    c.remove(link)
            dest = (vtr if kind == "video" else atr)[ti - 1]
            en = dest.find("enabled")
            dest.insert(list(dest).index(en) if en is not None else len(dest), c)
        lab = (labels or {}).get(fi)
        markers.append((pos, dur, (lab + ": " if lab else "") + text))
        pos += dur
    seen = set()                                     # in DOCUMENT order: the first <file> is complete, the rest id only
    for kind, trs in (("video", vtr), ("audio", atr)):
        for t in trs:
            for it in [c for c in t if c.tag in xmlimport.ITEM_TAGS]:
                f = it.find("file")
                if f is None or not f.get("id") or f.get("id") not in full:
                    continue
                for ch in list(f):
                    f.remove(ch)
                if f.get("id") not in seen:
                    for ch in full[f.get("id")]:
                        f.append(copy.deepcopy(ch))
                    seen.add(f.get("id"))
    where = {}                                       # clipindex = position in its track
    for kind, trs in (("video", vtr), ("audio", atr)):
        for ti, t in enumerate(trs, 1):
            for ci, it in enumerate([c for c in t if c.tag in xmlimport.ITEM_TAGS], 1):
                where[it.get("id")] = (kind, ti, ci)
    for link in seq.iter("link"):
        k, ti, ci = where[link.findtext("linkclipref")]
        (link.find("mediatype") if link.find("mediatype") is not None else ET.SubElement(link, "mediatype")).text = k
        (link.find("trackindex") if link.find("trackindex") is not None else ET.SubElement(link, "trackindex")).text = str(ti)
        (link.find("clipindex") if link.find("clipindex") is not None else ET.SubElement(link, "clipindex")).text = str(ci)
    rate = seq.find("rate")
    idx = list(seq).index(rate) + 1 if rate is not None else 0
    for k, (st, dur, txt) in enumerate(markers):
        m = ET.Element("marker")
        ET.SubElement(m, "name").text = txt[:60]
        ET.SubElement(m, "comment").text = txt
        ET.SubElement(m, "in").text = str(st)
        ET.SubElement(m, "out").text = str(st + dur)
        seq.insert(idx + k, m)
    if seq.find("duration") is not None:
        seq.find("duration").text = str(pos)
    if seq.find("name") is not None:
        seq.find("name").text = name
    u = seq.find("uuid")
    if u is not None:
        seq.remove(u)
    seq.set("id", "sequence-story")
    root = tree.getroot()
    if root.tag == "xmeml" and root.find("sequence") is not seq:  # a project export: keep only this sequence
        for ch in list(root):
            root.remove(ch)
        root.append(seq)
    with open(out_path, "wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
        tree.write(fh, encoding="utf-8", xml_declaration=False)
    return dict(pieces=len(plan), seconds=pos / fps)
