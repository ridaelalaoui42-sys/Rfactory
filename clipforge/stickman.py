"""Optional, rights-gated bridge to kaomei/stickman-video-director.

The upstream Skill is installed separately; we never vendor its fonts,
assets, dependencies or scripts into the ClipForge Python package.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from . import storage
from .render import media_root

UPSTREAM = 'https://github.com/kaomei/stickman-video-director'
RUNTIME_STYLES = ('B1', 'B2', 'B3', 'B4')
STYLE_CATALOG = {
    'A1': 'Classic Black & White', 'A2': 'Modern Pop',
    'A3': 'Prehistoric Cave', 'A4': 'Cozy Storytelling',
    'A5': 'Historical Cartoon', 'A6': 'Amber Noir',
    'B1': 'Minimal Line Art', 'B2': 'Colorful Hand-Drawn',
    'B3': 'Retro TV', 'B4': 'Survival Thriller',
    'B5': 'Character Explainer',
}
DDL = """CREATE TABLE IF NOT EXISTS stickman_projects (
 id INTEGER PRIMARY KEY,
 project_file TEXT NOT NULL UNIQUE,
 style TEXT NOT NULL,
 rights TEXT NOT NULL,
 rights_evidence TEXT NOT NULL,
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);"""


class RegisterProject(BaseModel):
    project_file: str = Field(min_length=1, max_length=4096)
    rights: Literal['owned', 'licensed', 'permission', 'public_domain']
    rights_evidence: str = Field(min_length=3, max_length=4096)


class PreviewOptions(BaseModel):
    seconds: int = Field(default=20, ge=1, le=60)


class ApprovalOptions(BaseModel):
    note: str = Field(min_length=4, max_length=1000)


def init():
    with storage.connect() as db:
        db.execute(DDL)


def _project_file(filename: str) -> Path:
    """Only read manifests from the operator's configured media volume."""
    root = media_root()
    file = Path(filename).expanduser().resolve()
    if not file.is_relative_to(root) or not file.is_file() or file.name != 'project.json':
        raise ValueError('project.json must exist inside CLIPFORGE_MEDIA_ROOT')
    if file.stat().st_size > 1024 * 1024:
        raise ValueError('Project manifest exceeds 1 MiB')
    return file


def _manifest(filename: str) -> tuple[Path, dict]:
    file = _project_file(filename)
    try:
        doc = json.loads(file.read_text(encoding='utf-8'))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError('Invalid UTF-8 project.json') from exc
    if not isinstance(doc, dict) or doc.get('version') != 1:
        raise ValueError('Expected Stickman manifest version 1')
    style = doc.get('style')
    if style not in RUNTIME_STYLES:
        raise ValueError('Executable manifest renderer supports B1–B4; A1–A6 and B5 use other workflows')
    width, height, fps = doc.get('width'), doc.get('height'), doc.get('fps')
    if not all(type(x) is int for x in (width, height, fps)):
        raise ValueError('Integer width, height and fps are required')
    # Rfactory export policy: native 1080p or better, never upscale 720p.
    if not ((width >= 1920 and height >= 1080 and width * 9 == height * 16) or
            (width >= 1080 and height >= 1920 and width * 16 == height * 9)):
        raise ValueError('Use native 16:9 or 9:16 at 1080p or higher')
    if width > 3840 or height > 3840 or fps not in (30, 60) or width % 2 or height % 2:
        raise ValueError('Maximum side 3840px; even dimensions; 30 or 60 fps required')
    if not isinstance(doc.get('shots'), list) or not doc['shots']:
        raise ValueError('Authored shot list required')
    if not isinstance(doc.get('voice'), dict) or not doc['voice'].get('path'):
        raise ValueError('Upstream renderer requires a real narration asset')
    if not isinstance(doc.get('captions'), list) or not doc['captions']:
        raise ValueError('Upstream B1–B4 renderer requires timed, visible captions')
    return file, doc


def register(item: RegisterProject) -> dict:
    file, doc = _manifest(item.project_file)
    evidence = item.rights_evidence.strip()
    if len(evidence) < 3:
        raise ValueError('Nonblank rights evidence required')
    init()
    with storage.connect() as db:
        db.execute("""INSERT INTO stickman_projects(project_file,style,rights,rights_evidence)
          VALUES(?,?,?,?) ON CONFLICT(project_file) DO UPDATE SET
          style=excluded.style, rights=excluded.rights,
          rights_evidence=excluded.rights_evidence""",
          (str(file), doc['style'], item.rights, evidence))
        row = db.execute('SELECT id FROM stickman_projects WHERE project_file=?',
                         (str(file),)).fetchone()
    return {'id': row['id'], 'style': doc['style'], 'project_file': str(file),
            'rights': item.rights, 'note': 'Renders require visible captions in upstream B1–B4'}


