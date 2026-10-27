"""Optional local Whisper speech recognition for rights-approved source files."""
from . import storage
from .core import render_allowed,safe_local,TranscriptItem
from .render import media_root

def transcribe(source_id,model="small",language=None):
    src=storage.source(source_id)
    if not src:raise ValueError("Source not found")
    if not render_allowed(src):raise ValueError("Rights gate rejected transcription")
    if model not in ("tiny","base","small","medium"):raise ValueError("Unapproved model")
    path=safe_local(src["local_file"],media_root())
    try:from faster_whisper import WhisperModel
    except ImportError as exc:raise RuntimeError('Install transcription dependency: pip install -e ".[speech]"') from exc
    engine=WhisperModel(model,device="cpu",compute_type="int8")
    segments,info=engine.transcribe(str(path),language=language,vad_filter=True)
    rows=[TranscriptItem(start=s.start,end=s.end,text=s.text.strip(),language=info.language or "und")
          for s in segments if s.text.strip() and s.end>s.start]
    count=storage.import_transcript(source_id,rows)
    return {"source_id":source_id,"count":count,"language":info.language,"model":model}
