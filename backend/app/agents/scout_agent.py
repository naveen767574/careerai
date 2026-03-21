import json
from dataclasses import dataclass

from groq import Groq
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.config import settings
from app.models.experience import Experience
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.skill import Skill
from app.scraper.orchestrator import ScraperOrchestrator


@dataclass
class ScoredListing:
    internship_id: int
    title: str
    company: str
    score: float
    rationale: str


@dataclass
class ScoutOutput:
    top_matches: list[ScoredListing]
    total_scraped: int
    new_listings: int


SCOUT_SCORING_PROMPT = """
You are evaluating whether a job listing is relevant for a specific user.

User profile:
- Skills: {user_skills}
- Experience level: {experience_level}

Job listing:
- Title: {title}
- Company: {company}
- Required skills: {required_skills}

Score the relevance from 0.0 to 1.0 and explain why in one sentence.
Respond ONLY with valid JSON: {{"score": 0.0, "rationale": "..."}}
"""


class ScoutAgent:
    def __init__(self, db: Session):
        self.db = db
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def run(self, user_id: int, state: dict) -> ScoutOutput:
        user_skills = self._get_user_skills(user_id)
        experience_level = self._get_experience_level(user_id)

        scraper = ScraperOrchestrator()
        scrape_results = scraper.scrape_all()
        total_scraped = sum(scrape_results.get("sources", {}).values())
        new_listings = int(scrape_results.get("inserted", 0))

        internships = (
            self.db.execute(select(Internship).order_by(Internship.created_at.desc()).limit(50)).scalars().all()
        )

        user_skills_lower = [s.lower() for s in user_skills]
        scored: list[ScoredListing] = []
        for internship in internships:
            required_skills = self._get_required_skills(internship.id)
            if not self._keyword_prefilter(internship, user_skills_lower, required_skills):
                continue
            scored.append(self._score_listing(internship, user_skills, experience_level, required_skills))

        scored = [s for s in scored if s.score >= 0.4]
        scored.sort(key=lambda s: s.score, reverse=True)
        top_matches = scored[:20]

        return ScoutOutput(top_matches=top_matches, total_scraped=total_scraped, new_listings=new_listings)

    def _score_listing(self, internship, user_skills: list[str], experience_level: str, required_skills: list[str]) -> ScoredListing:
        prompt = SCOUT_SCORING_PROMPT.format(
            user_skills=", ".join(user_skills),
            experience_level=experience_level,
            title=internship.title,
            company=internship.company,
            required_skills=", ".join(required_skills),
        )
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=100,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            score = float(data.get("score", 0.0))
            rationale = data.get("rationale", "scoring failed")
        except Exception:
            score = 0.0
            rationale = "scoring failed"

        return ScoredListing(
            internship_id=internship.id,
            title=internship.title,
            company=internship.company,
            score=score,
            rationale=rationale,
        )

    def _get_user_skills(self, user_id: int) -> list[str]:
        return self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id)).scalars().all()

    def _get_experience_level(self, user_id: int) -> str:
        exp_count = (
            self.db.execute(select(func.count()).select_from(Experience).where(Experience.user_id == user_id)).scalar_one()
        )
        if exp_count <= 1:
            return "Entry level"
        if exp_count <= 3:
            return "Mid level"
        return "Senior level"

    def _get_required_skills(self, internship_id: int) -> list[str]:
        return (
            self.db.execute(select(InternshipSkill.skill_name).where(InternshipSkill.internship_id == internship_id))
            .scalars()
            .all()
        )

    def _keyword_prefilter(self, internship, user_skills_lower: list[str], required_skills: list[str]) -> bool:
        title = internship.title.lower()
        if any(skill in title for skill in user_skills_lower):
            return True
        req_lower = [s.lower() for s in required_skills]
        return any(skill in req_lower for skill in user_skills_lower)
