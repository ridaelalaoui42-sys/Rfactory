#!/usr/bin/env python3
"""Original 3-character motion showcase, rendered entirely on a GitHub runner.

No secret and no external images are required. Artwork is stylized procedural
and intentionally NOT labelled as Gemini-generated. Each video: 1080x1920,
12 seconds, 30 fps, five exact one-frame source crossings with no hold.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import random

from PIL import Image, ImageDraw, ImageFilter
from services.engine.renderer import RenderConfig, PuzzleVideoRenderer
from services.engine.qa_validator import validate_rendered_video

ROOT = Path(__file__).resolve().parents[1]


def make_artwork(name: str, destination: Path) -> None:
    scale = 2
    S = lambda n: int(round(n * scale))
    im = Image.new("RGBA", (S(820), S(820)), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    def ell(box, fill, outline=None, width=0):
        d.ellipse(tuple(map(S, box)), fill=fill, outline=outline, width=S(width))
    def poly(points, fill, outline=None, width=0):
        d.polygon([(S(x), S(y)) for x,y in points], fill=fill)
        if outline:
            d.line([(S(x), S(y)) for x,y in points + [points[0]]], fill=outline, width=S(width), joint="curve")
    def line(points, fill, width=1):
        d.line([(S(x),S(y)) for x,y in points], fill=fill, width=S(width), joint="curve")
    black = "#1E2230"
    rng = random.Random(611 if name == "snow_leopard" else 817)

    if name == "snow_leopard":
        # Ice-grey fur, broad cheeks, curved ears, high-contrast rosette fur.
        poly([(225,660),(255,480),(410,445),(590,490),(630,690),(515,735),(292,720)], "#B8C5CC", black, 8)
        ell((175,115,338,305), "#D1DADF", black, 8)
        ell((482,115,645,305), "#D1DADF", black, 8)
        ell((214,152,308,269), "#66717E", black, 3)
        ell((512,152,606,269), "#66717E", black, 3)
        ell((190,155,630,600), "#DBE6E8", black, 9)
        ell((209,320,390,564), "#EDF4F0")
        ell((430,320,610,564), "#EDF4F0")
        # Distinctive ink-and-stone leopard rosettes, leaving eyes clear.
        for _ in range(54):
            x=rng.randint(227,591);y=rng.randint(215,525)
            if 290<x<530 and 326<y<490: continue
            rr=rng.randint(5,16)
            d.arc((S(x-rr),S(y-rr),S(x+rr),S(y+rr)), 18, 140, fill="#435366", width=S(4))
            d.arc((S(x-rr),S(y-rr),S(x+rr),S(y+rr)), 200, 315, fill="#435366", width=S(4))
        ell((286,324,381,377), "#FEFFFF", black, 5)
        ell((437,324,532,377), "#FEFFFF", black, 5)
        ell((327,325,361,377), "#8AC6D9", black, 4)
        ell((459,325,493,377), "#8AC6D9", black, 4)
        ell((341,332,353,373), black)
        ell((473,332,485,373), black)
        poly([(369,451),(449,451),(410,492)], "#45515B", black, 5)
        line([(410,491),(408,527),(371,549)],black,6)
        line([(408,527),(453,550)],black,6)
        for dy in (0,22,44):
            line([(361,493+dy),(195,476+dy*0.7)], "#83929A", 3)
            line([(457,493+dy),(625,476+dy*0.7)], "#83929A", 3)
        for x,y in ((289,477),(311,488),(529,475),(551,486)):
            ell((x,y,x+8,y+8), "#404A55")

    elif name == "red_panda":
        # Triangular muzzle and striped ringtail make this clearly a red panda.
        ell((502,432,775,680), "#983A2D", black, 9)
        for x in (552,615,682):
            line([(x,468),(x+46,506),(x+58,553)], "#F6C18C", 23)
        poly([(236,685),(277,484),(415,456),(564,496),(612,696)], "#B95A37", black, 8)
        poly([(196,287),(175,126),(340,220)], "#A3472F", black, 9)
        poly([(482,215),(636,123),(629,304)], "#A3472F", black, 9)
        poly([(222,258),(216,185),(309,241)], "#EAC09D")
        poly([(517,240),(604,185),(591,265)], "#EAC09D")
        ell((189,185,635,595), "#C66339", black, 9)
        ell((220,288,422,557), "#FAF2D9")
        ell((402,292,599,558), "#FAF2D9")
        poly([(248,241),(343,253),(374,338),(289,328)], "#F9E5CE")
        poly([(468,341),(506,245),(573,245),(549,329)], "#F9E5CE")
        ell((285,348,365,400), "#FFF9E7", black, 4)
        ell((457,348,537,400), "#FFF9E7", black, 4)
        ell((316,354,342,396), "#372A2A")
        ell((486,354,512,396), "#372A2A")
        ell((323,362,332,372), "#FFFFFF")
        ell((490,362,499,372), "#FFFFFF")
        ell((323,417,500,566), "#FFF4DF")
        poly([(376,450),(447,449),(408,484)], "#3A2928", black, 3)
        line([(408,483),(409,512),(377,525)],black,4)
        line([(409,512),(446,524)],black,4)
        for i in range(3):
            line([(327,483+i*16),(191,464+i*15)], "#DDD2C2", 3)
            line([(493,483+i*16),(618,464+i*15)], "#DDD2C2", 3)
        ell((307,607,384,710), "#4B302C", black, 6)
        ell((447,607,524,710), "#4B302C", black, 6)

    elif name == "astronaut":
        # Human figure with coherent helmet, reflective visor and suit controls.
        poly([(195,715),(222,473),(318,424),(504,427),(608,489),(638,730)],
             "#E4EDF3", black, 9)
        ell((141,465,256,645), "#ECF5FA", black, 9)
        ell((564,465,680,645), "#ECF5FA", black, 9)
        ell((208,620,304,746), "#F8FAFC", black, 6)
        ell((511,620,608,746), "#F8FAFC", black, 6)
        ell((237,135,579,500), "#EEF6FB", black, 12)
        ell((255,153,562,482), "#A3D9EF", "#586982", 11)
        # Visor shade, sky reflection and astronaut expression visible inside.
        ell((286,218,531,473), "#31465C", "#8DBBC9", 8)
        ell((328,290,491,466), "#C08E6F")
        ell((346,341,380,362), "#F8FDFF")
        ell((434,341,468,362), "#F8FDFF")
        ell((358,344,370,361), black)
        ell((447,344,459,361), black)
        line([(387,401),(433,401)],"#67493E",6)
        poly([(296,194),(339,165),(488,177),(524,227),(435,205),(366,224)],
             (235,251,255,88))
        ell((225,445,590,582), "#D5E2EA", black, 10)
        poly([(336,502),(490,502),(493,629),(332,629)], "#637A95",black,7)
        for x,y,color in ((361,531,"#68E6E1"),(405,531,"#FFC655"),(451,531,"#F98176")):
            ell((x,y,x+25,y+25),color)
        line([(363,585),(464,585)], "#F8FDFF",6)
        ell((583,493,648,554), "#EED184", black, 6)
        ell((603,511,630,538), "#2D6786")
        poly([(233,656),(279,656),(279,695),(226,696)], "#ED6D45")
        ell((384,95,433,155), "#DDE9ED", black, 6)
        line([(409,98),(409,61)], "#445870",7)
        ell((396,47,422,73), "#EF8365",black,3)
    else:
        raise ValueError(name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    im.resize((820,820), Image.Resampling.LANCZOS).save(destination)


SHOWCASE = (
    ("snow_leopard", "MISSING_PIECE_SLIDE", "orbit_lock", "#E8F2FA", 42001),
    ("red_panda", "FACE_FEATURE_SLIDE", "pendulum", "#FFF3E5", 42002),
    ("astronaut", "FACE_SPLIT_3BAND", "spiral", "#E9F1FF", 42003),
)


def main() -> None:
    arg = argparse.ArgumentParser()
    arg.add_argument("--duration", type=float, default=12)
    arg.add_argument("--count", type=int, default=5)
    arg.add_argument("--output-dir", type=Path, default=Path("storage/showcase_continuous"))
    args = arg.parse_args()
    output = args.output_dir.resolve()
    assets = ROOT / "storage" / "assets"
    artist = assets / "showcase"
    renderer = PuzzleVideoRenderer(assets, output)
    manifest = []
    for name, template, profile, background, seed in SHOWCASE:
        sprite = artist / f"{name}.png"
        make_artwork(name,sprite)
        cfg = RenderConfig(
            job_id=f"{name}_continuous_v5",
            species=name, template_id=template,
            asset_path=f"showcase/{name}.png",
            duration_sec=args.duration, fps=30, seed=seed, cycles=args.count,
            snap_count=args.count, randomize_snap_timing=True,
            continuous_motion=True, motion_profile=profile, motion_intensity=1.0,
            enable_audio=True, sound_mode="match_only",
            background_hex=background,
        )
        artifact = renderer.render_video(cfg)
        video = Path(artifact.mp4_path)
        snap_report = json.loads(video.with_suffix(".snaps.json").read_text())
        qa_report = json.loads(video.with_suffix(".frameqa.json").read_text())
        assessment = validate_rendered_video(
            video, expected_duration_sec=args.duration,
            missing_piece_mad=artifact.pixel_match_mad,
        )
        if not assessment.passed or len(artifact.alignment_frames) != args.count:
            raise RuntimeError(f"QA failed for {name}: {assessment.errors}")
        if any(p["first_locked_frame"] != p["last_locked_frame"] for p in snap_report["snap_windows"]):
            raise RuntimeError(f"Unexpected hold frame for {name}")
        manifest.append({
            "name": name, "template": template, "motion":profile,
            "duration_sec": args.duration, "fps":30,
            "fit_count":args.count, "crossing_times_sec":snap_report["snap_timestamps_sec"],
            "exact_fit_mad":artifact.pixel_match_mad,
            "frame_qa":qa_report, "video":str(video),
            "art_provenance":"original procedural artwork; not Gemini",
            "tts_provenance":"none; optional SFX only",
        })
        print(f"PASS {name} {video} crossings={snap_report['snap_timestamps_sec']}",flush=True)
    (output/"showcase_manifest.json").write_text(json.dumps(manifest,indent=2),encoding="utf-8")
    print("SUCCESS: 3 unique continuously moving Reels, no visual match indicator",flush=True)

if __name__ == "__main__":
    main()
