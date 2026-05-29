"""
Groups API — lớp học: GV tạo nhóm, chia sẻ mã, HS tham gia.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional

from ..core.security import get_current_user
from ..db.group_store import group_store
from ..db.group_scores import group_scores
import json, re
from pathlib import Path


def user_dir(uid):
    d = Path("D:/CobraQ/backend/data/users") / re.sub(r"[^\w]", "_", uid or "guest")
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_json(path, default):
    try:
        if Path(path).exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except:
        pass
    return default


def files_index_path(uid): return user_dir(uid) / "files_index.json"

router = APIRouter(prefix="/groups", tags=["groups"])


class CreateGroupBody(BaseModel):
    name: str


class JoinGroupBody(BaseModel):
    code: str


# ── STUDENT ──────────────────────────────────────────────────────────────────

@router.post("/join")
def join_group(
    body: JoinGroupBody,
    current_user: dict = Depends(get_current_user),
):
    """Student joins a group by code."""
    if current_user.get("role") == "admin":
        raise HTTPException(403, "Admin không cần tham gia nhóm")

    group = group_store.get_group(body.code)
    if not group:
        raise HTTPException(404, "Mã nhóm không tồn tại")

    ok = group_store.add_member(
        body.code,
        current_user["sub"],
        current_user.get("name", ""),
    )
    if not ok:
        raise HTTPException(400, "Không thể tham gia nhóm")

    return {
        "message": f"Đã tham gia nhóm '{group['name']}'",
        "group": _group_info(group),
    }


@router.get("/my")
def get_my_groups(
    current_user: dict = Depends(get_current_user),
):
    """Get all groups a student or teacher belongs to."""
    email = current_user["sub"]
    role = current_user.get("role")

    if role == "teacher":
        groups = group_store.get_teacher_groups(email)
    elif role == "student":
        groups = group_store.get_student_groups(email)
    elif role == "admin":
        groups = group_store._load()
    else:
        groups = []

    return {"groups": [_group_info(g) for g in groups]}


@router.delete("/leave/{code}")
def leave_group(
    code: str,
    current_user: dict = Depends(get_current_user),
):
    """Student leaves a group."""
    ok = group_store.remove_member(code, current_user["sub"])
    if not ok:
        raise HTTPException(404, "Không tìm thấy nhóm")
    return {"message": "Đã rời nhóm"}


# ── TEACHER ──────────────────────────────────────────────────────────────────

@router.post("/")
def create_group(
    body: CreateGroupBody,
    current_user: dict = Depends(get_current_user),
):
    """Teacher creates a new group."""
    if current_user.get("role") not in ("teacher", "admin"):
        raise HTTPException(403, "Chỉ giáo viên mới được tạo nhóm")

    if not body.name.strip():
        raise HTTPException(400, "Tên nhóm không được để trống")

    group = group_store.create_group(
        body.name.strip(),
        current_user["sub"],
        current_user.get("name", ""),
    )
    return {"message": "Đã tạo nhóm", "group": _group_info(group)}


@router.put("/{code}")
def update_group(
    code: str,
    body: CreateGroupBody,
    current_user: dict = Depends(get_current_user),
):
    """Teacher updates a group's name."""
    if current_user.get("role") not in ("teacher", "admin"):
        raise HTTPException(403, "Chỉ giáo viên mới được sửa nhóm")

    group = group_store.update_group(code, current_user["sub"], {"name": body.name.strip()})
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm hoặc không có quyền")
    return {"message": "Đã cập nhật nhóm", "group": _group_info(group)}


@router.delete("/{code}")
def delete_group(
    code: str,
    current_user: dict = Depends(get_current_user),
):
    """Teacher deletes their own group."""
    if current_user.get("role") not in ("teacher", "admin"):
        raise HTTPException(403, "Chỉ giáo viên mới được xóa nhóm")

    ok = group_store.delete_group(code, current_user["sub"])
    if not ok:
        raise HTTPException(404, "Không tìm thấy nhóm hoặc không có quyền")
    return {"message": "Đã xóa nhóm"}


@router.get("/{code}/members")
def get_members(
    code: str,
    current_user: dict = Depends(get_current_user),
):
    """Get members of a group. Teacher sees own groups, admin sees all."""
    group = group_store.get_group(code)
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm")

    email = current_user["sub"]
    role = current_user.get("role")

    if role == "admin":
        pass
    elif role == "teacher" and group["teacher_email"] != email:
        raise HTTPException(403, "Không có quyền xem nhóm này")
    elif role == "student" and not any(m["email"] == email for m in group.get("members", [])):
        raise HTTPException(403, "Bạn chưa tham gia nhóm này")

    return {"members": group.get("members", []), "count": len(group.get("members", []))}


@router.delete("/{code}/members/{student_email}")
def remove_member(
    code: str,
    student_email: str,
    current_user: dict = Depends(get_current_user),
):
    """Teacher removes a student from their group."""
    group = group_store.get_group(code)
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm")

    if current_user.get("role") not in ("teacher", "admin") or group["teacher_email"] != current_user["sub"]:
        raise HTTPException(403, "Không có quyền")

    ok = group_store.remove_member(code, student_email)
    if not ok:
        raise HTTPException(404, "Không tìm thấy thành viên")
    return {"message": f"Đã xóa {student_email} khỏi nhóm"}


# ── SCORES ──────────────────────────────────────────────────────────────────

