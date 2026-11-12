from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from tools.sandbox import PROJECT, initialize, root_path


def original_fingerprint():
    result = {}
    for relative in ("backend/data", "data", "research/corpus", "research/datasets", "research/reviews"):
        folder = PROJECT / relative
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                result[path.relative_to(PROJECT).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return result


class SandboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root = root_path(PROJECT / '.sandboxes' / ('test-' + uuid4().hex))
        cls.before = original_fingerprint()
        initialize(cls.root)

    @classmethod
    def tearDownClass(cls):
        assert original_fingerprint() == cls.before, 'Production data changed during sandbox tests'
        assert cls.root.parent == PROJECT / '.sandboxes' and cls.root.name.startswith('test-')
        shutil.rmtree(cls.root)

    def run_child(self, code):
        env = os.environ.copy(); env['PYTHONIOENCODING'] = 'utf-8'
        completed = subprocess.run([sys.executable,'-c',code,str(self.root)], cwd=PROJECT,
                                   env=env, capture_output=True, text=True, encoding='utf-8', timeout=60)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        return completed.stdout

    def test_idempotent_init_preserves_accounts_and_secret(self):
        paths = [self.root / p for p in ('.env','credentials.json','data/users_store.json','manifest.json')]
        before = [p.read_bytes() for p in paths]
        initialize(self.root)
        self.assertEqual(before, [p.read_bytes() for p in paths])

    def test_copies_never_gain_teacher_approval(self):
        for relative in ('corpus/chunks.jsonl','datasets/independent_review_60.jsonl'):
            rows = [json.loads(s) for s in (self.root/'research'/relative).read_text(encoding='utf-8').splitlines()]
            self.assertTrue(rows)
            self.assertTrue(all(r['review_status']=='review_required' and not r['reviewer_id'] for r in rows))
        self.assertFalse((self.root/'research/reviews').exists())

    def test_only_synthetic_accounts_are_seeded(self):
        users = json.loads((self.root/'data/users_store.json').read_text(encoding='utf-8'))
        self.assertEqual(len(users), 3)
        self.assertEqual({u['role'] for u in users.values()}, {'admin','teacher','student'})
        self.assertTrue(all(email.endswith('@sandbox.example.com') for email in users))
        self.assertTrue(all(u['password_hash'].startswith('$2') for u in users.values()))

    def test_rejects_root_at_existing_working_data_or_symlink_escape(self):
        for path in (PROJECT, PROJECT/'backend/data', PROJECT/'research', PROJECT.parent):
            with self.assertRaises(ValueError): root_path(path)

    def test_profile_paths_and_ai_policy_survive_hostile_environment(self):
        self.run_child('''
from pathlib import Path
import os,sys
from tools.sandbox import activate
activate(Path(sys.argv[1]))
os.environ['COBRAQ_EXTERNAL_AI_ENABLED']='true'
os.environ['ANTHROPIC_API_KEY']='not-a-real-key'
from backend.app.core.config import get_settings
s=get_settings()
assert s.profile=='sandbox' and not s.external_ai_enabled and not s.cloud_ai_available
assert not s.anthropic_api_key
''')

    def test_rejects_paths_outside_sandbox(self):
        self.run_child('''
from pathlib import Path
import os,sys
from tools.sandbox import activate
activate(Path(sys.argv[1]))
os.environ['COBRAQ_DATA_DIR']=str(Path.cwd()/'backend/data')
try:
 from backend.app.core.config import get_settings
 get_settings()
except ValueError: pass
else: raise AssertionError('sandbox escaped')
''')

    def test_full_application_works_without_outgoing_connections(self):
        self.run_child('''
from pathlib import Path
import socket,sys
attempts=[]
original_connect=socket.socket.connect
def blocked(*args,**kwargs):
 address=args[1]
 if isinstance(address,tuple) and address[0] in ('127.0.0.1','::1','localhost'):
  return original_connect(*args,**kwargs)
 attempts.append(args[1:] if len(args)>1 else args)
 raise OSError('Network disabled for sandbox test')
socket.socket.connect=blocked
from tools.sandbox import smoke
smoke(Path(sys.argv[1]))
assert not attempts, 'Application attempted outgoing connections'
''')

    def test_each_storage_module_uses_the_profile(self):
        self.run_child('''
from pathlib import Path
import sys
from tools.sandbox import activate
root=Path(sys.argv[1]); activate(root)
from backend.app.main import app
from backend.app.api import router, files, quiz, groups, tutoring, admin, config
from backend.app.core.audit import audit_log
from backend.app.db.user_store import user_store
from backend.app.db.group_store import group_store
from backend.app.db.group_scores import group_scores
from backend.app.services.evaluation import evaluation_logger
from backend.app.services.vector_service import vector_service
from backend.app.research.store import CorpusStore
for module in (router,files,quiz,groups,admin):
 assert module.user_dir('qa').is_relative_to(root/'data')
assert tutoring.files_index_path('qa').is_relative_to(root/'data')
for obj in (user_store,group_store,group_scores): assert obj._path.is_relative_to(root/'data')
for obj in (audit_log,evaluation_logger): assert obj._log_path.is_relative_to(root/'data')
assert config.CONFIG_FILE.is_relative_to(root/'data')
assert Path(vector_service.persist_dir).is_relative_to(root/'data')
assert CorpusStore().root==root/'research'
''')

    def test_settings_are_independent_of_current_directory(self):
        self.run_child('''
from pathlib import Path
import os,sys
from tools.sandbox import activate
root=Path(sys.argv[1]); activate(root); os.chdir(root/'cache')
from backend.app.core.config import get_settings
assert get_settings().data_dir==root/'data'
''')

    def test_cloud_helpers_refuse_before_constructing_clients(self):
        self.run_child('''
from pathlib import Path
import sys
from tools.sandbox import activate
activate(Path(sys.argv[1]))
from backend.app.api.files import parse_with_vision_ai
from backend.app.api.tutoring import call_claude_api
from fastapi import HTTPException
assert call_claude_api('q','context',[],'unused')[1]
try: parse_with_vision_ai(b'invalid','pdf','unused')
except HTTPException as exc: assert exc.status_code==503
else: raise AssertionError('cloud should be disabled')
''')

    def test_upload_limits_and_env_cannot_enable_cloud(self):
        self.run_child('''
from pathlib import Path
import os,sys
from tools.sandbox import activate
activate(Path(sys.argv[1])); os.environ['COBRAQ_MAX_UPLOAD_BYTES']='1024'
from backend.app.main import app
from fastapi.testclient import TestClient
with TestClient(app) as c:
 assert c.post('/api/files/upload',files={'file':('large.pdf',b'x'*1025,'application/pdf')}).status_code==413
 assert c.post('/api/files/upload',headers={'X-Force-Ai':'true'},files={'file':('test.pdf',b'fake','application/pdf')}).status_code==503
 c.post('/api/config',json={'ai_parse_enabled':True})
 assert not c.get('/api/config/ai').json()['ai_enabled']
''')

    def test_config_uses_separate_secret(self):
        self.run_child('''
from pathlib import Path
import sys
from tools.sandbox import activate
activate(Path(sys.argv[1]))
from backend.app.main import app
from backend.app.core.config import get_settings
from jose import jwt
from fastapi.testclient import TestClient
assert len(get_settings().secret_key)>=64
token=jwt.encode({'sub':'other-profile','role':'admin'}, 'a-different-environment-key', algorithm='HS256')
with TestClient(app) as c:
 assert c.get('/api/research/status',headers={'Authorization':'Bearer '+token}).status_code==401
''')

    def test_start_status_and_stop_only_own_server(self):
        import urllib.request
        with socket.socket() as probe:
            probe.bind(('127.0.0.1',0)); port=probe.getsockname()[1]
        command=[sys.executable,'tools/sandbox.py','serve','--root',str(self.root),'--port',str(port)]
        process=subprocess.Popen(command,cwd=PROJECT,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        try:
            deadline=time.monotonic()+20
            ready=False
            while time.monotonic()<deadline and process.poll() is None:
                try:
                    with urllib.request.urlopen(f'http://127.0.0.1:{port}/health', timeout=.5) as response:
                        ready=json.load(response)['profile']=='sandbox'
                    if ready: break
                except OSError: pass
                time.sleep(.1)
            self.assertTrue(ready,'Sandbox failed to start')
            status=subprocess.run([sys.executable,'tools/sandbox.py','status','--root',str(self.root)],
                cwd=PROJECT,capture_output=True,text=True,timeout=10)
            self.assertTrue(json.loads(status.stdout)['running'])
            stopped=subprocess.run([sys.executable,'tools/sandbox.py','stop','--root',str(self.root)],
                cwd=PROJECT,capture_output=True,text=True,timeout=20)
            self.assertEqual(stopped.returncode,0,stopped.stderr)
            process.wait(timeout=10)
            self.assertFalse((self.root/'run/server.json').exists())
        finally:
            if process.poll() is None:
                process.terminate();process.wait(timeout=10)
            process.communicate(timeout=5)

    def test_stale_pid_file_cannot_kill_another_process(self):
        self.run_child('''
from pathlib import Path
import sys,psutil
from tools.sandbox import json_write,stop
root=Path(sys.argv[1]); me=psutil.Process()
json_write(root/'run/server.json', {'pid':me.pid,'created':me.create_time(),'port':8010})
stop(root)
assert me.is_running()
''')


if __name__=='__main__': unittest.main()
