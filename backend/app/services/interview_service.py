import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.interview_answer import InterviewAnswer
from app.models.interview_question import InterviewQuestion
from app.models.interview_report import InterviewReport
from app.models.interview_session import InterviewSession
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.project import Project
from app.models.resume_data import ResumeData
from app.models.skill import Skill
from app.models.experience import Experience
from app.services.notification_service import create_notification
from app.services.question_generator import QuestionGenerator
from app.services.answer_evaluator import AnswerEvaluator
from app.services.feedback_reporter import FeedbackReporter


class InterviewService:
    def __init__(self, db: Session):
        self.db = db
        self.question_generator = QuestionGenerator()
        self.answer_evaluator = AnswerEvaluator()
        self.feedback_reporter = FeedbackReporter()

    def start_session(self, user_id: int, internship_id: int) -> dict:
        internship = self.db.query(Internship).filter(Internship.id == internship_id).first()
        if not internship:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")

        profile = self._get_user_profile(user_id)
        required_skills = [s.skill_name for s in self.db.query(InternshipSkill).filter(InternshipSkill.internship_id == internship_id).all() if s.skill_name]

        questions = self.question_generator.generate_question_set(
            internship=internship,
            required_skills=required_skills,
            user_skills=profile["skills"],
            user_projects=profile["projects"],
            experience_level=profile["experience_level"],
        )

        session = InterviewSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            internship_id=internship_id,
            status="in_progress",
        )
        self.db.add(session)
        self.db.flush()

        question_rows = [
            InterviewQuestion(
                session_id=session.session_id,
                question_text=q["question_text"],
                category=q["category"],
                difficulty=q.get("difficulty"),
                skill_tested=q.get("skill_tested"),
                order_index=q["order_index"],
            )
            for q in questions
        ]
        self.db.add_all(question_rows)
        self.db.commit()

        first_question = min(question_rows, key=lambda x: x.order_index)
        return {
            "session_id": session.session_id,
            "internship": {"title": internship.title, "company": internship.company},
            "first_question": first_question,
            "total_questions": 10,
        }

    def submit_answer(self, session_id: str, user_id: int, question_id: int, answer_text: str) -> dict:
        session = self._get_session(session_id, user_id)
        if session.status != "in_progress":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session completed")

        question = (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.id == question_id, InterviewQuestion.session_id == session_id)
            .first()
        )
        if not question:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")

        existing = (
            self.db.query(InterviewAnswer)
            .filter(InterviewAnswer.question_id == question_id, InterviewAnswer.user_id == user_id)
            .first()
        )
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Already answered")

        evaluation = self.answer_evaluator.evaluate(question, answer_text)

        answer = InterviewAnswer(
            question_id=question.id,
            session_id=session_id,
            user_id=user_id,
            answer_text=answer_text,
            score=evaluation["score"],
            verdict=evaluation["verdict"],
            strengths=evaluation["strengths"],
            weaknesses=evaluation["weaknesses"],
            model_answer=evaluation["model_answer"],
            improvement_tip=evaluation["improvement_tip"],
        )
        self.db.add(answer)
        self.db.commit()

        answers_submitted = (
            self.db.query(func.count())
            .select_from(InterviewAnswer)
            .filter(InterviewAnswer.session_id == session_id, InterviewAnswer.user_id == user_id)
            .scalar()
        )

        next_question = (
            self.db.query(InterviewQuestion)
            .filter(
                InterviewQuestion.session_id == session_id,
                InterviewQuestion.order_index == question.order_index + 1,
            )
            .first()
        )

        return {
            "answer_saved": True,
            "score": evaluation["score"],
            "verdict": evaluation["verdict"],
            "strengths": evaluation["strengths"],
            "weaknesses": evaluation["weaknesses"],
            "model_answer": evaluation["model_answer"],
            "improvement_tip": evaluation["improvement_tip"],
            "next_question": next_question,
            "answers_submitted": int(answers_submitted or 0),
            "total_questions": 10,
        }

    def complete_session(self, session_id: str, user_id: int) -> dict:
        session = self._get_session(session_id, user_id)
        if session.status != "in_progress":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session already completed")

        answers = (
            self.db.query(InterviewAnswer)
            .filter(InterviewAnswer.session_id == session_id, InterviewAnswer.user_id == user_id)
            .all()
        )
        if len(answers) < 10:
            remaining = 10 - len(answers)
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"{remaining} questions remaining")

        questions = (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.session_id == session_id)
            .order_by(InterviewQuestion.order_index.asc())
            .all()
        )

        internship = self.db.query(Internship).filter(Internship.id == session.internship_id).first()
        report_data = self.feedback_reporter.compile(session, questions, answers, internship)

        report = InterviewReport(
            session_id=session_id,
            user_id=user_id,
            internship_id=session.internship_id,
            overall_score=report_data["overall_score"],
            technical_score=report_data["technical_score"],
            behavioral_score=report_data["behavioral_score"],
            readiness_level=report_data["readiness_level"],
            top_strengths=report_data["top_strengths"],
            top_improvements=report_data["top_improvements"],
            recommended_resources=report_data["recommended_resources"],
        )
        self.db.add(report)

        session.status = "completed"
        session.overall_score = report_data["overall_score"]
        session.readiness_level = report_data["readiness_level"]
        session.completed_at = datetime.utcnow()
        self.db.add(session)

        create_notification(
            self.db,
            user_id=user_id,
            type="INTERVIEW_REPORT_READY",
            title="Interview report ready",
            message="Your mock interview report is ready to review.",
        )

        self.db.commit()
        self.db.refresh(report)
        report_data["created_at"] = report.created_at
        return report_data

    def get_report(self, session_id: str, user_id: int) -> InterviewReport:
        report = self.db.query(InterviewReport).filter(InterviewReport.session_id == session_id).first()
        if not report:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
        if report.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your report")
        return report

    def get_history(self, user_id: int) -> list[dict]:
        rows = (
            self.db.query(InterviewSession, Internship)
            .join(Internship, Internship.id == InterviewSession.internship_id)
            .filter(InterviewSession.user_id == user_id)
            .order_by(InterviewSession.created_at.desc())
            .all()
        )
        return [
            {
                "session_id": s.session_id,
                "internship_title": i.title,
                "company": i.company,
                "status": s.status,
                "overall_score": s.overall_score,
                "readiness_level": s.readiness_level,
                "created_at": s.created_at,
            }
            for s, i in rows
        ]

    def get_questions(self, session_id: str, user_id: int) -> list[InterviewQuestion]:
        session = self._get_session(session_id, user_id)
        return (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.session_id == session.session_id)
            .order_by(InterviewQuestion.order_index.asc())
            .all()
        )

    def retry_session(self, session_id: str, user_id: int) -> dict:
        original = self._get_session(session_id, user_id)
        internship = self.db.query(Internship).filter(Internship.id == original.internship_id).first()
        if not internship:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Internship not found")

        new_session = InterviewSession(
            session_id=str(uuid.uuid4()),
            user_id=user_id,
            internship_id=original.internship_id,
            status="in_progress",
        )
        self.db.add(new_session)
        self.db.flush()

        original_questions = (
            self.db.query(InterviewQuestion)
            .filter(InterviewQuestion.session_id == original.session_id)
            .order_by(InterviewQuestion.order_index.asc())
            .all()
        )
        new_questions = [
            InterviewQuestion(
                session_id=new_session.session_id,
                question_text=q.question_text,
                category=q.category,
                difficulty=q.difficulty,
                skill_tested=q.skill_tested,
                order_index=q.order_index,
            )
            for q in original_questions
        ]
        self.db.add_all(new_questions)
        self.db.commit()

        first_question = min(new_questions, key=lambda x: x.order_index)
        return {
            "session_id": new_session.session_id,
            "internship": {"title": internship.title, "company": internship.company},
            "first_question": first_question,
            "total_questions": 10,
        }

    def _get_user_profile(self, user_id: int) -> dict:
        skills = [s.skill_name for s in self.db.query(Skill).filter(Skill.user_id == user_id).all() if s.skill_name]
        projects = [p.name for p in self.db.query(Project).filter(Project.user_id == user_id).all() if p.name]
        experience_count = (
            self.db.query(func.count()).select_from(Experience).filter(Experience.user_id == user_id).scalar()
        )
        if experience_count <= 1:
            level = "Entry"
        elif experience_count <= 3:
            level = "Mid"
        else:
            level = "Senior"

        resume_data = self.db.query(ResumeData).filter(ResumeData.user_id == user_id).first()
        career_interests = []
        if resume_data and resume_data.summary:
            career_interests = [resume_data.summary]

        return {
            "skills": skills,
            "projects": projects,
            "experience_level": level,
            "career_interests": career_interests,
        }

    def _get_session(self, session_id: str, user_id: int) -> InterviewSession:
        session = self.db.query(InterviewSession).filter(InterviewSession.session_id == session_id).first()
        if not session:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
        if session.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your session")
        return session

