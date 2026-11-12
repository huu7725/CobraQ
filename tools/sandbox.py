"""Create and run CobraQ's disposable local sandbox without copying production accounts."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
from uuid import uuid4

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))


def root_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    allowed = path == PROJECT / ".sandbox" or path.is_relative_to(PROJECT / ".sandboxes")
    container = os.environ.get("COBRAQ_CONTAINER") == "1" and path == Path("/runtime")
    if not allowed and not container:
        raise ValueError("Use .sandbox or .sandboxes/<name> inside the project")
    return path


def json_write(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def initialize(root: Path) -> dict:
    manifest = root / "manifest.json"
    if manifest.exists() and (root / ".env").exists():
        result = read_json(manifest)
        if result.get("kind") != "cobraq-sandbox":
            raise ValueError("Unrecognized sandbox manifest")
        return result
    if root.exists():
        raise ValueError("Incomplete sandbox already exists; choose a new .sandboxes/<name> profile")
    root.parent.mkdir(parents=True, exist_ok=True)
    stage = root.with_name(root.name + ".initializing-" + uuid4().hex)
    stage.mkdir()
    try:
        from passlib.context import CryptContext
        passwords = CryptContext(schemes=["bcrypt"], deprecated="auto")
        now = datetime.now(timezone.utc).isoformat()
        for name in ("data", "logs", "run", "cache", "models", "artifacts/adapters"):
            (stage / name).mkdir(parents=True, exist_ok=True)
        secret = secrets.token_hex(32)
        env = {"COBRAQ_PROFILE":"sandbox", "COBRAQ_SANDBOX_ROOT":root.as_posix(),
               "COBRAQ_DATA_DIR":(root / "data").as_posix(), "COBRAQ_RESEARCH_ROOT":(root / "research").as_posix(),
               "COBRAQ_EXTERNAL_AI_ENABLED":"false", "COBRAQ_VECTOR_ENABLED":"false",
               "COBRAQ_MAX_UPLOAD_BYTES":str(100 * 1024 * 1024), "SECRET_KEY":secret,
               "ANTHROPIC_API_KEY":"", "APP_NAME":"CobraQ Sandbox", "DEBUG":"false"}
        (stage / ".env").write_text("".join(f'{key}="{value}"\n' for key,value in env.items()), encoding="utf-8")
        source_hashes = {}
        for relative in ("corpus/chunks.jsonl", "corpus/lessons.json", "datasets/independent_review_60.jsonl",
                         "datasets/retrieval_gold_recovered.csv", "sources/history12_kntt_2023_sample.pdf", "RECOVERY_MANIFEST.json"):
            source = PROJECT / "research" / relative
            if not source.exists():
                if relative.startswith("sources/"):
                    continue
                raise ValueError(f"Missing sandbox seed: research/{relative}")
            target = stage / "research" / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            source_hashes[relative] = hashlib.sha256(source.read_bytes()).hexdigest()
        # Copies always begin unreviewed. Production review revisions are never copied.
        for relative in ("corpus/chunks.jsonl", "datasets/independent_review_60.jsonl"):
            path = stage / "research" / relative
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
            for row in rows:
                row.update(review_status="review_required", reviewer_id="", reviewed_at="")
                for key in list(row):
                    if key.startswith("approved_"): row.pop(key)
            path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
        import csv
        gold = stage / "research/datasets/retrieval_gold_recovered.csv"
        with gold.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream); fields = reader.fieldnames; rows = list(reader)
        for row in rows:
            row.update(relevant_chunk_ids="[]", review_status="review_required", reviewer_id="", reviewed_at="")
            if "approved_source_hash" in row: row["approved_source_hash"] = ""
        with gold.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
        users, credentials = {}, []
        questions = [{"id":i, "question":f"[MÔ PHỎNG {i}] Đây là môi trường nào?",
                      "choices":[{"label":"A", "text":"Sandbox thử nghiệm"}, {"label":"B", "text":"Hệ thống dữ liệu thật"},
                                 {"label":"C", "text":"Kết quả nghiên cứu chính thức"}, {"label":"D", "text":"Ngân hàng câu đã được giáo viên duyệt"}],
                      "answer":"A", "explanation":"Dữ liệu mô phỏng chỉ để thử chức năng, không dùng học hoặc nghiên cứu."}
                     for i in range(1,11)]
        for role in ("admin", "teacher", "student"):
            email = f"{role}@sandbox.example.com"
            password = secrets.token_urlsafe(18)
            users[email] = {"email":email, "name":f"Sandbox {role}", "password_hash":passwords.hash(password),
                            "role":role, "created_at":now}
            credentials.append({"role":role, "email":email, "password":password})
            folder = stage / "data/users" / re.sub(r"[^\w]", "_", email)
            json_write(folder / "sandbox_demo.json", questions)
            json_write(folder / "files_index.json", {"sandbox_demo":{"name":"[SANDBOX] Đề mô phỏng 10 câu",
                       "filename":"sandbox_demo.json", "count":10, "with_answer":10, "uploaded_at":now,
                       "file_id":"sandbox_demo", "parse_method":"sandbox_seed"}})
        json_write(stage / "data/users_store.json", users)
        json_write(stage / "data/config.json", {"ai_parse_enabled":False})
        json_write(stage / "credentials.json", {"notice":"LOCAL TEST ACCOUNTS ONLY", "accounts":credentials})
        for private in (stage / ".env", stage / "credentials.json"):
            private.chmod(0o600)
        result = {"kind":"cobraq-sandbox", "schema_version":1, "created_at":now, "port":8010,
                  "source_hashes":source_hashes, "external_ai_enabled":False,
                  "notice":"Application data isolation; local mode is not an OS security boundary."}
        json_write(stage / "manifest.json", result)
        stage.rename(root)
        return result
    except BaseException:
        # Only the exact, freshly generated staging directory may be removed.
        assert stage.parent == root.parent and stage.name.startswith(root.name + ".initializing-")
        if stage.exists(): shutil.rmtree(stage)
        raise


def activate(root: Path):
    if not (root / ".env").is_file() or read_json(root / "manifest.json").get("kind") != "cobraq-sandbox":
        raise ValueError("Run setup_sandbox.bat first")
    from dotenv import dotenv_values
    os.environ.update({k:v for k,v in dotenv_values(root / ".env").items() if v is not None})
    # Derive paths again so a copied environment file remains portable, including Docker.
    os.environ.update(COBRAQ_ENV_FILE=str(root / ".env"), COBRAQ_PROFILE="sandbox",
                      COBRAQ_SANDBOX_ROOT=str(root), COBRAQ_DATA_DIR=str(root / "data"),
                      COBRAQ_RESEARCH_ROOT=str(root / "research"), COBRAQ_EXTERNAL_AI_ENABLED="false",
                      COBRAQ_VECTOR_ENABLED="false", ANTHROPIC_API_KEY="", HF_HUB_OFFLINE="1",
                      TRANSFORMERS_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", ANONYMIZED_TELEMETRY="false",
                      HF_HOME=str(root / "cache/huggingface"), TIKTOKEN_CACHE_DIR=str(root / "cache/tiktoken"),
                      COBRAQ_MODEL_DIR=str(root / "models/TinyLlama-1.1B-Chat-v1.0"),
                      COBRAQ_ADAPTER_DIR=str(root / "artifacts/adapters/history12_lora_v2_1"))


def owned_process(root: Path):
    import psutil
    path = root / "run/server.json"
    if not path.exists(): return None
    record = read_json(path)
    try:
        process = psutil.Process(record["pid"])
        if abs(process.create_time() - record["created"]) > .01: return None
        command = process.cmdline()
        if "serve" not in command or not any(Path(arg).name == "sandbox.py" for arg in command): return None
        if Path(process.cwd()).resolve() != PROJECT: return None
        return process
    except (psutil.NoSuchProcess, psutil.AccessDenied):
        return None


def serve(root: Path, port: int):
    import psutil
    if owned_process(root):
        raise ValueError("This sandbox is already running; use status or stop")
    activate(root)
    import uvicorn
    os.chdir(PROJECT)
    process = psutil.Process()
    record = root / "run/server.json"
    json_write(record, {"pid":process.pid, "created":process.create_time(), "port":port})
    print(f"CobraQ SANDBOX: http://127.0.0.1:{port}", flush=True)
    print(f"Test accounts: {root / 'credentials.json'}", flush=True)
    try:
        uvicorn.run("backend.app.main:app", host="127.0.0.1", port=port, reload=False, workers=1)
    finally:
        record.unlink(missing_ok=True)


def stop(root: Path):
    import psutil
    process = owned_process(root)
    if process:
        process.terminate()
        try: process.wait(timeout=10)
        except psutil.TimeoutExpired:
            process.kill(); process.wait(timeout=5)
    (root / "run/server.json").unlink(missing_ok=True)
    print("Sandbox stopped; data retained.")


def smoke(root: Path):
    activate(root)
    from fastapi.testclient import TestClient
    from backend.app.main import app
    from backend.app.core.config import data_path, get_settings
    from backend.app.db.user_store import user_store
    from backend.app.core.audit import audit_log
    from backend.app.services.vector_service import vector_service
    from backend.app.research.store import CorpusStore
    assert get_settings().data_dir == root / "data"
    assert CorpusStore().root == root / "research"
    assert user_store._path.is_relative_to(root) and audit_log._log_path.is_relative_to(root)
    assert not vector_service.is_vector_enabled
    checks = []
    with TestClient(app) as client:
        assert client.get('/health').json()['profile'] == 'sandbox'; checks.append("health")
        assert 'sandbox-banner' in client.get('/').text; checks.append("environment_banner")
        tokens = {}
        for account in read_json(root / "credentials.json")["accounts"]:
            response = client.post('/api/auth/login', json={"email":account['email'], "password":account['password']})
            assert response.status_code == 200, response.text
            assert response.json()['user']['role'] == account['role']
            tokens[account['role']] = {"Authorization":"Bearer " + response.json()['access_token']}
        checks.append("three_role_login")
        student = tokens['student']
        assert client.get('/api/stats', headers=student).json()['total_questions'] == 10
        quiz = client.get('/api/quiz/start?num=5&file_id=sandbox_demo', headers=student).json()
        result = client.post('/api/quiz/submit', headers=student, json={"session_id":quiz['session_id'],
            "file_id":"sandbox_demo", "answers":{str(q['id']):'A' for q in quiz['questions']}, "time_taken":10})
        assert result.json()['score'] == 5; checks.append("quiz_submit_and_history")
        assert client.get('/api/research/reviews/questions', headers=student).status_code == 403
        assert client.get('/api/research/reviews/questions', headers=tokens['teacher']).status_code == 200
        assert client.get('/api/admin/stats', headers=student).status_code == 403
        assert client.get('/api/admin/stats', headers=tokens['admin']).status_code == 200
        checks.append("role_permissions")
        assert not client.get('/api/config/ai', headers=student).json()['ai_available']
        assert client.get('/api/quiz/start', params={'file_id':'../../outside'}, headers=student).status_code == 400
        checks.append("cloud_disabled_and_path_validation")
        assert client.get('/api/research/practice', headers=student).json()['questions'] == []
        checks.append("unreviewed_research_hidden")
    report = {"status":"passed", "checks":checks, "profile":"sandbox", "data_root":str(data_path())}
    json_write(root / "logs/smoke-report.json", report)
    print(json.dumps(report, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['init','serve','stop','status','smoke'])
    parser.add_argument('--root', type=Path, default=Path(os.environ.get('COBRAQ_SANDBOX_ROOT', PROJECT / '.sandbox')))
    parser.add_argument('--port', type=int, default=8010)
    args = parser.parse_args()
    try:
        root = root_path(args.root)
        if not 1024 <= args.port <= 65535: raise ValueError('Port must be in 1024..65535')
        if args.action == 'init':
            initialize(root)
            print(f"Sandbox ready: {root}\nTest accounts: {root / 'credentials.json'}")
        elif args.action == 'serve': serve(root, args.port)
        elif args.action == 'stop': stop(root)
        elif args.action == 'smoke': smoke(root)
        else:
            process = owned_process(root)
            port = read_json(root / 'run/server.json')['port'] if process else args.port
            print(json.dumps({'initialized':(root/'manifest.json').exists(), 'running':bool(process),
                              'url':f'http://127.0.0.1:{port}', 'profile_root':str(root)}, ensure_ascii=False))
    except (ValueError, OSError, ImportError) as exc:
        parser.exit(1, f"{exc}\n")


if __name__ == '__main__': main()
