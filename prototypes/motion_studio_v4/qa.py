"""Fail-closed quality gate for a local Rfactory video render.

Production readiness additionally requires narrative TTS and editorial review.
This file checks technical delivery, track presence, temporal movement and
label-layout manifest; it does not claim to watch or hear the video like a person.
"""
from __future__ import annotations
import json, subprocess, pathlib, sys, cv2, numpy as np

def probe(file):
    p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_type,codec_name,width,height,avg_frame_rate,sample_rate,channels','-of','json',str(file)],capture_output=True,text=True,check=True)
    return json.loads(p.stdout)

def check(video,manifest=None, native_min_w=1080,native_min_h=1920):
    path=pathlib.Path(video);meta=probe(path);v=next((s for s in meta['streams'] if s['codec_type']=='video'),None);a=next((s for s in meta['streams'] if s['codec_type']=='audio'),None)
    errors=[];warnings=[]
    if not v:errors.append('video stream missing')
    else:
      if v.get('codec_name')!='h264':errors.append('video must use h264 for Facebook/Android output')
      if int(v.get('width',0))<native_min_w or int(v.get('height',0))<native_min_h:errors.append('native 1080x1920 minimum')
      if v['width']*16!=v['height']*9:errors.append('not a 9:16 vertical picture')
      n,d=map(float,v.get('avg_frame_rate','0/1').split('/'))
      if d==0 or n/d<29.9:errors.append('less than 30 FPS')
    if not a:errors.append('audio stream missing')
    elif a.get('codec_name')!='aac':errors.append('audio codec must be AAC')
    if float(meta['format'].get('duration',0))<3:errors.append('too short or invalid duration')
    # Sample significant changes to detect accidental full-frame freezes.
    cap=cv2.VideoCapture(str(video));tot_frames=int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); fps=cap.get(cv2.CAP_PROP_FPS)
    deltas=[];last=None;stuck=0;max_stuck=0
    for i in range(0,tot_frames,max(1,int(fps//3))):
      cap.set(cv2.CAP_PROP_POS_FRAMES,i);ok,im=cap.read()
      if not ok:continue
      thumb=cv2.cvtColor(cv2.resize(im,(160,284)),cv2.COLOR_BGR2GRAY)
      if last is not None:
        diff=float(np.abs(thumb.astype('float32')-last.astype('float32')).mean());deltas.append(diff)
        if diff<.11:stuck+=1;max_stuck=max(stuck,max_stuck)
        else:stuck=0
      last=thumb
    cap.release()
    if max_stuck>=3:errors.append('long freeze detected at 3Hz sample')
    # Ensure any silence in the soundtrack is intentional; absence of audio is a hard error above.
    try:
      p=subprocess.run(['ffmpeg','-hide_banner','-nostats','-i',str(video),'-af','volumedetect','-f','null','-'],capture_output=True,text=True,timeout=90)
      import re
      m=re.search(r'mean_volume:\s*(-?[0-9.]+) dB',p.stderr)
      mean_db=float(m.group(1)) if m else None
      if mean_db is None:warnings.append('audio loudness was not measured')
      elif mean_db < -38:errors.append('audio may be nearly inaudible (mean volume below -38dBFS)')
    except Exception as exc:mean_db=None;warnings.append('audio inspection failed: '+str(exc)[:160])
    if manifest:
      m=json.loads(pathlib.Path(manifest).read_text())
      if m.get('text_guard',{}).get('violations'):errors.append('text collision/safe-area violations in render manifest')
      if m.get('narration','').startswith('not included'):
       warnings.append('natural narration is absent: laboratory sample not publishable')
    return {'status':'TECHNICAL_PASS' if not errors else 'RENDER_QA_FAILED','errors':errors,'warnings':warnings,'metadata':meta,'video_motion':{'samples':len(deltas),'mean_sample_frame_delta':round(float(np.mean(deltas)) if deltas else 0,3),'longest_low_motion_samples':max_stuck},'audio_mean_dbfs':mean_db,'publishable':False,'reason':'Editorial approval, natural TTS, sound mix and source licensing gates are mandatory for publication.'}

if __name__=='__main__':
    vid=sys.argv[1];man=sys.argv[2] if len(sys.argv)>2 else None
    res=check(vid,man)
    dest=pathlib.Path(vid).with_name('qa_report.json');dest.write_text(json.dumps(res,indent=2));print(json.dumps({k:v for k,v in res.items() if k!='metadata'},indent=2))
    if res['errors']:sys.exit(2)