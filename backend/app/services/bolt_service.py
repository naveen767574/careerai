from datetime import datetime
import uuid
import uuid



from fastapi import HTTPException, status

from groq import Groq

from sqlalchemy import select, func

from sqlalchemy.orm import Session



from app.config import settings

from app.models.chat_log import ChatLog

from app.models.experience import Experience

from app.models.notification import Notification

from app.models.recommendation import Recommendation

from app.models.resume import Resume

from app.models.resume_analysis import ResumeAnalysis

from app.models.skill import Skill

from app.models.user import User

from app.models.internship import Internship

from app.services.notification_service import NotificationService





class BoltAIService:    INTENT_KEYWORDS = {
        "navigation": ["where", "how to", "find", "navigate", "go to", "show me", "page", "section"],
        "resume_coach": ["resume", "cv", "skills", "improve", "score", "feedback", "upload", "section"],
        "job_search": ["internship", "job", "listing", "apply", "search", "recommend", "match", "role"],
        "career_mentor": ["career", "path", "future", "grow", "mentor", "goal", "long term", "advice"],
        "skill_advisor": ["learn", "skill", "course", "gap", "missing", "improve", "study", "roadmap", "interview", "practice", "mock", "question", "answer", "feedback"],
    }

    SYSTEM_PROMPTS = {
        "navigation": """You are Bolt, a concise AI assistant for CareerAI platform.
Answer in 2-3 sentences maximum. Be direct and helpful.
Platform sections: Dashboard, Resume Analyzer, Internships, Career Paths, Applications, Interview Prep, LinkedIn Analyzer.
User context: {user_context}""",

        "resume_coach": """You are Bolt, a concise AI resume coach.
Give specific advice in 3-4 bullet points maximum. Be direct and actionable.
User context: {user_context}""",

        "job_search": """You are Bolt, a concise AI job search assistant.
Answer in 2-3 sentences. Be direct and specific.
User context: {user_context}""",

        "career_mentor": """You are Bolt, a concise AI career mentor.
Answer in 2-3 sentences. Focus on practical next steps only.
User context: {user_context}""",

        "skill_advisor": """You are Bolt, a concise AI skills advisor.
Give tips in 2-3 bullet points maximum. Be specific and practical.
User context: {user_context}""",
    }

    def __init__(self, db: Session):

        self.db = db

        api_key = getattr(settings, "GROQ_API_KEY", None)

        self.client = Groq(api_key=api_key) if api_key else None



    def process_message(self, user_id: int, message: str, session_id: str = None) -> tuple[str, str, str]:

        if not session_id:
            session_id = str(uuid.uuid4())

        if not self.client:

            raise HTTPException(

                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

                detail="Bolt AI is not configured. Set GROQ_API_KEY in your environment.",

            )



        intent = self.classify_intent(message)

        user_context = self._build_user_context(user_id)

        system_prompt = self.SYSTEM_PROMPTS[intent].format(user_context=user_context)

        history = self._get_session_history(user_id, session_id)



        messages = [{"role": "system", "content": system_prompt}] + history + [

            {"role": "user", "content": message}

        ]



        try:

            response = self.client.chat.completions.create(

                model="llama-3.1-8b-instant",

                messages=messages,

                max_tokens=300,

            )

            content = response.choices[0].message.content

        except Exception:

            raise HTTPException(

                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,

                detail="Bolt AI temporarily unavailable. Please try again.",

            )



        self._persist_message(user_id, session_id, "user", message, None)

        self._persist_message(user_id, session_id, "assistant", content, intent)

        return content, intent, session_id



    def classify_intent(self, message: str) -> str:

        text = message.lower()

        scores = {k: 0 for k in self.INTENT_KEYWORDS.keys()}

        for intent, keywords in self.INTENT_KEYWORDS.items():

            for kw in keywords:

                if kw in text:

                    scores[intent] += 1

        best = max(scores, key=scores.get)

        if scores[best] == 0:

            return "career_mentor"

        return best



    def _build_user_context(self, user_id: int) -> str:

        resume = self.db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()

        if not resume:

            return "No profile data available yet."



        user = self.db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()

        name = user.name if user else "User"



        resume_analysis = (

            self.db.execute(

                select(ResumeAnalysis)

                .where(ResumeAnalysis.user_id == user_id)

                .order_by(ResumeAnalysis.created_at.desc())

            )

            .scalars()

            .first()

        )

        resume_score = resume_analysis.ats_score if resume_analysis else None



        skills = (

            self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id).limit(5))

            .scalars()

            .all()

        )



        recs = (

            self.db.query(Recommendation, Internship)

            .join(Internship, Internship.id == Recommendation.internship_id)

            .filter(Recommendation.user_id == user_id)

            .order_by(Recommendation.similarity_score.desc())

            .limit(3)

            .all()

        )

        rec_text = ", ".join([f"{i.title} at {i.company} ({r.similarity_score:.2f})" for r, i in recs])



        exp_count = (

            self.db.execute(select(func.count()).select_from(Experience).where(Experience.user_id == user_id))

            .scalar_one()

        )



        unread_count = NotificationService(self.db).get_unread_count(user_id)



        parts = [

            f"Name: {name}",

            f"Resume score: {resume_score if resume_score is not None else 'N/A'}",

            f"Top skills: {', '.join(skills) if skills else 'N/A'}",

            f"Top recommendations: {rec_text if rec_text else 'N/A'}",

            f"Experience entries: {exp_count}",

            f"Unread notifications: {unread_count}",

        ]

        return "\n".join(parts)



    def _get_session_history(self, user_id: int, session_id: str) -> list[dict]:

        logs = (

            self.db.execute(

                select(ChatLog)

                .where(ChatLog.user_id == user_id, ChatLog.session_id == session_id)

                .order_by(ChatLog.created_at.desc())

                .limit(10)

            )

            .scalars()

            .all()

        )

        logs = list(reversed(logs))

        return [{"role": l.role, "content": l.content} for l in logs]



    def _persist_message(self, user_id: int, session_id: str, role: str, content: str, intent: str | None = None) -> None:

        log = ChatLog(

            user_id=user_id,

            session_id=session_id,

            role=role,

            content=content,

            intent=intent,

        )

        self.db.add(log)

        self.db.commit()



    def get_session_history(self, user_id: int, session_id: str) -> list[ChatLog]:

        return (

            self.db.execute(

                select(ChatLog)

                .where(ChatLog.user_id == user_id, ChatLog.session_id == session_id)

                .order_by(ChatLog.created_at.asc())

            )

            .scalars()

            .all()

        )



    def delete_session(self, user_id: int, session_id: str) -> int:

        result = self.db.execute(

            select(ChatLog).where(ChatLog.user_id == user_id, ChatLog.session_id == session_id)

        ).scalars().all()

        if not result:

            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

        deleted = self.db.query(ChatLog).filter(ChatLog.user_id == user_id, ChatLog.session_id == session_id).delete()

        self.db.commit()

        return deleted














