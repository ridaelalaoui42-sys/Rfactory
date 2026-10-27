"""Token-protected FastAPI with local video operations."""
import os,secrets
from fastapi import FastAPI,Depends,HTTPException,Header
from .core import FORMATS,SourceCreate,TranscriptItem,EditPlan,safe_local
from . import storage
from .render import render,media_root
from .research import youtube_search
from .editorv1 import status as upstream_status

app=FastAPI(title="ClipForge AI",version="0.1.0")

def admin(authorization:str|None=Header(default=None)):
    token=os.getenv("CLIPFORGE_API_TOKEN","").strip()
    if not token:raise HTTPException(503,"Set CLIPFORGE_API_TOKEN to enable API")
    given=authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not secrets.compare_digest(token,given):raise HTTPException(401,"Unauthorized")

@app.get("/health")
def health():return {"status":"ok","service":"clipforge","version":"0.1.0"}

@app.get("/v1/formats",dependencies=[Depends(admin)])
def formats():return {name:{"width":dims[0],"height":dims[1]} for name,dims in FORMATS.items()}

@app.get("/v1/sources",dependencies=[Depends(admin)])
def sources():return storage.sources()

@app.post("/v1/sources",dependencies=[Depends(admin)])
def add_source(payload:SourceCreate):
    if payload.local_file:
        try:payload.local_file=str(safe_local(payload.local_file,media_root()))
        except ValueError as exc:raise HTTPException(400,str(exc))
    return {"id":storage.create_source(payload)}

@app.post("/v1/sources/{source_id}/transcripts",dependencies=[Depends(admin)])
def transcript(source_id:int,segments:list[TranscriptItem]):
    try:return {"count":storage.import_transcript(source_id,segments)}
    except ValueError as exc:raise HTTPException(404,str(exc))

@app.get("/v1/transcripts/search",dependencies=[Depends(admin)])
def search(q:str,limit:int=50):return storage.search(q,limit)

@app.get("/v1/discover",dependencies=[Depends(admin)])
def discover(q:str,max_results:int=10):
    try:return youtube_search(q,max_results)
    except ValueError as exc:raise HTTPException(400,str(exc))
    except Exception:raise HTTPException(502,"YouTube metadata discovery failed")

@app.post("/v1/plans",dependencies=[Depends(admin)])
def plan(payload:EditPlan):
    try:return {"id":storage.create_plan(payload)}
    except ValueError as exc:raise HTTPException(404,str(exc))

@app.get("/v1/plans/{plan_id}",dependencies=[Depends(admin)])
def plan_status(plan_id:int):
    x=storage.plan(plan_id)
    if not x:raise HTTPException(404,"Plan not found")
    return x

@app.post("/v1/plans/{plan_id}/render",dependencies=[Depends(admin)])
def do_render(plan_id:int):
    try:return render(plan_id)
    except ValueError as exc:raise HTTPException(400,str(exc))
    except Exception:raise HTTPException(500,"Render failed; inspect server logs")

@app.get("/v1/editor-v1/status",dependencies=[Depends(admin)])
def editor_status():return upstream_status()
