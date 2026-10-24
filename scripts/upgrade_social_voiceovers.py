#!/usr/bin/env python3
"""Expressive puzzle narration with *verified* provider provenance.

Providers:
  gemini: actual Gemini neural TTS; require explicit API key/network and --allow-paid-tts.
  wav: audio supplied by a genuine external voice provider or recorded actor.
  offline-preview: sentence-level eSpeak prosody, NEVER labelled neural audio.

Video frames are preserved by FFmpeg stream copy. No visual puzzle retiming.
"""
from __future__ import annotations
import argparse
import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave
from dataclasses import dataclass
import numpy as np
from scipy.io import wavfile

SR = 24000
SPEECH = {
    '04_dino_donut_dash': {
        'duration':10, 'voice':'Puck', 'offline':'en-us+f3', 'start':[0.43,3.43,6.62],
        'lines': ['Whoa! Dino lost a bite!', 'Watch that donut!', 'Can you catch the missing piece?'],
        'styles':['Genuinely surprised, wide-eyed and animated; warm, not shouting.',
                  'Playfully excited, fast but clearly articulated, with a curious rise.',
                  'Inviting game-show challenge, smiling, gently suspenseful on "catch".'],
        'rates': [166,183,177], 'pitches':[67,76,71],
    },
    '05_bunny_ice_cream': {
        'duration':11,'voice':'Aoede','offline':'en-us+f4','start':[0.44,3.57,7.26],
        'lines':["Oh no! Bunny's ice cream is slipping!",'Keep your eyes on the scoop!', 'Can you fix it? Go, go, go!'],
        'styles':['Soft but expressive concern, curious and playful, not panicked.',
                  'Bright gentle encouragement, slightly hushed as if sharing a secret.',
                  'Cheery countdown energy with crisp individual "go" beats.'],
        'rates':[169,179,181],'pitches':[71,75,80],
    },
    '06_monkey_burger_pop': {
        'duration':10,'voice':'Kore','offline':'en-us+m3','start':[0.40,3.42,6.62],
        'lines':['Hey! Monkey needs his burger!', 'See that flying piece?', 'Catch it when it fits!'],
        'styles':['Energetic grin and friendly surprise, playful emphasis on "Monkey".',
                  'Curious, conspiratorial, lively upward question tone.',
                  'Exciting playful challenge; concise, punchy, confident ending.'],
        'rates':[170,173,184],'pitches':[67,71,78],
    },
}

def shell(cmd, *, capture=True):
    return subprocess.run(cmd, check=True, capture_output=capture, text=not capture)


def wav_seconds(path):
    with wave.open(str(path),'rb') as w:
        return w.getnframes()/w.getframerate()


def get_duration_from_probe(path):
    return json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries','format=duration','-of','json',str(path)]))['format']['duration']


def decoded_voice(path:Path):
    # Normalise source to mono WAV 24 kHz PCM; provider outputs can vary.
    with tempfile.TemporaryDirectory() as tmp:
        intermediate=Path(tmp)/'voice.wav'
        shell(['ffmpeg','-loglevel','error','-y','-i',str(path),'-ar',str(SR),'-ac','1',
               '-af','highpass=f=85,lowpass=f=10200,acompressor=threshold=-22dB:ratio=2.0:attack=12:release=140',
               '-c:a','pcm_s16le',str(intermediate)])
        fs,raw=wavfile.read(intermediate)
    assert fs==SR
    x=raw.astype(np.float32)/32768.
    if x.size<SR//5 or not np.all(np.isfinite(x)):
        raise ValueError(f'Invalid/empty audio from {path}')
    # Mild peak normalisation + soft saturation; preserve dynamic expression.
    peak=max(1e-6,float(np.max(np.abs(x))))
    x=np.tanh((x/max(.50,peak))*.72)
    return x.astype(np.float32)


def offline_preview(text, voice, rate, pitch, output):
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        raw=Path(tmp)/'tts_raw.wav'
        with raw.open('wb') as f:
            subprocess.run(['espeak','--stdout','-v',voice,'-s',str(rate),'-p',str(pitch),'-g','5',text],stdout=f,check=True)
        shell(['ffmpeg','-loglevel','error','-y','-i',str(raw),'-ac','1','-ar',str(SR),
               '-c:a','pcm_s16le',str(output)])


def real_gemini(text, style, voice, output, *, model='gemini-3.8-flash-lite-tts'):
    if not (os.environ.get('GEMINI_API_KEY') or os.environ.get('GOOGLE_API_KEY')):
        raise RuntimeError('GEMINI_API_KEY/GOOGLE_API_KEY not configured; no neural voice produced')
    os.environ['RFACTORY_AI_ENABLED']='true'
    try:
        from services.ai.studio import GeminiCreativeStudio, VoiceBrief
    except ImportError as exc:
        raise RuntimeError('Install Rfactory AI dependencies (requirements-ai.txt)') from exc
    provider=GeminiCreativeStudio()
    audio=provider.voice(VoiceBrief(text=text,style=style,voice=voice,language='en',model=model))
    with wave.open(io.BytesIO(audio),'rb') as r:
        if r.getnframes()<2000:raise ValueError('Gemini TTS returned insufficient speech')
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(audio)


