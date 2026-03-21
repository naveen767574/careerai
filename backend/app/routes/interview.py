from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.interview_answer import InterviewAnswer
from app.models.interview_session import InterviewSession
from app.schemas.interview import (
    AnswerFeedback,
    HistoryResponse,
    QuestionOut,
    ReportOut,
    StartInterviewRequest,
    StartInterviewResponse,
    SubmitAnswerRequest,
)
from app.services.auth_service import AuthService
from app.services.interview_service import InterviewService
from app.services.feedback_reporter import FeedbackReporter


router = APIRouter(prefix="/interview", tags=["interview"])
security = HTTPBearer()


def get_current_user(db: Session, credentials: HTTPAuthorizationCredentials):
    try:
        return AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc


@router.post("/start", response_model=StartInterviewResponse, status_code=status.HTTP_201_CREATED)
async def start_interview(
    payload: StartInterviewRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    result = InterviewService(db).start_session(user.id, payload.internship_id)
    return {
        "session_id": result["session_id"],
        "internship": result["internship"],
        "first_question": QuestionOut.model_validate(result["first_question"]),
        "total_questions": result["total_questions"],
    }


@router.get("/session/{session_id}")
async def get_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    service = InterviewService(db)
    questions = service.get_questions(session_id, user.id)

    answers_submitted = (
        db.query(InterviewAnswer)
        .filter(InterviewAnswer.session_id == session_id, InterviewAnswer.user_id == user.id)
        .count()
    )
    session = db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
    if not session or session.user_id != user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    return {
        "session": {
            "session_id": session.session_id,
            "internship_id": session.internship_id,
            "status": session.status,
            "overall_score": session.overall_score,
            "readiness_level": session.readiness_level,
            "created_at": session.created_at,
            "completed_at": session.completed_at,
        },
        "questions": [QuestionOut.model_validate(q) for q in questions],
        "answers_submitted": answers_submitted,
    }


@router.post("/answer", response_model=AnswerFeedback)
async def submit_answer(
    payload: SubmitAnswerRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    if not payload.answer_text or not payload.answer_text.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer text cannot be empty")
    if len(payload.answer_text) > 2000:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Answer too long (max 2000 characters)")

    user = get_current_user(db, credentials)
    result = InterviewService(db).submit_answer(
        payload.session_id,
        user.id,
        payload.question_id,
        payload.answer_text,
    )

    return {
        **result,
        "next_question": QuestionOut.model_validate(result["next_question"]) if result.get("next_question") else None,
    }


@router.post("/complete", response_model=ReportOut)
async def complete_session(
    payload: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    session_id = payload.get("session_id") if isinstance(payload, dict) else None
    if not session_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="session_id is required")
    user = get_current_user(db, credentials)
    report_data = InterviewService(db).complete_session(session_id, user.id)
    return {
        "session_id": report_data["session_id"],
        "internship_id": report_data["internship_id"],
        "overall_score": report_data["overall_score"],
        "technical_score": report_data["technical_score"],
        "behavioral_score": report_data["behavioral_score"],
        "readiness_level": report_data["readiness_level"],
        "readiness_message": report_data["readiness_message"],
        "top_strengths": report_data["top_strengths"],
        "top_improvements": report_data["top_improvements"],
        "recommended_resources": report_data["recommended_resources"],
        "created_at": report_data["created_at"],
    }


@router.get("/report/{session_id}", response_model=ReportOut)
async def get_report(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    report = InterviewService(db).get_report(session_id, user.id)
    readiness_message = FeedbackReporter()._get_readiness_message(report.readiness_level)
    return {
        "session_id": report.session_id,
        "internship_id": report.internship_id,
        "overall_score": report.overall_score,
        "technical_score": report.technical_score,
        "behavioral_score": report.behavioral_score,
        "readiness_level": report.readiness_level,
        "readiness_message": readiness_message,
        "top_strengths": report.top_strengths or [],
        "top_improvements": report.top_improvements or [],
        "recommended_resources": report.recommended_resources or [],
        "created_at": report.created_at,
    }


@router.get("/history", response_model=HistoryResponse)
async def history(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    sessions = InterviewService(db).get_history(user.id)
    return {"sessions": sessions, "total": len(sessions)}


@router.post("/retry/{session_id}", response_model=StartInterviewResponse, status_code=status.HTTP_201_CREATED)
async def retry_session(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    result = InterviewService(db).retry_session(session_id, user.id)
    return {
        "session_id": result["session_id"],
        "internship": result["internship"],
        "first_question": QuestionOut.model_validate(result["first_question"]),
        "total_questions": result["total_questions"],
    }


@router.get("/questions/{session_id}")
async def list_questions(
    session_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    user = get_current_user(db, credentials)
    questions = InterviewService(db).get_questions(session_id, user.id)
    return {
        "questions": [QuestionOut.model_validate(q) for q in questions],
        "session_id": session_id,
    }



