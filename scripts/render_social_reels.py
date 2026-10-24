#!/usr/bin/env python3
"""Render three animated social puzzle reels using real transparent asset pixels.
The small mosaic-sourced sprites are SOCIAL PREVIEWS, not new native-HD sources.
Requires Pillow, NumPy and ffmpeg/ffprobe. No image API keys or external services.
"""
from __future__ import annotations
import argparse, json, math, random, subprocess, wave
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

W,H,FPS=720,1280,24
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FONT2='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
PRESETS=[
 dict(name='01_puppy_pop',duration=8,theme='orange_comic',primary='animals__puppy_thumbsup',
      sidekick='characters__boy_chef_surprised',badge='badges__wow_badge_yellow',
      shape='circle',title='PUPPY POP!',subtitle='MATCH THE FACE!',c1='#fff447',c2='#ff2774',
      move='orbit',speed=1.0,sparkles=16,reveal_at=6.45),
 dict(name='02_pizza_party',duration=9,theme='purple_arcade',primary='food__whole_pizza',
      sidekick='characters__girl_chef_cheering',badge='badges__heart_eyes_emoji',
      shape='wedge',title='PIZZA PARTY!',subtitle='FIND THE SLICE!',c1='#fff59d',c2='#ff454e',
      move='bounce',speed=1.35,sparkles=14,reveal_at=7.3),
 dict(name='03_kitty_mixup',duration=10,theme='blue_sky_party',primary='animals__happy_kitty',
      sidekick='characters__girl_chef_surprised',badge='badges__laugh_emoji',
      shape='eye_band',title='KITTY MIX-UP!',subtitle='FIX THE KITTY!',c1='#ffffff',c2='#ff2389',
      move='zigzag',speed=1.65,sparkles=20,reveal_at=8.3),
]

def clamp(x,a=0,b=1): return max(a,min(b,x))
def ease(x):
    x=clamp(x)
    return x*x*(3-2*x)
def font(sz):
    return ImageFont.truetype(FONT if Path(FONT).exists() else FONT2,sz)
def sticker(root,key,target):
    p=root/'assets'/'png'/f'{key}@2x.png'
    if not p.is_file(): p=root/'assets'/'png'/f'{key}.png'
    if not p.is_file(): raise FileNotFoundError(p)
    im=Image.open(p).convert('RGBA')
    return im.resize((int(target),max(1,round(target*im.height/im.width))),Image.Resampling.LANCZOS)
def put(bg,s,x,y): bg.alpha_composite(s,(int(x),int(y)))
def label(bg,msg,y,size,color,width=6):
    draw=ImageDraw.Draw(bg);f=font(size)
    bb=draw.textbbox((0,0),msg,font=f,stroke_width=width)
    if bb[2]-bb[0]>W-36:f=font(int(size*(W-36)/(bb[2]-bb[0])))
    draw.text((W/2,y),msg,font=f,anchor='mm',fill=color,
              stroke_width=width,stroke_fill='#2b163d')
