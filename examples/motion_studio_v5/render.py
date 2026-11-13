"""Rfactory seekable HTML/Canvas capture (no external JS packages).

Uses system Chromium via Python Playwright, FFmpeg for deterministic Full HD.
The renderer never sleeps to advance animation; each timestamp is explicitly sought.
"""
from __future__ import annotations
import argparse, asyncio, subprocess, time, os, math, json, base64
from pathlib import Path
from PIL import Image, ImageDraw, ImageOps
from io import BytesIO
from playwright.async_api import async_playwright
BASE=Path(__file__).resolve().parents[1]
APP='http://127.0.0.1:8765/src/studio.html'
FPS=30
DURATION=27.5
W=1080;H=1920
TIMES=(.8,2.25,4.7,6.7,8.7,10.4,12.6,14.6,17.2,19.9,22.4,25.3)

async def capture(kind='sheet',dest=None,quick=False,start_frame=0,num_frames=None):
 names=['router_beauty','phone_hand','network_diorama','router_macro','phone_product','server_diorama','router_uplink','phone_detailed','network_earth','node_router','node_phone','node_server']
 embedded={n:'data:image/jpeg;base64,'+base64.b64encode((BASE/'assets'/f'{n}.jpg').read_bytes()).decode() for n in names}
 html=(BASE/'src/studio.html').read_text().replace("im.src='../assets/'+n+'.jpg'",'im.src=window.embeddedAssets[n]')
 html=html.replace('<script>', '<script>window.embeddedAssets='+json.dumps(embedded)+'</script><script>',1)
 async with async_playwright() as p:
  browser=await p.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-dev-shm-usage','--disable-gpu','--font-render-hinting=none'])
  page=await browser.new_page(viewport={'width':W,'height':H},device_scale_factor=1)
  await page.set_content(html,wait_until='load');await page.wait_for_function('window.assetsLoaded===true',timeout=30000)
  if kind=='sheet':
   sel=TIMES
   if dest is None:dest=BASE/'review/contact_v5.jpg'
   dest=Path(dest);dest.parent.mkdir(exist_ok=True,parents=True)
   thumb=(270,480);sheet=Image.new('RGB',(thumb[0]*4,(thumb[1]+34)*3),(12,22,28));dr=ImageDraw.Draw(sheet)
   for i,t in enumerate(sel):
    await page.evaluate('(t)=>window.renderAt(t)',t)
    bs=await page.screenshot(type='jpeg',quality=87,animations='disabled')
    im=Image.open(BytesIO(bs)).convert('RGB');im=ImageOps.fit(im,thumb)
    x=(i%4)*thumb[0];y=(i//4)*(thumb[1]+34);sheet.paste(im,(x,y))
    dr.text((x+10,y+thumb[1]+8),f'{t:04.1f}s',fill=(210,220,230))
   sheet.save(dest,quality=92)
   print('Contact:',dest)
  else:
   if dest is None:dest=BASE/'CTRL_PULSE_WiFi_Not_Internet_V5_SILENT.mp4'
   dest=Path(dest);dest.parent.mkdir(exist_ok=True,parents=True)
   cmd=['ffmpeg','-y','-loglevel','error','-f','image2pipe','-vcodec','mjpeg','-framerate',str(FPS),'-i','pipe:0','-an','-c:v','libx264','-preset','veryfast','-crf','19','-pix_fmt','yuv420p','-r',str(FPS),'-movflags','+faststart',str(dest)]
   proc=subprocess.Popen(cmd,stdin=subprocess.PIPE)
   n=num_frames if num_frames is not None else (150 if quick else int(FPS*DURATION))
   start=time.monotonic()
   try:
    for i in range(n):
     await page.evaluate('(t)=>window.renderAt(t)',(start_frame+i)/FPS)
     frame=await page.screenshot(type='jpeg',quality=89,animations='disabled')
     proc.stdin.write(frame)
     if i%90==0:print(f'Frame {start_frame+i}/{start_frame+n} {time.monotonic()-start:.1f}s',flush=True)
   finally:
    proc.stdin.close();rc=proc.wait()
   if rc:raise RuntimeError('FFmpeg failed with '+str(rc))
   print('Rendered:',dest,'in',round(time.monotonic()-start,1),'seconds')
  await browser.close()

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['sheet','video'],default='sheet');ap.add_argument('--out');ap.add_argument('--quick',action='store_true');ap.add_argument('--start-frame',type=int,default=0);ap.add_argument('--num-frames',type=int,default=None);a=ap.parse_args()
 asyncio.run(capture(a.mode,a.out,a.quick,a.start_frame,a.num_frames))