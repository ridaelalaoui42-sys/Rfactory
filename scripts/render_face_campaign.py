#!/usr/bin/env python3
"""Produce four face-puzzle Reels from two approved HD originals.

Only existing, operator-reviewed SAME-SOURCE cutout packs may be rendered.
No AI-model-generated fake cutouts, no extrapolated background pixels, no
silent fallback, no Facebook posting, and no Gemini image charges.

Example:
 python -m scripts.render_face_campaign \
   --animal-core face_<24 hex> --animal-eye face_<24 hex> \
   --human-slices face_<24 hex> --human-triangles face_<24 hex>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

from services.assets.library import AssetLibrary
from scripts.render_from_library import render_approved_asset

ROOT=Path(__file__).resolve().parents[1]
FACE_ID=re.compile(r"^face_[a-f0-9]{24}$")

CAMPAIGN=(
    ("animal_face_core","animal","orbit_lock","animal_core"),
    ("animal_eye_band","animal","pendulum","animal_eye_band"),
    ("human_three_slice_face","human","spiral","human_three_slices"),
    ("human_triangle_face_puzzle","human","helix","human_face_triangles"),
)


def _approved(root: Path,face_id: str,mode: str,subject: str,lib: AssetLibrary)->dict:
    if not FACE_ID.fullmatch(face_id):
        raise ValueError("Invalid cutout pack identifier")
    file=root/"cutout_packs"/face_id/"puzzle_manifest.json"
    if not file.is_file():
        raise FileNotFoundError("Approved cutout pack missing: "+face_id)
    manifest=json.loads(file.read_text(encoding="utf-8"))
    if (manifest.get("mode") != mode or manifest.get("subject_type") != subject or
        not manifest.get("approved") or manifest.get("status")!="APPROVED"):
        raise ValueError("Face cutout must have the exact expected approved mode and subject")
    original=lib.get(manifest["library_asset_id"])
    if not original["approved"] or not original["production_eligible"]:
        raise ValueError("Original art approval/resolution no longer valid")
    if original["sha256"] != manifest["original_image_sha256"]:
        raise ValueError("Reviewed geometry was tied to a different source hash")
    return manifest


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--animal-core",required=True)
    parser.add_argument("--animal-eye",required=True)
    parser.add_argument("--human-slices",required=True)
    parser.add_argument("--human-triangles",required=True)
    parser.add_argument("--storage-root",type=Path,default=ROOT/"storage")
    parser.add_argument("--duration",type=float,default=12.0)
    parser.add_argument("--crossings",type=int,default=5)
    parser.add_argument("--allow-fallback",action="store_true")
    parser.add_argument("--no-sfx",action="store_true")
    args=parser.parse_args()
    if not 2<=args.duration<=30 or not 1<=args.crossings<=12:
        parser.error("Duration or crossings out of bounds")
    face_ids=(args.animal_core,args.animal_eye,args.human_slices,args.human_triangles)
    storage=args.storage_root.resolve()
    library=AssetLibrary(storage)
    # Verify ALL four source-packs and approvals before any expensive video
    # rendering: no partial campaign if a source is invalid.
    try:
        prepared=[
            _approved(storage,face_id,mode,subject,library)
            for face_id,(mode,subject,_,_) in zip(face_ids,CAMPAIGN)
        ]
    except (ValueError,FileNotFoundError,KeyError,json.JSONDecodeError) as exc:
        print(f"Source review failed: {exc}",file=sys.stderr)
        return 1
    outputs=[]
    for i,(meta,(mode,subject,motion,label)) in enumerate(zip(prepared,CAMPAIGN)):
        output=render_approved_asset(
            meta["library_asset_id"],storage_root=storage,
            allow_fallback=args.allow_fallback,
            geometry="organic",motion=motion,
            duration=args.duration,crossings=args.crossings,
            seed=24680+i*673,enable_sfx=not args.no_sfx,
            face_mode=mode,subject_type=subject,
            face_bbox_norm=tuple(meta["face_bbox_norm"]) if meta.get("face_bbox_norm") else None,
            face_asset_seed=int(meta["seed"]),
        )
        output["campaign_variant"]=label
        output["reviewed_face_cutout_id"]=face_ids[i]
        outputs.append(output)
        print(f"PASS {label}: {output['video']} · {output['exact_fit_times_sec']}",flush=True)
    manifest=storage/"renders"/"face_campaign_manifest.json"
    manifest.write_text(json.dumps(outputs,indent=2),encoding="utf-8")
    print(f"PASS: 4 HD Reels, full frame QA. Manifest: {manifest}",flush=True)
    return 0


if __name__=="__main__":
    raise SystemExit(main())
