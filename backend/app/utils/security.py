from datetime import datetime, timedelta, timezone
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password, rounds=settings.BCRYPT_ROUNDS)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def create_access_token(subject: str, expires_hours: int | None = None) -> str:
    expire_hours = expires_hours if expires_hours is not None else settings.JWT_EXPIRATION_HOURS
    expire = datetime.now(timezone.utc) + timedelta(hours=expire_hours)
    payload = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_reset_token(subject: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(hours=settings.RESET_TOKEN_EXPIRE_HOURS)
    payload = {"sub": subject, "exp": expire, "type": "reset"}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError:
        return None


def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def token_subject(token: str) -> str:
    payload = decode_token(token)
    subject = payload.get("sub")
    if not subject:
        raise JWTError("Missing subject")
    return str(subject)
