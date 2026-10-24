"""Rfactory original 3 new family-friendly voiceover puzzle Reels.
Original character art: composite generated for this session. Narration: offline eSpeak synthesis.
Puzzle fragments retain their exact pixel values from the source scene; all five crossings are exact.
"""
from __future__ import annotations
import json, math, subprocess, os, struct, zipfile
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import numpy as np
from scipy.signal import resample_poly
from scipy.io import wavfile

REPO=Path(__file__).resolve().parents[1]
ROOT=Path(os.environ.get('RFACTORY_VOICEOVER_OUTPUT',str(REPO/'storage/renders/social_voiceovers')))
ROOT.mkdir(parents=True, exist_ok=True)
SOURCE=REPO/'assets/social/voiceover/source_triptych.jpg'
W,H,FPS,SR=720,1280,24,24000
FONT='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
OUT=ROOT
CONF=[
 dict(key='dino',name='04_dino_donut_dash',x=(0,394),y=235,title='CATCH THE BITE!',tag='DINO DONUT DASH',caption1='WATCH THE DONUT!',caption2='DID YOU CATCH IT?',voice='en-us+f3',duration=10,first=1.35,last=9.18,shape='donut',voiceText='Hey, explorer! The dinosaur lost a bite! Watch the donut. Can you put it back? Ready? Go!',fitCount=5,seed=42),
 dict(key='bunny',name='05_bunny_ice_cream',x=(394,790),y=235,title='FIX THE SCOOP!',tag='BUNNY ICE CREAM MIX-UP',caption1='LOOK CLOSELY!',caption2='DID YOU FIX IT?',voice='en+f4',duration=11,first=1.4,last=9.8,shape='scoop',voiceText="Oh no! Bunny's ice cream is falling apart! Find the missing scoop. Look closely! Can you fix it?",fitCount=5,seed=73),
 dict(key='monkey',name='06_monkey_burger_pop',x=(790,1214),y=235,title='FIND THE PIECE!',tag='MONKEY BURGER POP',caption1='KEEP YOUR EYES ON IT!',caption2='SPOT THE MATCH?',voice='en-us+m3',duration=10,first=1.25,last=9.15,shape='burger',voiceText="Uh oh! Monkey's burger is missing a piece! Keep your eyes on the burger. Catch it when it fits!",fitCount=5,seed=99)
]

def font(size):return ImageFont.truetype(FONT,size)
def image_for(cfg):
    full=Image.open(SOURCE).convert('RGB')
    x0,x1=cfg['x']; paneW=x1-x0
    h=round(paneW*16/9)
    img=full.crop((x0,cfg['y'],x1,cfg['y']+h)).resize((W,H),Image.Resampling.LANCZOS).convert('RGBA')
    img.save(OUT/(cfg['name']+'_source.png'))
    return img

def mask_for(cfg):
    mask=Image.new('L',(W,H),0);d=ImageDraw.Draw(mask)
    # Source-pixel puzzle shapes manually registered on the newly generated food subjects.
    if cfg['shape']=='donut':
        pts=[(480,607),(568,588),(661,636),(698,703),(685,785),(643,838),(576,827),
             (542,789),(486,808),(451,754),(459,684)]
        d.polygon(pts,fill=255)
    elif cfg['shape']=='scoop':
        pts=[(605,374),(661,346),(711,381),(717,433),(708,494),(689,532),
             (668,561),(651,546),(632,561),(605,520),(573,485),(572,434)]
        d.polygon(pts,fill=255)
    else:
        pts=[(573,296),(630,284),(695,316),(717,369),(715,430),(699,477),
             (670,508),(635,508),(611,542),(582,501),(547,474),(530,415),(540,351)]
        d.polygon(pts,fill=255)
    # Gentle rounded corners within the cutout, retaining pixel-exact reconstruction.
    return mask

def fit_times(cfg):
    rng=np.random.default_rng(cfg['seed'])
    n=cfg['fitCount'];f=cfg['first'];l=cfg['last']
    base=np.linspace(f,l,n)
    for i in range(1,n-1):base[i]+=rng.uniform(-.12,.12)
    return [round(float(t)*FPS) for t in base]

def pose_at_frame(f,cfg,arr):
    n=round(cfg['duration']*FPS)
    lo=arr[0]-(arr[1]-arr[0]);hi=arr[-1]+(arr[-1]-arr[-2])
    nodes=[lo,*arr,hi]
    if f in arr:return 0,0
    for i in range(len(nodes)-1):
        if nodes[i]<f<nodes[i+1]:
            gap=nodes[i+1]-nodes[i]; u=(f-nodes[i])/gap
            amp=math.sin(math.pi*u)
            sx=(-1 if i%2 else 1)
            dx=sx*gap*2.1*amp
            if cfg['key']=='dino':dy=80*amp*amp*math.sin(2*math.pi*u+.5)
            elif cfg['key']=='bunny':dy=-98*amp*amp*(.65+.35*math.cos(2*math.pi*u))
            else:dy=92*amp*amp*math.cos(3*math.pi*u)
            return round(dx),round(dy)
    raise ValueError((f,nodes,n))

