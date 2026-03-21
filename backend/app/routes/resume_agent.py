import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.builder_session import BuilderSession
from app.models.resume_version import ResumeVersion
from app.services.auth_service import AuthService
from app.services.builder_service import ResumeBuilderService
from app.services.export_service import ExportService
from app.services.template_engine import TemplateEngine
from app.services.resume_optimizer import ResumeOptimizer
from app.schemas.builder import (
    AnswerRequest,
    ATSScoreOut,
    BuilderStepResponse,
    FinalizeResponse,
    ResumeVersionOut,
    StartSessionResponse,
)


router = APIRouter(prefix="/resume-agent", tags=["resume-agent"])
security = HTTPBearer()


def get_current_user(db: Session, credentials: HTTPAuthorizationCredentials):
    try:
        return AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/start-session", response_model=StartSessionResponse, status_code=status.HTTP_201_CREATED)
async def start_session(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    return ResumeBuilderService(db).start_session(user.id)


@router.post("/answer", response_model=BuilderStepResponse)
async def answer(
    payload: AnswerRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be empty")
    user = get_current_user(db, credentials)
    return ResumeBuilderService(db).process_answer(payload.session_id, user.id, payload.message)


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    session = ResumeBuilderService(db).get_session(session_id, user.id)
    return {
        "session_id": session.session_id,
        "current_step": session.current_step,
        "resume_data": session.resume_data,
        "selected_template": session.selected_template,
        "status": session.status,
        "created_at": session.created_at,
        "updated_at": session.updated_at,
    }


@router.get("/templates")
async def list_templates(
    session_id: str | None = Query(default=None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    engine = TemplateEngine()
    if session_id:
        session = ResumeBuilderService(db).get_session(session_id, user.id)
        templates = engine.recommend(session.resume_data)
    else:
        templates = engine.get_all_templates()
    return {"templates": templates}


@router.get("/preview/{session_id}")
async def preview_resume(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    session = ResumeBuilderService(db).get_session(session_id, user.id)
    template_name = session.selected_template or "minimal_ats"
    html = TemplateEngine().render(template_name, session.resume_data)
    return Response(content=html, media_type="text/html")


@router.post("/optimize")
async def optimize_bullets(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required")
    user = get_current_user(db, credentials)
    session = ResumeBuilderService(db).get_session(session_id, user.id)
    return ResumeOptimizer(db).optimize_all_bullets(session)


@router.get("/ats-score/{session_id}", response_model=ATSScoreOut)
async def ats_score(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    session = ResumeBuilderService(db).get_session(session_id, user.id)
    return ResumeOptimizer().calculate_ats_score(session.resume_data)


@router.post("/finalize", response_model=FinalizeResponse)
async def finalize_resume(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required")
    user = get_current_user(db, credentials)
    return ResumeBuilderService(db).finalize(session_id, user.id)


@router.post("/export-pdf")
async def export_pdf(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required")
    user = get_current_user(db, credentials)
    session = ResumeBuilderService(db).get_session(session_id, user.id)
    pdf_bytes = ExportService(db).export_pdf_for_session(session)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=resume.pdf"},
    )


@router.post("/export-docx")
async def export_docx(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required")
    user = get_current_user(db, credentials)
    session = ResumeBuilderService(db).get_session(session_id, user.id)
    docx_bytes = ExportService(db).export_docx_for_session(session)
    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Content-Disposition": "attachment; filename=resume.docx"},
    )


@router.get("/versions")
async def list_versions(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    versions = (
        db.query(ResumeVersion)
        .filter(ResumeVersion.user_id == user.id)
        .order_by(ResumeVersion.version_number.desc())
        .all()
    )
    return {
        "versions": [ResumeVersionOut.model_validate(v) for v in versions],
        "total": len(versions),
    }


@router.get("/versions/{version_id}")
async def get_version(
    version_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    version = db.query(ResumeVersion).filter(ResumeVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    if version.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your resume version")
    return {
        **ResumeVersionOut.model_validate(version).model_dump(),
        "resume_data": version.resume_data,
    }


@router.post("/versions/{version_id}/restore", response_model=StartSessionResponse)
async def restore_version(
    version_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    version = db.query(ResumeVersion).filter(ResumeVersion.id == version_id).first()
    if not version:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Version not found")
    if version.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your resume version")

    session = BuilderSession(
        session_id=str(uuid.uuid4()),
        user_id=user.id,
        current_step=12,
        resume_data=version.resume_data,
        selected_template=version.template_name,
        status="in_progress",
    )
    db.add(session)
    db.commit()

    return {
        "session_id": session.session_id,
        "step": 12,
        "question": "Your resume is ready for preview! You can say: 'export pdf', 'export docx', 'improve bullets', 'check ats score', or 'finalize'.",
    }

