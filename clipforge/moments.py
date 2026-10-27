"""Transparent, non-ML ranking of self-contained transcript moments."""
import re
from . import storage

HOOKS=("why","how","because","mistake","secret","علاش","كيفاش","واش","خطأ","سر","pourquoi","comment")

def score(text,seconds):
    t=text.casefold().strip()
    points=25
    reasons=[]
    if any(k in t for k in HOOKS):
        points+=18;reasons.append("hook")
    if re.search(r"\d",t):
        points+=8;reasons.append("specificity")
    if "?" in t or "؟" in t:
        points+=7;reasons.append("question")
    words=len(t.split())
    if 20<=words<=160: points+=18;reasons.append("context")
    if t.endswith((".","!","?","؟")):points+=10;reasons.append("complete")
    if seconds<12 or seconds>95:points-=18
    if words<10:points-=20
    return max(0,min(100,points)),reasons

def candidates(source_id,max_duration=60,limit=10):
    if not storage.source(source_id): raise ValueError("Source not found")
    if not 8<=max_duration<=600:raise ValueError("max_duration outside 8-600s")
    with storage.connect() as db:
        rows=[dict(r) for r in db.execute("SELECT start,end,text FROM transcripts WHERE source_id=? ORDER BY start",(source_id,))]
    choices=[]
    for start_i,first in enumerate(rows):
        chunks=[];start=first["start"];last_end=start
        for current in rows[start_i:]:
            if current["start"]-last_end>4:break
            if current["end"]-start>max_duration:break
            chunks.append(current["text"]);last_end=current["end"]
            if last_end-start>=min(15,max_duration):
                text=" ".join(chunks);rating,reasons=score(text,last_end-start)
                choices.append({"source_id":source_id,"start":start,"end":last_end,
                    "score":rating,"reasons":reasons,"text":text})
    choices.sort(key=lambda x:(-x["score"],-(x["end"]-x["start"])))
    selected=[]
    for candidate in choices:
        if all(max(0,min(candidate["end"],x["end"])-max(candidate["start"],x["start"])) <
               0.35*min(candidate["end"]-candidate["start"],x["end"]-x["start"]) for x in selected):
            selected.append(candidate)
            if len(selected)>=min(50,max(1,limit)):break
    return selected
