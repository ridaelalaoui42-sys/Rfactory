import shutil,subprocess
import pytest
from clipforge import storage
from clipforge.core import SourceCreate,EditPlan,ClipRange
from clipforge.render import render,probe

@pytest.mark.skipif(not (shutil.which("ffmpeg") and shutil.which("ffprobe")),reason="needs FFmpeg")
def test_render_two_formats(tmp_path,monkeypatch):
    media=tmp_path/"media";media.mkdir()
    output=tmp_path/"out"
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("CLIPFORGE_MEDIA_ROOT",str(media))
    monkeypatch.setenv("CLIPFORGE_OUTPUT_ROOT",str(output))
    sample=media/"sample.mp4"
    subprocess.run(["ffmpeg","-v","error","-y","-f","lavfi","-i",
                    "testsrc2=size=320x180:rate=15","-f","lavfi","-i",
                    "sine=frequency=440:sample_rate=48000","-t","3",
                    "-c:v","libx264","-preset","ultrafast","-c:a","aac",str(sample)],check=True)
    sid=storage.create_source(SourceCreate(title="My own",rights="owned",
                          evidence="Created as test footage",local_file=str(sample)))
    for fmt in ("vertical","horizontal"):
        pid=storage.create_plan(EditPlan(source_id=sid,format=fmt,output_name=fmt+".mp4",
                      ranges=[ClipRange(start=0,end=0.5),ClipRange(start=1,end=1.5)]))
        result=render(pid)
        assert result["status"]=="complete"
        assert (output/(fmt+".mp4")).is_file()
        assert (output/(fmt+".editor-v1.json")).is_file()
        assert 0.8 < probe(output/(fmt+".mp4")) < 1.3

def test_unknown_rights_fail_closed(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    sid=storage.create_source(SourceCreate(title="unreviewed",rights="fair_use_review",local_file="/tmp/x.mp4"))
    pid=storage.create_plan(EditPlan(source_id=sid,format="vertical",output_name="invalid.mp4",
                   ranges=[ClipRange(start=0,end=1)]))
    with pytest.raises(ValueError,match="Rights gate"):render(pid)
