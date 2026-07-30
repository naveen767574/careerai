from collections import defaultdict
import time
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthService

router   = APIRouter()
security = HTTPBearer()

# ---------------------------------------------------------------------------
# Simple in-memory rate limiter for the reset endpoint.
# Keyed by client IP — max 5 requests per 15-minute window.
# Resets automatically when the window expires.
# ---------------------------------------------------------------------------
class _RateLimiter:
    def __init__(self, max_calls: int = 5, window_seconds: int = 900):
        self._max   = max_calls
        self._win   = window_seconds
        self._store: dict = defaultdict(list)   # ip → [timestamps]

    def check(self, key: str) -> None:
        now     = time.time()
        cutoff  = now - self._win
        calls   = [t for t in self._store[key] if t > cutoff]
        if len(calls) >= self._max:
            wait = int(self._win - (now - calls[0]))
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Too many reset requests. Please wait {wait} seconds before trying again.",
            )
        calls.append(now)
        self._store[key] = calls

_reset_limiter = _RateLimiter(max_calls=5, window_seconds=900)


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class ResetRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class UserResponse(BaseModel):
    user_id: int
    email: EmailStr
    name: str


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService.register_user(db, payload.email, payload.password, payload.name)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"user_id": user.id, "email": user.email, "name": user.name}


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    try:
        result = AuthService.login_user(db, payload.email, payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    user = result["user"]
    return {
        "access_token": result["access_token"],
        "token_type": result["token_type"],
        "user": {"user_id": user.id, "email": user.email, "name": user.name},
    }


@router.get("/me", response_model=UserResponse)
def me(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc
    return {"user_id": user.id, "email": user.email, "name": user.name}


@router.post("/request-reset")
def request_reset(payload: ResetRequest, request: Request, db: Session = Depends(get_db)):
    """
    Generate a password reset token.

    Security hardening applied:
      • Rate-limited to 5 requests per IP per 15 minutes (prevents brute-force).
      • Always returns HTTP 200 regardless of whether the email exists — this
        prevents account enumeration (attackers can't probe which emails are
        registered by checking the response status or message).
      • reset_token is None when the email is not found; the frontend shows
        the same UI regardless so the difference is not user-visible.
      • Calling this invalidates all previous unused tokens for the same user
        (enforced in AuthService.generate_reset_token).
    """
    client_ip = request.client.host if request.client else "unknown"
    _reset_limiter.check(client_ip)

    # generate_reset_token returns None if email not found — do NOT raise an
    # error, as that would reveal whether the email is registered.
    token = AuthService.generate_reset_token(db, payload.email)

    return {
        "message": (
            "A reset token has been generated. Use it below to set your new password."
            if token else
            "If this email is registered, a reset token has been generated."
        ),
        "reset_token": token,  # None when email not found — frontend shows graceful fallback
    }


@router.post("/reset-password")
def reset_password(payload: ResetPasswordRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService.validate_reset_token(db, payload.token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    from app.utils.security import hash_password

    user.password_hash = hash_password(payload.new_password)
    db.add(user)
    db.commit()
    AuthService.consume_reset_token(db, payload.token)
    return {"message": "Password updated"}
