"""Source-backed History 12 missions. Viewing a marker never awards learning credit."""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import random
import re
from threading import RLock
from uuid import uuid4

from ..core.config import PROJECT_ROOT, data_path
from .document_store import atomic_json, read_json

LOCK = RLock()
PACK_PATH = PROJECT_ROOT / 'research/mission_maps/history12-v1.json'
ERROR_LABELS = {'chronology': 'Thứ tự thời gian', 'evidence': 'Lựa chọn chứng cứ', 'relationship': 'Giải thích quan hệ'}


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


class MissionError(ValueError):
    def __init__(self, message, status=422):
        super().__init__(message)
        self.status = status


def load_pack(path=PACK_PATH):
    pack = json.loads(Path(path).read_text(encoding='utf-8'))
    events = {e['id']: e for e in pack['events']}
    sources = {s['id']: s for s in pack['evidence']}
    missions = {m['id']: m for m in pack['missions']}
    if any(len(rows) != len(ids) for rows, ids in ((pack['events'], events), (pack['evidence'], sources), (pack['missions'], missions))):
        raise ValueError('Duplicate mission pack IDs')
    for event in events.values():
        if date.fromisoformat(event['date_start']) > date.fromisoformat(event['date_end']):
            raise ValueError('Invalid event date interval')
        if not -90 <= event['latitude'] <= 90 or not -180 <= event['longitude'] <= 180:
            raise ValueError('Invalid map coordinate')
        if not set(event['source_ids']) <= sources.keys():
            raise ValueError('Unknown event source')
    for source in sources.values():
        if source['quote_sha256'] != hashlib.sha256(source['quote'].encode()).hexdigest():
            raise ValueError('Source transcription integrity failure')
        if source['book_page'] + 2 != source['pdf_page']:
            raise ValueError('Invalid textbook/PDF page mapping')
    for mission in missions.values():
        if not re.fullmatch(r'[a-z0-9-]{3,80}', mission['id']):
            raise ValueError('Invalid mission ID')
        if not set(mission['event_ids']) <= events.keys() or not set(mission['source_ids']) <= sources.keys():
            raise ValueError('Unknown mission references')
        if len(set(mission['correct_order'])) != len(mission['event_ids']) or set(mission['correct_order']) != set(mission['event_ids']):
            raise ValueError('Invalid reference sequence')
        if mission['correct_order'] != sorted(mission['event_ids'], key=lambda key: events[key]['date_start']):
            raise ValueError('Reference order conflicts with dates')
        if len(set(mission['correct_evidence_ids'])) != 2 or not set(mission['correct_evidence_ids']) <= set(mission['source_ids']):
            raise ValueError('Invalid evidence key')
        if mission['correct_relation_id'] not in {o['id'] for o in mission['relation_options']}:
            raise ValueError('Invalid relationship key')
    return pack


