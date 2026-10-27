from fastapi.testclient import TestClient
from clipforge.api import app

def test_auth_fail_closed(monkeypatch):
    monkeypatch.delenv("CLIPFORGE_API_TOKEN",raising=False)
    client=TestClient(app)
    assert client.get("/health").status_code==200
    assert client.get("/v1/sources").status_code==503

def test_api_crud(tmp_path,monkeypatch):
    monkeypatch.setenv("CLIPFORGE_API_TOKEN","unit-test-secret")
    monkeypatch.setenv("CLIPFORGE_DB_PATH",str(tmp_path/"db.sqlite"))
    client=TestClient(app)
    assert client.get("/v1/formats").status_code==401
    hdr={"Authorization":"Bearer unit-test-secret"}
    assert client.get("/v1/formats",headers=hdr).json()["horizontal"]["width"]==1920
    res=client.post("/v1/sources",json={"title":"Interview","rights":"unknown"},headers=hdr)
    assert res.status_code==200
    assert client.get("/v1/sources",headers=hdr).json()[0]["title"]=="Interview"
