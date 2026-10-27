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
    return normalize_transcript(data)
