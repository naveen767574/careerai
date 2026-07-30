from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db, SessionLocal
from app.models.agent_run import AgentRun
from app.models.agent_state import AgentState
from app.models.resume import Resume
from app.orchestrator.runner import OrchestratorRunner
from app.schemas.agent import AgentRunOut, AgentStatusResponse, AgentTriggerRequest, AgentTriggerResponse
from app.services.auth_service import AuthService

router = APIRouter(prefix="/agent", tags=["agent"])
security = HTTPBearer()


def _run_orchestrator(user_id: int, trigger: str) -> None:
    db = SessionLocal()
    try:
        OrchestratorRunner(db).run(user_id, trigger)
    finally:
        db.close()


@router.post("/trigger", response_model=AgentTriggerResponse)
async def trigger_agent(
    payload: AgentTriggerRequest,
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    resume = db.query(Resume).filter(Resume.user_id == user.id).first()
    if not resume:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No resume found")

    background_tasks.add_task(_run_orchestrator, user.id, payload.trigger)
    return {
        "message": "Orchestrator triggered successfully",
        "trigger": payload.trigger,
        "completed_agents": [],
    }


@router.get("/status", response_model=AgentStatusResponse)
async def agent_status(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    state = db.query(AgentState).filter(AgentState.user_id == user.id).first()
    completed_agents = []
    current_keys = []
    last_run_at = None
    if state and state.state_json:
        completed_agents = state.state_json.get("completed_agents", [])
        current_keys = list(state.state_json.keys())
        last_run_at = state.last_run_at

    runs = (
        db.query(AgentRun)
        .filter(AgentRun.user_id == user.id)
        .order_by(AgentRun.started_at.desc())
        .limit(5)
        .all()
    )

    return {
        "last_run_at": last_run_at,
        "completed_agents": completed_agents,
        "current_state_keys": current_keys,
        "recent_runs": runs,
    }


@router.get("/runs")
async def list_runs(
    limit: int = Query(20, ge=1, le=50),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    runs = (
        db.query(AgentRun)
        .filter(AgentRun.user_id == user.id)
        .order_by(AgentRun.started_at.desc())
        .limit(limit)
        .all()
    )

    return {"runs": runs, "total": len(runs)}


@router.get("/runs/{run_id}")
async def get_run(
    run_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    try:
        user = AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    run = db.query(AgentRun).filter(AgentRun.id == run_id, AgentRun.user_id == user.id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    return {
        "id": run.id,
        "agent_name": run.agent_name,
        "trigger": run.trigger,
        "status": run.status,
        "error_message": run.error_message,
        "input_json": run.input_json,
        "output_json": run.output_json,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
    }


# ---------------------------------------------------------------------------
# POST /api/scraper/run   — manual scraper trigger
# Fires both scraper phases (scrape + embed) in a background thread.
# Returns immediately; poll /api/agent/status or check logs for progress.
# ---------------------------------------------------------------------------

import logging as _sc_logger
_scraper_log = _sc_logger.getLogger("scraper.manual_trigger")


def _run_scraper_pipeline() -> None:
    """
    Manual scraper trigger — delegates to scraper_scheduler.run_pipeline_once()
    so the shared concurrency lock is respected: if the scheduler is already
    running, this call logs a warning and returns without double-running.
    """
    from app.services.scraper_scheduler import run_pipeline_once
    acquired = run_pipeline_once(reason="manual_trigger")
    if not acquired:
        _scraper_log.warning("manual_scraper.skipped — scraper lock busy")


@router.post("/scraper/run")
async def run_scraper_now(
    background_tasks: BackgroundTasks,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db),
):
    """
    Manually trigger the scraper + embedding pipeline.
    Runs in background — returns immediately.
    If the scheduler is already running the lock prevents a double-run.
    """
    try:
        AuthService.verify_token(db, credentials.credentials)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(exc)) from exc

    background_tasks.add_task(_run_scraper_pipeline)
    _scraper_log.info("manual_scraper.triggered")
    return {"message": "Scraper pipeline started in background. Check server logs for progress."}
