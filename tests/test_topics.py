import pytest
from clipforge import topics

def test_scheduled_research_and_dedup(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    monkeypatch.setenv("YOUTUBE_API_KEY","fake-for-mocked-test")
    calls=[]
    def fake_search(q,max_results,region_code,language):
        calls.append(q)
        return [{"youtube_id":"S5Y3Hp2P740","title":"Local Tech",
                 "channel":"Creator","published_at":"2026-10-01T12:00:00Z"}]
    monkeypatch.setattr(topics,"youtube_search",fake_search)
    topic=topics.create("ai maroc",region="MA",language="fr")
    assert len(topics.scan_due())==1
    assert len(topics.scan_due())==0
    assert len(topics.results(topic))==1
    assert calls==["ai maroc"]
    assert topics.scan(topic)["found"]==1
    assert len(topics.results(topic))==1

def test_topic_limits(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    with pytest.raises(ValueError):topics.create("",region="MA")
    with pytest.raises(ValueError):topics.create("test",region="MAR")
