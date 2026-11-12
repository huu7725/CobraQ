"""History 12 learning missions, source inspection, teacher publication and feedback."""
from __future__ import annotations

from functools import lru_cache
import hashlib
import os
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from ..core.config import PROJECT_ROOT, get_settings
from ..core.security import get_current_user, get_current_user_optional
from ..services.mission_maps import MissionError, MissionStore

router = APIRouter(prefix='/mission-map', tags=['history12-missions'])


def store():
    return MissionStore()


def teacher(user=Depends(get_current_user)):
    if user.get('role') not in {'teacher', 'admin'}:
        raise HTTPException(403, 'Cần quyền giáo viên hoặc quản trị viên')
    return user


def invoke(function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except MissionError as exc:
        raise HTTPException(exc.status, str(exc)) from exc


class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Answers(StrictBody):
    event_order: list[str] = Field(min_length=1, max_length=12)
    evidence_ids: list[str] = Field(default_factory=list, max_length=2)
    relation_id: str = Field(default='', max_length=40)
    explanation: str = Field(default='', max_length=5000)


class Draft(Answers):
    expected_revision: int = Field(ge=1)


class Publication(StrictBody):
    expected_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    decision: Literal['published', 'draft']
    source_checked: bool = False
    notes: str = Field(default='', max_length=3000)


class OpenSource(StrictBody):
    source_id: str = Field(min_length=1, max_length=40)


class Grade(StrictBody):
    owner: str = Field(min_length=1, max_length=254)
    expected_revision: int = Field(ge=1)
    history_points: int = Field(ge=0, le=2, strict=True)
    source_points: int = Field(ge=0, le=2, strict=True)
    comment: str = Field(min_length=10, max_length=3000)


@router.get('/catalog')
def catalog(user=Depends(get_current_user_optional), repository=Depends(store)):
    return repository.catalog(user)


@router.get('/progress')
def progress(user=Depends(get_current_user), repository=Depends(store)):
    return repository.progress(user['sub'])


@router.get('/teacher/submissions')
def submissions(user=Depends(teacher), repository=Depends(store)):
    return {'submissions': repository.teacher_queue()}


@router.post('/teacher/submissions/{attempt_id}/grade')
def grade(attempt_id: str, body: Grade, user=Depends(teacher), repository=Depends(store)):
    return invoke(repository.grade, user['sub'], body.owner, attempt_id, body.history_points,
                  body.source_points, body.comment, body.expected_revision)


@router.get('/missions/{mission_id}')
def mission(mission_id: str, user=Depends(teacher), repository=Depends(store)):
    public = invoke(repository.public_mission, mission_id)
    public['teacher_reference'] = repository.bundle(mission_id)['mission']
    return public


@router.get('/missions/{mission_id}/demo')
def demo(mission_id: str, repository=Depends(store)):
    return invoke(repository.demo, mission_id)


@router.post('/missions/{mission_id}/demo/check')
def check_demo(mission_id: str, body: Answers, repository=Depends(store)):
    return invoke(repository.check_demo, mission_id, body.model_dump())


@router.post('/missions/{mission_id}/review')
def review(mission_id: str, body: Publication, user=Depends(teacher), repository=Depends(store)):
    return invoke(repository.decide, mission_id, user['sub'], body.expected_hash, body.decision, body.source_checked, body.notes)


@router.post('/missions/{mission_id}/start')
def start(mission_id: str, user=Depends(get_current_user), repository=Depends(store)):
    return invoke(repository.start, user, mission_id)


def own_attempt(repository, user, attempt_id):
    row = invoke(repository.attempt, user['sub'], attempt_id)
    if row['is_preview'] and user.get('role') not in {'teacher', 'admin'}:
        raise HTTPException(403, 'Đây là lượt xem trước của giáo viên')
    return row


@router.get('/attempts/{attempt_id}')
def attempt(attempt_id: str, user=Depends(get_current_user), repository=Depends(store)):
    return repository.public_attempt(own_attempt(repository, user, attempt_id))


@router.put('/attempts/{attempt_id}/draft')
def draft(attempt_id: str, body: Draft, user=Depends(get_current_user), repository=Depends(store)):
    own_attempt(repository, user, attempt_id)
    answers = body.model_dump(exclude={'expected_revision'})
    return invoke(repository.draft, user['sub'], attempt_id, answers, body.expected_revision)


@router.post('/attempts/{attempt_id}/sources')
def opened(attempt_id: str, body: OpenSource, user=Depends(get_current_user), repository=Depends(store)):
    own_attempt(repository, user, attempt_id)
    return invoke(repository.opened, user['sub'], attempt_id, body.source_id)


@router.post('/attempts/{attempt_id}/submit')
def submit(attempt_id: str, body: Answers, user=Depends(get_current_user), repository=Depends(store)):
    own_attempt(repository, user, attempt_id)
    return invoke(repository.submit, user['sub'], attempt_id, body.model_dump())


@lru_cache(maxsize=4)
def pdf_digest(path, modified, size):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def source_pdf(expected_hash):
    config = get_settings()
    candidates = [Path(os.environ['COBRAQ_HISTORY12_PDF'])] if os.environ.get('COBRAQ_HISTORY12_PDF') else []
    candidates += [config.research_dir / 'sources/history12_kntt_2023_sample.pdf', PROJECT_ROOT / 'research/sources/history12_kntt_2023_sample.pdf']
    candidates += list((config.data_dir / 'documents').glob(f'*/doc-{expected_hash[:24]}/source.pdf'))
    for path in candidates:
        if path.is_file():
            stat = path.stat()
            if pdf_digest(str(path), stat.st_mtime_ns, stat.st_size) == expected_hash:
                return path
    raise HTTPException(503, 'Chưa có bản PDF nguồn khớp. Giáo viên có thể đọc trích đoạn và cấp PDF gốc để đối chiếu ảnh.')


@router.get('/sources/{source_id}/page')
def source_page(source_id: str, user=Depends(get_current_user), repository=Depends(store)):
    pack = repository.pack()
    allowed = set()
    for m in pack['missions']:
        if user.get('role') in {'teacher', 'admin'} or repository.review(m['id'])['published']:
            allowed.update(m['source_ids'])
    if source_id not in allowed:
        raise HTTPException(403, 'Nguồn chưa được mở cho tài khoản này')
    source = next((s for s in pack['evidence'] if s['id'] == source_id), None)
    if source is None:
        raise HTTPException(404, 'Không có nguồn này')
    import pymupdf
    with pymupdf.open(source_pdf(pack['source_sha256'])) as pdf:
        if not 1 <= source['pdf_page'] <= len(pdf):
            raise HTTPException(404, 'Trang nguồn không hợp lệ')
        png = pdf[source['pdf_page'] - 1].get_pixmap(matrix=pymupdf.Matrix(1.4, 1.4), alpha=False).tobytes('png')
    return Response(png, media_type='image/png', headers={'Cache-Control': 'private, max-age=300'})
