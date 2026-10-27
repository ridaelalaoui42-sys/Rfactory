import pytest
from clipforge import ytb

def test_ytb_transcript_millisecond_cues(monkeypatch):
    payload={"cues":[{"start_ms":1500,"end_ms":3700,"text":"Hello world"},
                     {"startMs":4000,"durationMs":2100,"text":"سلام عليكم"}]}
    monkeypatch.setattr(ytb,"call",lambda *a:payload)
    result=ytb.transcript("S5Y3Hp2P740")
    assert len(result)==2
    assert result[0].start==1.5
    assert result[1].end==6.1

def test_ytb_rejects_malformed(monkeypatch):
    monkeypatch.setattr(ytb,"call",lambda *a:{"cues":[{"foo":"bar"}]})
    with pytest.raises(ValueError,match="No timestamped"):ytb.transcript("S5Y3Hp2P740")
