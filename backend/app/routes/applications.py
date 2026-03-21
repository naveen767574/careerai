from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload
from app.database import get_db
from app.utils.dependencies import get_current_user
from app.models.application import Application
from app.models.internship import Internship
from app.schemas.application import (
    ApplicationCreate, ApplicationUpdate, ApplicationOut, ApplicationListResponse
)

router = APIRouter(prefix="/applications", tags=["applications"])

VALID_STATUSES = ["saved", "applied", "interview", "offer", "rejected", "withdrawn"]


@router.post("", status_code=201, response_model=ApplicationOut)
def create_application(
    body: ApplicationCreate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    internship = db.query(Internship).filter(Internship.id == body.internship_id).first()
    if not internship:
        raise HTTPException(status_code=404, detail="Internship not found")
    existing = db.query(Application).filter(
        Application.user_id == current_user.id,
        Application.internship_id == body.internship_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="Already tracking this internship")
    app = Application(
        user_id=current_user.id,
        internship_id=body.internship_id,
        status=body.status,
        notes=body.notes
    )
    db.add(app)
    db.commit()
    db.refresh(app)
    return db.query(Application).options(
        joinedload(Application.internship)
    ).filter(Application.id == app.id).first()


@router.get("", response_model=ApplicationListResponse)
def list_applications(
    status: str = None,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    query = db.query(Application).options(
        joinedload(Application.internship)
    ).filter(Application.user_id == current_user.id)
    if status:
        query = query.filter(Application.status == status)
    apps = query.order_by(Application.updated_at.desc()).all()
    return {"applications": apps, "total": len(apps)}


@router.get("/{app_id}", response_model=ApplicationOut)
def get_application(
    app_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    app = db.query(Application).options(
        joinedload(Application.internship)
    ).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not yours")
    return app


@router.patch("/{app_id}", response_model=ApplicationOut)
def update_application(
    app_id: int,
    body: ApplicationUpdate,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not yours")
    if body.status and body.status not in VALID_STATUSES:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {VALID_STATUSES}")
    if body.status:
        app.status = body.status
    if body.notes is not None:
        app.notes = body.notes
    if body.applied_at is not None:
        app.applied_at = body.applied_at
    db.commit()
    db.refresh(app)
    return db.query(Application).options(
        joinedload(Application.internship)
    ).filter(Application.id == app.id).first()


@router.delete("/{app_id}")
def delete_application(
    app_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    app = db.query(Application).filter(Application.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found")
    if app.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not yours")
    db.delete(app)
    db.commit()
    return {"message": "Application deleted"}
