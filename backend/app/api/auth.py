from fastapi import APIRouter, HTTPException, Header, status, Depends
from pydantic import BaseModel, EmailStr
from typing import Optional

from ..core.security import (
    hash_password, verify_password, create_access_token, get_current_user_optional, Role
)
from ..core.audit import audit_log, EventType
from ..db.user_store import user_store

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterBody(BaseModel):
    email: EmailStr
    name: str
    password: str
    role: str = "student"


class LoginBody(BaseModel):
    email: str
    password: str


@router.post("/register")
def register(body: RegisterBody, x_user_id: str = Header(default="")):
    if len(body.password) < 6:
        raise HTTPException(400, "Mật khẩu phải ít nhất 6 ký tự")
    if user_store.user_exists(body.email):
        raise HTTPException(400, "Email đã được đăng ký")

    role = body.role if body.role == "student" else "student"

    pw_hash = hash_password(body.password)
    user = user_store.create_user(body.email, body.name, pw_hash, role)

    audit_log.log(
        EventType.AUTH_REGISTER,
        user_id=body.email,
        role=role,
    )

    token = create_access_token({
        "sub": body.email,
        "name": body.name,
        "role": role,
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user["email"], "name": user["name"], "role": user["role"]},
    }


@router.post("/login")
def login(body: LoginBody, x_user_id: str = Header(default="")):
    user = user_store.get_user(body.email)
    if not user or not verify_password(body.password, user["password_hash"]):
        audit_log.log(
            EventType.AUTH_FAILED,
            user_id=body.email,
            details={"reason": "invalid_credentials"},
        )
        raise HTTPException(401, "Email hoặc mật khẩu không đúng")

    audit_log.log(
        EventType.AUTH_LOGIN,
        user_id=user["email"],
        role=user["role"],
    )

    token = create_access_token({
        "sub": user["email"],
        "name": user["name"],
        "role": user["role"],
    })

    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {"email": user["email"], "name": user["name"], "role": user["role"]},
    }


@router.get("/me")
def get_me(current_user: Optional[dict] = Depends(get_current_user_optional)):
    if not current_user:
        return {"email": "guest", "name": "Khách", "role": "guest"}
    return {
        "email": current_user.get("sub"),
        "name": current_user.get("name"),
        "role": current_user.get("role", "student"),
    }


@router.post("/logout")
def logout(current_user: Optional[dict] = Depends(get_current_user_optional)):
    if current_user:
        audit_log.log(
            EventType.AUTH_LOGOUT,
            user_id=current_user.get("sub", "unknown"),
            role=current_user.get("role", "guest"),
        )
    return {"message": "Đã đăng xuất"}
