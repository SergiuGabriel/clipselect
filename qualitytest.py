"""Quality test on several weddings (owner: "a change is good only if it breaks nothing on the others").

A test folder (e.g. teste/) holds one sub-folder per wedding: its interview sound / video files and, optionally, the
source XML of the interviews (Premiere export). Nothing about a wedding is written in the code: the files come from
the XML (xmlimport.interviews) or, without one, from every sound / video file of the folder; the couple's names come
from the folder name (transcribe.couple_names) like everywhere else.

For every wedding: every interview is transcribed with the app's own engine, then MEASURED:
  codes over 8 s / under 0.8 s, codes with a '?' inside, % of code borders in a real pause of the sound;
  a test story (every code that is not a question, alternating the interviews) -> cuts (story.cut_times with the
  sound) -> % of cut in / out points in a real pause, overlaps (story.check_cuts) -> the XML (copied from the source
  XML when there is one, like the app) -> story.check_xml errors.
The numbers of every version are kept in <test folder>/rezultate.json; compare() says which got worse than the
previous version.
"""
import json
import os
import tempfile
import time
from pathlib import Path

import core
import story
import transcribe
import xmlimport

MEDIA = tuple(xmlimport.AUDIO_EXT) + tuple(core.VIDEO_EXT)
# metric -> (label, True when a HIGHER number is better)
METRICS = {
    "codes": ("Codes", None),
    "over8": ("Over 8 s", False),
    "under08": ("Under 0.8 s", False),
    "glued": ("'?' inside", False),
    "forced": ("Forced cuts", False),
    "vid": ("[QUESTION] from the sound", None),
    "unsure": ("Unsure who speaks", False),
    "border_pct": ("Borders in a pause %", True),
    "cut_pct": ("Cuts in a pause %", True),
    "overlaps": ("Overlaps", False),
    "xml_errors": ("XML errors", False),
}


def fails(key, val):
    """True when a number misses its target: 0 codes over 8 s, 0 '?' inside, 0 overlaps / XML errors, >= 95 % in a pause."""
    if val is None:
        return False
    if key in ("border_pct", "cut_pct"):
        return val < 95
    return key in ("over8", "glued", "overlaps", "xml_errors") and val > 0


def projects(folder):
    """The weddings of the test folder: [(name, [interview files], source xml or None)]."""
    out = []
    for d in sorted(p for p in Path(folder).iterdir() if p.is_dir() and not p.name.startswith(".")):
        xmls = sorted(p for p in d.glob("*.xml") if not p.name.startswith(".") and "STORY" not in p.name.upper()
                      and not p.name.endswith(".checking"))
        files, src = [], None
        for x in xmls:
            try:
                found, _missing = xmlimport.interviews(str(x))
            except Exception:
                continue
            if found:
                files, src = list(found), str(x)
                break
        if not files:
            files = sorted(str(p) for p in d.rglob("*") if p.is_file() and p.suffix.lower() in MEDIA
                           and not p.name.startswith("."))
        if files:
            out.append((d.name, files, src))
    return out


def _pct(good, n):
    return round(100.0 * good / n, 1) if n else None


