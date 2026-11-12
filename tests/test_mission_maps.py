from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.api.mission_map import router, store
from backend.app.core.security import get_current_user, get_current_user_optional
from backend.app.services.mission_maps import MissionStore, MissionError, PACK_PATH, load_pack


class MissionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.pack_path = root / 'pack.json'
        self.pack_path.write_bytes(PACK_PATH.read_bytes())
        self.store = MissionStore(root / 'data', self.pack_path)
        self.teacher = {'sub': 'teacher@example.com', 'name': 'Teacher', 'role': 'teacher'}
        self.student = {'sub': 'student@example.com', 'name': 'Student', 'role': 'student'}
        self.mid = 'chien-truong-ban-dam-phan-1954'
        self.user = self.student
        self.app = FastAPI()
        self.app.include_router(router, prefix='/api')
        self.app.dependency_overrides[store] = lambda: self.store
        self.app.dependency_overrides[get_current_user] = lambda: self.user
        self.app.dependency_overrides[get_current_user_optional] = lambda: self.user
        self.client = TestClient(self.app)

    def publish(self):
        review = self.store.review(self.mid)
        self.store.decide(self.mid, self.teacher['sub'], review['content_hash'], 'published', True, 'Đã đối chiếu nguồn')

    def start(self, preview=False):
        if not preview:
            self.publish()
        return self.store.start(self.teacher if preview else self.student, self.mid)

    def answers(self, a):
        mission = self.store.bundle(a['mission_id'])['mission']
        return {'event_order': mission['correct_order'], 'evidence_ids': mission['correct_evidence_ids'],
                'relation_id': mission['correct_relation_id'],
                'explanation': 'Theo nguồn SGK trang 42 và 79, cần giải thích quan hệ giữa chiến trường và đàm phán từ chứng cứ.'}

    def open_sources(self, a, answers):
        for source in answers['evidence_ids']:
            self.store.opened(self.student['sub'] if not a['is_preview'] else self.teacher['sub'], a['id'], source)

    def test_pack_references_and_two_independent_missions(self):
        p = load_pack()
        self.assertEqual(len(p['missions']), 2)
        self.assertEqual(len(p['events']), 6)
        self.assertTrue(all(e['location_note'] for e in p['events']))
        self.assertTrue(all(s['quote_sha256'] for s in p['evidence']))

    def test_catalog_covers_17_lessons_without_claiming_17_missions(self):
        catalog = self.store.catalog(self.student)
        self.assertEqual(len(catalog['lessons']), 17)
        self.assertEqual(len(catalog['missions']), 2)
        self.assertFalse(any(m['published'] for m in catalog['missions']))

    def test_student_cannot_start_draft(self):
        with self.assertRaises(MissionError) as e:
            self.store.start(self.student, self.mid)
        self.assertEqual(e.exception.status, 403)

    def test_preview_never_awards_student_progress(self):
        a = self.start(preview=True)
        answers = self.answers(a)
        self.open_sources(a, answers)
        self.store.submit(self.teacher['sub'], a['id'], answers)
        progress = self.store.progress(self.teacher['sub'])
        self.assertEqual(progress['submitted_missions'], 0)
        self.assertEqual(progress['recommendations'], [])

    def test_publication_requires_source_check_and_current_hash(self):
        h = self.store.review(self.mid)['content_hash']
        with self.assertRaises(MissionError):
            self.store.decide(self.mid, 'teacher', h, 'published', False, '')
        with self.assertRaises(MissionError):
            self.store.decide(self.mid, 'teacher', '0' * 64, 'published', True, '')
        self.assertFalse(self.store.review(self.mid)['published'])

    def test_source_or_coordinate_changes_invalidate_publication(self):
        self.publish()
        p = json.loads(self.pack_path.read_text(encoding='utf-8'))
        p['events'][3]['latitude'] += .001
        self.pack_path.write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
        self.assertEqual(self.store.review(self.mid)['status'], 'changed')
        self.assertFalse(self.store.review(self.mid)['published'])

    def test_public_attempt_contains_no_reference_answer_or_teacher_guide(self):
        a = self.start()
        raw = json.dumps(a)
        for key in ('correct_order', 'correct_evidence_ids', 'correct_relation_id', 'teacher_guide', 'relation_explanation', 'snapshot'):
            self.assertNotIn('"' + key + '"', raw)
        self.assertIsNone(a['result'])

    def test_own_draft_survives_new_store_instance(self):
        a = self.start()
        answers = self.answers(a)
        saved = self.store.draft(self.student['sub'], a['id'], answers, 1)
        other = MissionStore(self.store.root, self.pack_path)
        restored = other.attempt(self.student['sub'], a['id'])
        self.assertEqual(saved['revision'], 2)
        self.assertEqual(restored['draft'], answers)

    def test_stale_draft_revision_is_rejected(self):
        a = self.start()
        answers = self.answers(a)
        self.store.draft(self.student['sub'], a['id'], answers, 1)
        with self.assertRaises(MissionError):
            self.store.draft(self.student['sub'], a['id'], answers, 1)

    def test_duplicate_event_or_foreign_evidence_rejected(self):
        a = self.start()
        answers = self.answers(a)
        answers['event_order'] = ['e04'] * 3
        with self.assertRaises(MissionError):
            self.store.draft(self.student['sub'], a['id'], answers, 1)
        answers = self.answers(a)
        answers['evidence_ids'] = ['s01', 's99']
        with self.assertRaises(MissionError):
            self.store.draft(self.student['sub'], a['id'], answers, 1)

    def test_source_must_be_opened_before_submission(self):
        a = self.start()
        with self.assertRaises(MissionError):
            self.store.submit(self.student['sub'], a['id'], self.answers(a))
        self.assertEqual(self.store.attempt(self.student['sub'], a['id'])['status'], 'in_progress')

    def test_viewing_source_awards_no_points(self):
        a = self.start()
        self.store.opened(self.student['sub'], a['id'], 's04')
        row = self.store.attempt(self.student['sub'], a['id'])
        self.assertIsNone(row['result'])
        self.assertEqual(self.store.progress(self.student['sub'])['submitted_missions'], 0)

    def test_full_answer_only_grades_the_six_objective_points(self):
        a = self.start()
        answers = self.answers(a)
        self.open_sources(a, answers)
        response = self.store.submit(self.student['sub'], a['id'], answers)
        self.assertEqual(response['result']['automatic_points'], 6)
        self.assertIsNone(response['result']['total_points'])
        self.assertIsNone(response['result']['manual_review'])
        self.assertEqual(response['result']['needs_practice'], [])

    def test_wrong_chronology_evidence_relation_have_separate_feedback(self):
        a = self.start()
        answers = self.answers(a)
        answers.update(event_order=list(reversed(answers['event_order'])), evidence_ids=['s04', 's07'], relation_id='r1')
        self.open_sources(a, answers)
        response = self.store.submit(self.student['sub'], a['id'], answers)
        self.assertEqual(response['result']['automatic_points'], 0)
        self.assertEqual(set(response['result']['needs_practice']), {'chronology', 'evidence', 'relationship'})
        progress = self.store.progress(self.student['sub'])
        self.assertEqual(progress['submitted_missions'], 1)
        self.assertTrue(progress['recommendations'])

    def test_double_submit_is_idempotent_and_mutation_rejected(self):
        a = self.start()
        answers = self.answers(a)
        self.open_sources(a, answers)
        first = self.store.submit(self.student['sub'], a['id'], answers)
        second = self.store.submit(self.student['sub'], a['id'], answers)
        self.assertEqual(first['revision'], second['revision'])
        answers['relation_id'] = 'r3'
        with self.assertRaises(MissionError):
            self.store.submit(self.student['sub'], a['id'], answers)

    def test_successful_retry_clears_old_recommendation(self):
        a = self.start()
        answers = self.answers(a)
        answers['relation_id'] = 'r1'
        self.open_sources(a, answers)
        self.store.submit(self.student['sub'], a['id'], answers)
        self.assertTrue(self.store.progress(self.student['sub'])['recommendations'])
        retry = self.store.start(self.student, self.mid)
        correct = self.answers(retry)
        self.open_sources(retry, correct)
        self.store.submit(self.student['sub'], retry['id'], correct)
        self.assertEqual(self.store.progress(self.student['sub'])['recommendations'], [])

    def test_student_cannot_fetch_draft_page_image(self):
        self.assertEqual(self.client.get('/api/mission-map/sources/s04/page').status_code, 403)

    def test_pack_rejects_reference_order_that_conflicts_with_dates(self):
        p = json.loads(self.pack_path.read_text(encoding='utf-8'))
        p['missions'][1]['correct_order'].reverse()
        self.pack_path.write_text(json.dumps(p, ensure_ascii=False), encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'conflicts with dates'):
            self.store.pack()

    def test_student_cannot_read_another_attempt(self):
        a = self.start()
        with self.assertRaises(MissionError):
            self.store.attempt('other@example.com', a['id'])
        self.assertEqual(self.client.get('/api/mission-map/attempts/../../etc').status_code, 404)

    def test_unpublish_blocks_inflight_student_submission(self):
        a = self.start()
        state = self.store.review(self.mid)
        self.store.decide(self.mid, 'teacher', state['content_hash'], 'draft', False, '')
        with self.assertRaises(MissionError):
            self.store.opened(self.student['sub'], a['id'], 's04')

    def test_api_role_permissions(self):
        self.assertEqual(self.client.get('/api/mission-map/teacher/submissions').status_code, 403)
        self.assertEqual(self.client.get('/api/mission-map/missions/' + self.mid).status_code, 403)
        self.assertEqual(self.client.post('/api/mission-map/missions/' + self.mid + '/start').status_code, 403)
        self.user = self.teacher
        self.assertEqual(self.client.get('/api/mission-map/teacher/submissions').status_code, 200)
        self.assertEqual(self.client.post('/api/mission-map/missions/' + self.mid + '/start').status_code, 200)

    def test_api_requires_login(self):
        self.app.dependency_overrides.pop(get_current_user)
        self.assertEqual(self.client.get('/api/mission-map/progress').status_code, 401)
        self.assertEqual(self.client.post('/api/mission-map/missions/' + self.mid + '/start').status_code, 401)

    def test_public_demo_is_usable_without_login_and_contains_no_answer_key(self):
        self.app.dependency_overrides.pop(get_current_user)
        response = self.client.get('/api/mission-map/missions/' + self.mid + '/demo')
        self.assertEqual(response.status_code, 200)
        a = response.json()
        self.assertTrue(a['is_demo'])
        self.assertIsNone(a['id'])
        self.assertNotIn('correct_order', a['content']['mission'])
        self.assertNotIn('teacher_guide', a['content']['mission'])
        self.assertFalse(self.store.root.exists())

    def test_demo_check_does_not_publish_grade_or_store_student_attempt(self):
        a = self.store.demo(self.mid)
        answers = self.answers(a)
        response = self.client.post('/api/mission-map/missions/' + self.mid + '/demo/check', json=answers)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['result']['automatic_points'], 6)
        self.assertFalse(response.json()['persisted'])
        self.assertIsNone(response.json()['result']['manual_review'])
        self.assertFalse(self.store.root.exists())
        self.assertFalse(self.store.review(self.mid)['published'])

    def test_demo_still_validates_answers(self):
        a = self.store.demo(self.mid)
        answers = self.answers(a)
        answers['event_order'] = ['e04'] * 3
        response = self.client.post('/api/mission-map/missions/' + self.mid + '/demo/check', json=answers)
        self.assertEqual(response.status_code, 422)

    def test_teacher_grading_preserves_objective_scores_and_updates_student_result(self):
        a = self.start()
        answers = self.answers(a)
        self.open_sources(a, answers)
        submitted = self.store.submit(self.student['sub'], a['id'], answers)
        self.user = self.teacher
        payload = {'owner': self.student['sub'], 'expected_revision': submitted['revision'],
                   'history_points': 2, 'source_points': 1, 'comment': 'Lập luận rõ, cần dẫn đúng cả hai nguồn trong phần giải thích.'}
        response = self.client.post('/api/mission-map/teacher/submissions/' + a['id'] + '/grade', json=payload)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['result']['total_points'], 9)
        self.assertEqual(response.json()['result']['automatic_points'], 6)
        self.assertEqual(self.client.post('/api/mission-map/teacher/submissions/' + a['id'] + '/grade', json=payload).status_code, 409)
        self.user = self.student
        self.assertEqual(self.client.get('/api/mission-map/attempts/' + a['id']).json()['result']['total_points'], 9)

    def test_grade_rejects_out_of_range_or_automatic_student_grading(self):
        a = self.start()
        payload = {'owner': self.student['sub'], 'expected_revision': 1, 'history_points': 2, 'source_points': 2, 'comment': 'Nhận xét của học sinh tự gửi.'}
        self.assertEqual(self.client.post('/api/mission-map/teacher/submissions/' + a['id'] + '/grade', json=payload).status_code, 403)
        self.user = self.teacher
        payload['history_points'] = 3
        self.assertEqual(self.client.post('/api/mission-map/teacher/submissions/' + a['id'] + '/grade', json=payload).status_code, 422)


if __name__ == '__main__':
    unittest.main()
