#!/usr/bin/env python3
"""Rfactory social puzzle reels. Generate MP4s from actual transparent sticker pixels.

No AI calls or placeholder geometric 'subjects'. A moving puzzle fragment is cut
from the exact same source RGBA sticker as the stationary board. Outputs are
labelled social previews because the stickers came from reference mosaic sheets.
Dependencies: Pillow, NumPy, FFmpeg + FFprobe in PATH.
Usage: python scripts/render_social_reels.py --assets public/rfactory-social --out storage/renders/social
"""
import argparse
import json
import math
import random
import shutil
import subprocess
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from scripts.social_motion import pose_at_frame, validate_schedule

W, H, FPS = 720, 1280, 24
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FONT_FALLBACK = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

PRESETS = [
    dict(name='01_puppy_pop', duration=8, theme='orange_comic', primary='animals__puppy_thumbsup',
         sidekick='characters__boy_chef_surprised', badge='badges__wow_badge_yellow',
         shape='circle', title='PUPPY POP!', subtitle='MATCH THE FACE!', c1='#fff447', c2='#ff2774',
         move='orbit', speed=1.0, sparkles=16, reveal_at=6.45),
    dict(name='02_pizza_party', duration=9, theme='purple_arcade', primary='food__whole_pizza',
         sidekick='characters__girl_chef_cheering', badge='badges__heart_eyes_emoji',
         shape='wedge', title='PIZZA PARTY!', subtitle="FIND THE SLICE!", c1='#fff59d', c2='#ff454e',
         move='bounce', speed=1.35, sparkles=14, reveal_at=7.3),
    dict(name='03_kitty_mixup', duration=10, theme='blue_sky_party', primary='animals__happy_kitty',
         sidekick='characters__girl_chef_surprised', badge='badges__laugh_emoji',
         shape='eye_band', title='KITTY MIX-UP!', subtitle='FIX THE KITTY!', c1='#ffffff', c2='#ff2389',
         move='zigzag', speed=1.65, sparkles=20, reveal_at=8.3),
]

def clamp(n,a=0,b=1): return max(a,min(b,n))
def ease(x):
    x=clamp(x)
    return x*x*(3-2*x)

def font(sz):
    return ImageFont.truetype(FONT if Path(FONT).exists() else FONT_FALLBACK, sz)

def sticker(base, id, target_w):
    p=base/'assets'/'png'/f'{id}@2x.png'
    if not p.exists(): p=base/'assets'/'png'/f'{id}.png'
    if not p.exists(): p=base/'assets'/'webp'/f'{id}.webp'
    if not p.exists(): raise FileNotFoundError(f'Missing real cutout {p}')
    im=Image.open(p).convert('RGBA')
    nw=int(target_w);nh=max(1,round(nw*im.height/im.width))
    return im.resize((nw,nh),Image.Resampling.LANCZOS)

def paste_at(bg, sprite, x,y):
    bg.alpha_composite(sprite,(int(x),int(y)))

def boxed_text(bg,text,center_y,sz,fill,stroke='#2b163d',stroke_width=6):
    draw=ImageDraw.Draw(bg)
    f=font(sz)
    box=draw.textbbox((0,0),text,font=f,stroke_width=stroke_width)
    width=box[2]-box[0]
    if width>W-36:
        factor=(W-36)/width
        f=font(int(sz*factor))
    draw.text((W/2,center_y),text,font=f,anchor='mm',fill=fill,stroke_width=stroke_width,stroke_fill=stroke)

