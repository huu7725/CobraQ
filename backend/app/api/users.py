"""
User management endpoints — admin only.
List users, update role, delete user.
"""

from fastapi import APIRouter, HTTPException, Header, Depends
from pydantic import BaseModel
from typing import Optional

from ..core.security import get_current_user, Role
from ..core.audit import audit_log, EventType
from ..db.user_store import user_store

router = APIRouter(prefix="/users", tags=["users"])


def _check_admin(current_user: dict):
    if current_user.get("role") != Role.ADMIN.value:
        raise HTTPException(403, "Chỉ quản trị viên mới có quyền truy cập")


class UpdateRoleBody(BaseModel):
    role: str


@router.get("/")
def list_users(
    current_user: dict = Depends(get_current_user),
):
    """List all users — admin only."""
    _check_admin(current_user)

    all_users = user_store.get_all_users()
    return {
        "users": [
            {
                "email": u["email"],
                "name": u["name"],
                "role": u["role"],
                "created_at": u.get("created_at", ""),
            }
            for u in all_users
        ],
        "total": len(all_users),
    }


@router.put("/{email}/role")
def update_user_role(
    email: str,
    body: UpdateRoleBody,
    current_user: dict = Depends(get_current_user),
):
    """Update a user's role — admin only."""
    _check_admin(current_user)

    if body.role not in [r.value for r in Role]:
        raise HTTPException(400, f"Role không hợp lệ. Chọn: {[r.value for r in Role]}")

    # Prevent admin from demoting themselves
    if current_user.get("sub") == email and body.role != Role.ADMIN.value:
        raise HTTPException(400, "Không thể tự thay đổi quyền của mình")

    updated = user_store.update_user(email, {"role": body.role})
    if not updated:
        raise HTTPException(404, "Không tìm thấy người dùng")

    audit_log.log(
        EventType.CONFIG_UPDATE,
        user_id=current_user.get("sub"),
        role=current_user.get("role"),
        resource=f"user:{email}",
        details={"action": "role_update", "new_role": body.role},
    )

    return {"message": f"Đã cập nhật vai trò thành {body.role}", "user": updated}


@router.delete("/{email}")
def delete_user(
    email: str,
    current_user: dict = Depends(get_current_user),
):
    """Delete a user — admin only."""
    _check_admin(current_user)

    if current_user.get("sub") == email:
        raise HTTPException(400, "Không thể tự xóa tài khoản của mình")

    user = user_store.get_user(email)
    if not user:
        raise HTTPException(404, "Không tìm thấy người dùng")

    user_store.delete_user(email)

    audit_log.log(
        EventType.CONFIG_UPDATE,
        user_id=current_user.get("sub"),
        role=current_user.get("role"),
        resource=f"user:{email}",
        details={"action": "delete_user", "deleted_role": user.get("role")},
    )

    return {"message": f"Đã xóa người dùng {email}"}


@router.put("/{email}")
def update_user_info(
    email: str,
    body: dict,
    current_user: dict = Depends(get_current_user),
):
    """Update user name — user themselves or admin."""
    if current_user.get("sub") != email and current_user.get("role") != Role.ADMIN.value:
        raise HTTPException(403, "Không có quyền")

    allowed = {k: v for k, v in body.items() if k in ("name",)}
    if not allowed:
        raise HTTPException(400, "Chỉ được cập nhật: name")

    updated = user_store.update_user(email, allowed)
    if not updated:
        raise HTTPException(404, "Không tìm thấy người dùng")

    return {"message": "Đã cập nhật", "user": updated}
