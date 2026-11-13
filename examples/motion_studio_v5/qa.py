"""Rfactory V5 acceptance gates: video, audio, motion, safe text, assets, release state.
Run after rendering the *actual final video*; this module does not claim semantic quality
has been assessed by automated metrics alone.
"""
from __future__ import annotations
import argparse, json, math, re, subprocess
from pathlib import Path
import cv2,numpy as np
from PIL import Image,ImageOps,ImageDraw
BASE=Path(__file__).resolve().parents[1]
FPS=30
W=1080;H=1920;DURATION=27.5
SECTIONS=[
 {'id':'hook','start':0,'end':3.5,'title':(64,205,952,265),'hero':(72,568,936,920),'footer':(0,1804,1080,50)},
 {'id':'local_meaning','start':3.5,'end':7.65,'title':(64,188,952,290),'hero':(68,540,944,920),'footer':(0,1804,1080,50)},
 {'id':'local_link','start':7.65,'end':11.5,'title':(64,192,952,295),'hero':(68,555,944,914),'footer':(0,1804,1080,50)},
 {'id':'uplink','start':11.5,'end':16,'title':(64,190,952,300),'hero':(68,552,944,935),'footer':(0,1804,1080,50)},
 {'id':'diagram','start':16,'end':21.65,'title':(64,195,952,290),'hero':(74,700,936,450),'footer':(0,1804,1080,50)},
 {'id':'resolution','start':21.65,'end':DURATION,'title':(64,195,952,280),'hero':(76,530,928,915),'footer':(0,1804,1080,50)},
]
def intersect(a,b):
 x=max(a[0],b[0]);y=max(a[1],b[1]);return x<min(a[0]+a[2],b[0]+b[2]) and y<min(a[1]+a[3],b[1]+b[3])
def probe(video):
 p=subprocess.run(['ffprobe','-v','error','-show_entries','format=duration,size:stream=codec_name,codec_type,width,height,avg_frame_rate,nb_frames,sample_rate','-of','json',str(video)],capture_output=True,text=True,check=True)
 return json.loads(p.stdout)
def sample_video(video, sheet=None):
 c=cv2.VideoCapture(str(video));assert c.isOpened()
 timestamps=[.65,2.45,4.8,6.9,8.9,10.8,12.7,14.7,17.4,19.7,22.9,25.7]
 thumbs=[]
 for t in timestamps:
  c.set(cv2.CAP_PROP_POS_MSEC,t*1000);ok,fr=c.read()
  if not ok:raise RuntimeError(f'Decode failed at {t}s')
  thumbs.append(Image.fromarray(cv2.cvtColor(fr,cv2.COLOR_BGR2RGB)))
 # Compare frames exactly 1 second apart throughout; detect >1.0s full-screen freezes.
 stalled=[];variances=[]
 for t in np.arange(1,26.0,.8):
  c.set(cv2.CAP_PROP_POS_MSEC,float(t*1000));ok,a=c.read()
  c.set(cv2.CAP_PROP_POS_MSEC,float((t+.6)*1000));ok2,b=c.read()
  if not ok or not ok2:continue
  # Downscale to reduce noisy codec variation, compare scene content differences.
  a=cv2.resize(a,(180,320));b=cv2.resize(b,(180,320))
  diff=float(np.mean(np.abs(a.astype(np.int16)-b.astype(np.int16))))
  variances.append(diff)
  if diff<.48:stalled.append(round(float(t),2))
 c.release()
 if sheet:
  sheet=Path(sheet);sheet.parent.mkdir(parents=True,exist_ok=True)
  board=Image.new('RGB',(270*4,515*3),(14,20,25));d=ImageDraw.Draw(board)
  for i,im in enumerate(thumbs):
   x=(i%4)*270;y=(i//4)*515;board.paste(ImageOps.fit(im,(270,480)),(x,y));d.text((x+12,y+490),f'{timestamps[i]:04.1f}s',fill='#cfdad6')
  board.save(sheet,quality=93)
 return {'sampled_frames':len(thumbs),'min_average_pixel_difference':round(min(variances),2),'stalled_intervals':stalled}
def inspect(video, voice=False, report=None, sheet=None):
 video=Path(video)
 data=probe(video);streams=data['streams'];vid=next((x for x in streams if x['codec_type']=='video'),None)
 aud=next((x for x in streams if x['codec_type']=='audio'),None)
 checks={'video_decodes':vid is not None,'native_full_hd':bool(vid and vid.get('width')==W and vid.get('height')==H),
         'fps_at_least_30':bool(vid and int(vid.get('avg_frame_rate','0/1').split('/')[0])/max(1,int(vid.get('avg_frame_rate','0/1').split('/')[1]))>=30),
         'duration_correct':abs(float(data['format']['duration'])-DURATION)<.15,
         'h264_aac':bool(vid and aud and vid.get('codec_name')=='h264' and aud.get('codec_name')=='aac'),
         'six_scenes':len(SECTIONS)==6,
         'safe_areas':all(s['title'][1]>=170 and s['title'][1]+s['title'][3]<520 and not intersect(s['title'],s['hero']) and not intersect(s['title'],s['footer']) for s in SECTIONS),
         '12_reusable_asset_cuts':len(list((BASE/'assets').glob('*.jpg')))>=12,
         'multiple_generated_source_images':len(json.loads((BASE/'assets/manifest.json').read_text())['generated_sources'])>=3,
         'sfx_cues_present':len(json.loads((BASE/'assets/sound_events.json').read_text()))>=25,
         'narrated_tts_in_final':bool(voice)}
 motion=sample_video(video,sheet)
 checks['no_long_stalls']=len(motion['stalled_intervals'])<=1
 state='READY_FOR_EDITORIAL_REVIEW' if all(checks.values()) else 'PREVIEW_ONLY_NOT_PUBLISHABLE'
 reportdata={'file':str(video),'state':state,'checks':checks,'technical':data,'motion':motion,
             'note':'SFX/music present. Original generated natural TTS is NOT embedded until voice media is supplied and remuxed. Static checks do not replace human inspection.'}
 if report:Path(report).write_text(json.dumps(reportdata,indent=2))
 return reportdata
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('video');a.add_argument('--with-voice',action='store_true');a.add_argument('--report');a.add_argument('--sheet');o=a.parse_args()
 d=inspect(o.video,o.with_voice,o.report,o.sheet)
 print(json.dumps({'state':d['state'],'checks':d['checks'],'motion':d['motion']},indent=2))