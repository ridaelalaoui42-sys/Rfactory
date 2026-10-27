import pytest
from clipforge import publishing,storage
from clipforge.core import EditPlan,ClipRange,SourceCreate

def test_publishing_cannot_use_unapproved_source(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    sid=storage.create_source(SourceCreate(title="Unknown content",rights="unknown"))
    pid=storage.create_plan(EditPlan(source_id=sid,format="vertical",
          output_name="video.mp4",ranges=[ClipRange(start=0,end=15)]))
    with pytest.raises(ValueError,match="Complete rendering"):
        publishing.approve(pid,"youtube")
    with pytest.raises(ValueError,match="Complete render"):
        publishing.approved_media(pid,"youtube")

def test_no_arbitrary_platform_or_early_approval(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    with pytest.raises(ValueError,match="Unsupported destination"):
        publishing.approve(1,"random-platform")

def test_gate_requires_approval(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("CLIPFORGE_OUTPUT_ROOT",str(tmp_path/"out"))
    sid=storage.create_source(SourceCreate(title="Owned content",rights="owned",
          evidence="Recorded by creator",local_file="/work/original.mp4"))
    pid=storage.create_plan(EditPlan(source_id=sid,format="vertical",
          output_name="clip.mp4",ranges=[ClipRange(start=0,end=15)]))
    with storage.connect() as db:
        db.execute("UPDATE plans SET status='complete',result_file=? WHERE id=?",
                   (str(tmp_path/"out"/"clip.mp4"),pid))
    with pytest.raises(ValueError,match="approve"):
        publishing.approved_media(pid,"facebook")
