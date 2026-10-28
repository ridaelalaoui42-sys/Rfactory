#!/usr/bin/env python3
"""Render original ClipForge Canvas style packs to MP4 using Node + Skia Canvas + FFmpeg.

The same style's draw(ctx,w,h,t) runs in the interactive browser player and in
headless native Canvas. Style packs must be reviewed before they are executable.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import wave
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
JS=ROOT/'scripts'/'frames.cjs'


def dimensions(fmt:str,width:int)->tuple[int,int]:
    if not (144<=width<=4096) or width%2:raise ValueError('width must be even and 144-4096')
    if fmt=='horizontal':return width,round(width*9/16/2)*2
    if fmt=='vertical':return width,round(width*16/9/2)*2
    if fmt=='square':return width,width
    raise ValueError('invalid format')


def env_node():
    env=os.environ.copy()
    # Normal npm installation needs no NODE_PATH; this is only a fallback for this environment.
    if not env.get('NODE_PATH'):
        global_modules=Path('/opt/nvm/versions/node/v22.16.0/lib/node_modules')
        if global_modules.is_dir():env['NODE_PATH']=str(global_modules)
    return env


def node(*args, text=True):
    return subprocess.run(['node',str(JS),*map(str,args)],capture_output=True,text=text,env=env_node(),check=True)


def events():
    return json.loads(node('--events').stdout)


def _fx_sample(kind:str,t:np.ndarray,sr:int,seed:int):
    """Create distinct original printer/graphic sound effects from simple oscillators."""
    config={
        'roller':(120,65,.42,'saw'), 'press':(135,55,.16,'triangle'),
        'paper':(310,145,.2,'noise'),'tick':(930,610,.048,'square'),
        'swish':(300,800,.18,'noise'),'impact':(140,48,.30,'sine'),
        'ding':(730,740,.5,'sine')}
    start,end,seconds,waveform=config[kind]
    inst=start*np.exp(np.log(end/start)*t/seconds)
    phase=np.cumsum(inst,dtype=np.float64)/sr
    if waveform=='sine':signal=np.sin(2*np.pi*phase)
    elif waveform=='square':signal=np.where(phase%1<.5,1.,-1.)
    elif waveform=='triangle':signal=1.-4.*np.abs((phase%1)-.5)
    elif waveform=='saw':signal=2.*(phase%1)-1.
    else:
        noise=np.random.default_rng(seed).normal(0,1,len(t)).astype(np.float64)
        signal=np.convolve(noise,[.18,.22,.28,.22,.10],mode='same')
    rise=1-np.exp(-t/.006)
    envelope=rise*np.exp(-4*t/seconds)
    return (signal*envelope).astype(np.float64)


def write_sfx(wavpath:Path,duration:float,rate=48000):
    samples=int(math.ceil(duration*rate))
    master=np.zeros((samples,2),dtype=np.float64)
    meta={'roller':.42,'press':.16,'paper':.2,'tick':.048,'swish':.18,'impact':.3,'ding':.5}
    for i,e in enumerate(events()):
        if e['time']>=duration:continue
        start=round(e['time']*rate)
        length=min(round(meta[e['kind']]*rate),samples-start)
        if length<=0:continue
        t=np.arange(length,dtype=np.float64)/rate
        signal=_fx_sample(e['kind'],t,rate,2026+i)
        gain=e.get('gain',.5)*.33
        master[start:start+length,0]+=signal*gain
        master[start:start+length,1]+=signal*gain
    master=np.tanh(master)
    pcm=np.round(np.clip(master,-1,1)*32767).astype('<i2')
    with wave.open(str(wavpath),'wb') as f:
        f.setnchannels(2);f.setsampwidth(2);f.setframerate(rate);f.writeframes(pcm.tobytes())
    return wavpath


def run(args)->dict:
    if not shutil.which('ffmpeg') or not shutil.which('ffprobe'):raise RuntimeError('FFmpeg and FFprobe needed')
    if not (1<=args.fps<=60):raise ValueError('fps must be 1-60')
    if not (0<args.duration<=15):raise ValueError('demo supports 0-15 seconds')
    width,height=dimensions(args.format,args.width)
    output=Path(args.output).expanduser().resolve();output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='clipforge-riso-') as tmp:
        tmpdir=Path(tmp)
        # Seek-based determinism: pixel bytes at the same timestamp must not change.
        a=tmpdir/'a.png';b=tmpdir/'b.png'
        for path in (a,b):node('--format',args.format,'--width',width,'--single',3.125,'--poster',path)
        if a.read_bytes()!=b.read_bytes():raise RuntimeError('deterministic frame QA failed')
        poster=output.with_suffix('.poster.png')
        node('--format',args.format,'--width',width,'--single',min(11.6,args.duration*.74),'--poster',poster)
        fx=tmpdir/'effects.wav'
        if not args.silent:write_sfx(fx,args.duration)
        frames=['node',str(JS),'--format',args.format,'--width',str(width),'--fps',str(args.fps),'--duration',str(args.duration)]
        enc=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','image2pipe','-vcodec','mjpeg',
             '-framerate',str(args.fps),'-i','pipe:0']
        if not args.silent:enc+=['-i',str(fx)]
        if args.voiceover:
            if not Path(args.voiceover).is_file():raise FileNotFoundError(args.voiceover)
            if args.silent:raise ValueError('voiceover mixing requires effects enabled')
            enc+=['-i',str(Path(args.voiceover).resolve())]
            enc+=['-filter_complex','[2:a]loudnorm=I=-17:TP=-2,asplit=2[v1][v2];[1:a]volume=0.5[fx0];[fx0][v1]sidechaincompress=threshold=0.04:ratio=3:attack=10:release=260[fx];[v2][fx]amix=inputs=2:normalize=0,loudnorm=I=-16:TP=-1.5:LRA=11[a]','-map','0:v:0','-map','[a]']
        else:
            enc+=['-map','0:v:0']
            if not args.silent:enc+=['-map','1:a:0']
        enc+=['-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p',
              '-r',str(args.fps),'-movflags','+faststart']
        if not args.silent:enc+=['-c:a','aac','-b:a','128k']
        enc+=['-t',str(args.duration),str(output)]
        # Direct stream: no images or temporary video frames stored on disk.
        proc1=subprocess.Popen(frames,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env_node())
        proc2=subprocess.Popen(enc,stdin=proc1.stdout,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        proc1.stdout.close()
        _,stderr2=proc2.communicate(timeout=360)
        stderr1=proc1.stderr.read().decode(errors='replace')
        rc1=proc1.wait(timeout=30)
        if rc1 or proc2.returncode:
            output.unlink(missing_ok=True)
            raise RuntimeError(f'Native renderer: {stderr1[-1000:]} | FFmpeg: {stderr2.decode(errors="replace")[-1000:]}')
        if not output.is_file() or output.stat().st_size<1000:raise RuntimeError('no video output')
    probe=subprocess.run(['ffprobe','-v','error','-show_entries','stream=codec_type,width,height','-of','json',str(output)],capture_output=True,text=True,check=True)
    streams=json.loads(probe.stdout)['streams']
    if not any(s.get('codec_type')=='video' and s.get('width')==width and s.get('height')==height for s in streams):raise RuntimeError('QA resolution mismatch')
    if not args.silent and not any(s.get('codec_type')=='audio' for s in streams):raise RuntimeError('QA missing audio stream')
    result={'style':'risograph_zine','format':args.format,'width':width,'height':height,'fps':args.fps,
      'duration':args.duration,'frames':round(args.duration*args.fps),'deterministic':True,
      'audio':not args.silent,'voiceover':bool(args.voiceover),'output':str(output),'poster':str(poster),
      'bytes':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest()}
    output.with_suffix('.qa.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--format',choices=['vertical','horizontal','square'],default='horizontal')
    parser.add_argument('--width',type=int,default=960)
    parser.add_argument('--fps',type=int,default=24)
    parser.add_argument('--duration',type=float,default=15.)
    parser.add_argument('--output',default='risograph-demo.mp4')
    parser.add_argument('--voiceover',default=None)
    parser.add_argument('--silent',action='store_true')
    args=parser.parse_args()
    print(json.dumps(run(args),indent=2))

if __name__=='__main__':main()
