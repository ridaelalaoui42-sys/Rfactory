import shutil,subprocess
import pytest
from clipforge.core import SourceCreate,EditPlan,ClipRange,TranscriptItem
from clipforge import storage
from clipforge.render import render,probe

@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")), reason="requires ffmpeg")
def test_render_with_captions(tmp_path,monkeypatch):
    media=tmp_path/"media";media.mkdir()
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("CLIPFORGE_MEDIA_ROOT",str(media))
    monkeypatch.setenv("CLIPFORGE_OUTPUT_ROOT",str(tmp_path/"out"))
    sample=media/"recording.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i",
        "testsrc2=size=320x180:rate=15","-f","lavfi","-i",
        "sine=frequency=440:sample_rate=48000","-t","2",
        "-c:v","libx264","-preset","ultrafast","-c:a","aac",str(sample)],check=True)
    sid=storage.create_source(SourceCreate(title="Test",rights="owned",
          evidence="Created in test",local_file=str(sample)))
    storage.import_transcript(sid,[TranscriptItem(start=0,end=1.5,text="ClipForge is ready.")])
    plan_id=storage.create_plan(EditPlan(source_id=sid,
        ranges=[ClipRange(start=0,end=1.5)],format="horizontal",
        output_name="captions.mp4",captions=True))
    result=render(plan_id)
    assert result["status"]=="complete"
    assert 1.2<probe(tmp_path/"out"/"captions.mp4")<1.8

def test_caption_requires_transcript(tmp_path,monkeypatch):
    # Caption styling must fail explicitly if no timed transcript exists.
    from clipforge.captions import srt
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    sid=storage.create_source(SourceCreate(title="Empty"))
    assert srt(sid,[ClipRange(start=0,end=2)])==""
