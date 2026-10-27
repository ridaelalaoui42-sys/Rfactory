"""Official platform upload adapters. Never publishes publicly.

Credentials come from environment-mounted operator secrets. Approvals recorded
per plan/destination are required. Platform tokens are not persisted in SQLite.
"""
from __future__ import annotations
import json,os,re
from pathlib import Path
from urllib.parse import urlparse
from . import storage
from .core import render_allowed
from .render import output_root,probe

DDL="""CREATE TABLE IF NOT EXISTS publish_approvals(
plan_id INTEGER NOT NULL,destination TEXT NOT NULL,
approved_by TEXT NOT NULL, approved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY(plan_id,destination));
CREATE TABLE IF NOT EXISTS publish_history(
plan_id INTEGER NOT NULL,destination TEXT NOT NULL,
external_id TEXT NOT NULL,status TEXT NOT NULL,
created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
PRIMARY KEY(plan_id,destination));"""

def init():
    with storage.connect() as db:db.executescript(DDL)

def approved_media(plan_id:int,destination:str):
    if destination not in ("youtube","facebook"):raise ValueError("Unsupported destination")
    init()
    plan=storage.plan(plan_id)
    if not plan or plan["status"]!="complete" or not plan["result_file"]:
        raise ValueError("Complete render required before publishing")
    src=storage.source(plan["source_id"])
    if not src or not render_allowed(src):
        raise ValueError("Rights evidence missing for source")
    with storage.connect() as db:
        approval=db.execute("SELECT approved_by FROM publish_approvals WHERE plan_id=? AND destination=?",
                            (plan_id,destination)).fetchone()
        existing=db.execute("SELECT external_id FROM publish_history WHERE plan_id=? AND destination=?",
                            (plan_id,destination)).fetchone()
    if not approval:raise ValueError("Operator must approve this destination first")
    if existing:raise ValueError("Already uploaded to this destination; check the platform before retrying")
    path=Path(plan["result_file"]).resolve()
    if not path.is_relative_to(output_root()) or not path.is_file():
        raise ValueError("Rendered video does not exist")
    return path,plan

def approve(plan_id:int,destination:str,approved_by:str="operator"):
    init()
    if destination not in ("youtube","facebook"):raise ValueError("Unsupported destination")
    plan=storage.plan(plan_id)
    if not plan or plan["status"]!="complete":raise ValueError("Complete rendering first")
    source=storage.source(plan["source_id"])
    if not source or not render_allowed(source):raise ValueError("Rights status not approved")
    with storage.connect() as db:
        db.execute("INSERT OR REPLACE INTO publish_approvals(plan_id,destination,approved_by) VALUES(?,?,?)",
                   (plan_id,destination,approved_by))
    return {"plan_id":plan_id,"destination":destination,"approved":True}

def mark_uploaded(plan_id:int,destination:str,video_id:str,status:str):
    init()
    with storage.connect() as db:
        db.execute("""INSERT INTO publish_history(plan_id,destination,external_id,status)
                      VALUES(?,?,?,?)""",(plan_id,destination,video_id,status))

def youtube_private(plan_id:int,title:str,description:str=""):
    path,_=approved_media(plan_id,"youtube")
    credential_path=os.getenv("CLIPFORGE_YOUTUBE_OAUTH_JSON","").strip()
    if not credential_path or not Path(credential_path).is_file():
        raise RuntimeError("Mount authorized YouTube OAuth user credentials at CLIPFORGE_YOUTUBE_OAUTH_JSON")
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
    except ImportError as exc:raise RuntimeError('Install optional publishing SDK: pip install -e ".[publish]"') from exc
    scopes=["https://www.googleapis.com/auth/youtube.upload"]
    creds=Credentials.from_authorized_user_file(credential_path,scopes=scopes)
    if not creds.valid:
        if creds.expired and creds.refresh_token:creds.refresh(Request())
        else:raise RuntimeError("YouTube OAuth credentials need renewed authorization")
    service=build("youtube","v3",credentials=creds,cache_discovery=False)
    request=service.videos().insert(part="snippet,status",
       body={"snippet":{"title":title[:100],"description":description[:5000],"categoryId":"22"},
             "status":{"privacyStatus":"private"}},
       media_body=MediaFileUpload(str(path),mimetype="video/mp4",chunksize=8*1024*1024,resumable=True))
    result=None
    while result is None:
        _,result=request.next_chunk()
    video_id=result.get("id")
    if not video_id:raise RuntimeError("YouTube upload returned no video ID")
    mark_uploaded(plan_id,"youtube",video_id,"private")
    return {"destination":"youtube","video_id":video_id,"state":"private","url":"https://youtu.be/"+video_id}

def facebook_draft(plan_id:int,title:str,description:str=""):
    path,plan=approved_media(plan_id,"facebook")
    if plan["payload"]["format"]!="vertical":
        raise ValueError("Facebook Reel adapter requires a 9:16 video")
    seconds=probe(path)
    if not 4<=seconds<=60:
        raise ValueError("Facebook Reel adapter accepts 4–60-second clips until API limits are verified")
    token=os.getenv("CLIPFORGE_META_PAGE_TOKEN","")
    version=os.getenv("CLIPFORGE_META_GRAPH_VERSION","")
    if not token or not re.fullmatch(r"v\d+\.\d+",version):
        raise RuntimeError("Configure CLIPFORGE_META_PAGE_TOKEN and CLIPFORGE_META_GRAPH_VERSION")
    try:import requests
    except ImportError as exc:raise RuntimeError('Install optional publishing SDK: pip install -e ".[publish]"') from exc
    url="https://graph.facebook.com/"+version+"/me/video_reels"
    start=requests.post(url,data={"upload_phase":"start"},
                        headers={"Authorization":"Bearer "+token},timeout=40)
    start.raise_for_status();session=start.json()
    video_id=session.get("video_id")
    upload_url=session.get("upload_url","")
    parsed=urlparse(upload_url)
    if not video_id or parsed.scheme!="https" or parsed.hostname!="rupload.facebook.com":
        raise RuntimeError("Unexpected Meta upload session URL; refused")
    with path.open("rb") as file:
        uploaded=requests.post(upload_url,data=file,headers={
            "Authorization":"OAuth "+token,"offset":"0","file_size":str(path.stat().st_size),
            "Content-Type":"application/octet-stream"},timeout=600)
    uploaded.raise_for_status()
    if not uploaded.json().get("success"):
        raise RuntimeError("Meta did not confirm uploaded bytes")
    end=requests.post(url,data={"upload_phase":"finish","video_id":video_id,
                                "video_state":"DRAFT","title":title[:100],
                                "description":description[:2000]},
                      headers={"Authorization":"Bearer "+token},timeout=60)
    end.raise_for_status()
    if not end.json().get("success"):
        raise RuntimeError("Meta did not accept Reel draft")
    mark_uploaded(plan_id,"facebook",str(video_id),"draft")
    return {"destination":"facebook","video_id":str(video_id),"state":"draft"}
