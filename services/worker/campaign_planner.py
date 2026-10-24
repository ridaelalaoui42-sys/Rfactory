"""Seeded, visually varied plans for approved-source short-form Reel campaigns.

No AI calls, no procedural 'fake source' artwork, no automatic publishing.
This module plans only video *motions* over existing approved canonical images.
"""
from __future__ import annotations

import random
from typing import Any

MOTION_FAMILIES = (
    "orbit_lock", "bezier_sweep", "helix", "figure_eight",
    "spiral", "pendulum", "vortex", "opposed_spin",
    "catmull_wave", "magnetic", "zigzag", "ricochet",
)
GEOMETRY_FAMILIES = (
    "organic", "jigsaw", "ellipse", "curved_band",
    "hexagon", "ring_sector", "triangle", "rectangle",
)


def make_campaign_plan(
    asset_ids: list[str], *,
    count: int, base_seed: int,
    duration_sec: float, exact_fit_count: int,
    enable_sfx: bool, allow_fallback: bool,
    cutout_ids: dict[str,str] | None = None,
) -> list[dict[str,Any]]:
    """Unique seeds, diverse trajectories and cutouts across approved originals.

    The output is deterministic, so a campaign can be reviewed/recreated.
    Caller must verify source approval and every face-pack ID before enqueue.
    No claim of perceptual uniqueness: it checks motion/geometry signatures.
    """
    if not 2 <= count <= 24:
        raise ValueError("Campaign size must be between 2 and 24 videos")
    if not 1 <= len(asset_ids) <= 8 or len(asset_ids) != len(set(asset_ids)):
        raise ValueError("Use 1–8 distinct canonical source assets")
    if not all(isinstance(x,str) and len(x)==32 for x in asset_ids):
        raise ValueError("Invalid canonical source asset identifier")
    if not 0 <= base_seed < 2**31:
        raise ValueError("Invalid campaign seed")
    if not 2 <= duration_sec <= 30 or not 1 <= exact_fit_count <= 12:
        raise ValueError("Invalid video duration or exact-fit count")
    extra=cutout_ids or {}
    if any(key not in asset_ids or not isinstance(val,str) or not val
           for key,val in extra.items()):
        raise ValueError("Cutout IDs must match the campaign artwork")
    rng=random.Random(base_seed)
    ordered=sorted(asset_ids)
    rng.shuffle(ordered)
    profiles=list(MOTION_FAMILIES)
    geometries=list(GEOMETRY_FAMILIES)
    rng.shuffle(profiles)
    rng.shuffle(geometries)
    plan=[]
    signatures=set()
    for i in range(count):
        source=ordered[i % len(ordered)]
        # Coprime-style walks across the lists avoid long repeating cycles.
        # Reshuffle on complete profile cycles, but never repeat neighbors.
        motion=profiles[i % len(profiles)]
        if i > 0 and motion==plan[-1]["motion_profile"]:
            motion=profiles[(i+1) % len(profiles)]
        geometry=geometries[(i*3) % len(geometries)]
        if i > 0 and geometry==plan[-1]["geometry"]:
            geometry=geometries[(i*3+1)%len(geometries)]
        seed=rng.randrange(1,2**31)
        signature=(source,motion,geometry,seed)
        if signature in signatures:
            raise AssertionError("Duplicate campaign motion and subject signature")
        signatures.add(signature)
        plan.append({
            "asset_id":source,
            "cutout_id":extra.get(source),
            "allow_fallback":allow_fallback,
            "geometry":geometry,
            "motion_profile":motion,
            "duration_sec":duration_sec,
            "exact_fit_count":exact_fit_count,
            "seed":seed,
            "enable_sfx":enable_sfx,
        })
    return plan