def assets(root,cfg):
    subject=sticker(root,cfg['primary'],530)
    if subject.height>530:
        subject=subject.resize((round(subject.width*530/subject.height),530),Image.Resampling.LANCZOS)
    w,h=subject.size
    mask=Image.new('L',(w,h),0);d=ImageDraw.Draw(mask)
    cx=int(w*.52);cy=int(h*.39)
    if cfg['shape']=='circle':
        r=int(min(w,h)*.22);d.ellipse((cx-r,cy-r,cx+r,cy+r),fill=255)
    elif cfg['shape']=='wedge':
        cx=int(w*.52);cy=int(h*.47);r=max(w,h)
        d.polygon([(cx,cy),(cx+int(r*.80),cy-int(r*.48)),(cx+int(r*.80),cy+int(r*.17))],fill=255)
    else:
        d.rounded_rectangle((int(w*.12),int(h*.32),int(w*.91),int(h*.58)),radius=15,fill=255)
    orig=np.asarray(subject.getchannel('A'),dtype=np.uint16)
    mp=np.asarray(mask,dtype=np.uint16)
    base=subject.copy();base.putalpha(Image.fromarray((orig*(255-mp)//255).astype('uint8'),'L'))
    part=subject.copy();part.putalpha(Image.fromarray((orig*mp//255).astype('uint8'),'L'))
    side=sticker(root,cfg['sidekick'],180)
    badge=sticker(root,cfg['badge'],150)
    bg=Image.open(root/'backgrounds'/f"{cfg['theme']}_vertical.webp").convert('RGBA')
    bg=bg.resize((W,H),Image.Resampling.LANCZOS)
    return base,part,side,badge,bg,subject

def base_frame(cfg,parts):
    fixed,moving,side,badge,bg,original=parts
    out=bg.copy();d=ImageDraw.Draw(out)
    d.rounded_rectangle((32,110,688,287),radius=45,fill=(255,255,255,231),outline=(40,23,67,255),width=8)
    d.rounded_rectangle((54,985,666,1160),radius=52,fill=(30,18,63,238),outline=(255,255,255,255),width=7)
    d.rounded_rectangle((46,350,674,956),radius=45,fill=(255,255,255,215),outline=(65,25,95,255),width=7)
    label(out,cfg['title'],170,76,cfg['c1'])
    label(out,cfg['subtitle'],250,46,cfg['c2'],3)
    label(out,'3  ·  2  ·  1  ·  GO!',1073,37,'#ffffff',2)
    put(out,side,25,800-side.height//4)
    x=(W-original.width)//2;y=500+(440-original.height)//2
    ghost=Image.new('RGBA',original.size,(0,0,0,0))
    ghost.putalpha(original.getchannel('A').point(lambda a:int(a*.17)))
    put(out,ghost,x,y);put(out,fixed,x,y)
    return out,x,y
def compose(cfg,t,parts,fixed,x,y):
    base,piece,side,badge,bg,source=parts
    im=fixed.copy()
    prog=ease((t-cfg['reveal_at'])/.65) if t>=cfg['reveal_at'] else 0
    s=cfg['speed']
    if cfg['move']=='orbit':dx=190*math.cos(t*2.9*s);dy=185*math.sin(t*2.9*s)
    elif cfg['move']=='bounce':dx=210*math.sin(t*3.3*s);dy=-135+95*abs(math.sin(t*4.2*s))
    else:dx=235*math.sin(t*3.0*s);dy=100*math.cos(t*4.1*s)
    put(im,piece,x+dx*(1-prog),y+dy*(1-prog))
    d=ImageDraw.Draw(im)
    if prog>.93:
        r=145+16*math.sin(t*18)
        d.ellipse((360-r,670-r,360+r,670+r),outline=(255,227,55,215),width=9)
        put(im,badge,542,858);label(im,'NAILED IT!',1056,60,'#50f579')
    else:
        d.rounded_rectangle((116,1138,604,1163),radius=11,fill=(255,255,255,75))
        d.rounded_rectangle((116,1138,116+int(488*clamp(t/cfg['reveal_at'])),1163),
                            radius=11,fill=(255,220,39,240))
    palette=[(255,255,255,240),(255,219,38,235),(255,56,134,225),(62,219,255,235)]
    for i in range(cfg['sparkles']):
        xx=47+(i*93.7)%630+12*math.sin(t*2+i)
        yy=310+(i*91.9)%660+15*math.sin(t*2.7+i)
        rr=2+(i*11)%5
        d.ellipse((xx-rr,yy-rr,xx+rr,yy+rr),fill=palette[i%4])
    return im.convert('RGB')
def audio(path,duration,reveal):
    sr=22050;n=duration*sr;out=np.zeros(n,np.float32)
    for tm in np.arange(0,duration,.5):
        pos=int(tm*sr);length=int(.10*sr)
        if pos+length>n:continue
        tt=np.arange(length,dtype=np.float32)/sr
        note=330 if round(tm*2)%2==0 else 495
        out[pos:pos+length]+=((np.sin(2*np.pi*note*tt)+.35*np.sin(4*np.pi*note*tt))
                            *np.exp(-30*tt)*.07)
    for tm in (1.8,3.6,5.4,reveal+.58):
        pos=int(tm*sr);length=min(int(.18*sr),n-pos)
        if length<=0:continue
        tt=np.arange(length,dtype=np.float32)/sr
        out[pos:pos+length]+=np.sin(2*np.pi*(720*tt+700*tt*tt))*np.exp(-16*tt)*.17
    with wave.open(str(path),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(sr)
        f.writeframes((np.clip(out,-.8,.8)*32767).astype('<i2').tobytes())
def render(root,out,cfg):
    parts=assets(root,cfg);board,x,y=base_frame(cfg,parts)
    name=cfg['name'];silent=out/f'{name}.silent.mp4';wav=out/f'{name}.wav'
    mp4=out/f'{name}.mp4';duration=int(cfg['duration']);audio(wav,duration,cfg['reveal_at'])
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pix_fmt','rgb24',
         '-s',f'{W}x{H}','-r',str(FPS),'-i','pipe:0','-vf','scale=1080:1920:flags=lanczos',
         '-c:v','libx264','-preset','veryfast','-crf','22','-pix_fmt','yuv420p',
         '-movflags','+faststart',str(silent)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    poster=None
    for i in range(duration*FPS):
        shot=compose(cfg,i/FPS,parts,board,x,y)
        if i==duration*FPS//2:poster=shot.copy()
        proc.stdin.write(shot.tobytes())
    proc.stdin.close()
    err=proc.stderr.read().decode()
    if proc.wait():raise RuntimeError(err)
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(silent),
                    '-i',str(wav),'-c:v','copy','-c:a','aac','-b:a','128k',
                    '-shortest','-movflags','+faststart',str(mp4)],check=True)
    poster.resize((540,960),Image.Resampling.LANCZOS).save(out/f'{name}_poster.jpg',quality=88)
    silent.unlink(missing_ok=True);wav.unlink(missing_ok=True)
    probe=subprocess.run(['ffprobe','-v','error','-show_entries',
           'format=duration,size:stream=codec_name,width,height','-of','json',str(mp4)],
           check=True,capture_output=True,text=True)
    qa=json.loads(probe.stdout);qa.update({'preset':cfg,'sourceTier':'reference_only'})
    (out/f'{name}_qa.json').write_text(json.dumps(qa,indent=2))
    return qa
def main():
    p=argparse.ArgumentParser()
    p.add_argument('--assets',type=Path,default=Path('public/rfactory-social'))
    p.add_argument('--out',type=Path,default=Path('storage/renders/social'))
    p.add_argument('--only',choices=[x['name'] for x in PRESETS])
    a=p.parse_args();a.out.mkdir(parents=True,exist_ok=True)
    records=[render(a.assets,a.out,c) for c in PRESETS if not a.only or a.only==c['name']]
    (a.out/'render_report.json').write_text(json.dumps(records,indent=2))
    print('Rendered',len(records),'reels to',a.out)
if __name__=='__main__':main()
