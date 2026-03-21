from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.resume import Resume
from app.models.skill import Skill


@dataclass
class RoleComparisonItem:
    internship_id: int
    title: str
    company: str
    location: str
    required_skills: list[str]
    user_match_percentage: float
    matched_skills: list[str]
    missing_skills: list[str]


@dataclass
class RoleComparison:
    roles: list[RoleComparisonItem]
    common_skills: list[str]
    unique_skills: dict[int, list[str]]


class RoleComparator:
    def __init__(self, db: Session):
        self.db = db

    def compare(self, internship_ids: list[int], user_id: int) -> RoleComparison:
        if len(internship_ids) < 2 or len(internship_ids) > 4:
            raise ValueError("Provide between 2 and 4 internship IDs.")

        user_skills = self._get_user_skills(user_id)
        roles: list[RoleComparisonItem] = []
        required_by_role: dict[int, list[str]] = {}

        for internship_id in internship_ids:
            internship = self.db.get(Internship, internship_id)
            if not internship:
                raise ValueError(f"Internship {internship_id} not found.")
            required_skills = self._get_internship_skills(internship_id)
            required_by_role[internship_id] = required_skills
            matched, missing, match_pct = self._compute_match(user_skills, required_skills)
            roles.append(
                RoleComparisonItem(
                    internship_id=internship.id,
                    title=internship.title,
                    company=internship.company,
                    location=internship.location,
                    required_skills=required_skills,
                    user_match_percentage=match_pct,
                    matched_skills=matched,
                    missing_skills=missing,
                )
            )

        common_skills = self._compute_common_skills(required_by_role)
        unique_skills = {
            internship_id: [s for s in skills if s.lower() not in {c.lower() for c in common_skills}]
            for internship_id, skills in required_by_role.items()
        }

        return RoleComparison(roles=roles, common_skills=common_skills, unique_skills=unique_skills)

    def _get_user_skills(self, user_id: int) -> list[str]:
        resume = self.db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()
        if not resume:
            return []
        skills = self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id)).scalars().all()
        return [s for s in skills if s]

    def _get_internship_skills(self, internship_id: int) -> list[str]:
        return (
            self.db.execute(select(InternshipSkill.skill_name).where(InternshipSkill.internship_id == internship_id))
            .scalars()
            .all()
        )

    def _compute_match(
        self,
        user_skills: list[str],
        required_skills: list[str],
    ) -> tuple[list[str], list[str], float]:
        user_set = {s.lower() for s in user_skills}
        required_set = {s.lower() for s in required_skills}
        matched = [s for s in required_skills if s.lower() in user_set]
        missing = [s for s in required_skills if s.lower() not in user_set]
        match_percentage = 0.0
        if required_set:
            match_percentage = (len(matched) / len(required_set)) * 100
        return sorted(matched), sorted(missing), round(match_percentage, 2)

    def _compute_common_skills(self, required_by_role: dict[int, list[str]]) -> list[str]:
        skill_sets = []
        for skills in required_by_role.values():
            skill_sets.append({s.lower() for s in skills})
        if not skill_sets:
            return []
        common = set.intersection(*skill_sets)
        ordered = []
        seen = set()
        for skills in required_by_role.values():
            for s in skills:
                if s.lower() in common and s.lower() not in seen:
                    ordered.append(s)
                    seen.add(s.lower())
        return ordered
