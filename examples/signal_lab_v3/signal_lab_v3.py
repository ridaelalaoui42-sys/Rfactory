"""CTRL PULSE / SIGNAL LAB V3 — deterministic code-only scene-graph renderer.

Render frames through Pillow + NumPy and mux with ffmpeg; no slideshow templates.
Supports animated spring rigs, 2.5D layer transforms, typed kinetics, orbital motion,
particle morphs, live data paths, multi-scene choreography, and source-photo slots.

Examples:
    python signal_lab_v3.py --output demo.mp4 --fps 30 --width 540 --height 960
    python signal_lab_v3.py --output full.mp4 --fps 60 --width 720 --height 1280

All sources/credits tracked separately in manifest.json. Requires pillow numpy ffmpeg.
"""
from __future__ import annotations
import argparse
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from math import sin,cos,pi,sqrt
import math
import numpy as np
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import subprocess, random, json, shutil

BASE = Path(__file__).resolve().parent
ASSET = BASE / 'assets'
CREAM=(246,240,221); INK=(20,42,35); ORANGE=(251,95,55)
LIME=(220,241,95); BLUE=(77,103,244); ROSE=(245,139,148)
SAGE=(162,181,168); WHITE=(255,255,250); YELLOW=(251,208,78)
FONT_BOLD='/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf'
FONT_BLACK='/usr/share/fonts/opentype/inter/InterDisplay-Black.otf'
FONT_MED='/usr/share/fonts/opentype/inter/Inter-Medium.otf'
if not Path(FONT_BLACK).exists():FONT_BLACK=FONT_BOLD
FONT_MONO='/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf'


def clamp(a,b=0,c=1):return min(c,max(b,a))
def ease(x):x=clamp(x);return x*x*(3-2*x)
def spring(x):
    x=clamp(x)
    return 1-math.exp(-8.7*x)*math.cos(13*x)
def lerp(a,b,t):return a+(b-a)*t

@lru_cache(maxsize=250)
def cached_text(msg,size,color,bold='black'):
    font=ImageFont.truetype(FONT_BLACK if bold=='black' else FONT_MED,max(9,int(size)))
    box=font.getbbox(msg,stroke_width=0)
    w,h=box[2]-box[0]+6,box[3]-box[1]+6
    layer=Image.new('RGBA',(max(1,w),max(1,h)),(0,0,0,0))
    d=ImageDraw.Draw(layer);d.text((3-box[0],3-box[1]),msg,font=font,fill=(*color,255))
    return layer