def prepare_assets(root, cfg):
    primary=sticker(root,cfg['primary'],530)
    if primary.height>530:
        primary=primary.resize((round(primary.width*530/primary.height),530),Image.Resampling.LANCZOS)
    w,h=primary.size
    # The puzzle mask is constructed over the genuine source pixels.
    mask=Image.new('L',(w,h),0);d=ImageDraw.Draw(mask)
    cx=int(w*.52); cy=int(h*.39)
    if cfg['shape']=='circle':
        r=int(min(w,h)*.22)
        d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=255)
        outline=('ellipse',(cx-r,cy-r,cx+r,cy+r))
    elif cfg['shape']=='wedge':
        cx=int(w*.52);cy=int(h*.47);r=max(w,h)
        points=[(cx,cy),(cx+int(r*.80),cy-int(r*.48)),(cx+int(r*.80),cy+int(r*.17))]
        d.polygon(points,fill=255)
        outline=('polygon',points)
    else:
        x0=int(w*.12);y0=int(h*.32);x1=int(w*.91);y1=int(h*.58)
        # Horizontal strip cut directly from face original pixels.
        d.rounded_rectangle((x0,y0,x1,y1),radius=15,fill=255)
        outline=('rectangle',(x0,y0,x1,y1))
    alpha=np.asarray(primary.getchannel('A'),dtype=np.uint16)
    mp=np.asarray(mask,dtype=np.uint16)
    base_alpha=Image.fromarray((alpha*(255-mp)//255).astype('uint8'),'L')
    part_alpha=Image.fromarray((alpha*mp//255).astype('uint8'),'L')
    base_piece=primary.copy();base_piece.putalpha(base_alpha)
    moving_piece=primary.copy();moving_piece.putalpha(part_alpha)
    sidekick=sticker(root,cfg['sidekick'],180)
    badge=sticker(root,cfg['badge'],150)
    bg=Image.open(root/'backgrounds'/f"{cfg['theme']}_vertical.webp").convert('RGBA').resize((W,H),Image.Resampling.LANCZOS)
    return base_piece,moving_piece,sidekick,badge,bg,outline,primary

def composed_static(cfg, parts):
    base_piece,moving_piece,sidekick,badge,bg,outline,primary=parts
    bg=bg.copy(); d=ImageDraw.Draw(bg)
    # Playful blocks and visible preview-quality message.
    d.rounded_rectangle((32,110,688,287),radius=45,fill=(255,255,255,231),outline=(40,23,67,255),width=8)
    d.rounded_rectangle((54,985,666,1160),radius=52,fill=(30,18,63,238),outline=(255,255,255,255),width=7)
    d.rounded_rectangle((46,350,674,956),radius=45,fill=(255,255,255,215),outline=(65,25,95,255),width=7)
    boxed_text(bg,cfg['title'],170,76,cfg['c1'],stroke_width=6)
    boxed_text(bg,cfg['subtitle'],250,46,cfg['c2'],stroke_width=3)
    boxed_text(bg,'3  ·  2  ·  1  ·  GO!',1073,37,'#ffffff',stroke_width=2)
    # Fixed presenter and fixed image, with cutout hole reserved for actual source pixels.
    paste_at(bg,sidekick,25,800-sidekick.height//4)
    x=(W-primary.width)//2; y=500+(440-primary.height)//2
    # Fill puzzle hole with a dark translucent impression, then layer real-image mask around.
    ghost=Image.new('RGBA',primary.size,(0,0,0,0))
    ghost.putalpha(primary.getchannel('A').point(lambda a:int(a*.17)))
    paste_at(bg,ghost,x,y)
    paste_at(bg,base_piece,x,y)
    return bg,x,y

def motion_xy(cfg,t):
    pose=pose_at_frame(round(t*FPS),cfg,FPS)
    return pose.dx,pose.dy,pose

def frame(cfg, t, parts, static, pos):
    base_piece,piece,sidekick,badge,bg,outline,primary=parts
    x,y=pos
    canvas=static.copy();draw=ImageDraw.Draw(canvas)
    dx,dy,pose=motion_xy(cfg,t)
    paste_at(canvas,piece,x+dx,y+dy)
    # Pulsing neon ring when puzzle aligns, cut from same pixel board.
    if pose.final:
        r=145+16*math.sin(t*18)
        draw.ellipse((360-r,670-r,360+r,670+r),outline=(255,227,55,215),width=9)
        paste_at(canvas,badge,542,858)
        boxed_text(canvas,'ALL 5 MATCHES!',1056,51,'#50f579',stroke_width=6)
    elif pose.fit:
        # Visible repeated exact-fit event. Integer offset is precisely (0,0).
        boxed_text(canvas,f'MATCH {pose.fit_number}/{pose.total_fits}!',1056,58,'#63ff9d',stroke_width=5)
        draw.ellipse((185,490,535,840),outline=(255,233,42,255),width=9)
    else:
        # Moving score strip guides without covering subject.
        draw.rounded_rectangle((116,1138,604,1163),radius=11,fill=(255,255,255,75))
        draw.rounded_rectangle((116,1138,116+int(488*clamp(t/cfg['duration'])),1163),radius=11,fill=(255,220,39,240))
    rng=random.Random(552+int(t*3))
    for i in range(cfg['sparkles']):
        xx=(47 + (i*93.7)%630 + 12*math.sin(t*2+i))
        yy=310+(i*91.9)%660 + 15*math.sin(t*2.7+i)
        rr=2+((i*11)%5)
        color=[(255,255,255,240),(255,219,38,235),(255,56,134,225),(62,219,255,235)][i%4]
        draw.ellipse((xx-rr,yy-rr,xx+rr,yy+rr),fill=color)
    return canvas.convert('RGB')

def make_audio(path,duration,reveal, cfg=None):
    sr=22050
    n=int(sr*duration)
    out=np.zeros(n,dtype=np.float32)
    rng=np.random.default_rng(43)
    for t in np.arange(0,duration,.5):
        start=int(t*sr); length=int(.10*sr)
        if start+length>n:continue
        tt=np.arange(length,dtype=np.float32)/sr
        phase=330 if (round(t*2)%2==0) else 495
        beep=(np.sin(2*np.pi*phase*tt)+.35*np.sin(2*np.pi*phase*2*tt))*np.exp(-30*tt)
        out[start:start+length]+=beep*.07
    for t in ([x/FPS for x in validate_schedule(cfg,FPS)['fit_frames']] if cfg else [1.8,3.6,5.4,reveal+.58]):
        start=int(t*sr); length=min(int(.18*sr),n-start)
        if length<=0:continue
        tt=np.arange(length,dtype=np.float32)/sr
        chirp=np.sin(2*np.pi*(720*tt+700*tt*tt))*np.exp(-16*tt)
        out[start:start+length]+=chirp*.17
    out=np.clip(out,-.8,.8)
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr)
        f.writeframes((out*32767).astype('<i2').tobytes())

def produce(root,out,cfg):
    parts=prepare_assets(root,cfg)
    static,x,y=composed_static(cfg,parts)
    duration=int(cfg['duration']); n=duration*FPS
    outfile=out/f"{cfg['name']}.mp4"
    silent=out/f"{cfg['name']}.silent.mp4"
    audio=out/f"{cfg['name']}.wav"
    make_audio(audio,duration,cfg['reveal_at'],cfg)
    command=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
             '-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-vf','scale=1080:1920:flags=lanczos',
             '-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p','-movflags','+faststart',str(silent)]
    p=subprocess.Popen(command,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    poster=None
    try:
        for idx in range(n):
            t=idx/FPS
            picture=frame(cfg,t,parts,static,(x,y))
            if idx==n//2:poster=picture.copy()
            p.stdin.write(picture.tobytes())
            if idx%72==0: print(cfg['name'],idx,'/',n,flush=True)
        p.stdin.close();error=p.stderr.read().decode();ret=p.wait()
        if ret:raise RuntimeError(error)
    except Exception:
        p.kill();raise
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),'-i',str(audio),
                    '-c:v','copy','-c:a','aac','-b:a','128k','-shortest','-movflags','+faststart',str(outfile)],check=True)
    if poster:poster.resize((540,960),Image.Resampling.LANCZOS).save(out/f"{cfg['name']}_poster.jpg",quality=88)
    silent.unlink(missing_ok=True);audio.unlink(missing_ok=True)
    ffprobe=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,width,height,r_frame_rate',
                            '-of','json',str(outfile)],capture_output=True,text=True,check=True)
    report=json.loads(ffprobe.stdout)
    report.update({'name':cfg['name'],'sourceSprite':cfg['primary'],'sourceAssetTier':'reference_only',
                   'repeated_alignment':validate_schedule(cfg,FPS),
                   'puzzle':'exact same source pixels','settings':cfg})
    (out/f"{cfg['name']}_qa.json").write_text(json.dumps(report,indent=2))
    return report

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--assets',type=Path,default=Path(__file__).resolve().parents[1])
    p.add_argument('--out',type=Path,default=Path('storage/renders/social'))
    p.add_argument('--only',choices=[c['name'] for c in PRESETS])
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    cfgs=[x for x in PRESETS if not a.only or x['name']==a.only]
    qa=[]
    for cfg in cfgs:
        qa.append(produce(a.assets,a.out,cfg))
    (a.out/'render_report.json').write_text(json.dumps({'status':'rendered-preview','reels':qa},indent=2))
    print('COMPLETE',len(qa),flush=True)

if __name__=='__main__':main()