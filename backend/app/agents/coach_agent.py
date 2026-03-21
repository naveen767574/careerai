import json
from dataclasses import dataclass
from datetime import datetime, timedelta

from groq import Groq
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.application import Application
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.services.career_path_predictor import CareerPathPredictor
from app.services.notification_service import create_notification


@dataclass
class CoachingBrief:
    user_id: int
    nudges: list[str]
    generated_at: str
    days_inactive: int


COACH_BRIEF_PROMPT = """
You are a proactive career coach. Generate a short coaching brief (3-5 bullet points)
for this user based on their current career situation.

Context:
- Days since last application: {days_inactive}
- Top new job matches this week: {top_matches_summary}
- Rising skill this week: {top_rising_skill}
- Resume score: {resume_score}/100
- Career path alignment: {path_alignment}
- Analyst insight: {analyst_insight}

Be specific, actionable, and encouraging. Reference actual job titles and skill names.
Do NOT be generic. Each nudge should reference real data from the context above.
Respond as a JSON array of strings: ["nudge 1", "nudge 2", "nudge 3"]
"""


class CoachAgent:
    def __init__(self, db: Session):
        self.db = db
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def run(self, user_id: int, state: dict) -> dict:
        top_matches = state.get("scout_output", {}).get("top_matches", [])
        analyst_output = state.get("analyst_output", {})

        days_inactive = self._days_since_last_application(user_id)
        resume_score = self._get_resume_score(user_id)
        predictor = CareerPathPredictor(self.db)
        paths = predictor.get_paths_for_user(user_id)
        path_alignment = f"{paths[0].match_percentage:.1f}%" if paths else "N/A"

        context = {
            "days_inactive": days_inactive,
            "top_matches_summary": self._build_top_matches_summary(top_matches),
            "top_rising_skill": self._get_top_rising_skill(state),
            "resume_score": resume_score,
            "path_alignment": path_alignment,
            "analyst_insight": analyst_output.get("insight", "") if isinstance(analyst_output, dict) else "",
        }

        nudges = self._generate_brief(context)
        create_notification(
            self.db,
            user_id=user_id,
            type="COACHING_BRIEF",
            title="Your weekly coaching brief",
            message="\n".join(nudges),
        )

        return {
            "user_id": user_id,
            "nudges": nudges,
            "generated_at": datetime.utcnow().isoformat(),
            "days_inactive": days_inactive,
        }

    def _days_since_last_application(self, user_id: int) -> int:
        last_applied = (
            self.db.execute(
                select(func.max(Application.created_at)).where(Application.user_id == user_id)
            )
            .scalar_one()
        )
        if not last_applied:
            return 999
        return (datetime.utcnow() - last_applied).days

    def _get_resume_score(self, user_id: int) -> int:
        resume = self.db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()
        if not resume:
            return 0
        analysis = (
            self.db.execute(
                select(ResumeAnalysis)
                .where(ResumeAnalysis.user_id == user_id)
                .order_by(ResumeAnalysis.created_at.desc())
            )
            .scalars()
            .first()
        )
        return int(analysis.ats_score) if analysis else 0

    def _build_top_matches_summary(self, top_matches: list[dict]) -> str:
        if not top_matches:
            return "No new matches this week."
        lines = []
        for idx, match in enumerate(top_matches[:3], start=1):
            lines.append(
                f"{idx}. {match.get('title', '')} at {match.get('company', '')} (score: {match.get('score', 0)})"
            )
        return "\n".join(lines)

    def _get_top_rising_skill(self, state: dict) -> str:
        trends = state.get("analyst_output", {}).get("trends", [])
        if not trends:
            return "No rising skills detected this week."
        rising = [t for t in trends if t.get("trend") == "rising"]
        if not rising:
            return "No rising skills detected this week."
        rising.sort(key=lambda t: t.get("delta", 0), reverse=True)
        return rising[0].get("skill_name", "No rising skills detected this week.")

    def _generate_brief(self, context: dict) -> list[str]:
        prompt = COACH_BRIEF_PROMPT.format(**context)
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=400,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            if isinstance(data, list):
                return [str(x) for x in data]
        except Exception:
            pass
        return ["Keep applying to new listings.", "Review your top skill matches."]
