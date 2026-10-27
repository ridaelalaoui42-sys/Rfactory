import pytest
from clipforge.core import ClipRange,EditPlan,SourceCreate,render_allowed,safe_local,FORMATS
from clipforge.research import normalize_transcript
from clipforge import storage

def test_video_formats():
    assert FORMATS["vertical"]==(1080,1920)
    assert FORMATS["horizontal"]==(1920,1080)

def test_ranges():
    with pytest.raises(ValueError):ClipRange(start=5,end=1)
    plan=EditPlan(source_id=1,format="horizontal",output_name="long.mp4",
                  ranges=[ClipRange(start=0,end=300)])
    assert plan.ranges[0].end==300

def test_rights():
    assert not render_allowed({"rights":"fair_use_review","evidence":"notes","local_file":"x.mp4"})
    assert render_allowed({"rights":"licensed","evidence":"contract","local_file":"x.mp4"})

def test_safe_root(tmp_path):
    folder=tmp_path/"media";folder.mkdir()
    outside=tmp_path/"other.mp4";outside.write_bytes(b"x")
    with pytest.raises(ValueError):safe_local(str(outside),folder)

def test_transcript_index(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"catalog.sqlite"))
    sid=storage.create_source(SourceCreate(title="Moroccan podcast"))
    segments=normalize_transcript({"segments":[{"start":1,"duration":2,
                              "text":"تكنولوجيا مغربية","language":"ar"}]})
    assert storage.import_transcript(sid,segments)==1
    matches=storage.search("مغربية")
    assert len(matches)==1 and matches[0]["start"]==1
    assert storage.search("%")==[]

def test_plan_persistence(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"catalog.sqlite"))
    sid=storage.create_source(SourceCreate(title="Owned",rights="owned",evidence="I shot it"))
    pid=storage.create_plan(EditPlan(source_id=sid,format="square",
                           ranges=[ClipRange(start=0,end=2)],output_name="test.mp4"))
    assert storage.plan(pid)["payload"]["format"]=="square"
