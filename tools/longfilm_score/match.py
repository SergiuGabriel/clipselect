import sys, collections; sys.path.insert(0,"/tmp/pair"); from parse import load, visible
def sections(sh):
    """name every visible shot by section, from the structure seen: teaser / getting ready / first look / church / venue+couple"""
    return sh
def match(final, sel):
    """every final shot -> the selection it came from (same file, overlapping source range)"""
    by={}
    for i,s in enumerate(sel):
        by.setdefault(s["file"],[]).append((i,s))
    out=[]
    for t0,t1,c in final:
        best=None; bo=0
        for i,s in by.get(c["file"],[]):
            o=min(c["b"],s["b"])-max(c["a"],s["a"])
            if o>bo: bo,best=o,(i,s)
        out.append((t0,t1,c,best))
    return out
