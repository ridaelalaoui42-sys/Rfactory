"""Generate timestamp-accurate SRT captions from ClipForge cut ranges."""
from __future__ import annotations
import re
from . import storage

def timestamp(seconds: float) -> str:
    ms=round(max(0,seconds)*1000)
    hour,rem=divmod(ms,3600000)
    minute,rem=divmod(rem,60000)
    second,millisecond=divmod(rem,1000)
    return f"{hour:02d}:{minute:02d}:{second:02d},{millisecond:03d}"

def caption_entries(source_id:int,ranges):
    with storage.connect() as db:
        rows=[dict(x) for x in db.execute(
           "SELECT start,end,text FROM transcripts WHERE source_id=? ORDER BY start",(source_id,))]
    entries=[];out_offset=0.0
    for selected in ranges:
        for cue in rows:
            beg=max(cue["start"],selected.start)
            end=min(cue["end"],selected.end)
            if end-beg < 0.05:continue
            content=re.sub(r"\s+"," ",cue["text"]).strip()
            if not content:continue
            entries.append((out_offset+(beg-selected.start),
                            out_offset+(end-selected.start),content[:240]))
        out_offset+=selected.end-selected.start
    return entries

def srt(source_id:int,ranges)->str:
    rows=caption_entries(source_id,ranges)
    output=[]
    for i,(start,end,text) in enumerate(rows,1):
        output.append(f"{i}\n{timestamp(start)} --> {timestamp(end)}\n{text}\n")
    return "\n".join(output)+("\n" if output else "")
