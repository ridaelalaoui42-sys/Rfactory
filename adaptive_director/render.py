"""Deterministic frame seekable native-FHD video export.
Usage: python -m adaptive_director.render --out output/preview.mp4 --fps 24
The generator computes every frame independently from t, so frames can be parallelized.
"""
import os,sys,math,argparse,subprocess, json, time
from pathlib import Path
from .visuals import W,H,draw_frame,draw_module_frame
from .router import choose_style,validate_brand
DURATION=29.05

def render(out,fps=24,seconds=DURATION,crf=21,style=None,topic=None,scene_plan=None):
    if scene_plan:
        validate_brand(scene_plan.get("brand",{}))
        seconds=float(scene_plan.get("total_seconds",scene_plan["shots"][-1]["end"]))
    elif style or topic:
        style=choose_style(topic or "tech",override=style)["module"]
    if W<1080 or H<1920:raise RuntimeError('native Full HD gate')
    output=Path(out);output.parent.mkdir(parents=True,exist_ok=True)
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}','-framerate',str(fps),'-i','pipe:0','-an','-c:v','libx264','-preset','ultrafast','-crf',str(crf),'-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    total=math.ceil(seconds*fps); st=time.time()
    try:
        for idx in range(total):
            t=idx/fps
            if scene_plan:
                shot=next((s for s in scene_plan["shots"] if s["start"]<=t<s["end"]),scene_plan["shots"][-1])
                frame=draw_module_frame(shot["module"],t-shot["start"])
            elif style:frame=draw_module_frame(style,t)
            else:frame=draw_frame(t)
            proc.stdin.write(frame.tobytes())
            if idx%120==0:print(f'{idx}/{total} native 1080x1920',flush=True)
    except Exception:
        proc.kill();raise
    finally:
        try:proc.stdin.close()
        except:pass
    ret=proc.wait(timeout=120); err=proc.stderr.read().decode('utf8','replace')
    if ret:raise RuntimeError(err[-2000:])
    print('DONE',output,'frames',total,'elapsed_seconds',round(time.time()-st,1))
    return output

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out',required=True);ap.add_argument('--fps',type=int,default=24);ap.add_argument('--seconds',type=float,default=DURATION);ap.add_argument('--crf',type=int,default=21);ap.add_argument('--topic');ap.add_argument('--style');ap.add_argument('--plan');args=ap.parse_args();scene_plan=json.loads(Path(args.plan).read_text()) if args.plan else None;render(args.out,args.fps,args.seconds,args.crf,args.style,args.topic,scene_plan)
if __name__=='__main__':main()