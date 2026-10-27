from clipforge.core import SourceCreate,TranscriptItem
from clipforge import storage,jobs,moments,ytb
from fastapi.testclient import TestClient
from clipforge.api import app

def test_moment_ranking(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    sid=storage.create_source(SourceCreate(title="Interview"))
    storage.import_transcript(sid,[
        TranscriptItem(start=0,end=9,text="Why do Moroccan founders struggle to raise capital?"),
        TranscriptItem(start=9,end=24,text="Because investors need specific traction and strong evidence from the business."),
        TranscriptItem(start=24,end=32,text="This example shows 3 useful ways to improve a pitch."),
    ])
    result=moments.candidates(sid,60)
    assert result and result[0]["source_id"]==sid
    assert all(x["end"]>x["start"] for x in result)

def test_job_queue_idempotency(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    sid=storage.create_source(SourceCreate(title="Unlicensed",rights="unknown"))
    jobid=jobs.enqueue("transcribe",sid,{"model":"tiny"})
    assert jobs.enqueue("transcribe",sid)==jobid
    assert jobs.claim()["id"]==jobid
    assert jobs.claim() is None
    assert jobs.get(jobid)["status"]=="running"

def test_ytb_video_id():
    vid="S5Y3Hp2P740"
    assert ytb.video_id(vid)==vid
    assert ytb.video_id("https://youtu.be/"+vid+"?si=abc")==vid
    assert ytb.video_id("https://www.youtube.com/watch?v="+vid)==vid

def test_dashboard_and_auth(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("CLIPFORGE_API_TOKEN","integration-token")
    client=TestClient(app)
    assert client.get("/").status_code==200
    assert "CLIPFORGE" in client.get("/").text
    assert client.get("/v1/jobs").status_code==401
    h={"Authorization":"Bearer integration-token"}
    assert client.get("/v1/jobs",headers=h).json()==[]
    assert client.get("/v1/ytb/status",headers=h).status_code==200