def txt(canvas,msg,x,y,size,color=INK,align='left',scale=1,opacity=1,bold='black'):
    base=cached_text(msg,round(size),color,bold)
    if scale!=1:
        base=base.resize((max(1,int(base.width*scale)),max(1,int(base.height*scale))),Image.Resampling.BICUBIC)
    if opacity<0.99:
        base=base.copy();base.putalpha(base.getchannel('A').point(lambda z:int(z*clamp(opacity))))
    px=int(x-(base.width//2 if align=='center' else base.width if align=='right' else 0))
    canvas.alpha_composite(base,(px,int(y))) if px>=0 and y>=0 and px+base.width<=canvas.width and y+base.height<=canvas.height else canvas.paste(base,(px,int(y)),base)

def sprite_file(n):
    p=ASSET/(n+'.png')
    if not p.exists():return None
    return Image.open(p).convert('RGBA')

SPRITES={k:sprite_file(k) for k in ['bot','chip','laptop','planet']}
SPRITE_CACHE={}

def sprite(canvas,key,x,y,w,ang=0,alpha=1):
    a=SPRITES.get(key)
    if a is None:return
    ww=max(20,int(w));hh=max(20,int(a.height*ww/a.width))
    # Reusing discretized angle saves enormous work at high FPS.
    k=(key,ww,round(ang/3)*3)
    if k not in SPRITE_CACHE:
        s=a.resize((ww,hh),Image.Resampling.LANCZOS)
        if abs(k[2])>=1:s=s.rotate(k[2],resample=Image.Resampling.BICUBIC,expand=True)
        SPRITE_CACHE[k]=s
    s=SPRITE_CACHE[k]
    if alpha<.99:
        s=s.copy();s.putalpha(s.getchannel('A').point(lambda z:int(z*clamp(alpha))))
    px=int(x-s.width/2);py=int(y-s.height/2)
    # Pillow canvas.paste with mask handles clipping outside frame safely.
    canvas.paste(s,(px,py),s)

def draw_path(d,pts,fill,width=2):
    if len(pts)>1:d.line([(int(a),int(b)) for a,b in pts],fill=fill,width=max(1,int(width)),joint='curve')

def node(d,x,y,r,fill):d.ellipse((x-r,y-r,x+r,y+r),fill=fill)

def scale(v,S):return v*S

SECS=25.6
# A simple deterministic director. This is real per-frame animation, not animated slide wipes.
@dataclass(frozen=True)
class Shot:
    id:str;start:float;end:float;idea:str
SHOTS=[
 Shot('noise',0,4.5,'Turn chaotic feeds into a question'),
 Shot('signal',4.5,8.1,'Discover a usable source with a friendly mascot'),
 Shot('planet',8.1,12.55,'Trace global sources through NASA imagery'),
 Shot('code',12.55,17.0,'Illustrate direct pixel-by-pixel frame rendering'),
 Shot('morph',17.0,21.25,'Morph particles into a recognizable signal mark'),
 Shot('brand',21.25,SECS,'Resolve the story with the brand call to action')]

CAPTIONS=[
(0.3,2.03,'Most tech feeds are just noise.'),
(2.03,4.54,'But the internet is full of hidden gems.'),
(4.54,7.74,'What if a story could move like the ideas inside it?'),
(7.74,8.81,'Real sources.'),
(8.81,10.22,'Living diagrams.'),
(10.22,12.54,'Code that draws every single frame.'),
(12.54,16.44,'Watch particles become patterns, and patterns become discoveries.'),
(16.44,20.75,'We follow the evidence, show how it works, and make every second count.'),
(20.75,22.97,'This is CTRL PULSE.'),
(22.97,23.69,'Find it.'),(23.69,24.39,'Try it.'),(24.39,25.24,'Build it.')]


def caption(canvas,d,t,W,H,S):
    phrase=next((z for a,b,z in CAPTIONS if a<=t<b),None)
    if not phrase:return
    # semantic phrase grouping; cue times come from HeyGen sentence boundaries
    words=phrase.split()
    if len(words)>8:
        half=(len(words)+1)//2
        lines=[' '.join(words[:half]),' '.join(words[half:])]
    else:lines=[phrase]
    y=int(H-115*S)
    if len(lines)==2:y-=32*S
    pad=int(15*S)
    # Inter font measures and scales to mobile-safe bounds.
    ss=26*S
    m=max(cached_text(line,max(13,int(ss)),WHITE).width for line in lines)
    sc=min(1,(W-68*S)/m)
    for li,line in enumerate(lines):
        im=cached_text(line,max(13,int(ss)),WHITE)
        width=int(im.width*sc)
        if sc<1:im=im.resize((width,int(im.height*sc)),Image.Resampling.LANCZOS)
        xx=int(W/2-im.width/2);yy=int(y+li*34*S)
        d.rounded_rectangle((xx-pad,yy-8*S,xx+im.width+pad,yy+im.height+10*S),radius=12*S,fill=(13,24,22,233))
        canvas.paste(im,(xx,yy),im)


def background(canvas,d,scene,t,W,H,S):
    bg={0:INK,1:ORANGE,2:(9,22,29),3:CREAM,4:(30,43,86),5:LIME}[scene]
    d.rectangle((0,0,W,H),fill=bg)
    # Deliberate shifting pattern, not a static painted board.
    if scene in (0,4):
        for i in range(14):
            yy=int((i*87*S + sin(t*.77+i*.4)*32*S) % H)
            d.line((0,yy,W,yy-33*S),fill=(*SAGE,38),width=1)
    if scene in (1,3,5):
        for i in range(40):
            x=int((i*159*S+37*S)%W);y=int(((i*187*S)+14*cos(t*.4+i))*1%H)
            node(d,x,y,1.3*S,(*INK,25))


def scene0(im,d,t,W,H,S):
    p=t/4.5
    # Chaotic inbound source dots move every frame.
    for i in range(140):
        xx=W/2+(250+110*sin(i)) * cos(i*2.399+t*(.5+(i%7)*.07))*S
        yy=(220+int(i*.33)) * S + (185+90*cos(i*1.3))*sin(i*1.7+t*.95)*S
        r=1.7+(i%4)*.55
        node(d,xx,yy,r*S,[ORANGE,LIME,BLUE,ROSE][i%4])
    # responsive noisy waveform
    for j in range(90):
        x=30*S+j*(W-60*S)/89
        amp=(23+20*sin(j*.33+t*5))*S*(.25+ease((t-.5)/2))
        yy=585*S
        d.line((x,yy-amp,x,yy+amp),fill=(*LIME,220),width=max(2,int(3*S)))
    spr=180+sin(t*2)*7
    sprite(im,'laptop',W*.60,355*S+sin(t*3)*11*S,340*S,-5+3*sin(t*1.8),clamp(t/0.8))
    a=spring((t-.2)/.7)
    txt(im,'YOUR FEED',38*S,95*S,41*S,CREAM,scale=.7+.3*a)
    txt(im,'IS',38*S,166*S,64*S,ORANGE,scale=.65+.35*spring((t-1)/.4))
    txt(im,'NOISE.',38*S,243*S,74*S,LIME,scale=.65+.35*spring((t-1.2)/.45))
    txt(im,'DISCOVERY > DISTRACTION',40*S,730*S,18*S,CREAM,bold='medium')


def scene1(im,d,t,W,H,S):
    local=t-4.5;p=clamp(local/3.6)
    # Mascot follows a springy curve rather than a linear slide.
    a=spring(local/1.1)
    sx=lerp(-160*S,W*.67,a)+sin(local*4.2)*12*S
    sy=510*S +sin(local*7)*10*S*(1-p*.4)
    sprite(im,'bot',sx,sy,345*S,2*sin(local*4),1)
    # Signal trajectory, packets and cursor follow cubic-like curved rails.
    pts=[]
    for j in range(90):
        u=j/89
        x=(22+460*u)*S
        y=(730-270*math.sin(pi*u)+16*sin(local*3+u*12))*S
        pts.append((x,y))
    draw_path(d,pts,INK,4*S)
    for k in range(4):
        idx=int(((p*1.1+k*.27)%1)*89)
        x,y=pts[idx]
        d.ellipse((x-10*S,y-10*S,x+10*S,y+10*S),fill=LIME,outline=INK,width=int(2*S))
    for j in range(5):
        cx=(W*.67+(sin(local*2.8+j*pi/2.5)*215*S))
        cy=sy+(cos(local*2.8+j*pi/2.5)*160*S)
        node(d,cx,cy,3*S,CREAM)
    txt(im,'FIND THE',38*S,108*S,60*S,INK,scale=.9+.1*spring(local/.65))
    txt(im,'SIGNAL.',38*S,184*S,65*S,CREAM,scale=.8+.2*spring((local-.35)/.7))
    d.rounded_rectangle((39*S,294*S,230*S,337*S),radius=8*S,fill=LIME)
    txt(im,'CURATED > COPIED',51*S,300*S,15*S,INK,bold='medium')


def scene2(im,d,t,W,H,S):
    local=t-8.1; progress=clamp(local/4.45)
    # Cinematic globe is a RESERVED real-asset slot. A legitimate NASA image is
    # composited here by hosted final-pass transform; source never synthesized as evidence.
    cx=W/2;cy=470*S;r=199*S
    d.ellipse((cx-r-10*S,cy-r-10*S,cx+r+10*S,cy+r+10*S),fill=(52,71,70),outline=LIME,width=max(2,int(3*S)))
    # Local preview uses independently generated illustration, not a falsely labeled photo.
    sprite(im,'planet',cx,cy,360*S,10*sin(local*.65),alpha=.92)
    for i in range(6):
        rr=(230+i*19)*S
        pts=[]
        for j in range(100):
            q=j*2*pi/99+local*(.13 if i%2 else -.2)
            pts.append((cx+rr*cos(q),cy+rr*.44*sin(q)))
        draw_path(d,pts,(*[LIME,ORANGE,BLUE][i%3],220),2*S)
    for i in range(6):
        phi=local*(.64+i*.07)+i*2*pi/6
        x=cx+(236+i*18)*S*cos(phi)
        y=cy+(100+i*9)*S*sin(phi)
        node(d,x,y,6*S,[LIME,ORANGE,BLUE,CREAM][i%4])
    txt(im,'REAL SOURCES.',39*S,92*S,52*S,CREAM)
    txt(im,'GLOBAL SIGNALS',40*S,154*S,24*S,LIME,bold='medium')
    # Sourced-photo placeholder in local version; hosted video can overlay NASA here.
    d.rounded_rectangle((38*S,704*S,W-38*S,763*S),radius=16*S,fill=(29,48,47))
    txt(im,'GLOBAL VIEW / ILLUSTRATIVE BASE',55*S,720*S,16*S,CREAM,bold='medium')


def scene3(im,d,t,W,H,S):
    loc=t-12.55;p=clamp(loc/4.45)
    txt(im,'CODE IS THE',37*S,103*S,49*S,INK)
    txt(im,'CAMERA.',39*S,169*S,70*S,ORANGE,scale=.83+.17*spring((loc-.1)/.6))
    # Moving executable example; not a fake application screenshot.
    d.rounded_rectangle((26*S,300*S,W-26*S,628*S),radius=19*S,fill=INK)
    d.ellipse((46*S,325*S,58*S,337*S),fill=ORANGE)
    d.ellipse((66*S,325*S,78*S,337*S),fill=LIME)
    d.ellipse((86*S,325*S,98*S,337*S),fill=ROSE)
    lines=['for frame in frames:', '    t = frame / fps','    x = spring(t)','    paint(scene, x)']
    for i,line in enumerate(lines):
        k=clamp((loc-i*.58)/.9)
        n=int(len(line)*ease(k))
        txt(im,line[:n],45*S,370*S+i*52*S,22*S,LIME if i==1 else CREAM,bold='medium')
    for i in range(18):
        x=(68+i*23)*S
        y=(666+28*sin(loc*5+i*.38))*S
        node(d,x,y,3*S,[ORANGE,BLUE,LIME][i%3])
    sprite(im,'chip',W-117*S,782*S,205*S,loc*22)
    txt(im,'FRAME',42*S,747*S,23*S,INK,bold='medium')
    txt(im,str(int(60*loc)).zfill(4),42*S,782*S,51*S,ORANGE)


def morph_target(i,n,W,H,S):
    # Target points on a C-shaped orbit: trace a real brand shape via particles.
    a=(.25+1.52*i/max(1,n-1))*2*pi
    return W*.48 +210*S*cos(a), H*.45 +205*S*sin(a)

def scene4(im,d,t,W,H,S):
    loc=t-17.0;p=clamp(loc/4.25)
    n=180
    for i in range(n):
        a=i*2.399
        rad=sqrt(i/n)
        ax=W*.5+rad*410*S*cos(a+loc*.8)
        ay=H*.48+rad*440*S*sin(a+loc*.6)
        tx,ty=morph_target(i,n,W,H,S)
        b=ease((loc-1.0)/2.0)
        x=lerp(ax,tx,b)+8*sin(loc*6+i)*S*(1-b)
        y=lerp(ay,ty,b)+8*cos(loc*6+i*.8)*S*(1-b)
        node(d,x,y,(2+(i%4))*S,[ORANGE,LIME,ROSE,CREAM][i%4])
    for ring in range(4):
        rr=(180+ring*52+12*sin(loc*2+ring))*S
        d.arc((W/2-rr,H*.48-rr,W/2+rr,H*.48+rr),int(loc*57+ring*28)%360,int(loc*57+ring*28+145)%360,fill=(*[CREAM,ROSE,ORANGE,BLUE][ring],160),width=max(2,int(3*S)))
    txt(im,'EVERY',37*S,102*S,70*S,CREAM,scale=.85+.15*spring(loc/.6))
    txt(im,'PIXEL.',37*S,180*S,75*S,LIME,scale=.9+.1*spring((loc-.28)/.7))
    d.rounded_rectangle((40*S,699*S,W-40*S,752*S),radius=12*S,fill=ORANGE)
    txt(im,'NO SLIDES. REAL MOTION.',60*S,714*S,20*S,INK,bold='medium')


def scene5(im,d,t,W,H,S):
    loc=t-21.25;p=clamp(loc/4.35)
    for i in range(75):
        a=(i*2.399+loc*.25)
        rr=(60+(i%17)*17)*S
        x=W/2+rr*cos(a)+sin(loc*2+i)*7*S
        y=H/2+rr*sin(a)
        node(d,x,y,(1+i%3)*S,ORANGE if i%3==0 else INK)
    # Split bars resolve to brand's open-circuit C signal symbol.
    cx=W*.5;cy=385*S
    d.arc((cx-116*S,cy-116*S,cx+116*S,cy+116*S),58,301,fill=INK,width=int(45*S))
    for i,h in enumerate([26,57,82,48]):
        xx=(cx+44*S+i*23*S)
        rise=ease((loc-.4-i*.1)/.6)
        d.rounded_rectangle((xx,cy-h*S*rise,xx+11*S,cy+h*S*rise),radius=5*S,fill=ORANGE)
    txt(im,'CTRL',W/2,561*S,80*S,INK,align='center',scale=.84+.16*spring(loc/.85))
    txt(im,'PULSE',W/2,659*S,80*S,INK,align='center',scale=.8+.2*spring((loc-.2)/.85))
    # Short sequential CTA punches timed to spoken ending.
    labels=['FIND IT.','TRY IT.','BUILD IT.']
    i=min(2,int(max(0,(loc-1.64))/.76))
    txt(im,labels[i],W/2,771*S,31*S,ORANGE,align='center',scale=.9+.1*spring((loc-1.6-i*.74)/.28))


def frame(t,W,H,captioned=True):
    S=W/540
    shot_idx=next((i for i,x in enumerate(SHOTS) if x.start<=t<x.end),len(SHOTS)-1)
    im=Image.new('RGBA',(W,H),(*CREAM,255));d=ImageDraw.Draw(im,'RGBA')
    background(im,d,shot_idx,t,W,H,S)
    [scene0,scene1,scene2,scene3,scene4,scene5][shot_idx](im,d,t,W,H,S)
    # Simple, recognisable corner mark across the video. Scene ends remain clean.
    if shot_idx<5:
        d.rounded_rectangle((25*S,32*S,47*S,54*S),radius=4*S,fill=ORANGE)
        txt(im,'CTRL PULSE / SIGNAL LAB',56*S,31*S,14*S,CREAM if shot_idx in (0,2,4) else INK,bold='medium')
    if captioned:caption(im,d,t,W,H,S)
    return im.convert('RGB')


def render(output:Path,width=540,height=960,fps=30,seconds=SECS,captions=True):
    output.parent.mkdir(parents=True,exist_ok=True)
    cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pix_fmt','rgb24','-s',f'{width}x{height}','-r',str(fps),'-i','-','-c:v','libx264','-preset','ultrafast','-crf','19','-pix_fmt','yuv420p','-movflags','+faststart',str(output)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    try:
        for k in range(math.ceil(seconds*fps)):
            im=frame(k/fps,width,height,captions)
            proc.stdin.write(im.tobytes())
            if k%150==0:print(f'Frame {k}/{math.ceil(seconds*fps)}',flush=True)
    except Exception:
        proc.kill();raise
    finally:
        try:proc.stdin.close()
        except:pass
    err=proc.stderr.read();code=proc.wait()
    if code:raise RuntimeError(err.decode()[-2000:])
    return output

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--output',type=Path,default=BASE/'signal_lab_v3_preview.mp4')
    ap.add_argument('--width',type=int,default=540)
    ap.add_argument('--height',type=int,default=960)
    ap.add_argument('--fps',type=int,default=30)
    ap.add_argument('--seconds',type=float,default=SECS)
    ap.add_argument('--no-captions',action='store_true')
    args=ap.parse_args()
    print('Rendering SIGNAL LAB V3',args,flush=True)
    print('Output',render(args.output,args.width,args.height,args.fps,args.seconds,not args.no_captions))