from clipforge import storage
from clipforge.core import SourceCreate,TranscriptItem,ClipRange
from clipforge.captions import srt,timestamp

def test_timecode_conversion():
    assert timestamp(60.045)=="00:01:00,045"
    assert timestamp(3600.9)=="01:00:00,900"

def test_caption_retime_multiple_cuts(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    sid=storage.create_source(SourceCreate(title="original"))
    storage.import_transcript(sid,[
        TranscriptItem(start=5,end=8,text="Hello Morocco"),
        TranscriptItem(start=12,end=16,text="How can we build it?"),
    ])
    data=srt(sid,[ClipRange(start=5,end=9),ClipRange(start=13,end=16)])
    assert "00:00:00,000 --> 00:00:03,000" in data
    assert "00:00:04,000 --> 00:00:07,000" in data
    assert "Hello Morocco" in data and "How can we" in data
