"""Original event-driven sound design for CTRL Pulse editorial reel.
All sound waves are deterministic and generated locally; no copyrighted loops.
Creates a genuine stereo designed soundtrack. The externally generated natural
narration URL remains separate until the host can ingest its media bytes.
"""
from __future__ import annotations
import argparse, json, math, wave
from pathlib import Path
import numpy as np
BASE=Path(__file__).resolve().parents[1]
RATE=48000;DURATION=27.5
N=int(DURATION*RATE)
R=np.random.default_rng(20261113)
sound=np.zeros((N,2),dtype=np.float64)
EVENTS=[]
def mix(data,at=0,pan=0,gain=1.0,name='sfx'):
 start=int(at*RATE);stop=min(N,start+len(data));
 if start<0 or stop<=start:return
 x=data[:stop-start]*gain
 if np.ndim(x)==1:
  sound[start:stop,0]+=x*math.sqrt((1-pan)/2)
  sound[start:stop,1]+=x*math.sqrt((1+pan)/2)
 else:sound[start:stop]+=x
 EVENTS.append({'time':round(at,2),'type':name,'gain':gain,'pan':pan})
def env(d,atk=.018,rel=.15):
 n=int(d*RATE);q=np.arange(n)/RATE
 return np.minimum(1,q/max(atk,.0001))*np.minimum(1,(d-q)/max(rel,.0001))
def tone(freq,d=.30,amp=.12):
 q=np.arange(int(d*RATE))/RATE
 return amp*np.sin(2*np.pi*freq*q)*env(d,.011,.12)
def blip(at,root=560,d=.12,pan=0,gain=1):
 tt=np.arange(int(d*RATE))/RATE
 ph=2*np.pi*(root*tt+140*tt*tt)
 x=.11*np.sin(ph)*np.exp(-11*tt)+.03*np.sin(2*ph)*np.exp(-18*tt)
 mix(x,at,pan,gain,'data_blip')
def bass(at,sub=73,gain=1):
 d=.42;q=np.arange(int(d*RATE))/RATE;ph=2*np.pi*(sub*q+60*(1-np.exp(-13*q))/13)
 x=.20*np.sin(ph)*np.exp(-8*q)+.024*R.standard_normal(len(q))*np.exp(-55*q)
 mix(x,at,0,gain,'kick_low')
def whoosh(at,d=.46,gain=1.0,pan=0):
 n=int(d*RATE);q=np.arange(n)/RATE
 noise=R.standard_normal(n)
 # Finite impulse smoothed colored noise, fast onset / sharp fall.
 filt=np.convolve(noise,np.ones(80)/80,mode='same')
 win=(np.sin(np.pi*q/d)**1.6)
 mix((filt*.16+noise*.018)*win,at,pan,gain,'whoosh')
def error(at):
 d=.56;q=np.arange(int(d*RATE))/RATE
 n=.056*R.standard_normal(len(q));n*=np.exp(-5*q)
 sq=np.sign(np.sin(2*np.pi*(200-55*q)*q))
 x=(.14*sq+.5*n)*np.exp(-7*q)
 mix(x,at,.18,1,'disconnect')
def shimmer(at,pan=0):
 d=.56;q=np.arange(int(d*RATE))/RATE
 x=(.078*np.sin(2*np.pi*660*q)+.055*np.sin(2*np.pi*990*q)+.03*np.sin(2*np.pi*1320*q))*np.exp(-7*q)
 mix(x,at,pan,.9,'completion')

# Harmonic original score: slow moving D minor/A minor tone with controlled modulation.
t=np.arange(N)/RATE
amp=(.56+.20*np.sin(2*np.pi*.065*t))
chord=(np.sin(2*np.pi*73.416*t)*.011 + np.sin(2*np.pi*110*t)*.012 + np.sin(2*np.pi*174.614*t)*.006 + np.sin(2*np.pi*261.626*t)*.003)
chord*=amp*(np.minimum(1,t/1.1))*(np.minimum(1,(DURATION-t)/2.0))
sound[:,0]+=chord; sound[:,1]+=chord*np.sin(.35+2*np.pi*.12*t)*.22 + chord*.72
# Subtle dotted tempo motifs. Keep space for narration.
for k in np.arange(.65,27.0,1.75):
 blip(float(k),root=490+(int(k*2)%4)*65,d=.08,pan=-.28 if int(k)%2 else .28,gain=.31)
for at in [0.08,3.48,7.60,11.50,15.97,21.62,26.7]:bass(at,sub=62 if at>11 else 74,gain=.78 if at>0 else 1.05)
for at in [3.37,7.52,11.41,15.90,21.56]:whoosh(at,d=.34,gain=.85)
for at in [1.3,4.78,5.20,5.58,8.50,9.02,9.51,17.1,17.62,18.10]:blip(at,root=690,pan=-.50 if int(at)%2 else .50,gain=.70)
error(12.98);error(15.72)
for at in [18.65,19.15,19.7]:blip(at,root=330,d=.12,pan=-.24,gain=.95)
shimmer(22.7,.25);shimmer(24.04,-.12);whoosh(26.50,.3,.50)
# Master without overshooting true-peak margin; final AAC -14 LUFS target is a separate finalizer.
peak=np.max(abs(sound));sound=sound*min(1,.78/max(peak,1e-6))
out=BASE/'assets/score_sfx_stereo.wav';out.parent.mkdir(parents=True,exist_ok=True)
with wave.open(str(out),'wb') as w:
 w.setnchannels(2);w.setsampwidth(2);w.setframerate(RATE)
 w.writeframes((np.clip(sound,-1,1)*32767).astype('<i2').tobytes())
(BASE/'assets/sound_events.json').write_text(json.dumps(EVENTS,indent=2))
print('Wrote original score and SFX',out,'peak',peak,'event_count',len(EVENTS))