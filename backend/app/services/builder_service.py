import threading
import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.builder_session import BuilderSession
from app.models.resume_analysis import ResumeAnalysis
from app.models.resume_version import ResumeVersion
from app.services.notification_service import create_notification
from app.services.resume_analyzer import ResumeAnalyzer
from app.services.resume_optimizer import ResumeOptimizer
from app.services.export_service import ExportService
from app.orchestrator.runner import OrchestratorRunner


STEPS = {
    1: {"fields": ["name", "email", "phone"], "question": "Let's build your resume! What's your full name, email, and phone number?"},
    2: {"fields": ["linkedin", "portfolio"], "question": "Great! What's your LinkedIn URL? (Add your portfolio link too if you have one, or just skip.)"},
    3: {"fields": ["career_interests"], "question": "What roles or job titles are you targeting? (e.g. Backend Developer, Data Analyst)"},
    4: {"fields": ["skills"], "question": "List your technical skills, comma separated. (e.g. Python, React, PostgreSQL, Docker)"},
    5: {"fields": ["education"], "question": "Tell me about your education - degree, institution, year, GPA (optional)."},
    6: {"fields": ["experience"], "question": "Add your work or internship experience. Include role, company, dates, and key responsibilities. Type 'skip' if none."},
    7: {"fields": ["projects"], "question": "Describe a project you're proud of - name, what it does, tech used, and your role. Type 'skip' if none."},
    8: {"fields": ["certifications"], "question": "Any certifications? (e.g. AWS Certified, Google Analytics). Type 'skip' if none."},
    9: {"fields": ["achievements"], "question": "Any awards, publications, or competitions worth mentioning? Type 'skip' if none."},
    10: {"fields": [], "question": "Here's a summary of everything you've shared. Does it look right? Type 'confirm' to continue, or tell me what to change."},
    11: {"fields": ["selected_template"], "question": "Choose a template:\n1. Minimal ATS\n2. Developer Modern\n3. Corporate Classic\n4. Student Simple\n5. Technical Professional\nWhich number?"},
    12: {"fields": [], "question": "Your resume is ready for preview! You can say: 'export pdf', 'export docx', 'improve bullets', 'check ats score', or 'finalize'."},
}

TEMPLATE_MAP = {
    "1": "minimal_ats",
    "2": "developer_modern",
    "3": "corporate_classic",
    "4": "student_simple",
    "5": "technical_professional",
}


