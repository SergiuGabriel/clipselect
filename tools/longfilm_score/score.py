import os
"""Score the app's Long Film against HIS finished film, part by part (selection level)."""
import sys, collections; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),"..",".."))
from parse import load, visible; from match import match
CASES=[("selectie_madalina_si_radu.xml","Madalina_si_Radu_-_The_Movie.xml",
        [("Getting ready",56.5,214),("Vornic and first look",214,1120),("Church",1120,1710),("Couple and venue",1710,1800)]),
       ("selectie_4_iulie_de_test.xml","Alexandra_si_Vlad_-_The_Movie.xml",
        [("Getting ready",55,205),("Vornic and first look",205,290),("Church",290,630),("Couple and venue",630,740)])]
def key(file, a): return (file, round(a, 1))
def his(sf, ff, secs):
    S=load(os.environ.get("MMM_PAIRS","/mnt/user-data/uploads")+"/"+sf); F=load(os.environ.get("MMM_PAIRS","/mnt/user-data/uploads")+"/"+ff)
    sel=sorted([c for c in S["clips"] if (c["t1"]-c["t0"])<3600], key=lambda c:(c["t0"],c["track"]))
    m=match([s for s in visible(F) if s[2]["label"] not in ("Tan","Lavender")], sel)
    out={}
    for name,a,b in secs:
        seq=[]
        for t0,t1,c,bb in m:
            if a<=t0<b:
                k=key(bb[1]["file"], bb[1]["a"])
                if not seq or seq[-1]!=k: seq.append(k)
        out[name]=dict(seq=seq, dur=b-a, shots=sum(1 for t0,*_ in m if a<=t0<b),
                       labels=[c["label"] for t0,t1,c,bb in m if a<=t0<b])
    return out
def blocks(labels):
    """groom / bride blocks of a getting ready: (first two, median of the rest)"""
    import itertools
    runs=[len(list(g)) for k,g in itertools.groupby(l for l in labels if l in ("groom","bride","Blue","Rose"))]
    rest=sorted(runs[2:]); return runs[:2], (rest[len(rest)//2] if rest else 0), len(runs)
def kendall(order_a, order_b):
    common=[k for k in order_a if k in set(order_b)]
    pos={k:i for i,k in enumerate(dict.fromkeys(order_b))}
    c=list(dict.fromkeys(common)); ok=tot=0
    for i in range(len(c)):
        for j in range(i+1,min(len(c),i+25)):
            tot+=1; ok+= pos[c[i]]<pos[c[j]]
    return ok/tot if tot else 1.0
def score(app_layout, ref, name_map=None):
    """app_layout: [(part, length, items)], items (track, t0, piece, a, b). Returns per-part metrics."""
    import pathlib
    res={}
    for part, length, items in app_layout:
        nm=(name_map or {}).get(part, part)
        if nm not in ref: continue
        seq=[]
        for tr,t0,p,a,b in sorted(items, key=lambda x:(x[1],x[0])):
            k=key(pathlib.Path(p["path"]).name, p["a"])
            if not seq or seq[-1]!=k: seq.append(k)
        A=set(seq); H=set(ref[nm]["seq"])
        inter=len(A&H)
        bl=None
        if nm=="Getting ready":
            bl=(blocks([p["cat"] for tr,t0,p,a,b in sorted(items,key=lambda x:x[1]) if tr==1]), blocks(ref[nm]["labels"]))
        res[nm]=dict(blocks=bl, found=inter/max(1,len(H)), right=inter/max(1,len(A)), order=kendall(seq, ref[nm]["seq"]),
                     dur=length/ref[nm]["dur"], app_n=len(A), his_n=len(H), app_min=length/60, his_min=ref[nm]["dur"]/60)
    return res
def show(title, res):
    print(f"  {title}")
    for k,v in res.items():
        print(f"    {k:22} found {v['found']:4.0%} right {v['right']:4.0%} order {v['order']:4.0%} | length {v['app_min']:5.1f} vs his {v['his_min']:5.1f} min | selections {v['app_n']} vs {v['his_n']}")
        if v.get("blocks"):
            (af,am,an),(hf,hm,hn)=v["blocks"]
            print(f"    {'':22} blocks: first two {af} vs his {hf} | usual block {am} vs his {hm} | number of blocks {an} vs his {hn}")
