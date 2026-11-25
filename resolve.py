"""The same XML, made for DaVinci Resolve (File > Import > Timeline).

Every exporter of the app writes the xmeml Premiere reads; convert() turns that file into the one Resolve reads well:
- Basic Motion "scale to fill" is removed: Resolve already fits every clip to the timeline (Project Settings > Image
  Scaling, default "Scale entire image to fit"); with the Premiere scale on top a 4K clip came out at a quarter size.
- Lumetri (Premiere's colour effect) is removed: Resolve cannot read it (apply the LUT in Resolve's Color page).
- A Premiere PROJECT (bins + master clips, Create Project) becomes its sequence alone: Resolve's Import Timeline wants
  a sequence; every <file> is written in full where the sequence first uses it, master clip references are dropped
  (Resolve puts every clip in the Media Pool by itself).
Nothing else changes: clip names = file names (Resolve links media by name), times, tracks, links, markers, the
sound channels, disabled clips and the label colours stay exactly as in the Premiere file.
"""
import copy
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'


def _drop_filters(root):
    n = dict(scale=0, colour=0)
    for parent in root.iter():
        for f in list(parent.findall("filter")):
            eff = f.find("effect")
            eid = (eff.findtext("effectid") or "") if eff is not None else ""
            name = (eff.findtext("name") or "") if eff is not None else ""
            # the colour of the Long Film v2 card (LUT + crop) is Premiere only: in Resolve it goes on the Color page
            if eid in ("basic", "crop") or "lumetri" in eid.lower() or "lumetri" in name.lower():
                parent.remove(f)
                n["scale" if eid == "basic" else "colour"] += 1
    return n


def _unwrap(root):
    """<xmeml><project>... bins ... <sequence>  ->  <xmeml><sequence> with every file complete at its first use."""
    if root.find("project") is None:
        return root
    full = {}
    for f in root.iter("file"):
        if f.get("id") and len(f) and f.get("id") not in full:
            full[f.get("id")] = f
    seqs = [s for s in root.iter("sequence")]
    new = ET.Element("xmeml", root.attrib)
    for s in seqs:
        s = copy.deepcopy(s)
        seen = set()
        for parent in s.iter():
            for m in list(parent.findall("masterclipid")):
                parent.remove(m)
        for f in s.iter("file"):
            i = f.get("id")
            if not i:
                continue
            if i not in seen:
                seen.add(i)
                if not len(f) and i in full:
                    for c in full[i]:
                        f.append(copy.deepcopy(c))
        new.append(s)
    return new


def _path(url):
    p = urllib.parse.unquote(url or "")
    for pre in ("file://localhost", "file://"):
        if p.startswith(pre):
            p = p[len(pre):]
            break
    if len(p) > 2 and p[0] == "/" and p[2] == ":":          # file://localhost/C:/... on Windows
        p = p[1:]
    return p


def _fix_names(root):
    """Resolve links a timeline clip to its media by NAME: every clipitem is named exactly like its file."""
    names, n = {}, 0
    for f in root.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            names[f.get("id")] = Path(_path(f.findtext("pathurl"))).name
    for c in root.iter("clipitem"):
        f = c.find("file")
        want = names.get(f.get("id")) if f is not None else None
        nm = c.find("name")
        if want and nm is not None and nm.text != want:
            nm.text = want
            n += 1
    return n