class MissionStore:
    def __init__(self, root=None, pack_path=None):
        self.root = Path(root) if root else data_path('mission_maps')
        self.pack_path = Path(pack_path) if pack_path else PACK_PATH

    def pack(self):
        return load_pack(self.pack_path)

    def bundle(self, mission_id):
        pack = self.pack()
        mission = next((m for m in pack['missions'] if m['id'] == mission_id), None)
        if mission is None:
            raise MissionError('Không có nhiệm vụ này', 404)
        return {'mission': mission, 'events': [e for e in pack['events'] if e['id'] in mission['event_ids']],
                'evidence': [s for s in pack['evidence'] if s['id'] in mission['source_ids']],
                'source_sha256': pack['source_sha256'], 'edition': pack['edition'],
                'coordinate_note': pack['coordinate_note']}

    def review(self, mission_id):
        bundle = self.bundle(mission_id)
        revision = digest(bundle)
        decision = read_json(self.root / 'reviews' / (mission_id + '.json'), {})
        published = decision.get('decision') == 'published' and decision.get('content_hash') == revision
        return {'content_hash': revision, 'published': published,
                'status': 'published' if published else 'changed' if decision.get('decision') == 'published' else 'draft',
                'reviewer_id': decision.get('reviewer_id', ''), 'reviewed_at': decision.get('reviewed_at', '')}

    def decide(self, mission_id, user, expected_hash, decision, source_checked, notes):
        with LOCK:
            state = self.review(mission_id)
            if expected_hash != state['content_hash']:
                raise MissionError('Nội dung đã thay đổi. Tải lại trước khi duyệt.', 409)
            if decision == 'published' and not source_checked:
                raise MissionError('Cần xác nhận đã đối chiếu nguồn, mốc thời gian và vị trí trước khi mở cho học sinh.')
            row = {'mission_id': mission_id, 'content_hash': expected_hash, 'decision': decision,
                   'source_checked': source_checked, 'reviewer_id': user, 'reviewed_at': now(), 'notes': notes}
            atomic_json(self.root / 'reviews' / (mission_id + '.json'), row)
            atomic_json(self.root / 'review_history' / f'{uuid4().hex}.json', row)
            return self.review(mission_id)

    def public_mission(self, mission_id):
        bundle = self.bundle(mission_id)
        mission = {k: v for k, v in bundle['mission'].items() if not k.startswith('correct_') and k not in {'teacher_guide', 'relation_explanation'}}
        return {**bundle, 'mission': mission, 'review': self.review(mission_id)}

    def catalog(self, user):
        pack = self.pack()
        teacher = user and user.get('role') in {'teacher', 'admin'}
        lessons = json.loads((PROJECT_ROOT / 'research/corpus/lessons.json').read_text(encoding='utf-8'))
        rows = []
        for m in pack['missions']:
            state = self.review(m['id'])
            rows.append({k: m[k] for k in ('id', 'title', 'summary', 'lesson_ids', 'duration_minutes')})
            rows[-1].update(state, can_start=bool(user and (teacher or state['published'])), preview=not state['published'])
        return {'title': pack['title'], 'edition': pack['edition'], 'coordinate_note': pack['coordinate_note'],
                'lessons': lessons, 'missions': rows, 'can_review': bool(teacher),
                'rubric': [{'id': 'history', 'title': 'Tính chính xác và lập luận', 'max_points': 2},
                           {'id': 'sources', 'title': 'Sử dụng chứng cứ phù hợp', 'max_points': 2}]}

    def _owner(self, uid):
        return self.root / 'attempts' / hashlib.sha256(uid.encode()).hexdigest()[:24]

    def attempt(self, uid, attempt_id):
        if not re.fullmatch(r'[a-f0-9]{32}', attempt_id):
            raise MissionError('Không tìm thấy lượt làm', 404)
        row = read_json(self._owner(uid) / (attempt_id + '.json'))
        if row is None:
            raise MissionError('Không tìm thấy lượt làm', 404)
        return row

    def save(self, row):
        atomic_json(self._owner(row['owner']) / (row['id'] + '.json'), row)

    def start(self, user, mission_id):
        with LOCK:
            state = self.review(mission_id)
            teacher = user.get('role') in {'teacher', 'admin'}
            if not state['published'] and not teacher:
                raise MissionError('Nhiệm vụ đang chờ giáo viên đối chiếu và duyệt.', 403)
            bundle = self.bundle(mission_id)
            event_order = list(bundle['mission']['event_ids'])
            source_order = list(bundle['mission']['source_ids'])
            random.SystemRandom().shuffle(event_order)
            random.SystemRandom().shuffle(source_order)
            row = {'id': uuid4().hex, 'mission_id': mission_id, 'owner': user['sub'], 'display_name': user.get('name') or user['sub'],
                   'revision': 1, 'content_hash': state['content_hash'], 'snapshot': bundle, 'is_preview': not state['published'],
                   'created_at': now(), 'status': 'in_progress', 'opened_sources': [],
                   'draft': {'event_order': event_order, 'evidence_ids': [], 'relation_id': '', 'explanation': ''},
                   'source_order': source_order, 'result': None}
            self.save(row)
            return self.public_attempt(row)

    def public_attempt(self, row):
        snapshot = row['snapshot']
        mission = {k: v for k, v in snapshot['mission'].items() if not k.startswith('correct_') and k not in {'teacher_guide', 'relation_explanation'}}
        public = {**snapshot, 'mission': mission, 'review': self.review(row['mission_id'])}
        return {k: v for k, v in row.items() if k not in {'snapshot', 'owner', 'source_order', 'submission_hash'}} | {
            'content': public, 'source_order': row['source_order']}

    def _active(self, row):
        if row['content_hash'] != self.review(row['mission_id'])['content_hash']:
            raise MissionError('Nhiệm vụ đã được cập nhật. Hãy mở một lượt mới.', 409)
        if not row['is_preview'] and not self.review(row['mission_id'])['published']:
            raise MissionError('Giáo viên đã tạm dừng nhiệm vụ này.', 409)

    def opened(self, uid, attempt_id, source_id):
        with LOCK:
            row = self.attempt(uid, attempt_id)
            self._active(row)
            if source_id not in row['snapshot']['mission']['source_ids']:
                raise MissionError('Nguồn không thuộc nhiệm vụ')
            if source_id not in row['opened_sources']:
                row['opened_sources'].append(source_id)
                self.save(row)
            return {'opened_sources': row['opened_sources']}

    def validate_answers(self, row, answers, final=False):
        mission = row['snapshot']['mission']
        order, evidence = answers['event_order'], answers['evidence_ids']
        if len(order) != len(set(order)) or set(order) != set(mission['event_ids']):
            raise MissionError('Mỗi mốc phải xuất hiện đúng một lần trong trình tự.')
        if len(evidence) != len(set(evidence)) or not set(evidence) <= set(mission['source_ids']) or len(evidence) > 2:
            raise MissionError('Chọn tối đa hai nguồn khác nhau trong nhiệm vụ.')
        if answers['relation_id'] and answers['relation_id'] not in {o['id'] for o in mission['relation_options']}:
            raise MissionError('Lựa chọn nhận định không hợp lệ')
        if final and (len(evidence) != 2 or not answers['relation_id'] or len(answers['explanation'].strip()) < 30):
            raise MissionError('Cần chọn hai chứng cứ, một nhận định và viết ít nhất 30 ký tự giải thích.')
        if final and not set(evidence) <= set(row['opened_sources']):
            raise MissionError('Mở và đọc từng nguồn đã chọn trước khi nộp bài.')

    def draft(self, uid, attempt_id, answers, expected_revision):
        with LOCK:
            row = self.attempt(uid, attempt_id)
            self._active(row)
            if row['status'] != 'in_progress' or row['revision'] != expected_revision:
                raise MissionError('Lượt làm đã thay đổi hoặc đã nộp. Tải lại trước khi lưu.', 409)
            self.validate_answers(row, answers)
            row.update(draft=answers, revision=row['revision'] + 1)
            self.save(row)
            return self.public_attempt(row)

    def objective_result(self, mission, answers):
        expected = mission['correct_order']
        actual = answers['event_order']
        pairs = list(zip(expected, expected[1:]))
        chronology = round(2 * sum(actual.index(a) < actual.index(b) for a, b in pairs) / len(pairs), 2)
        evidence = float(set(answers['evidence_ids']) == set(mission['correct_evidence_ids'])) * 2
        relationship = float(answers['relation_id'] == mission['correct_relation_id']) * 2
        return {'automatic_points': chronology + evidence + relationship, 'automatic_max': 6,
                'parts': {'chronology': chronology, 'evidence': evidence, 'relationship': relationship},
                'needs_practice': [key for key, score in [('chronology', chronology), ('evidence', evidence), ('relationship', relationship)] if score < 2],
                'manual_review': None, 'total_points': None, 'total_max': 10,
                'reference_order': expected, 'reference_evidence_ids': mission['correct_evidence_ids'],
                'reference_relation_id': mission['correct_relation_id'], 'explanation': mission['relation_explanation']}

    def demo(self, mission_id):
        content = self.public_mission(mission_id)
        order = list(content['mission']['event_ids'])
        random.SystemRandom().shuffle(order)
        return {'id': None, 'mission_id': mission_id, 'display_name': 'Trải nghiệm nhiệm vụ',
                'is_demo': True, 'is_preview': True, 'status': 'in_progress', 'revision': 0,
                'content': content, 'source_order': [s['id'] for s in content['evidence']],
                'draft': {'event_order': order, 'evidence_ids': [], 'relation_id': '', 'explanation': ''}, 'result': None}

    def check_demo(self, mission_id, answers):
        bundle = self.bundle(mission_id)
        row = {'snapshot': bundle, 'opened_sources': answers['evidence_ids']}
        self.validate_answers(row, answers, final=True)
        # A demo never writes attempts, publishes content or creates a teacher grade.
        return {'is_demo': True, 'persisted': False, 'result': self.objective_result(bundle['mission'], answers)}

    def submit(self, uid, attempt_id, answers):
        with LOCK:
            row = self.attempt(uid, attempt_id)
            self._active(row)
            if row['status'] != 'in_progress':
                if row.get('submission_hash') == digest(answers):
                    return self.public_attempt(row)
                raise MissionError('Lượt làm đã nộp. Mở lượt mới để luyện lại.', 409)
            self.validate_answers(row, answers, final=True)
            row.update(draft=answers, status='submitted', submitted_at=now(), submission_hash=digest(answers), revision=row['revision'] + 1,
                       result=self.objective_result(row['snapshot']['mission'], answers))
            self.save(row)
            return self.public_attempt(row)

    def progress(self, uid):
        attempts = [read_json(p) for p in self._owner(uid).glob('*.json')]
        valid = [a for a in attempts if a['status'] != 'in_progress' and not a['is_preview']
                 and a['content_hash'] == self.review(a['mission_id'])['content_hash']]
        latest = {}
        for a in sorted(valid, key=lambda row: row['submitted_at']):
            latest[a['mission_id']] = a
        weak = {key: sum(key in a['result']['needs_practice'] for a in latest.values()) for key in ERROR_LABELS}
        return {'attempts': [{'id': a['id'], 'mission_id': a['mission_id'], 'status': a['status'], 'is_preview': a['is_preview'],
                             'revision': a['revision'], 'submitted_at': a.get('submitted_at'), 'result': a['result']} for a in sorted(attempts, key=lambda r: r['created_at'], reverse=True)],
                'submitted_missions': len({a['mission_id'] for a in valid}),
                'needs_practice': [{'id': k, 'label': ERROR_LABELS[k], 'count': v} for k, v in weak.items() if v],
                'recommendations': [{'mission_id': a['mission_id'], 'reason': 'Ôn lại ' + ', '.join(ERROR_LABELS[k] for k in a['result']['needs_practice'])}
                                    for a in latest.values() if a['result']['needs_practice']]}

    def teacher_queue(self):
        rows = [read_json(p) for p in (self.root / 'attempts').glob('*/*.json')]
        rows = [r for r in rows if r['status'] != 'in_progress']
        return [{'id': r['id'], 'owner': r['owner'], 'display_name': r['display_name'], 'mission_id': r['mission_id'],
                 'mission_title': r['snapshot']['mission']['title'], 'submitted_at': r['submitted_at'], 'revision': r['revision'],
                 'is_preview': r['is_preview'], 'answers': r['draft'], 'result': r['result'],
                 'teacher_guide': r['snapshot']['mission']['teacher_guide'], 'sources': r['snapshot']['evidence']}
                for r in sorted(rows, key=lambda r: r['submitted_at'], reverse=True)]

    def grade(self, reviewer, owner, attempt_id, history_points, source_points, comment, expected_revision):
        with LOCK:
            row = self.attempt(owner, attempt_id)
            if row['status'] == 'in_progress' or row['revision'] != expected_revision:
                raise MissionError('Bài chưa nộp hoặc nhận xét đã thay đổi. Tải lại danh sách.', 409)
            row['result']['manual_review'] = {'reviewer_id': reviewer, 'reviewed_at': now(), 'history_points': history_points,
                                              'source_points': source_points, 'comment': comment}
            row['result']['total_points'] = row['result']['automatic_points'] + history_points + source_points
            row.update(status='reviewed', revision=row['revision'] + 1)
            self.save(row)
            return {'revision': row['revision'], 'result': row['result']}