def get(project_id: int) -> dict | None:
    init()
    with storage.connect() as db:
        row = db.execute('SELECT * FROM stickman_projects WHERE id=?', (project_id,)).fetchone()
    return dict(row) if row else None


def _resolve(project_id: int) -> Path:
    record = get(project_id)
    if not record:
        raise ValueError('Unknown Stickman project')
    if record['rights'] not in ('owned', 'licensed', 'permission', 'public_domain') or not record['rights_evidence'].strip():
        raise ValueError('Rights approval and evidence required')
    file, manifest = _manifest(record['project_file'])
    if manifest['style'] != record['style']:
        raise ValueError('Style changed; re-register project before rendering')
    return file


def runtime_status() -> dict:
    root = os.getenv('CLIPFORGE_STICKMAN_SKILL_ROOT', '').strip()
    candidate = Path(root).expanduser().resolve() if root else None
    script = candidate / 'scripts' / 'autopilot.mjs' if candidate else None
    return {
        'configured': bool(candidate and script.is_file()),
        'node': bool(shutil.which('node')),
        'ffmpeg': bool(shutil.which('ffmpeg')),
        'ffprobe': bool(shutil.which('ffprobe')),
        'runtime_styles': list(RUNTIME_STYLES),
        'other_styles': [key for key in STYLE_CATALOG if key not in RUNTIME_STYLES],
        'styles': STYLE_CATALOG,
        'upstream': UPSTREAM,
        'minimum_output': '1080p native',
        'captions': 'required by upstream B1–B4; caption-free export not yet supported',
        'ready_to_check': bool(candidate and script.is_file() and shutil.which('node')
                               and shutil.which('ffmpeg') and shutil.which('ffprobe')),
    }


def execute(project_id: int, action: Literal['validate', 'preview', 'render', 'approve'],
            *, seconds: int = 20, note: str = '') -> dict:
    if action not in ('validate', 'preview', 'render', 'approve'):
        raise ValueError('Unsupported Stickman action')
    file = _resolve(project_id)
    root = os.getenv('CLIPFORGE_STICKMAN_SKILL_ROOT', '').strip()
    skill = Path(root).expanduser().resolve() if root else None
    script = skill / 'scripts' / 'autopilot.mjs' if skill else None
    if not script or not script.is_file():
        raise RuntimeError('Set CLIPFORGE_STICKMAN_SKILL_ROOT to the installed upstream Skill directory')
    if not shutil.which('node') or not shutil.which('ffmpeg') or not shutil.which('ffprobe'):
        raise RuntimeError('Node 20+, FFmpeg and FFprobe must be available to the worker')
    argv = ['node', str(script), action, str(file)]
    if action in ('preview', 'validate'):
        if not isinstance(seconds, int) or not 1 <= seconds <= 60:
            raise ValueError('Preview seconds must be an integer from 1 to 60')
        argv += ['--seconds', str(seconds)]
    if action == 'approve':
        if len(note.strip()) < 4:
            raise ValueError('Approval note must record actual operator review')
        argv += ['--note', note.strip()]
    try:
        completed = subprocess.run(argv, cwd=str(skill), text=True,
                                   capture_output=True, timeout=14400 if action == 'render' else 3600,
                                   check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f'Stickman {action} timed out') from exc
    if completed.returncode:
        raise RuntimeError(f'Upstream {action} failed: {completed.stderr[-1200:]}')
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError:
        raise RuntimeError('Upstream returned non-JSON output') from None
    return {'action': action, 'project_id': project_id, 'result': report}


def output_file(project_id: int, kind: Literal['preview', 'film']) -> Path:
    file = _resolve(project_id)
    if kind not in ('preview', 'film'):
        raise ValueError('Unknown Stickman output')
    output = (file.parent / 'output' / (kind + '.mp4')).resolve()
    if not output.is_relative_to(media_root()) or not output.is_file():
        raise ValueError('Rendered Stickman output not found')
    return output
