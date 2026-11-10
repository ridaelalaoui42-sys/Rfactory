"""Authenticated Stickman Director endpoints, registered from clipforge.api."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from . import jobs, stickman

router = APIRouter(prefix='/v1/stickman', tags=['stickman'])


@router.get('/status')
def status():
    return stickman.runtime_status()


@router.post('/projects')
def register(body: stickman.RegisterProject):
    try:
        return stickman.register(body)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/projects/{project_id}')
def get(project_id: int):
    project = stickman.get(project_id)
    if not project:
        raise HTTPException(404, 'Stickman project not found')
    return project


@router.post('/projects/{project_id}/validate')
def validate(project_id: int, options: stickman.PreviewOptions):
    try:
        return stickman.execute(project_id, 'validate', seconds=options.seconds)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/projects/{project_id}/queue-preview')
def queue_preview(project_id: int, options: stickman.PreviewOptions):
    try:
        return {'job_id': jobs.enqueue('stickman_preview', project_id, options.model_dump())}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.post('/projects/{project_id}/approve')
def approve(project_id: int, options: stickman.ApprovalOptions):
    # The caller must actually watch the preview. Upstream binds approval to its hash.
    try:
        return stickman.execute(project_id, 'approve', note=options.note)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc


@router.post('/projects/{project_id}/queue-render')
def queue_render(project_id: int):
    try:
        return {'job_id': jobs.enqueue('stickman_render', project_id)}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@router.get('/projects/{project_id}/download/{kind}')
def download(project_id: int, kind: str):
    if kind not in ('preview', 'film'):
        raise HTTPException(400, 'Choose preview or film')
    try:
        result = stickman.output_file(project_id, kind)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return FileResponse(result, filename=result.name, media_type='video/mp4')
