from clipforge import storage,jobs,publishing
from clipforge.core import SourceCreate,EditPlan,ClipRange

def test_approved_private_upload_queue(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    root=tmp_path/"out";root.mkdir()
    monkeypatch.setenv("CLIPFORGE_OUTPUT_ROOT",str(root))
    output=root/"clip.mp4";output.write_bytes(b"test-placeholder")
    sid=storage.create_source(SourceCreate(title="Licensed footage",
        rights="licensed",evidence="Creator signed agreement",
        local_file="/media/licensed.mp4"))
    pid=storage.create_plan(EditPlan(source_id=sid,format="vertical",
        output_name="clip.mp4",ranges=[ClipRange(start=0,end=15)]))
    with storage.connect() as db:
        db.execute("UPDATE plans SET status='complete',result_file=? WHERE id=?",(str(output),pid))
    result=publishing.approve(pid,"youtube")
    assert result["approved"]
    assert publishing.approved_media(pid,"youtube")[0]==output.resolve()
    job=jobs.enqueue("publish_youtube",pid,{"title":"My authorized footage"})
    assert jobs.get(job)["status"]=="queued"
    assert jobs.enqueue("publish_youtube",pid)==job
