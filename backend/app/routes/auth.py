from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.auth_service import AuthService

router = APIRouter()
security = HTTPBearer()


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
def request_reset(payload: ResetRequest, db: Session = Depends(get_db)):
    try:
        AuthService.generate_reset_token(db, payload.email)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return {"message": "Password reset token generated"}


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
