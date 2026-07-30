from datetime import datetime, timezone
from sqlalchemy import select, text
from sqlalchemy.orm import Session
from jose import JWTError

from app.models.user import User
from app.models.password_reset_token import PasswordResetToken
from app.utils.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_reset_token,
    decode_access_token,
    decode_token,
)


class AuthService:
    @staticmethod
    def register_user(db: Session, email: str, password: str, name: str) -> User:
        existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if existing:
            raise ValueError("Email already registered")
        user = User(email=email, name=name, password_hash=hash_password(password))
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def login_user(db: Session, email: str, password: str) -> dict:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Invalid credentials")
        token = create_access_token(str(user.id))
        return {"access_token": token, "token_type": "bearer", "user": user}

    @staticmethod
    def verify_token(db: Session, token: str) -> User:
        payload = decode_access_token(token)
        if payload is None:
            raise ValueError("Invalid token")
        if payload.get("type") != "access":
            raise ValueError("Invalid token")
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Invalid token")
        user = db.get(User, int(user_id))
        if not user:
            raise ValueError("User not found")
        return user

    @staticmethod
    def generate_reset_token(db: Session, email: str) -> str | None:
        """
        Generate a password reset token.

        Returns the token string if the email is registered, None otherwise.
        Callers must NOT expose whether None was returned — always respond with
        HTTP 200 to prevent email enumeration attacks.

        Security measures applied here:
          1. Invalidates ALL previous unused tokens for this user before issuing
             a new one, so only one valid token ever exists at a time.
          2. Also purges expired tokens for this user to keep the table clean.
        """
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if not user:
            return None   # caller returns 200 regardless — prevents enumeration

        # ── Invalidate every existing unused token for this user ──────────────
        # Without this, N reset requests produce N simultaneously valid tokens,
        # any one of which can be used to hijack the account.
        db.execute(
            text(
                "DELETE FROM password_reset_tokens "
                "WHERE user_id = :uid AND used = false"
            ),
            {"uid": user.id},
        )

        # ── Also purge expired (but still unused) tokens ──────────────────────
        # Belt-and-suspenders cleanup; the DELETE above already covers these,
        # but this keeps the table lean even across users over time.
        db.execute(
            text(
                "DELETE FROM password_reset_tokens "
                "WHERE user_id = :uid AND expires_at < NOW()"
            ),
            {"uid": user.id},
        )

        token = create_reset_token(str(user.id))
        expires_at = datetime.fromtimestamp(decode_token(token)["exp"], tz=timezone.utc)
        reset = PasswordResetToken(user_id=user.id, token=token, expires_at=expires_at)
        db.add(reset)
        db.commit()
        return token

    @staticmethod
    def validate_reset_token(db: Session, token: str) -> User:
        try:
            payload = decode_token(token)
        except JWTError as exc:
            raise ValueError("Invalid token") from exc
        if payload.get("type") != "reset":
            raise ValueError("Invalid token")
        record = db.execute(select(PasswordResetToken).where(PasswordResetToken.token == token)).scalar_one_or_none()
        if not record or record.used:
            raise ValueError("Invalid token")
        if record.expires_at < datetime.now(timezone.utc):
            raise ValueError("Token expired")
        user = db.get(User, record.user_id)
        if not user:
            raise ValueError("User not found")
        return user

    @staticmethod
    def consume_reset_token(db: Session, token: str) -> None:
        record = db.execute(select(PasswordResetToken).where(PasswordResetToken.token == token)).scalar_one_or_none()
        if record:
            record.used = True
            db.add(record)
            db.commit()