def fit_clip(x, available_s, *, minimum_speed=.82, maximum_speed=1.28):
    # If too long, mildly shorten without chopping words. High ratio fails visibly.
    allowed=int(available_s*SR)
    if allowed<SR//2:raise ValueError('Narration slot too short')
    if len(x)<=allowed:return x
    ratio=len(x)/allowed
    if ratio>maximum_speed:
        raise ValueError(f'Speech {len(x)/SR:.2f}s exceeds its slot {available_s:.2f}s; shorten script or regenerate, never cut dialogue')
    # Mono phase-vocoder time compression via ffmpeg rubberband? Use atempo at native quality.
    with tempfile.TemporaryDirectory() as td:
        a=Path(td)/'in.wav';b=Path(td)/'out.wav'
        wavfile.write(a,SR,(np.clip(x,-1,1)*32767).astype(np.int16))
        shell(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(a),'-af',f'atempo={ratio:.5f}',
               '-ac','1','-ar',str(SR),'-c:a','pcm_s16le',str(b)])
        fs, raw=wavfile.read(b)
        assert fs==SR
        result=raw.astype(np.float32)/32768.
        return result[:allowed]


def envelope(length, start, end):
    e=np.zeros(length,dtype=np.float32)
    if end<=start:return e
    start=max(0,start);end=min(length,end)
    e[start:end]=1
    fade=int(SR*.12)
    if fade:
        a=max(0,start-fade)
        if a<start:e[a:start]=np.linspace(0,1,start-a,endpoint=False)
        b=min(length,end+fade)
        if end<b:e[end:b]=np.linspace(1,0,b-end,endpoint=False)
    return e


def music_bed(duration, seed):
    n=round(duration*SR)
    out=np.zeros(n,dtype=np.float32)
    notes=[392,493.88,587.33,523.25,440,659.25,587.33,493.88]
    for j,tm in enumerate(np.arange(0,duration,.48)):
        pos=int(tm*SR)
        count=min(round(.34*SR),n-pos)
        if count<=0:break
        t=np.arange(count,dtype=np.float32)/SR
        freq=notes[(j+seed)%len(notes)]
        note=(np.sin(2*np.pi*freq*t)+.22*np.sin(2*np.pi*(freq*2)*t)) * np.exp(-9*t)
        out[pos:pos+count]+=note*.017
        if j%4==0:
            out[pos:pos+count]+=np.sin(2*np.pi*(freq*.5)*t)*np.exp(-13*t)*.008
    return out


