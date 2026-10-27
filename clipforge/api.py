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


# v0.2: dashboard, research adapters, uploads, and durable jobs
import uuid
from pathlib import Path
from fastapi import UploadFile, File, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel
from . import jobs, moments, ytb
from .render import output_root

@app.get("/", include_in_schema=False)
def dashboard():
    return FileResponse(Path(__file__).parent/"static"/"index.html")

@app.get("/v1/sources/{source_id}/moments", dependencies=[Depends(admin)])
def ranked_moments(source_id: int, duration: int=60, limit: int=10):
    try: return moments.candidates(source_id,duration,limit)
    except ValueError as exc: raise HTTPException(400,str(exc))

@app.get("/v1/ytb/status", dependencies=[Depends(admin)])
def ytb_status(): return {"installed": ytb.shutil.which("ytb") is not None,
                           "note":"ytb-cli uses unofficial YouTube endpoints"}

@app.get("/v1/ytb/search", dependencies=[Depends(admin)])
def ytb_search(q: str, limit: int=10):
    try: return ytb.search(q,limit)
    except (ValueError,RuntimeError) as exc: raise HTTPException(400,str(exc))

class TranscriptImport(BaseModel):
    video: str
    language: str | None = None

@app.post("/v1/sources/{source_id}/ytb-transcript", dependencies=[Depends(admin)])
def ytb_transcript_import(source_id:int, options:TranscriptImport):
    if not storage.source(source_id):raise HTTPException(404,"Source not found")
    try:
        cues=ytb.transcript(options.video, options.language)
        return {"count":storage.import_transcript(source_id,cues),"provenance":"ytb-cli"}
    except (ValueError,RuntimeError) as exc:raise HTTPException(400,str(exc))

@app.post("/v1/media/upload", dependencies=[Depends(admin)])
def upload_media(file:UploadFile=File(...), title:str=Form(...),
                 rights:str=Form("unknown"), evidence:str=Form("")):
    if rights not in ("owned","licensed","permission","public_domain","unknown","fair_use_review"):
        raise HTTPException(400,"Invalid rights status")
    if not title.strip():raise HTTPException(400,"Title required")
    extension=Path(file.filename or "").suffix.lower()
    if extension not in (".mp4",".mov",".mkv",".webm",".m4v"):
        raise HTTPException(400,"Unsupported file type")
    root=media_root()
    root.mkdir(parents=True,exist_ok=True)
    path=root/(str(uuid.uuid4())+extension)
    size=0
    try:
        with path.open("xb") as destination:
            while True:
                chunk=file.file.read(1024*1024)
                if not chunk:break
                size+=len(chunk)
                if size>int(os.getenv("CLIPFORGE_MAX_UPLOAD_MB","1024"))*1024*1024:
                    raise ValueError("Maximum upload size exceeded")
                destination.write(chunk)
        if not size:raise ValueError("Empty media")
        new=SourceCreate(title=title,local_file=str(path),rights=rights,evidence=evidence)
        return {"id":storage.create_source(new),"bytes":size}
    except Exception as exc:
        path.unlink(missing_ok=True)
        if isinstance(exc,ValueError):raise HTTPException(413,str(exc))
        raise

@app.post("/v1/plans/{plan_id}/queue", dependencies=[Depends(admin)])
def enqueue_render(plan_id:int):
    try:return {"job_id":jobs.enqueue("render",plan_id)}
    except ValueError as exc:raise HTTPException(400,str(exc))

class TranscribeOptions(BaseModel):
    model: str = "small"
    language: str | None = None

@app.post("/v1/sources/{source_id}/transcribe", dependencies=[Depends(admin)])
def enqueue_transcript(source_id:int,options:TranscribeOptions):
    if options.model not in ("tiny","base","small","medium"):
        raise HTTPException(400,"Invalid model")
    try:return {"job_id":jobs.enqueue("transcribe",source_id,options.model_dump())}
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.get("/v1/jobs",dependencies=[Depends(admin)])
def all_jobs(limit:int=30): return jobs.all_jobs(limit)

@app.get("/v1/jobs/{job_id}",dependencies=[Depends(admin)])
def job_status(job_id:int):
    result=jobs.get(job_id)
    if not result:raise HTTPException(404,"Job not found")
    return result

@app.get("/v1/plans/{plan_id}/download",dependencies=[Depends(admin)])
def output_download(plan_id:int):
    current=storage.plan(plan_id)
    if not current or current["status"]!="complete" or not current["result_file"]:
        raise HTTPException(404,"Completed video not found")
    target=Path(current["result_file"]).resolve()
    if not target.is_relative_to(output_root()) or not target.is_file():
        raise HTTPException(404,"Output file missing")
    return FileResponse(target,filename=target.name,media_type="video/mp4")


@app.post("/v1/plans/{plan_id}/prepare-editor-v1", dependencies=[Depends(admin)])
def prepare_editor_v1(plan_id:int):
    from .editorv1_project import prepare
    try: return prepare(plan_id)
    except ValueError as exc:raise HTTPException(400,str(exc))
    except RuntimeError as exc:raise HTTPException(409,str(exc))


class PublicationRequest(BaseModel):
    destination: str
    title: str
    description: str = ""

class ApprovalRequest(BaseModel):
    destination: str

@app.post("/v1/plans/{plan_id}/approve-publication", dependencies=[Depends(admin)])
def approve_publication(plan_id:int,body:ApprovalRequest):
    from .publishing import approve
    try:return approve(plan_id,body.destination)
    except ValueError as exc:raise HTTPException(400,str(exc))

@app.post("/v1/plans/{plan_id}/queue-publish-draft", dependencies=[Depends(admin)])
def publish_draft(plan_id:int,body:PublicationRequest):
    if body.destination not in ("youtube","facebook"):
        raise HTTPException(400,"Unsupported publishing destination")
    if not body.title.strip():raise HTTPException(400,"Title required")
    try:
        jobid=jobs.enqueue("publish_"+body.destination,plan_id,
                           {"title":body.title,"description":body.description})
        return {"job_id":jobid,"destination":body.destination,
                "note":"Destination creates private/draft content only, never public posts"}
    except ValueError as exc:raise HTTPException(400,str(exc))
