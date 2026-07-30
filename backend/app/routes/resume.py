from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.resume import Resume
from app.services.auth_service import AuthService
from app.services.resume_analyzer import ResumeAnalyzer
from app.services.resume_upload_service import ResumeUploadService, ALLOWED_TYPES, MAX_FILE_SIZE
from app.services.r2_storage import get_storage

import logging as _resume_log
_resume_logger = _resume_log.getLogger("resume.upload")


def _trigger_rec_refresh(user_id: int) -> None:
    """
    After a resume upload + analysis completes, regenerate recommendations
    so match scores immediately reflect the new resume content.
    Runs as a background task — failures are logged but never bubble up.
    """
    import time
    from app.database import SessionLocal
    from app.services.recommendation_engine import RecommendationEngine
    t0 = time.perf_counter()
    db = SessionLocal()
    try:
        result = RecommendationEngine(db).refresh_for_user(user_id)
        elapsed = round(time.perf_counter() - t0, 2)
        _resume_logger.info(
            "rec_refresh.complete user_id=%d recommendations=%d elapsed_s=%.2f",
            user_id, result.get("recommendations", 0), elapsed,
        )
    except Exception as exc:
        elapsed = round(time.perf_counter() - t0, 2)
        _resume_logger.error(
            "rec_refresh.failed user_id=%d elapsed_s=%.2f error=%s",
            user_id, elapsed, exc,
            exc_info=True,
        )
    finally:
        db.close()


router = APIRouter(prefix="/resumes", tags=["resume"])
security = HTTPBearer()


@router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_resume(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    content = file.file.read()
    size = len(content)
    file.file.seek(0)

    service = ResumeUploadService()
    try:
        service.validate_file(file, size)
    except ValueError as exc:
        status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE if size > MAX_FILE_SIZE else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

    key, url = service.upload_to_r2(file, user.id)
    file_type = ALLOWED_TYPES.get(file.content_type, "unknown")
    resume = service.create_or_replace_resume(
        db=db,
        user_id=user.id,
        file_name=file.filename or "resume",
        file_url=url,
        file_size=size,
        file_type=file_type,
    )

    background_tasks.add_task(ResumeAnalyzer.process_resume, str(resume.id), user.id)
    # Refresh recommendations once resume analysis finishes — keeps match scores current.
    # Runs as a second background task so it doesn't slow down the upload response.
    background_tasks.add_task(_trigger_rec_refresh, user.id)

    file_url = resume.file_url
    if file_url and not str(file_url).lower().startswith("http"):
        file_url = get_storage().get_public_url(file_url)

    return {
        "id": str(resume.id),
        "file_name": resume.file_name,
        "file_url": file_url,
        "file_size": resume.file_size,
        "file_type": resume.file_type,
        "uploaded_at": resume.uploaded_at,
    }


@router.get("/me")
def get_my_resume(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    file_url = resume.file_url
    if file_url and not str(file_url).lower().startswith("http"):
        file_url = get_storage().get_public_url(file_url)

    return {
        "id": str(resume.id),
        "file_name": resume.file_name,
        "file_url": file_url,
        "file_size": resume.file_size,
        "file_type": resume.file_type,
        "uploaded_at": resume.uploaded_at,
    }


@router.delete("/me")
def delete_my_resume(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    service = ResumeUploadService()
    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Resume not found")

    if resume.file_url and not str(resume.file_url).lower().startswith("http"):
        get_storage().delete(resume.file_url)

    service.delete_resume(db, user.id)
    return {"message": "Resume deleted"}