def mix(cfg, clips, match_times):
    duration=cfg['duration'];n=int(duration*SR)
    spoken=np.zeros(n,dtype=np.float32)
    occupied=np.zeros(n,dtype=np.float32)
    notes=[]
    for i,voice in enumerate(clips):
        start=round(cfg['start'][i]*SR)
        stop_s=cfg['start'][i+1]-.18 if i+1<len(clips) else duration-.29
        available=stop_s-cfg['start'][i]
        voice=fit_clip(voice,available)
        end=min(n,start+len(voice))
        portion=voice[:end-start]
        # A quick fade into/out of the spoken clause avoids hard edits.
        e=np.ones(len(portion),dtype=np.float32)
        fade=min(round(SR*.05),len(e)//2)
        if fade:
            e[:fade]=np.linspace(0,1,fade,endpoint=False)
            e[-fade:]=np.linspace(1,0,fade,endpoint=False)
        spoken[start:end]+=portion*e*.94
        occupied=np.maximum(occupied,envelope(n,start,end))
        notes.append({'line':i+1,'start_s':round(start/SR,3),'end_s':round(end/SR,3),'text':cfg['lines'][i]})
    bed=music_bed(duration,seed=int(duration))
    # Sidechain-style duck; voice gets center priority.
    bed*=(1-.69*occupied)
    sfx=np.zeros(n,dtype=np.float32)
    for sec in match_times:
        pos=round(sec*SR);cnt=min(round(.115*SR),n-pos)
        if cnt<=0:continue
        t=np.arange(cnt,dtype=np.float32)/SR
        cue=np.sin(2*np.pi*(780*t+810*t*t))*np.exp(-22*t)
        sfx[pos:pos+cnt]+=cue*.047
    audio=spoken+bed+sfx
    tail=min(int(.25*SR),n)
    audio[-tail:]*=np.linspace(1,0,tail)
    audio=np.tanh(audio*1.05)*.90
    return audio,notes


def video_stream_hash(video):
    return subprocess.check_output(['ffmpeg','-hide_banner','-loglevel','error','-i',str(video),
                    '-map','0:v:0','-c','copy','-f','hash','-hash','sha256','-']).decode().strip()


def create_one(stem, cfg, input_dir, output_dir, provider, *, voice_dir=None, model=None):
    original=Path(input_dir)/(stem+'.mp4')
    orig_manifest=Path(input_dir)/(stem+'_qa.json')
    if not original.is_file() or not orig_manifest.is_file():
        raise FileNotFoundError(f'Missing original video/QA: {stem}')
    qa=json.loads(orig_manifest.read_text())
    if qa['zeroFrameCount'] != 5 or qa['exactFitFrames']!=qa['observedZeroFrames']:
        raise ValueError('Cannot upgrade a Reel whose exact-fit puzzle QA failed')
    if int(cfg['duration'])!=int(qa['duration']):raise ValueError('Timing mismatch')
    output_dir=Path(output_dir);cache=output_dir/'voice_segments';cache.mkdir(parents=True,exist_ok=True)
    pieces=[];hashes=[]
    for i,line in enumerate(cfg['lines']):
        path=cache/f'{stem}_{i+1:02}_{provider}.wav'
        if provider=='offline-preview':
            offline_preview(line,cfg['offline'],cfg['rates'][i],cfg['pitches'][i],path)
        elif provider=='gemini':
            real_gemini(line,cfg['styles'][i],cfg['voice'],path,model=model or 'gemini-3.8-flash-lite-tts')
        elif provider=='wav':
            path=Path(voice_dir)/f'{stem}_{i+1:02}.wav'
            if not path.is_file():raise FileNotFoundError(path)
        else:raise ValueError(provider)
        hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
        pieces.append(decoded_voice(path))
    music,segments=mix(cfg,pieces,qa['exactFitTimes'])
    backing=output_dir/f'{stem}_{provider}_mix.wav'
    wavfile.write(backing,SR,(music*32767).astype(np.int16))
    final=output_dir/f'{stem}_{provider}.mp4'
    shell(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(original),'-i',str(backing),
            '-map','0:v:0','-map','1:a:0','-c:v','copy','-c:a','aac','-b:a','160k',
            '-t',str(cfg['duration']),'-movflags','+faststart',str(final)])
    before=video_stream_hash(original);after=video_stream_hash(final)
    if before!=after:raise AssertionError('Video stream unexpectedly modified while remuxing narration')
    probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_entries',
              'stream=codec_name,width,height,r_frame_rate:format=duration','-of','json',str(final)]))
    assert any(z.get('codec_name')=='aac' for z in probe['streams'])
    assert any(z.get('codec_name')=='h264' and z.get('width')==1080 and z.get('height')==1920 for z in probe['streams'])
    newqa={'name':stem,'provider':provider,'neural_voice':provider=='gemini' or provider=='wav',
           'voice_provenance':('verified_api_Gemini_TTS' if provider=='gemini' else ('externally_supplied_WAV_unverified_provider' if provider=='wav' else 'offline_eSpeak_prosodic_preview_not_neural')),
           'clips':segments,'clip_sha256':hashes,'source_video_sha256':hashlib.sha256(original.read_bytes()).hexdigest(),
           'original_video_stream_hash':before,'new_video_stream_hash':after,'video_preserved':True,
           'exactFitFrames':qa['exactFitFrames'],'originalQA':str(orig_manifest.name),'audio_duration_s':float(get_duration_from_probe(final)),
           'format':probe}
    if provider=='wav':newqa['neural_voice']=False # Cannot assert external audio source is neural without provenance.
    (output_dir/f'{stem}_{provider}_qa.json').write_text(json.dumps(newqa,indent=2))
    return final,newqa


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--provider',choices=['gemini','wav','offline-preview'],default='gemini')
    parser.add_argument('--input-dir',type=Path,default=Path('storage/renders/social_voiceovers'))
    parser.add_argument('--output-dir',type=Path,default=Path('storage/renders/social_neural'))
    parser.add_argument('--voice-dir',type=Path,default=None)
    parser.add_argument('--model',default='gemini-3.8-flash-lite-tts')
    parser.add_argument('--allow-paid-tts',action='store_true',help='Explicit opt-in for live provider billing')
    args=parser.parse_args()
    if args.provider=='gemini':
        if not args.allow_paid_tts:parser.error('Pass --allow-paid-tts for a real neural speech API call')
        if not (os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')):parser.error('Set GEMINI_API_KEY securely on your runner; none available here')
    if args.provider=='wav' and args.voice_dir is None:parser.error('Provide --voice-dir')
    args.output_dir.mkdir(parents=True,exist_ok=True)
    reports=[]
    for name,cfg in SPEECH.items():
        output,report=create_one(name,cfg,args.input_dir,args.output_dir,args.provider,voice_dir=args.voice_dir,model=args.model)
        print(f'{output.name}: {report["voice_provenance"]}, 5 exact matches, video stream unchanged',flush=True)
        reports.append({'file':output.name,**report})
    (args.output_dir/'upgrade_manifest.json').write_text(json.dumps({'provider':args.provider,'reels':reports},indent=2))

if __name__=='__main__':main()