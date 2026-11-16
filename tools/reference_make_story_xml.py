#!/usr/bin/env python3
"""
make_story_xml.py — construieste secventa "POVESTE" pentru Premiere Pro dintr-o lista de taieturi.

PRINCIPIU: nu inventeaza nicio structura audio/video. Copiaza EXACT clipurile din secventa sursa
exportata de Premiere (File > Export > Final Cut Pro XML) si schimba doar timpii (start/end/in/out/ticks),
ID-urile si legaturile (link/clipindex). Asa, pistele audio (ex. FX6 cu 4 piste, lavaliera mono)
ies identic cu ce a pus editorul manual.

UTILIZARE:
    python3 make_story_xml.py SURSA.xml TAIETURI.json IESIRE.xml ["Nume secventa"]

SURSA.xml  = secventa exportata din Premiere care contine cate un segment pentru fiecare vorbitor
             (ex. interviul mirelui, apoi interviul miresei), cu audio-ul pus EXACT cum vrea editorul.
             Fiecare segment = grupul de clipuri (video + audio) care incep si se termina la acelasi timp.
TAIETURI.json = lista in ordinea filmului:
    {"fps": 25,
     "segments": {"MIRE": 1, "MIREASA": 2},          # numarul segmentului din SURSA (1 = primul in timeline)
     "cuts": [
        {"seg": "MIRE",    "in": 21.96, "out": 27.92, "text": "E 22 august ..."},
        {"seg": "MIREASA", "in": 3.88,  "out": 16.16, "text": "Foarte emotionata ..."}
     ]}
    "in"/"out" = secunde in fisierul media sursa (timpii din transcrierea acelui fisier).
"""
import sys, json, copy
import xml.etree.ElementTree as ET

TICKS_PER_SEC = 254016000000  # Premiere ticks


def load(path):
    tree = ET.parse(path)
    return tree, tree.getroot().find("sequence")


def items_of(track):
    return [c for c in track if c.tag in ("clipitem", "generatoritem")]


def main():
    src_path, cuts_path, out_path = sys.argv[1:4]
    seq_name = sys.argv[4] if len(sys.argv) > 4 else "POVESTE"
    spec = json.load(open(cuts_path, encoding="utf-8"))
    fps = spec.get("fps", 25)
    tpf = TICKS_PER_SEC // fps

    tree, seq = load(src_path)
    media = seq.find("media")
    vtracks = media.find("video").findall("track")
    atracks = media.find("audio").findall("track")
    alltracks = [("video", i + 1, t) for i, t in enumerate(vtracks)] + [("audio", i + 1, t) for i, t in enumerate(atracks)]

    # --- 1. Grupeaza clipurile sursa in segmente (acelasi start/end) ---
    groups = {}
    for kind, ti, t in alltracks:
        for it in items_of(t):
            key = (int(it.find("start").text), int(it.find("end").text))
            groups.setdefault(key, []).append((kind, ti, it))
    seg_keys = sorted(groups)  # in ordinea din timeline
    print("Segmente gasite in sursa:")
    for n, k in enumerate(seg_keys, 1):
        names = sorted({it.findtext("name") for _, _, it in groups[k]})
        print(f"  {n}: start={k[0]} end={k[1]}  {names}")

    # definitia completa <file> pentru fiecare id (unele clipuri au doar <file id=".."/>)
    full_files = {}
    for f in seq.iter("file"):
        if len(f):
            full_files[f.get("id")] = f

    # --- 2. Goleste pistele si construieste clipurile noi ---
    for _, _, t in alltracks:
        for it in items_of(t):
            t.remove(it)

    written_files = set()
    counter = [0]
    pos = 0
    for cut in spec["cuts"]:
        seg_no = spec["segments"][cut["seg"]]
        key = seg_keys[seg_no - 1]
        seg_start = key[0]
        fin = round(cut["in"] * fps)
        fout = round(cut["out"] * fps)
        dur = fout - fin
        # clone + id-uri noi
        clones = []
        idmap = {}
        for kind, ti, it in groups[key]:
            c = copy.deepcopy(it)
            counter[0] += 1
            new_id = f"clipitem-{counter[0]}"
            idmap[it.get("id")] = new_id
            c.set("id", new_id)
            clones.append((kind, ti, it, c))
        for kind, ti, orig, c in clones:
            c.find("start").text = str(pos)
            c.find("end").text = str(pos + dur)
            if c.tag == "generatoritem":
                # generator (ex. Color Matte): pastreaza offset-ul intern
                gin = int(orig.find("in").text)
                c.find("in").text = str(gin)
                c.find("out").text = str(gin + dur)
            else:
                c.find("in").text = str(fin)
                c.find("out").text = str(fout)
                if c.find("pproTicksIn") is not None:
                    c.find("pproTicksIn").text = str(fin * tpf)
                    c.find("pproTicksOut").text = str(fout * tpf)
                f = c.find("file")
                if f is not None:
                    fid = f.get("id")
                    # prima aparitie a fisierului trebuie sa aiba definitia completa
                    for ch in list(f):
                        f.remove(ch)
                    if fid not in written_files:
                        for ch in full_files[fid]:
                            f.append(copy.deepcopy(ch))
                        written_files.add(fid)
            # actualizeaza legaturile catre clonele noi (clipindex se fixeaza la final)
            for link in c.findall("link"):
                ref = link.find("linkclipref").text
                if ref in idmap:
                    link.find("linkclipref").text = idmap[ref]
                else:
                    c.remove(link)  # link catre ceva ce nu e in segment
            dest = (vtracks if kind == "video" else atracks)[ti - 1]
            # insereaza inainte de <enabled>
            idx = list(dest).index(dest.find("enabled")) if dest.find("enabled") is not None else len(dest)
            dest.insert(idx, c)
        pos += dur

    # --- 3. clipindex corect pentru fiecare link ---
    where = {}
    for kind, ti, t in alltracks:
        for ci, it in enumerate(items_of(t), 1):
            where[it.get("id")] = (kind, ti, ci)
    for link in seq.iter("link"):
        k, ti, ci = where[link.find("linkclipref").text]
        link.find("mediatype").text = k
        link.find("trackindex").text = str(ti)
        ci_el = link.find("clipindex")
        if ci_el is None:
            ci_el = ET.SubElement(link, "clipindex")
        ci_el.text = str(ci)

    seq.find("duration").text = str(pos)
    seq.find("name").text = seq_name
    u = seq.find("uuid")
    if u is not None:
        seq.remove(u)
    seq.set("id", "sequence-poveste")
    with open(out_path, "wb") as fh:
        fh.write(b'<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE xmeml>\n')
        tree.write(fh, encoding="utf-8", xml_declaration=False)
    print(f"OK: {out_path}  ({len(spec['cuts'])} taieturi, {pos} frame-uri = {pos / fps:.1f}s)")


if __name__ == "__main__":
    main()
