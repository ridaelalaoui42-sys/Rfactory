"""Public metadata discovery; transcript input must come from authorized sources."""
import os,json
from urllib.parse import urlencode
from urllib.request import urlopen
from .core import TranscriptItem

def youtube_search(query:str,max_results:int=10,api_key:str|None=None):
    key=api_key or os.getenv("YOUTUBE_API_KEY")
    if not key:raise ValueError("Set YOUTUBE_API_KEY")
    if not query.strip():raise ValueError("Empty search query")
    qs=urlencode({"part":"snippet","type":"video","q":query,
                  "maxResults":min(max(max_results,1),50),"key":key})
    with urlopen("https://www.googleapis.com/youtube/v3/search?"+qs,timeout=15) as r:
        data=json.loads(r.read(1000000))
    return [{"youtube_id":x["id"]["videoId"],
            "url":"https://youtube.com/watch?v="+x["id"]["videoId"],
            "title":x["snippet"]["title"],"channel":x["snippet"]["channelTitle"],
            "published_at":x["snippet"]["publishedAt"]}
            for x in data.get("items",[]) if x.get("id",{}).get("videoId")]

def normalize_transcript(payload):
    if isinstance(payload,dict): payload=payload.get("segments",payload.get("transcript",[]))
    if not isinstance(payload,list): raise ValueError("Expected list of transcript segments")
    result=[]
    for x in payload:
        start=x.get("start",x.get("offset"))
        end=x.get("end")
        if end is None and x.get("duration") is not None and start is not None:
            end=float(start)+float(x["duration"])
        result.append(TranscriptItem(start=start,end=end,text=str(x.get("text","")).strip(),
                                     language=x.get("language","und")))
    return result
