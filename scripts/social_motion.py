"""Rfactory social-puzzle trajectories: continuous motion, single-frame matches.

A second independent renderer previously held solved artwork for five frames,
showed MATCH banners, and froze at the end. This module makes those states
impossible: all requested fits occupy precisely ONE frame, and position keeps
moving immediately before/after every fit with continuous nonzero velocity.

All frames are deterministic for a given campaign seed. No visual solve hint
is produced here; tiny optional audio cues are handled by the video renderer.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import random


@dataclass(frozen=True)
class MotionPose:
    dx: int
    dy: int
    fit: bool
    fit_number: int
    total_fits: int
    final: bool  # Legacy API field; always False. No victory hold or reveal.


def _duration(cfg: dict, fps: int) -> int:
    seconds=float(cfg["duration"])
    if not math.isfinite(seconds) or seconds < 5 or seconds > 30:
        raise ValueError("Duration must be finite and between 5 and 30 seconds")
    if not isinstance(fps,int) or not 12 <= fps <= 60:
        raise ValueError("FPS must be an integer from 12 to 60")
    return round(seconds*fps)


def _seed(cfg: dict) -> int:
    text=f"{cfg.get('seed',42041)}:{cfg.get('name','')}:{cfg.get('move','orbit')}"
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8],"big")


def fit_frames(cfg: dict, fps: int = 24) -> list[int]:
    frames=_duration(cfg,fps)
    count=int(cfg.get("fit_count",5))
    if not 3 <= count <= 9:
        raise ValueError("fit_count must be between 3 and 9")
    # Legacy social templates paused for five frames. Never allow a caller
    # to reactivate that behavior by loading an old settings JSON.
    if int(cfg.get("hold_frames",0)) != 0:
        raise ValueError("Solved-state hold frames are forbidden; use holdFrames: 0")
    first=round(float(cfg.get("first_fit",1.1))*fps)
    last=round(float(cfg.get("last_fit",frames/fps-.75))*fps)
    spacing=(last-first)/max(1,count-1)
    min_gap=max(9,round(fps*.38))
    if not (first>=min_gap and last<=frames-min_gap and spacing>=min_gap+4):
        raise ValueError("Exact-fit events require safe margins and separation")
    rng=random.Random(_seed(cfg))
    jitter=max(1,min(round(spacing*.15),round(fps*.40)))
    times=[first]
    for i in range(1,count-1):
        nominal=first+round(i*spacing)
        candidate=nominal+rng.randint(-jitter,jitter)
        remaining=count-1-i
        candidate=max(times[-1]+min_gap,min(candidate,last-remaining*min_gap))
        times.append(candidate)
    times.append(last)
    return times


def pose_at_frame(frame: int, cfg: dict, fps: int = 24) -> MotionPose:
    times=fit_frames(cfg,fps)
    n=_duration(cfg,fps)
    if not 0 <= frame < n:
        raise ValueError("Frame lies outside the video")
    scale=float(cfg.get("speed",1.0))
    if not math.isfinite(scale) or not .55<=scale<=1.75:
        raise ValueError("Motion speed must be finite in [0.55, 1.75]")
    style=cfg.get("move","orbit")
    if style not in {"orbit","bounce","zigzag"}:
        raise ValueError(f"Unknown motion mode: {style}")

    if frame in times:
        return MotionPose(0,0,True,times.index(frame)+1,len(times),False)

    # Virtual zero crossings outside the video keep the fragment moving
    # before the first event and beyond the final one. Never force a last-frame
    # exact solve, and don't restart movement from a frozen solved pose.
    virtual_start=min(-fps,times[0]-(times[1]-times[0]))
    virtual_end=max(n+fps,times[-1]+(times[-1]-times[-2]))
    knots=[virtual_start,*times,virtual_end]
    segment=next(i for i in range(len(knots)-1)
                 if knots[i] < frame < knots[i+1])
    left,right=knots[segment:segment+2]
    interval=right-left
    u=(frame-left)/interval

    # With alternate signs and amplitude proportional to interval length,
    # first derivatives agree across every scheduled exact-fit event.
    # Speed = velocity in pixels/frame at each crossing, always nonzero.
    longest=max(b-a for a,b in zip(knots,knots[1:]))
    velocity=min(7.0*scale,230.0*math.pi/longest)
    sign=1 if segment%2==0 else -1
    fundamental=math.sin(math.pi*u)
    amp=velocity*interval/math.pi
    dx=sign*amp*fundamental
    envelope=fundamental**2  # zero first derivative exactly at crossings
    phase=(_seed(cfg)%113)/113*math.pi
    if style=="orbit":
        dy=95*scale*envelope*(.74*math.sin(2*math.pi*u+phase)+.26*sign)
    elif style=="bounce":
        dy=-155*scale*envelope*(.68+.32*abs(math.cos(2*math.pi*u+phase)))
    else:  # zigzag: several gentle turns but no snapping pose / fit holds
        dy=115*scale*envelope*(.55*math.cos(4*math.pi*u+phase)+.45*sign)
    return MotionPose(round(dx),round(dy),False,max(0,segment),len(times),False)


def validate_schedule(cfg: dict,fps: int = 24) -> dict:
    times=fit_frames(cfg,fps)
    frames=_duration(cfg,fps)
    recognized=[]
    poses=[pose_at_frame(i,cfg,fps) for i in range(frames)]
    for idx,p in enumerate(poses):
        if p.fit:
            recognized.append(idx)
        if p.final:
            raise AssertionError("No final solved-state hold is allowed")
        if idx not in times and p.dx==0 and p.dy==0:
            raise AssertionError("Unscheduled solved frame")
    if recognized!=times:
        raise AssertionError("Exact fit positions are not single-frame events")
    for i,center in enumerate(times):
        if (poses[center].dx,poses[center].dy)!=(0,0):
            raise AssertionError("Non-exact fit")
        if center==0 or center==frames-1:
            raise AssertionError("Fit at video boundary")
        for neighbor in (center-1,center+1):
            candidate=poses[neighbor]
            if candidate.fit or abs(candidate.dx)+abs(candidate.dy)<2:
                raise AssertionError("Fragment paused or barely moves near a fit")
        if i and max(abs(poses[j].dx)+abs(poses[j].dy)
                     for j in range(times[i-1]+1,center))<45:
            raise AssertionError("Piece does not leave target between crossings")
    if len(poses)>1 and (poses[-1].dx,poses[-1].dy)==(0,0):
        raise AssertionError("Never hold the completed image at the end")
    gaps=[b-a for a,b in zip(times,times[1:])]
    return {
        "fit_frames":times,
        "fit_times_seconds":[round(x/fps,3) for x in times],
        "fit_count":len(times),
        "irregular_intervals_frames":gaps,
        "hold_frames":0,
        "exact_fit_frames_per_event":1,
        "pixel_alignment_exact":True,
        "continuous_motion":True,
        "no_visual_match_indicators":True,
        "final_frame_solved":False,
    }