def verify(path, progress=None, cancel=lambda: False):
    """Everything Resolve needs, checked on the written file. -> dict(errors, warnings, clips, files, missing)."""
    import story
    say = progress or (lambda t, f: None)
    errors, warnings = [], []
    say("Reading the XML…", 0.02)
    root = ET.parse(path).getroot()
    seqs = root.findall("sequence")
    if len(seqs) != 1:
        errors.append("The file must hold exactly one sequence (it has {}).".format(len(seqs)))
        return dict(errors=errors, warnings=warnings, clips=0, files=0, missing=[])
    seq = seqs[0]
    if not seq.findtext("rate/timebase"):
        errors.append("The sequence has no frame rate.")
    say("Checking links and clips…", 0.08)
    errors += story.check_xml(path)
    files = {}
    for f in seq.iter("file"):
        i = f.get("id")
        if i and len(f) and i not in files:
            files[i] = dict(path=_path(f.findtext("pathurl")), dur=int(f.findtext("duration") or 0),
                            name=Path(_path(f.findtext("pathurl"))).name)
    clips = list(seq.iter("clipitem"))
    left = sum(1 for p in seq.iter() for f in p.findall("filter")
               if (f.findtext("effect/effectid") or "") in ("basic", "crop") or "umetri" in (f.findtext("effect/effectid") or ""))
    if left:
        errors.append(f"{left} Premiere-only effects are still in the file.")
    bad_name = bad_range = 0
    for k, c in enumerate(clips):
        if cancel():
            raise RuntimeError("Cancelled")
        if k % 200 == 0:
            say("Checking clips: {} of {}".format(k, len(clips)), 0.1 + 0.4 * k / max(1, len(clips)))
        f = c.find("file")
        fi = files.get(f.get("id")) if f is not None else None
        if fi is None:
            continue
        if c.findtext("name") != fi["name"]:
            bad_name += 1
        try:
            i0, i1 = int(c.findtext("in")), int(c.findtext("out"))
            st, en = int(c.findtext("start")), int(c.findtext("end"))
        except (TypeError, ValueError):
            continue
        if i1 <= i0 or (st >= 0 and en >= 0 and en - st != i1 - i0):
            bad_range += 1
        sfps = float(c.findtext("rate/timebase") or 25)
        ffps = float(f.findtext("rate/timebase") or 0) if f is not None and len(f) else 0
        if fi["dur"] and ffps:
            if i1 > fi["dur"] * sfps / ffps + 2:
                bad_range += 1
    if bad_name:
        errors.append(f"{bad_name} clips are not named like their file (Resolve would show them offline).")
    if bad_range:
        errors.append(f"{bad_range} clips have a wrong in / out (outside the file or a length that does not match).")
    missing = []
    for k, fi in enumerate(files.values()):
        if cancel():
            raise RuntimeError("Cancelled")
        if k % 50 == 0:
            say("Looking for the files on this computer: {} of {}".format(k, len(files)), 0.5 + 0.45 * k / max(1, len(files)))
        if fi["path"] and not Path(fi["path"]).exists():
            missing.append(fi["name"])
    if missing:
        warnings.append("{} files are not on this computer right now (connect the disk before importing): {}".format(
            len(missing), ", ".join(missing[:5]) + (" …" if len(missing) > 5 else "")))
    say("Done", 1.0)
    return dict(errors=errors, warnings=warnings, clips=len(clips), files=len(files), missing=missing)


def convert(src, out=None):
    """Writes the DaVinci Resolve version of the xmeml `src` to `out` (default: in place). Returns a short summary."""
    out = out or src
    tree = ET.parse(src)
    root = tree.getroot()
    was_project = root.find("project") is not None
    root = _unwrap(root)
    n = _drop_filters(root)
    renamed = _fix_names(root)
    body = ET.tostring(root, encoding="unicode")
    Path(out).write_text(HEAD + body, encoding="utf-8")
    return dict(filters_removed=n["scale"] + n["colour"], scale_removed=n["scale"], colour_removed=n["colour"],
                project_unwrapped=was_project, renamed=renamed)


def make(src, out=None, progress=None, cancel=lambda: False):
    """The DaVinci export: convert, then verify the written file. -> convert summary + verify result."""
    say = progress or (lambda t, f: None)
    say("Making the DaVinci Resolve version…", 0.0)
    r = convert(src, out)
    v = verify(out or src, lambda t, f: say(t, 0.1 + 0.9 * f), cancel)
    r.update(v)
    return r


def name_for(path, target):
    """'Wedding.xml' -> 'Wedding (DaVinci).xml' for the Resolve file, unchanged for Premiere."""
    p = Path(path)
    if target != "davinci" or p.stem.endswith("(DaVinci)"):
        return str(p)
    return str(p.with_name(f"{p.stem} (DaVinci){p.suffix}"))


def how(target):
    return "DaVinci Resolve: File > Import > Timeline" if target == "davinci" else "Premiere Pro: File > Import"