def run_project(name, files, src, model, lang, progress=None, stop=None, tr=lambda t: t):
    """Transcribe and measure one wedding -> (metrics dict, report text)."""
    lines, segs_all, audio, qs = [f"== {name}"], [], {}, []
    for k, path in enumerate(files):
        if stop and stop():
            raise InterruptedError("Cancelled")
        keep = {}
        segs = transcribe.transcribe(path, model, lang, (lambda t, f, k=k: progress(f"{name} · {t}", (k + f) / len(files)))
                                     if progress else None, stop, keep=keep)
        x = keep.get(path)
        audio[k] = x
        q = transcribe.quality(segs, x, story.LETTERS[k])
        qs.append(q)
        segs_all.append(dict(path=path, segs=[list(s) for s in segs], spk=list(getattr(segs, "spk", None) or [])))
        lines.append(transcribe.quality_text(Path(path).name, q, tr).rstrip())
    m = dict(codes=sum(q["codes"] for q in qs), over8=sum(len(q["over8"]) for q in qs),
             under08=sum(len(q["under08"]) for q in qs), glued=sum(len(q["glued"]) for q in qs),
             forced=sum(len(q.get("forced", [])) for q in qs), vid=sum(len(q.get("vid", [])) for q in qs),
             unsure=sum(len(q.get("unsure", [])) for q in qs))
    nb = sum(q["borders"] for q in qs)
    m["border_pct"] = _pct(nb - sum(len(q["in_speech"]) for q in qs), nb)
    # a test story: every code that is not a question, alternating the interviews
    queues = [[(k, i, i) for i, q in enumerate(story.qflags(f)) if not q] for k, f in enumerate(segs_all)]
    pieces = []
    while any(queues):
        for qu in queues:
            if qu:
                pieces.append(qu.pop(0))
    durs = []
    for k, f in enumerate(segs_all):
        x = audio.get(k)
        durs.append(len(x) / transcribe.SR if x is not None else max([s[1] for s in f["segs"]] + [0.0]) + 1.0)
    cuts = story.cut_times(pieces, segs_all, durs, audio=audio) if pieces else []
    errs, _w = story.check_cuts(cuts, pieces, segs_all, durs) if cuts else ([], [])
    m["overlaps"] = sum(1 for e in errs if "overlap" in e)
    n = good = 0
    bad = []
    for j, (fi, t0, t1, _) in enumerate(cuts, 1):
        for label, t in (("in", t0), ("out", t1)):
            r = transcribe.in_pause(audio.get(fi), t)
            if r is None:
                continue
            n += 1
            good += bool(r)
            if not r:
                bad.append(f"{j} {label} ({transcribe._at(t)})")
    m["cut_pct"] = _pct(good, n)
    xml_err = []
    if cuts:
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "test.xml")
            try:
                if src:
                    story.export_from_source(cuts, segs_all, src, out, "TEST")
                else:
                    import projectsetup
                    infos = {f["path"]: projectsetup.probe(f["path"]) for f in segs_all}
                    story.export_xml(cuts, segs_all, infos, out, "TEST")
                xml_err = story.check_xml(out)
            except Exception as e:
                xml_err = [f"the XML could not be made: {e}"]
    m["xml_errors"] = len(xml_err)
    lines.append(tr("Test story: {} cuts, in / out in a real pause: {}").format(
        len(cuts), "—" if m["cut_pct"] is None else f"{m['cut_pct']:g} %") +
        ("; " + tr("in speech: {}").format(", ".join(bad[:30])) if bad else ""))
    lines += [f"XML: {tr(e)}" for e in xml_err + list(errs)] or ["XML: OK"]
    return m, "\n".join(lines) + "\n"


def run_all(folder, model, lang, version, progress=None, stop=None, tr=lambda t: t):
    """Every wedding of the test folder -> (results {name: metrics}, report text, worse list). Saved per version."""
    t0 = time.time()
    res, texts = {}, []
    plist = projects(folder)
    for n, (name, files, src) in enumerate(plist):
        sub = (lambda t, f, n=n: progress(t, (n + f) / len(plist))) if progress else None
        try:
            res[name], txt = run_project(name, files, src, model, lang, sub, stop, tr)
        except InterruptedError:
            raise
        except Exception as e:
            res[name], txt = dict(error=str(e)), f"== {name}\n" + tr("FAILED: {}").format(e) + "\n"
        texts.append(txt)
    path = Path(folder) / "rezultate.json"
    try:
        hist = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        hist = {}
    prev_ver = next((v for v in reversed(list(hist)) if v != version), None)
    hist.pop(version, None)
    hist[version] = res
    path.write_text(json.dumps(hist, indent=1, ensure_ascii=False), encoding="utf-8")
    worse = compare(hist.get(prev_ver, {}), res, tr) if prev_ver else []
    text = (tr("Test on {} weddings · {} · {} s").format(len(plist), version, int(time.time() - t0))
            + (" · " + tr("compared with {}").format(prev_ver) if prev_ver else " · " + tr("first run (nothing to compare with)"))
            + "\n\n"
            + "\n".join(texts))
    (Path(folder) / f"rezultate_{version}.txt").write_text(text + ("\n" + tr("WORSE than {}:").format(prev_ver) + "\n" + "\n".join(worse) if worse else ""),
                                                            encoding="utf-8")
    return res, text, worse, prev_ver, hist.get(prev_ver, {}) if prev_ver else {}


def compare(old, new, tr=lambda t: t):
    """['wedding: metric 96.0 -> 91.5', ...] for every number that got worse than in the previous version."""
    out = []
    for name, m in new.items():
        o = old.get(name)
        if not o or "error" in m or "error" in o:
            if o and "error" in m and "error" not in o:
                out.append(f"{name}: " + tr("failed") + f" ({m['error']})")
            continue
        for key, (label, higher) in METRICS.items():
            if higher is None or m.get(key) is None or o.get(key) is None:
                continue
            a, b = o[key], m[key]
            if (higher and b < a - 0.5) or (not higher and b > a):
                out.append(f"{name}: {tr(label)} {a:g} -> {b:g}")
    return out