@router.get("/{code}/files/{file_id}/scores")
def get_group_scores(
    code: str,
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Teacher views all student scores for a file in their group."""
    group = group_store.get_group(code)
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm")

    if current_user.get("role") not in ("teacher", "admin") or (
        current_user.get("role") == "teacher" and group["teacher_email"] != current_user["sub"]
    ):
        raise HTTPException(403, "Không có quyền")

    scores = group_scores.get_teacher_view(code, file_id)
    return {"scores": scores, "total": len(scores)}


@router.get("/{code}/files/{file_id}/scores/me")
def get_my_score(
    code: str,
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Student views their own score for a file."""
    score = group_scores.get_student_scores(code, file_id, current_user["sub"])
    if not score:
        return {"score": None, "message": "Chưa làm bài"}
    return {"score": score}


# ── FILE ASSIGNMENT ──────────────────────────────────────────────────────────

class AssignFileBody(BaseModel):
    file_id: str
    num_questions: int = 10
    time_limit: int = 0  # 0 = ko gioi han


@router.post("/{code}/files")
def assign_file_to_group(
    code: str,
    body: AssignFileBody,
    current_user: dict = Depends(get_current_user),
):
    """Teacher assigns one of their files as a quiz to the group."""
    group = group_store.get_group(code)
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm")

    if current_user.get("role") not in ("teacher", "admin") or group["teacher_email"] != current_user["sub"]:
        raise HTTPException(403, "Chỉ giáo viên chủ nhóm mới được thêm đề")

    index_path = files_index_path(current_user["sub"])
    index = load_json(index_path, {})
    if body.file_id not in index:
        raise HTTPException(404, "File không tồn tại trong tài khoản của bạn")

    ok = group_store.add_file(
        code, body.file_id,
        index[body.file_id].get("name", body.file_id),
        num_questions=max(1, body.num_questions),
        time_limit=max(0, body.time_limit),
    )
    if not ok:
        raise HTTPException(500, "Không thể thêm file vào nhóm")

    return {"message": "Đã gán đề thi cho nhóm", "file_id": body.file_id}


@router.delete("/{code}/files/{file_id}")
def remove_file_from_group(
    code: str,
    file_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Teacher removes a file from the group."""
    group = group_store.get_group(code)
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm")

    if current_user.get("role") not in ("teacher", "admin") or group["teacher_email"] != current_user["sub"]:
        raise HTTPException(403, "Chỉ giáo viên chủ nhóm mới được xóa đề")

    ok = group_store.remove_file(code, file_id)
    if not ok:
        raise HTTPException(500, "Không thể xóa file khỏi nhóm")

    return {"message": "Đã xóa đề khỏi nhóm"}


class UpdateFileBody(BaseModel):
    num_questions: Optional[int] = None
    time_limit: Optional[int] = None


@router.put("/{code}/files/{file_id}")
def update_group_file_settings(
    code: str,
    file_id: str,
    body: UpdateFileBody,
    current_user: dict = Depends(get_current_user),
):
    """Teacher updates num_questions / time_limit for a file in the group."""
    group = group_store.get_group(code)
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm")

    if current_user.get("role") not in ("teacher", "admin") or group["teacher_email"] != current_user["sub"]:
        raise HTTPException(403, "Chỉ giáo viên chủ nhóm mới được sửa")

    _target = next((entry for entry in group.get("files", []) if entry["file_id"] == file_id), None)
    if not _target:
        raise HTTPException(404, "File không có trong nhóm")

    if body.num_questions is not None:
        _target["num_questions"] = max(1, body.num_questions)
    if body.time_limit is not None:
        _target["time_limit"] = max(0, body.time_limit)

    groups = group_store._load()
    for g in groups:
        if g["id"] == code:
            for entry in g.get("files", []):
                if entry["file_id"] == file_id:
                    entry["num_questions"] = _target.get("num_questions", 10)
                    entry["time_limit"] = _target.get("time_limit", 0)
            group_store._save(groups)
            break

    return {"message": "Đã cập nhật cài đặt", "num_questions": _target.get("num_questions"), "time_limit": _target.get("time_limit")}


@router.get("/{code}/files")
def get_group_files(
    code: str,
    current_user: dict = Depends(get_current_user),
):
    """Get all files assigned to a group."""
    group = group_store.get_group(code)
    if not group:
        raise HTTPException(404, "Không tìm thấy nhóm")

    email = current_user["sub"]
    role = current_user.get("role")
    if role == "student" and not any(m["email"] == email for m in group.get("members", [])):
        raise HTTPException(403, "Bạn chưa tham gia nhóm này")

    files = []
    for f in group.get("files", []):
        fi = {
            "file_id": f["file_id"], "name": f["name"], "added_at": f.get("added_at", ""),
            "num_questions": f.get("num_questions", 10),
            "time_limit": f.get("time_limit", 0),
        }
        score_data = group_scores.get_student_scores(code, f["file_id"], email)
        fi["my_score"] = score_data
        files.append(fi)

    return {"files": files}


# ── HELPER ───────────────────────────────────────────────────────────────────

def _group_info(g: dict) -> dict:
    return {
        "id": g["id"],
        "code": g["code"],
        "name": g["name"],
        "teacher_email": g["teacher_email"],
        "teacher_name": g["teacher_name"],
        "member_count": len(g.get("members", [])),
        "file_count": len(g.get("files", [])),
        "files": g.get("files", []),
        "created_at": g.get("created_at", ""),
    }
