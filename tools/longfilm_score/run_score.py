import os
import sys, importlib; import os; sys.path.insert(0,os.path.dirname(os.path.abspath(__file__))); sys.path.insert(0,os.path.join(os.path.dirname(os.path.abspath(__file__)),"..",".."))
from score import CASES, his, score, show
import teaser, longfilm
importlib.reload(longfilm)
for sf,ff,secs in CASES:
    ref=his(sf,ff,secs)
    p,_=teaser.load_footage(os.environ.get("MMM_PAIRS","/mnt/user-data/uploads")+"/"+sf)
    trs,lay=longfilm.build_film(p)
    show(f"v4 on {ff}", score(lay, ref))
