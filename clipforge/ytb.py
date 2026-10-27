"""Optional ytb-cli metadata/transcript adapter. Never downloads video media."""
import json,shutil,subprocess
from urllib.parse import urlparse,parse_qs
from .research import normalize_transcript

def video_id(value):
    text=value.strip()
    if len(text)==11 and all(c.isalnum() or c in "_-" for c in text):return text
    u=urlparse(text)
    if u.hostname=="youtu.be":text=u.path.strip("/").split("/")[0]
    elif u.hostname in ("youtube.com","www.youtube.com","m.youtube.com") and u.path=="/watch":
        text=parse_qs(u.query).get("v",[""])[0]
    else:raise ValueError("Invalid YouTube URL")
    if len(text)!=11 or not all(c.isalnum() or c in "_-" for c in text):
        raise ValueError("Invalid YouTube video ID")
    return text

def call(*args):
    if not shutil.which("ytb"):raise RuntimeError("Install optional ytb-cli from github.com/tamnd/ytb-cli")
    r=subprocess.run(["ytb",*args],capture_output=True,text=True,timeout=40)
    if r.returncode:raise RuntimeError("ytb research query failed: "+r.stderr[-400:])
    try:return json.loads(r.stdout)
    except json.JSONDecodeError as exc:raise RuntimeError("ytb did not return JSON") from exc

def search(query,limit=10):
    if not query.strip():raise ValueError("Empty topic query")
    return call("search",query,"-n",str(min(50,max(1,limit))),"-o","json")

def transcript(video,language=None):
    args=["transcript",video_id(video),"--format","json"]
    if language:args+=["--lang",language]
    data=call(*args)
    if isinstance(data,dict):data=data.get("segments",data.get("cues",data.get("transcript")))
    if not isinstance(data,list):raise ValueError("Unrecognized ytb transcript format")
    cleaned=[]
    for cue in data:
        if not isinstance(cue,dict):continue
        if "start_ms" in cue or "startMs" in cue:
            first=float(cue.get("start_ms",cue.get("startMs")))/1000
            end_ms=cue.get("end_ms",cue.get("endMs"))
            length_ms=cue.get("duration_ms",cue.get("durationMs"))
            if end_ms is not None:last=float(end_ms)/1000
            elif length_ms is not None:last=first+float(length_ms)/1000
            else:continue
        else:
            first=cue.get("start",cue.get("offset"))
            last=cue.get("end")
            if last is None and cue.get("duration") is not None and first is not None:
                last=float(first)+float(cue["duration"])
        raw=cue.get("text",cue.get("body",cue.get("value","")))
        if not raw and isinstance(cue.get("runs"),list):
            raw="".join(str(x.get("text","")) for x in cue["runs"] if isinstance(x,dict))
        if first is not None and last is not None and str(raw).strip():
            cleaned.append({"start":first,"end":last,"text":str(raw).strip()})
    if not cleaned:raise ValueError("No timestamped captions found in ytb result")
    return normalize_transcript(cleaned)
