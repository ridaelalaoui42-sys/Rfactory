"""Batch and long-form FFmpeg rough cuts from authorized local source footage."""
import os,shutil,subprocess,tempfile
from pathlib import Path
from .core import FORMATS, EditPlan, render_allowed, safe_local
from .storage import source,plan as get_plan,plan_status
from .editorv1 import brief

def media_root():return Path(os.getenv("CLIPFORGE_MEDIA_ROOT","./media")).expanduser().resolve()
def output_root():return Path(os.getenv("CLIPFORGE_OUTPUT_ROOT","./out")).expanduser().resolve()

def command(argv):
    p=subprocess.run(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=14400)
    if p.returncode:
        raise RuntimeError("FFmpeg command failed: "+p.stderr.decode("utf-8",errors="replace")[-2000:])

def probe(path:Path):
    p=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of",
      "default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,text=True,check=True,timeout=30)
    return float(p.stdout.strip())

def has_audio(path:Path):
    p=subprocess.run(["ffprobe","-v","error","-select_streams","a:0","-show_entries",
      "stream=codec_type","-of","csv=p=0",str(path)],capture_output=True,text=True,check=True,timeout=30)
    return "audio" in p.stdout

def render(plan_id:int):
    row=get_plan(plan_id)
    if not row:raise ValueError("Plan not found")
    spec=EditPlan.model_validate(row["payload"])
    src=source(spec.source_id)
    if not src or not render_allowed(src):
        raise ValueError("Rights gate: approved rights, evidence and source media required")
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Install ffmpeg and ffprobe first")
    inp=safe_local(src["local_file"],media_root())
    total=probe(inp)
    if any(r.end>total+0.04 for r in spec.ranges):
        raise ValueError("Clip timestamp goes beyond media duration")
    root=output_root();root.mkdir(parents=True,exist_ok=True)
    target=(root/spec.output_name).resolve()
    if not target.is_relative_to(root):raise ValueError("Output name outside output root")
    width,height=FORMATS[spec.format]
    filt=(f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
          f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
          "setsar=1,fps=30,format=yuv420p")
    plan_status(plan_id,"rendering")
    try:
        with tempfile.TemporaryDirectory(prefix="clipforge-") as directory:
            temp=Path(directory)
            clips=[]
            audio=has_audio(inp)
            for i,r in enumerate(spec.ranges):
                segment=temp/(f"cut-{i:04d}.mp4")
                args=["ffmpeg","-v","error","-y","-ss",str(r.start),"-i",str(inp)]
                if not audio: args+=["-f","lavfi","-i","anullsrc=r=48000:cl=stereo"]
                args+=["-t",str(r.end-r.start),"-map","0:v:0","-map",
                       "0:a:0" if audio else "1:a:0","-vf",filt,
                       "-c:v","libx264","-preset","veryfast","-crf","23",
                       "-c:a","aac","-b:a","128k","-ar","48000","-ac","2",
                       "-shortest",str(segment)]
                command(args)
                clips.append(segment)
            playlist=temp/"concat.txt"
            playlist.write_text("".join("file '"+str(p)+"'\n" for p in clips),encoding="utf-8")
            result=temp/"assembled.mp4"
            command(["ffmpeg","-v","error","-y","-f","concat","-safe","0",
                     "-i",str(playlist),"-c","copy","-movflags","+faststart",str(result)])
            shutil.copyfile(result,target)
        jsonfile=brief(spec,src,target.with_suffix(".editor-v1.json"))
        plan_status(plan_id,"complete",result_file=str(target))
        return {"status":"complete","path":str(target),"editor_v1_brief":str(jsonfile),
                "format":spec.format,"seconds":probe(target)}
    except Exception as exc:
        plan_status(plan_id,"failed",error=str(exc)[:1000])
        raise
