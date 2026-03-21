import uuid

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.agent_state import AgentState
from app.models.linkedin_report import LinkedInReport
from app.models.linkedin_session import LinkedInSession
from app.models.project import Project
from app.models.resume import Resume
from app.models.resume_data import ResumeData
from app.models.skill import Skill
from app.models.experience import Experience
from app.services.notification_service import create_notification
from app.services.profile_scorer import ProfileScorer
from app.services.gap_analyzer import GapAnalyzer
from app.services.content_optimizer import ContentOptimizer


class LinkedInService:
    def __init__(self, db: Session):
        self.db = db
        self.scorer = ProfileScorer()
        self.gap_analyzer = GapAnalyzer()
        self.optimizer = ContentOptimizer()

    def analyze(self, user_id: int, profile_input: dict) -> dict:
        resume_data = self._get_resume_data(user_id)
        skill_trends = self._get_skill_trends(user_id)

        score_data = self.scorer.calculate(profile_input, resume_data)
        gap_analysis = self.gap_analyzer.analyze(profile_input, resume_data, skill_trends)

        career_interests = resume_data.get("career_interests", []) or []
        headline_variants = self.optimizer.rewrite_headline(
            profile_input.get("headline", ""),
            resume_data,
            career_interests,
        )
        about_section = self.optimizer.write_about_section(
            resume_data,
            career_interests,
            profile_input.get("about", ""),
        )
        experience_improvements = self.optimizer.enhance_experience_bullets(
            profile_input.get("experience", [])[:6],
            career_interests[0] if career_interests else "",
        )
        skills_optimization = self.optimizer.suggest_skills_optimization(
            profile_input.get("skills", []),
            resume_data.get("skills", []),
            skill_trends,
        )

        improvement_priority = self._build_improvement_priority(score_data["score_breakdown"], gap_analysis)

        session = LinkedInSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            profile_input=profile_input,
            status="completed",
        )
        self.db.add(session)
        self.db.flush()

        report = LinkedInReport(
            session_id=session.session_id,
            user_id=user_id,
            profile_score=score_data["profile_score"],
            score_breakdown=score_data["score_breakdown"],
            gap_analysis=gap_analysis,
            headline_variants=headline_variants,
            about_section=about_section,
            experience_improvements=experience_improvements,
            skills_optimization=skills_optimization,
            improvement_priority=improvement_priority,
        )
        self.db.add(report)

        create_notification(
            self.db,
            user_id=user_id,
            type="LINKEDIN_REPORT_READY",
            title="LinkedIn report ready",
            message="Your LinkedIn profile report is ready to review.",
        )

        self.db.commit()
        self.db.refresh(report)

        return self._report_to_dict(report)

    def get_report(self, session_id: str, user_id: int) -> LinkedInReport:
        report = self.db.query(LinkedInReport).filter(LinkedInReport.session_id == session_id).first()
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        if report.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your report")
        return report

    def get_score(self, session_id: str, user_id: int) -> dict:
        report = self.get_report(session_id, user_id)
        return {
            "session_id": report.session_id,
            "profile_score": report.profile_score,
            "score_breakdown": report.score_breakdown,
            "improvement_priority": report.improvement_priority,
        }

    def regenerate_section(self, session_id: str, user_id: int, section: str, feedback: str) -> dict:
        report = self.get_report(session_id, user_id)
        session = self.db.query(LinkedInSession).filter(LinkedInSession.session_id == session_id).first()
        if not session or session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        resume_data = self._get_resume_data(user_id)
        career_interests = resume_data.get("career_interests", []) or []

        if section == "headline":
            updated = self.optimizer.rewrite_headline(
                session.profile_input.get("headline", ""),
                resume_data,
                career_interests,
                feedback,
            )
            report.headline_variants = updated
            updated_content = updated
        elif section == "about":
            updated = self.optimizer.write_about_section(
                resume_data,
                career_interests,
                session.profile_input.get("about", ""),
                feedback,
            )
            report.about_section = updated
            updated_content = updated
        elif section == "bullets":
            updated = self.optimizer.enhance_experience_bullets(
                session.profile_input.get("experience", [])[:6],
                career_interests[0] if career_interests else "",
                feedback,
            )
            report.experience_improvements = updated
            updated_content = updated
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid section")

        self.db.add(report)
        self.db.commit()

        return {"section": section, "updated_content": updated_content}

    def get_history(self, user_id: int) -> list[dict]:
        rows = (
            self.db.query(LinkedInSession, LinkedInReport)
            .outerjoin(LinkedInReport, LinkedInReport.session_id == LinkedInSession.session_id)
            .filter(LinkedInSession.user_id == user_id)
            .order_by(LinkedInSession.created_at.desc())
            .all()
        )
        return [
            {
                "session_id": s.session_id,
                "profile_score": r.profile_score if r else None,
                "status": s.status,
                "created_at": s.created_at,
            }
            for s, r in rows
        ]

    def get_latest(self, user_id: int) -> dict | None:
        report = (
            self.db.query(LinkedInReport)
            .filter(LinkedInReport.user_id == user_id)
            .order_by(LinkedInReport.created_at.desc())
            .first()
        )
        if not report:
            return None
        return self._report_to_dict(report)

    def _get_resume_data(self, user_id: int) -> dict:
        resume = self.db.query(Resume).filter(Resume.user_id == user_id).first()
        if not resume:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No resume found")

        skills = [s.skill_name for s in self.db.query(Skill).filter(Skill.user_id == user_id).all() if s.skill_name]
        experiences = [e.description for e in self.db.query(Experience).filter(Experience.user_id == user_id).all() if e.description]
        projects = [p.name for p in self.db.query(Project).filter(Project.user_id == user_id).all() if p.name]

        resume_data = self.db.query(ResumeData).filter(ResumeData.user_id == user_id).first()
        career_interests = []
        if resume_data and resume_data.summary:
            career_interests = [resume_data.summary]

        return {
            "skills": skills,
            "experience": experiences,
            "projects": projects,
            "career_interests": career_interests,
            "education": [],
        }

    def _get_skill_trends(self, user_id: int) -> list[dict]:
        state = self.db.query(AgentState).filter(AgentState.user_id == user_id).first()
        if not state or not state.state_json:
            return []
        return state.state_json.get("analyst_output", {}).get("trends", []) or []

    def _build_improvement_priority(self, score_breakdown: dict, gap_analysis: dict) -> list[str]:
        priorities = []
        sorted_sections = sorted(score_breakdown.items(), key=lambda x: x[1])
        for section, score in sorted_sections:
            if score == 0:
                priorities.append(f"Add or improve your {section} section")
            elif score < 10 and section in {"headline", "about", "experience", "skills"}:
                priorities.append(f"Improve your {section} section")

        missing_skills = gap_analysis.get("missing_skills", [])
        if missing_skills:
            priorities.insert(0, f"Add {min(len(missing_skills), 5)} missing skills to your Skills section")

        headline_strength = gap_analysis.get("headline_strength")
        if headline_strength in {"weak", "generic"}:
            priorities.append("Update your headline with role and skill keywords")

        unique_priorities = []
        for p in priorities:
            if p not in unique_priorities:
                unique_priorities.append(p)
        while len(unique_priorities) < 3:
            unique_priorities.append("Expand your About section to 150+ words")
        return unique_priorities[:3]

    def _report_to_dict(self, report: LinkedInReport) -> dict:
        return {
            "session_id": report.session_id,
            "profile_score": report.profile_score,
            "score_breakdown": report.score_breakdown,
            "gap_analysis": report.gap_analysis,
            "headline_variants": report.headline_variants,
            "about_section": report.about_section,
            "experience_improvements": report.experience_improvements,
            "skills_optimization": report.skills_optimization,
            "improvement_priority": report.improvement_priority,
            "created_at": report.created_at,
        }
