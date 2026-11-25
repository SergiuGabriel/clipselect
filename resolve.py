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
import xml.etree.ElementTree as ET
from pathlib import Path

HEAD = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n'


def _drop_filters(root):
    n = 0
    for parent in root.iter():
        for f in list(parent.findall("filter")):
            eff = f.find("effect")
            eid = (eff.findtext("effectid") or "") if eff is not None else ""
            name = (eff.findtext("name") or "") if eff is not None else ""
            if eid == "basic" or "lumetri" in eid.lower() or "lumetri" in name.lower():
                parent.remove(f)
                n += 1
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


def convert(src, out=None):
    """Writes the DaVinci Resolve version of the xmeml `src` to `out` (default: in place). Returns a short summary."""
    out = out or src
    tree = ET.parse(src)
    root = tree.getroot()
    was_project = root.find("project") is not None
    root = _unwrap(root)
    n = _drop_filters(root)
    body = ET.tostring(root, encoding="unicode")
    Path(out).write_text(HEAD + body, encoding="utf-8")
    return dict(filters_removed=n, project_unwrapped=was_project)


def name_for(path, target):
    """'Wedding.xml' -> 'Wedding (DaVinci).xml' for the Resolve file, unchanged for Premiere."""
    p = Path(path)
    if target != "davinci" or p.stem.endswith("(DaVinci)"):
        return str(p)
    return str(p.with_name(f"{p.stem} (DaVinci){p.suffix}"))


def how(target):
    return "DaVinci Resolve: File > Import > Timeline" if target == "davinci" else "Premiere Pro: File > Import"
