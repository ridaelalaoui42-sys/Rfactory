"""Deterministic, repeatedly aligning puzzle-fragment trajectories.

Every scheduled fit is an exact integer-pixel (0, 0) offset for >= hold_frames.
No independent perpetual sine wave and no "only snaps right at the end" trick.
"""
from __future__ import annotations
import math
from dataclasses import dataclass

@dataclass(frozen=True)
class MotionPose:
    dx: int
    dy: int
    fit: bool
    fit_number: int
    total_fits: int
    final: bool

def fit_frames(cfg: dict, fps: int = 24) -> list[int]:
    duration = int(cfg['duration'])
    count = int(cfg.get('fit_count', 5))
    if not 3 <= count <= 9: raise ValueError('fit_count must be between 3 and 9')
    if duration < 5: raise ValueError('duration must be at least 5 seconds')
    first = int(round(float(cfg.get('first_fit', 1.1)) * fps))
    last = int(round(float(cfg.get('last_fit', duration - .72)) * fps))
    hold = int(cfg.get('hold_frames', 5))
    if first <= hold or last >= duration*fps or last <= first or last-first < (count-1)*(hold+4):
        raise ValueError('Fits are too crowded for given duration/hold')
    return [first + round(i * (last - first) / (count - 1)) for i in range(count)]

def ease(x: float) -> float:
    x = max(0., min(1., x))
    return x*x*(3.-2.*x)

def pose_at_frame(frame: int, cfg: dict, fps: int = 24) -> MotionPose:
    times = fit_frames(cfg, fps)
    hold = int(cfg.get('hold_frames',5))
    half = hold//2
    style = cfg.get('move', 'orbit')
    scale = max(.55, min(1.75, float(cfg.get('speed',1.0))))
    # Fix integer coordinates to (0,0) on each hit for visible dwell frames.
    for i,center in enumerate(times):
        if center-half <= frame <= center+half:
            return MotionPose(0,0,True,i+1,len(times),i==len(times)-1)
    if frame >= times[-1]-half:
        return MotionPose(0,0,True,len(times),len(times),True)
    if frame < times[0]-half:
        x=ease(1-frame/max(1,times[0]-half))
        dx=round(170*scale*x)
        dy=round(-95*scale*x)
        return MotionPose(dx,dy,False,0,len(times),False)
    segment=next(i for i in range(len(times)-1)
                 if times[i]+half < frame < times[i+1]-half)
    left=times[segment]+half
    right=times[segment+1]-half
    p=(frame-left)/(right-left)
    amplitude=math.sin(math.pi*p)  # Exactly 0 at boundaries; smooth arrival/departure
    direction=1 if segment%2==0 else -1
    if style=='orbit':
        dx=direction*190*scale*amplitude
        dy=(120*math.cos(math.pi*p)+45*direction)*scale*amplitude
    elif style=='bounce':
        dx=direction*150*scale*amplitude
        dy=-175*scale*amplitude*abs(math.sin(math.pi*p*.8+.3))
    elif style=='zigzag':
        dx=direction*220*scale*amplitude
        dy=direction*105*scale*amplitude*math.cos(2*math.pi*p)
    else:raise ValueError(f'Unknown motion mode: {style}')
    # If quantized x/y both 0 between hits, that's okay (near hit) but not a false fit event.
    return MotionPose(round(dx),round(dy),False,segment+1,len(times),False)

def validate_schedule(cfg: dict, fps: int = 24) -> dict:
    fits=fit_frames(cfg,fps)
    for i,center in enumerate(fits):
        p=pose_at_frame(center,cfg,fps)
        if not (p.fit and p.dx==0 and p.dy==0 and p.fit_number==i+1):
            raise AssertionError('Non-exact scheduled fit')
        # Motion must move visibly between every successive fit.
        if i and max(abs(pose_at_frame(j,cfg,fps).dx) +
                     abs(pose_at_frame(j,cfg,fps).dy)
                     for j in range(fits[i-1]+1,center)) < 45:
            raise AssertionError('Piece does not leave slot between fits')
    return {'fit_frames':fits,'fit_times_seconds':[round(x/fps,3) for x in fits],
            'fit_count':len(fits),'hold_frames':int(cfg.get('hold_frames',5)),
            'pixel_alignment_exact':True}