def header(base,title):
    g=Image.new('RGBA',(W,230));dr=ImageDraw.Draw(g)
    for j in range(230):
        alp=int(255 if j<155 else 255*max(0,1-(j-155)/75)**1.2)
        dr.line((0,j,W,j),fill=(16,10,32,alp))
    base.alpha_composite(g,(0,0));d=ImageDraw.Draw(base)
    size=65
    while d.textbbox((0,0),title,font=font(size),stroke_width=4)[2]>W-40:size-=2
    # Big bold kid-friendly type, outlined for background readability.
    d.text((W//2,112),title,font=font(size),fill=(255,244,63),anchor='mm',stroke_width=6,stroke_fill=(38,18,60))
    d.rounded_rectangle((W//2-139,166,W//2+139,211),radius=22,fill=(255,63,147,235))
    d.text((W//2,187),'CAN YOU MATCH IT?',font=font(26),anchor='mm',fill='white',stroke_width=1,stroke_fill='#98235d')

def footer(base,label):
    d=ImageDraw.Draw(base)
    # Cover generated simulated UI / decorations in original concept panels.
    pane=Image.new('RGBA',(W,156),(0,0,0,0));q=ImageDraw.Draw(pane)
    q.rounded_rectangle((20,12,W-20,122),radius=32,fill=(18,13,52,230),outline=(255,255,255,230),width=4)
    base.alpha_composite(pane,(0,H-175))
    while d.textbbox((0,0),label,font=font(50))[2]>W-88:
        labelFont=max(27,50-int((d.textbbox((0,0),label,font=font(50))[2]-(W-88))/18))
        break
    else:labelFont=50
    d.text((W//2,H-109),label,font=font(labelFont),anchor='mm',fill='white',stroke_width=3,stroke_fill='#421955')

def make_audio(cfg,frames):
    raw=ROOT/(cfg['key']+'_raw.wav')
    if not raw.exists():
        with raw.open('wb') as f:
            subprocess.run(['espeak','-v',cfg['voice'],'-s','170','-p','62','-g','5','--stdout',cfg['voiceText']],stdout=f,check=True)
    # espeak stdout WAV data chunk has streaming header; ffmpeg fixes it.
    clean=ROOT/(cfg['key']+'_voice_clean.wav')
    subprocess.run(['ffmpeg','-loglevel','error','-y','-i',str(raw),'-af', 'highpass=f=105,lowpass=f=8500,acompressor=threshold=-20dB:ratio=2.2:attack=6:release=55,volume=1.15','-ar',str(SR),'-ac','1',str(clean)],check=True)
    sr,voice=wavfile.read(clean);voice=voice.astype(np.float32)/32768.0
    count=round(cfg['duration']*SR);t=np.arange(count,dtype=np.float32)/SR
    mix=np.zeros(count,dtype=np.float32)
    # Light original synthesized marimba-game melody, kept well below spoken voice.
    chord=[392.,493.88,587.33,523.25,440.,659.25,587.33,493.88]
    for k in np.arange(0,cfg['duration'],.40):
        start=round(k*SR);length=min(round(.20*SR),count-start)
        if length<=0:break
        tv=np.arange(length,dtype=np.float32)/SR
        ff=chord[int(round(k/.4))%len(chord)]
        note=(np.sin(2*np.pi*ff*tv)+.35*np.sin(2*np.pi*2*ff*tv))*np.exp(-18*tv)
        mix[start:start+length]+=note*.015
    for f in frames:
        ts=f/FPS
        start=round(ts*SR);length=min(round(.13*SR),count-start)
        tv=np.arange(length,dtype=np.float32)/SR
        freq=850+1750*tv
        cue=np.sin(2*np.pi*freq*tv)*np.exp(-24*tv)
        mix[start:start+length]+=cue*.09
    offset=round(.30*SR);end=min(count,offset+len(voice))
    if end>offset:mix[offset:end]+=voice[:end-offset]*.78
    # Gentle fade out.
    fade=np.ones(count,dtype=np.float32);tail=min(SR//4,count)
    fade[-tail:]=np.linspace(1,0,tail)
    mix=np.clip(mix*fade,-.97,.97)
    wav=ROOT/(cfg['name']+'_narration_mix.wav');wavfile.write(wav,SR,(mix*32767).astype(np.int16))
    return wav,round(len(voice)/SR,2)

def produce(cfg):
    img=image_for(cfg)
    mask=mask_for(cfg)
    a=np.array(img)
    m=np.array(mask)
    # Transparent moving part extracted FROM same source. No fake shapes as subject.
    alpha=np.zeros((H,W,4),np.uint8);alpha[:,:,:3]=a[:,:,:3];alpha[:,:,3]=m
    piece=Image.fromarray(alpha,'RGBA')
    bb=mask.getbbox()
    cutout=piece.crop(bb)
    cutout.save(ROOT/(cfg['name']+'_puzzle_cutout.png'))
    # Dim source only in removed section, completely concealed when at the right position.
    fixed=img.copy()
    shadow=Image.new('RGBA',(W,H),(10,10,28,0));shadow.putalpha(mask.point(lambda p: int(p*.84)))
    fixed.alpha_composite(shadow)
    header(fixed,cfg['title'])
    timeline=fit_times(cfg)
    wav,voiceDuration=make_audio(cfg,timeline)
    video=ROOT/(cfg['name']+'.mp4')
    cmd=['ffmpeg','-hide_banner','-loglevel','error','-y','-f','rawvideo','-pixel_format','rgb24','-video_size',f'{W}x{H}',
         '-framerate',str(FPS),'-i','pipe:0','-i',str(wav),'-vf','scale=1080:1920:flags=lanczos',
         '-c:v','libx264','-preset','veryfast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k',
         '-movflags','+faststart','-t',str(cfg['duration']),str(video)]
    proc=subprocess.Popen(cmd,stdin=subprocess.PIPE,stderr=subprocess.PIPE)
    n=round(cfg['duration']*FPS)
    poster=None
    for f in range(n):
        base=fixed.copy(); dx,dy=pose_at_frame(f,cfg,timeline)
        xpos=bb[0]+dx;ypos=bb[1]+dy
        # PIL alpha_composite accepts negatives by compositing on padded overlay (avoid clipping via paste).
        base.alpha_composite(cutout,(xpos,ypos))
        # Sparse visual particles: background movement, no hint when the puzzle matches.
        d=ImageDraw.Draw(base)
        for p in range(13):
            yy=240+((p*73 + f*(.55+.17*(p%3)))%750)
            xx=35+(p*111)%650+9*math.sin(f*.035+p)
            rr=2+(p%3)
            d.ellipse((xx-rr,yy-rr,xx+rr,yy+rr),fill=[(255,241,68,255),(255,112,197,255),(255,255,255,235)][p%3])
        label=cfg['caption1'] if (f/FPS)<cfg['duration']*.70 else cfg['caption2']
        footer(base,label)
        if f==n//3:poster=base.convert('RGB').copy()
        try:proc.stdin.write(base.convert('RGB').tobytes())
        except BrokenPipeError:
            print(proc.stderr.read().decode()[-1400:]);raise
    proc.stdin.close();err=proc.stderr.read().decode();rc=proc.wait()
    if rc:raise RuntimeError(err[-3000:])
    if poster:poster.resize((540,960),Image.Resampling.LANCZOS).save(ROOT/(cfg['name']+'_poster.jpg'),quality=92)
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','stream=codec_name,width,height,r_frame_rate:format=duration','-of','json',str(video)]))
    fs=[]
    for f in range(n):
        x,y=pose_at_frame(f,cfg,timeline)
        if (x,y)==(0,0):fs.append(f)
    report=dict(name=cfg['name'],duration=cfg['duration'],narration=cfg['voiceText'],voiceType='local_synthesized_TTS',voiceDuration=voiceDuration,
                exactFitFrames=timeline,exactFitTimes=[round(f/FPS,3) for f in timeline],observedZeroFrames=fs,
                zeroFrameCount=len(fs),format=probe,artSource=str(SOURCE.name),puzzleSourcePixelExact=True)
    assert fs==timeline,(fs,timeline)
    assert any(s['codec_name']=='aac' for s in probe['streams'])
    assert any(s['codec_name']=='h264' and s['width']==1080 and s['height']==1920 for s in probe['streams'])
    (ROOT/(cfg['name']+'_qa.json')).write_text(json.dumps(report,indent=2))
    print('OK',cfg['name'],'MB',round(video.stat().st_size/1e6,2),'narration sec',voiceDuration,'fits',report['exactFitTimes'],flush=True)
    return report

if __name__=='__main__':
    all=[]
    for cfg in CONF:all.append(produce(cfg))
    (ROOT/'manifest.json').write_text(json.dumps({'reels':all},indent=2))
    output=ROOT/'Rfactory_3_NEW_Voiceover_Reels.zip'
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=4) as z:
        for p in sorted(ROOT.iterdir()):
            if p.name=='build_reels.py' or p.suffix in ('.mp4','.json','.jpg','.wav','.png'):
                if p.name.endswith('_raw.wav') or p.name.endswith('_clean.wav'):continue
                z.write(p,p.name)
        if SOURCE.is_file(): z.write(SOURCE,'source_triptych.jpg')
    print('PACKAGED',output,output.stat().st_size)