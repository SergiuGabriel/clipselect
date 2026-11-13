import xml.etree.ElementTree as ET, re, urllib.parse, collections
def n_(v, d=0):
    try: return int(round(float(v)))
    except: return d
def rate(el, d=25.0):
    tb=el.findtext("rate/timebase") if el is not None else None
    if not tb: return d
    return float(tb)*1000/1001 if (el.findtext("rate/ntsc") or "").upper()=="TRUE" else float(tb)
def load(path):
    r=ET.parse(path).getroot()
    seqs=list(r.iter("sequence")); seq=max(seqs,key=lambda s: sum(1 for _ in s.iter("clipitem")))
    fps=rate(seq)
    files={}
    for f in r.iter("file"):
        if f.get("id") and f.findtext("pathurl"):
            p=urllib.parse.unquote(f.findtext("pathurl")).replace("file://localhost","")
            files[f.get("id")]=dict(path=p, name=f.findtext("name"), fps=rate(f,fps), dur=n_(f.findtext("duration")))
    clips=[]; nests=0
    vid=seq.find("media/video")
    for ti,tr in enumerate(vid.findall("track") if vid is not None else [],1):
        en_tr=(tr.findtext("enabled") or "TRUE").upper()!="FALSE"
        for c in tr.findall("clipitem"):
            if c.find("sequence") is not None: nests+=1; continue
            f=c.find("file"); info=files.get(f.get("id")) if f is not None else None
            if not info: continue
            cf=rate(c,fps)
            st,en=n_(c.findtext("start"),-1),n_(c.findtext("end"),-1)
            ci,co=n_(c.findtext("in")),n_(c.findtext("out"))
            ln=round((co-ci)/cf*fps)
            if st<0 and en>=0: st=en-ln
            if en<0 and st>=0: en=st+ln
            if st<0: continue
            clips.append(dict(track=ti, t0=st/fps, t1=en/fps, a=ci/cf, b=co/cf, label=c.findtext("labels/label2") or "",
                              file=info["name"], path=info["path"], cam=info["path"].split("/")[-2] if "/" in info["path"] else "?",
                              enabled=en_tr and (c.findtext("enabled") or "TRUE").upper()!="FALSE"))
    return dict(name=seq.findtext("name"), fps=fps, dur=n_(seq.findtext("duration"))/fps, clips=clips, nests=nests,
                markers=[(m.findtext("name"), n_(m.findtext("in"))/fps) for m in seq.findall("marker")])
def visible(d, step=0.5):
    """the shot seen at every moment: top enabled track"""
    cl=[c for c in d["clips"] if c["enabled"] and (c["t1"]-c["t0"])<3600]
    edges=sorted({x for c in cl for x in (c["t0"],c["t1"])})
    shots=[]
    import bisect
    for a,b in zip(edges,edges[1:]):
        m=(a+b)/2; on=[c for c in cl if c["t0"]<=m<c["t1"]]
        if not on: continue
        top=max(on,key=lambda c:c["track"])
        if shots and shots[-1][2] is top: shots[-1][1]=b
        else: shots.append([a,b,top])
    return shots
