"""CI proof that exported social MP4s really contain 5 exact-fit events."""
from __future__ import annotations
import json
from pathlib import Path
import subprocess
import argparse

from scripts.social_motion import pose_at_frame, validate_schedule


def verify_one(video: Path, config: dict) -> dict:
    ffprobe = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_name,width,height,r_frame_rate",
         "-of", "json", str(video)],
        check=True, capture_output=True, text=True,
    )
    media = json.loads(ffprobe.stdout)
    streams = media.get("streams", [])
    v = next((s for s in streams if s.get("codec_name") == "h264"), None)
    a = next((s for s in streams if s.get("codec_name") == "aac"), None)
    assert v and a, f"Expected H.264 and AAC in {video.name}"
    assert (v["width"], v["height"], v["r_frame_rate"]) == (1080, 1920, "24/1")
    assert abs(float(media["format"]["duration"]) - float(config["duration"])) < .1
    qa = json.loads(video.with_name(video.stem + "_qa.json").read_text())
    schedule = validate_schedule(config, fps=24)
    assert qa["repeated_alignment"] == schedule
    assert schedule["fit_count"] == config.get("fit_count", 5)
    assert schedule["fit_count"] >= 3
    for i, fit in enumerate(schedule["fit_frames"]):
        for f in range(fit - 2, fit + 3):
            pose = pose_at_frame(f, config, 24)
            assert pose.fit and pose.fit_number == i + 1 and pose.dx == pose.dy == 0
    return {"video": video.name, "duration": media["format"]["duration"], "exactFits": schedule["fit_times_seconds"]}


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--out", type=Path, default=Path("storage/renders/social"))
    a = p.parse_args()
    reports = []
    for qa_path in sorted(a.out.glob("*_qa.json")):
        cfg = json.loads(qa_path.read_text())["settings"]
        reports.append(verify_one(a.out / f"{cfg['name']}.mp4", cfg))
    assert len(reports) == 3, f"Expected 3 MP4 outputs; got {len(reports)}"
    report = {"passed": True, "videos": reports}
    (a.out / "reel_verification.json").write_text(json.dumps(report, indent=2))
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
