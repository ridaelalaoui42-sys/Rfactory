import json
from types import SimpleNamespace
import pytest
from clipforge import stickman, jobs


def manifest(tmp_path, monkeypatch, style='B1', width=1080, height=1920, fps=30):
    root = tmp_path / 'media'
    project_dir = root / 'project'
    project_dir.mkdir(parents=True, exist_ok=True)
    f = project_dir / 'project.json'
    f.write_text(json.dumps({'version': 1, 'style': style, 'width': width, 'height': height,
                             'fps': fps, 'shots': [{'start': 0, 'end': 2, 'layers': [{'type': 'text','text':'a'}]}],
                             'voice': {'path': 'narration.wav'},
                             'captions': [{'start': 0, 'end': 2, 'text': 'test'}]}))
    monkeypatch.setenv('CLIPFORGE_MEDIA_ROOT', str(root))
    monkeypatch.setenv('CLIPFORGE_DB_PATH', str(tmp_path / 'db.sqlite3'))
    return f


def register(file):
    return stickman.register(stickman.RegisterProject(project_file=str(file),
                   rights='owned', rights_evidence='Produced original drawings'))


def test_styles_and_minimum_quality(tmp_path, monkeypatch):
    f = manifest(tmp_path, monkeypatch)
    assert register(f)['style'] == 'B1'
    doc = json.loads(f.read_text()); doc['width'], doc['height'] = 720, 1280
    f.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match='1080p'):
        register(f)


def test_landscape_1080p_and_60fps(tmp_path, monkeypatch):
    f = manifest(tmp_path, monkeypatch, width=1920, height=1080, fps=60)
    assert register(f)['style'] == 'B1'


def test_reject_non_runtime_styles(tmp_path, monkeypatch):
    f = manifest(tmp_path, monkeypatch, style='B5')
    with pytest.raises(ValueError, match='B1–B4'):
        register(f)


def test_disallows_manifest_outside_media(tmp_path, monkeypatch):
    f = manifest(tmp_path, monkeypatch)
    outsider = tmp_path / 'project.json'
    outsider.write_bytes(f.read_bytes())
    with pytest.raises(ValueError, match='CLIPFORGE_MEDIA_ROOT'):
        register(outsider)


def test_refuses_captionless_upstream_project(tmp_path, monkeypatch):
    f = manifest(tmp_path, monkeypatch)
    data = json.loads(f.read_text()); data['captions'] = []
    f.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='visible captions'):
        register(f)


def test_register_is_idempotent_and_queued(tmp_path, monkeypatch):
    f = manifest(tmp_path, monkeypatch)
    a, b = register(f), register(f)
    assert a['id'] == b['id']
    jobid = jobs.enqueue('stickman_preview', a['id'], {'seconds': 15})
    assert jobs.get(jobid)['payload']['seconds'] == 15


def test_no_command_injection_and_approval_check(tmp_path, monkeypatch):
    f = manifest(tmp_path, monkeypatch)
    project_id = register(f)['id']
    skill = tmp_path / 'skill'
    script = skill / 'scripts' / 'autopilot.mjs'
    script.parent.mkdir(parents=True)
    script.write_text('placeholder')
    monkeypatch.setenv('CLIPFORGE_STICKMAN_SKILL_ROOT', str(skill))
    monkeypatch.setattr(stickman.shutil, 'which', lambda _: '/usr/bin/fake')
    captured = {}
    def fake_run(argv, **kwargs):
        captured.update({'argv': argv, 'kwargs': kwargs})
        return SimpleNamespace(returncode=0, stdout='{"ok":true}', stderr='')
    monkeypatch.setattr(stickman.subprocess, 'run', fake_run)
    result = stickman.execute(project_id, 'preview', seconds=20)
    assert result['result']['ok']
    assert captured['argv'][0] == 'node'
    assert captured['argv'][2:4] == ['preview', str(f.resolve())]
    with pytest.raises(ValueError, match='Approval note'):
        stickman.execute(project_id, 'approve', note='')


def test_unauthenticated_endpoint_rejected(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from clipforge.api import app
    monkeypatch.setenv('CLIPFORGE_API_TOKEN', 'secret-value')
    response = TestClient(app).get('/v1/stickman/status')
    assert response.status_code == 401
    response = TestClient(app).get('/v1/stickman/status', headers={'Authorization': 'Bearer secret-value'})
    assert response.status_code == 200
    assert response.json()['minimum_output'] == '1080p native'
