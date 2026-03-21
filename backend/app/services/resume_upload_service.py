from typing import Tuple
import uuid

from fastapi import UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.resume import Resume
from app.services.r2_storage import get_storage

ALLOWED_TYPES = {
    "application/pdf": "pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
}
MAX_FILE_SIZE = 5 * 1024 * 1024


class ResumeUploadService:
    def __init__(self) -> None:
        self.storage = get_storage()

    def validate_file(self, file: UploadFile, size: int) -> None:
        if file.content_type not in ALLOWED_TYPES:
            raise ValueError("Invalid file type")
        if size > MAX_FILE_SIZE:
            raise ValueError("File too large")

    def upload_to_r2(self, file: UploadFile, user_id: int) -> Tuple[str, str]:
        key = f"{user_id}/{uuid.uuid4()}_{file.filename or 'resume'}"
        file_url = self.storage.upload(key, file.file, file.content_type or "application/octet-stream")
        return key, file_url

    def create_or_replace_resume(
        self,
        db: Session,
        user_id: int,
        file_name: str,
        file_url: str,
        file_size: int,
        file_type: str,
    ) -> Resume:
        existing = db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()
        if existing:
            existing.file_name = file_name
            existing.file_url = file_url
            existing.file_size = file_size
            existing.file_type = file_type
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return existing
        resume = Resume(
            user_id=user_id,
            file_name=file_name,
            file_url=file_url,
            file_size=file_size,
            file_type=file_type,
        )
        db.add(resume)
        db.commit()
        db.refresh(resume)
        return resume

    def delete_resume(self, db: Session, user_id: int) -> None:
        existing = db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()
        if not existing:
            return
        db.delete(existing)
        db.commit()
