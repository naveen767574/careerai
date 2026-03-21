import json

from dataclasses import dataclass

from datetime import date, datetime



from groq import Groq

from sqlalchemy import select, func

from sqlalchemy.orm import Session



from app.config import settings

from app.models.internship import Internship

from app.models.internship_skill import InternshipSkill

from app.models.skill_snapshot import SkillSnapshot

from app.models.skill import Skill





@dataclass

class SkillTrend:

    skill_name: str

    frequency_pct: float

    previous_pct: float

    trend: str

    delta: float





@dataclass

class AnalystOutput:

    trends: list[SkillTrend]

    insight: str

    snapshot_date: str





ANALYST_INSIGHT_PROMPT = """

You are a career analyst. Based on the skill trend data below, generate 2-3 specific,

actionable insights for this user. Reference actual skill names and percentages.



Skill trends this week:

{trends_summary}



User's current skills: {user_skills}



Write 2-3 natural language insights. Be specific and encouraging.

Example: "Docker appeared in 68% of your top matches this week, up from 40%  worth prioritising."

Respond as a plain paragraph, no bullet points, no JSON.

"""





class AnalystAgent:

    def __init__(self, db: Session):

        self.db = db

        self.client = Groq(api_key=settings.GROQ_API_KEY)



    def run(self, user_id: int, state: dict) -> AnalystOutput:

        top_matches = state.get("scout_output", {}).get("top_matches") or []

        if not top_matches:

            internships = (

                self.db.execute(select(Internship).order_by(Internship.created_at.desc()).limit(20))

                .scalars()

                .all()

            )

            top_matches = [{"internship_id": i.id} for i in internships]



        skill_freq = self._calculate_skill_frequency(top_matches)

        prev = self._load_previous_snapshot(user_id)



        trends: list[SkillTrend] = []

        for skill_name, pct in skill_freq.items():

            previous_pct = prev.get(skill_name, 0.0)

            delta = pct - previous_pct

            if delta > 10:

                trend = "rising"

            elif delta < -10:

                trend = "falling"

            else:

                trend = "stable"

            trends.append(SkillTrend(skill_name=skill_name, frequency_pct=pct, previous_pct=previous_pct, trend=trend, delta=delta))



        self._save_snapshot(user_id, skill_freq, trends)



        user_skills = self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id)).scalars().all()

        insight = self._generate_insight(trends, user_skills)



        snapshot_date = date.today().isoformat()

        return AnalystOutput(trends=trends, insight=insight, snapshot_date=snapshot_date)



    def _calculate_skill_frequency(self, top_matches: list[dict]) -> dict[str, float]:

        ids = [m.get("internship_id") for m in top_matches if m.get("internship_id")]

        if not ids:

            return {}

        rows = (

            self.db.execute(select(InternshipSkill.internship_id, InternshipSkill.skill_name).where(InternshipSkill.internship_id.in_(ids)))

            .all()

        )

        counts: dict[str, int] = {}

        total = len(set(ids))

        for _, skill in rows:

            if not skill:

                continue

            counts[skill] = counts.get(skill, 0) + 1

        return {k: round((v / total) * 100, 2) for k, v in counts.items()} if total else {}



    def _load_previous_snapshot(self, user_id: int) -> dict[str, float]:

        latest_date = (

            self.db.execute(

                select(SkillSnapshot.snapshot_date)

                .where(SkillSnapshot.user_id == user_id)

                .order_by(SkillSnapshot.snapshot_date.desc())

                .limit(1)

            )

            .scalars()

            .first()

        )

        if not latest_date:

            return {}

        rows = (

            self.db.execute(

                select(SkillSnapshot.skill_name, SkillSnapshot.frequency_pct)

                .where(SkillSnapshot.user_id == user_id, SkillSnapshot.snapshot_date == latest_date)

            )

            .all()

        )

        return {r[0]: float(r[1]) for r in rows}



    def _save_snapshot(self, user_id: int, skill_freq: dict, trends: list[SkillTrend]) -> None:

        today = date.today()

        exists = (

            self.db.execute(

                select(func.count()).select_from(SkillSnapshot).where(

                    SkillSnapshot.user_id == user_id, SkillSnapshot.snapshot_date == today

                )

            )

            .scalar_one()

        )

        if exists:

            return

        trend_map = {t.skill_name: t.trend for t in trends}

        for skill_name, pct in skill_freq.items():

            self.db.add(

                SkillSnapshot(

                    user_id=user_id,

                    snapshot_date=today,

                    skill_name=skill_name,

                    frequency_pct=pct,

                    trend=trend_map.get(skill_name),

                )

            )

        self.db.commit()



    def _generate_insight(self, trends: list[SkillTrend], user_skills: list[str]) -> str:

        try:

            top = sorted(trends, key=lambda t: t.frequency_pct, reverse=True)[:5]

            trends_summary = ", ".join([f"{t.skill_name} {t.frequency_pct}% ({t.trend})" for t in top])

            prompt = ANALYST_INSIGHT_PROMPT.format(trends_summary=trends_summary, user_skills=", ".join(user_skills))

            response = self.client.chat.completions.create(

                model="llama-3.1-8b-instant",

                messages=[{"role": "user", "content": prompt}],

                max_tokens=200,

            )

            return response.choices[0].message.content

        except Exception:

            return "Skill trend analysis complete."