class ResumeBuilderService:
    def __init__(self, db: Session):
        self.db = db

    def start_session(self, user_id: int) -> dict:
        session = BuilderSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            current_step=1,
            resume_data={},
            status="in_progress",
        )
        self.db.add(session)
        self.db.commit()
        return {
            "session_id": session.session_id,
            "step": 1,
            "question": STEPS[1]["question"],
        }

    def process_answer(self, session_id: str, user_id: int, message: str) -> dict:
        session = self.get_session(session_id, user_id)
        if session.status == "completed":
            session.status = "in_progress"
            self.db.add(session)
            self.db.commit()

        step = session.current_step
        message_clean = message.strip()

        if step in range(1, 10):
            parsed = self._parse_step_data(step, message_clean)
            session.resume_data = {**(session.resume_data or {}), **parsed}
            session.current_step = min(step + 1, 12)
            self.db.add(session)
            self.db.commit()
            return self._build_step_response(session)

        if step == 10:
            if message_clean.lower() == "confirm":
                session.current_step = 11
            else:
                notes = session.resume_data.get("edit_notes", [])
                notes.append(message_clean)
                session.resume_data["edit_notes"] = notes
            self.db.add(session)
            self.db.commit()
            return self._build_step_response(session, custom_question="Edit noted. Type 'confirm' to continue or add more changes.")

        if step == 11:
            choice = self._extract_template_choice(message_clean)
            if not choice:
                return self._build_step_response(session, custom_question=STEPS[11]["question"])
            session.selected_template = TEMPLATE_MAP[choice]
            session.current_step = 12
            self.db.add(session)
            self.db.commit()
            return self._build_step_response(session)

        if step == 12:
            lower = message_clean.lower()
            if "export pdf" in lower:
                ExportService(self.db).export_pdf_for_session(session)
                return self._build_step_response(session, custom_question="PDF generated. You can also use the export endpoint to download it.")
            if "export docx" in lower:
                ExportService(self.db).export_docx_for_session(session)
                return self._build_step_response(session, custom_question="DOCX generated. You can also use the export endpoint to download it.")
            if "improve" in lower:
                result = ResumeOptimizer(self.db).optimize_all_bullets(session)
                return self._build_step_response(session, extra_summary=result)
            if "ats" in lower:
                score = ResumeOptimizer(self.db).calculate_ats_score(session.resume_data)
                return self._build_step_response(session, extra_summary={"ats_score": score})
            if "finalize" in lower:
                result = self.finalize(session_id, user_id)
                return self._build_step_response(session, extra_summary=result)

            return self._build_step_response(session)

        return self._build_step_response(session)

    def get_session(self, session_id: str, user_id: int) -> BuilderSession:
        session = (
            self.db.query(BuilderSession)
            .filter(BuilderSession.session_id == session_id)
            .first()
        )
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")
        return session

    def finalize(self, session_id: str, user_id: int) -> dict:
        session = self.get_session(session_id, user_id)
        ats = ResumeOptimizer(self.db).calculate_ats_score(session.resume_data)
        ats_score = int(ats.get("total_score", 0))

        max_version = (
            self.db.query(func.max(ResumeVersion.version_number))
            .filter(ResumeVersion.user_id == user_id)
            .scalar()
        )
        version_number = (max_version or 0) + 1

        version = ResumeVersion(
            user_id=user_id,
            version_number=version_number,
            resume_data=session.resume_data,
            template_name=session.selected_template,
            ats_score=ats_score,
            source="builder",
        )
        self.db.add(version)
        session.status = "completed"
        session.current_step = 12
        self.db.add(session)
        self.db.commit()

        threading.Thread(
            target=self._post_build_pipeline,
            args=(user_id, session.resume_data),
            daemon=True,
        ).start()

        return {
            "message": "Resume finalized",
            "version_number": version_number,
            "ats_score": ats_score,
        }

    def _parse_step_data(self, step: int, message: str) -> dict:
        if step in {6, 7, 8, 9} and message.lower() == "skip":
            field = STEPS[step]["fields"][0]
            return {field: []}

        if step in {1, 2}:
            parts = [p.strip() for p in message.replace("\n", ",").split(",") if p.strip()]
            data = {}
            for idx, field in enumerate(STEPS[step]["fields"]):
                data[field] = parts[idx] if idx < len(parts) else ""
            return data

        if step == 3:
            return {"career_interests": message}

        if step == 4:
            skills = [s.strip() for s in message.replace("\n", ",").split(",") if s.strip()]
            return {"skills": skills}

        if step in {5, 6, 7, 8, 9}:
            items = [i.strip() for i in message.replace(";", "\n").split("\n") if i.strip()]
            field = STEPS[step]["fields"][0]
            return {field: items}

        return {}

    def _build_step_response(self, session: BuilderSession, custom_question: str | None = None, extra_summary: dict | None = None) -> dict:
        question = custom_question or STEPS.get(session.current_step, STEPS[12])["question"]
        summary = self._build_summary(session.resume_data)
        if extra_summary:
            summary.update(extra_summary)
        return {
            "session_id": session.session_id,
            "step": session.current_step,
            "question": question,
            "resume_data_summary": summary,
        }

    def _build_summary(self, resume_data: dict) -> dict:
        keys = ["name", "email", "phone", "linkedin", "portfolio", "career_interests", "skills"]
        summary = {k: resume_data.get(k) for k in keys if resume_data.get(k) is not None}
        summary["has_education"] = bool(resume_data.get("education"))
        summary["has_experience"] = bool(resume_data.get("experience"))
        summary["has_projects"] = bool(resume_data.get("projects"))
        return summary

    def _extract_template_choice(self, message: str) -> str | None:
        for ch in message:
            if ch in TEMPLATE_MAP:
                return ch
        return None

    def _post_build_pipeline(self, user_id: int, resume_data: dict) -> None:
        db = SessionLocal()
        try:
            text = self._resume_data_to_text(resume_data)
            analysis = ResumeAnalyzer._analyze(text)
            record = ResumeAnalysis(
                user_id=user_id,
                resume_id=None,
                ats_score=analysis.get("ats_score", 0),
                extracted_skills=analysis.get("skills"),
                missing_sections=analysis.get("missing_sections"),
                analysis_json=analysis,
            )
            db.add(record)
            db.commit()

            create_notification(
                db,
                user_id=user_id,
                type="RESUME_ANALYZED",
                title="Resume analyzed",
                message="Your builder resume has been analyzed and scored.",
            )

            try:
                OrchestratorRunner(db).run(user_id, trigger="resume_builder_complete")
            except Exception:
                db.rollback()
        finally:
            db.close()

    def _resume_data_to_text(self, resume_data: dict) -> str:
        parts = []
        for key in ["name", "email", "phone", "linkedin", "portfolio", "career_interests"]:
            if resume_data.get(key):
                parts.append(str(resume_data[key]))
        for key in ["skills", "education", "experience", "projects", "certifications", "achievements"]:
            value = resume_data.get(key) or []
            if isinstance(value, list):
                parts.extend(value)
            else:
                parts.append(str(value))
        return "\n".join(parts)



