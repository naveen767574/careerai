from dataclasses import dataclass
from typing import List

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.experience import Experience
from app.models.resume import Resume
from app.models.skill import Skill

CAREER_PATHS_CATALOG = [
    {
        "path_id": "frontend_dev",
        "title": "Frontend Developer",
        "description": "Build user interfaces and web experiences",
        "core_skills": ["JavaScript", "React", "HTML", "CSS", "TypeScript"],
        "bonus_skills": ["Vue", "Angular", "Tailwind", "Figma"],
        "levels": {
            "entry": {"years": "0-1", "add_skills": ["React", "TypeScript"]},
            "mid": {"years": "2-3", "add_skills": ["Testing", "Performance", "CI/CD"]},
            "senior": {"years": "5+", "add_skills": ["Architecture", "Mentoring", "System Design"]},
        },
    },
    {
        "path_id": "backend_dev",
        "title": "Backend Developer",
        "description": "Build APIs, services, and data pipelines",
        "core_skills": ["Python", "FastAPI", "PostgreSQL", "REST", "SQL"],
        "bonus_skills": ["Docker", "Redis", "Celery", "AWS", "Django"],
        "levels": {
            "entry": {"years": "0-1", "add_skills": ["FastAPI", "PostgreSQL"]},
            "mid": {"years": "2-3", "add_skills": ["Docker", "System Design", "Redis"]},
            "senior": {"years": "5+", "add_skills": ["Architecture", "Distributed Systems", "Mentoring"]},
        },
    },
    {
        "path_id": "fullstack_dev",
        "title": "Full Stack Developer",
        "description": "Build complete web applications end to end",
        "core_skills": ["JavaScript", "React", "Python", "PostgreSQL", "REST"],
        "bonus_skills": ["TypeScript", "Docker", "AWS", "Node.js"],
        "levels": {
            "entry": {"years": "0-1", "add_skills": ["React", "FastAPI"]},
            "mid": {"years": "2-3", "add_skills": ["Docker", "Testing", "CI/CD"]},
            "senior": {"years": "5+", "add_skills": ["Architecture", "Cloud", "Mentoring"]},
        },
    },
    {
        "path_id": "data_scientist",
        "title": "Data Scientist",
        "description": "Analyse data and build predictive models",
        "core_skills": ["Python", "pandas", "NumPy", "scikit-learn", "SQL"],
        "bonus_skills": ["TensorFlow", "PyTorch", "Spark", "Tableau", "R"],
        "levels": {
            "entry": {"years": "0-1", "add_skills": ["pandas", "scikit-learn", "Statistics"]},
            "mid": {"years": "2-3", "add_skills": ["Deep Learning", "MLOps", "Spark"]},
            "senior": {"years": "5+", "add_skills": ["Research", "Architecture", "Leadership"]},
        },
    },
    {
        "path_id": "ml_engineer",
        "title": "Machine Learning Engineer",
        "description": "Build and deploy machine learning systems at scale",
        "core_skills": ["Python", "TensorFlow", "PyTorch", "scikit-learn", "Docker"],
        "bonus_skills": ["Kubernetes", "MLflow", "AWS", "Spark", "FastAPI"],
        "levels": {
            "entry": {"years": "0-1", "add_skills": ["TensorFlow", "Model Training", "Python"]},
            "mid": {"years": "2-3", "add_skills": ["MLOps", "Docker", "APIs"]},
            "senior": {"years": "5+", "add_skills": ["Architecture", "Research", "Team Lead"]},
        },
    },
    {
        "path_id": "devops_engineer",
        "title": "DevOps / Cloud Engineer",
        "description": "Build and maintain infrastructure and deployment pipelines",
        "core_skills": ["Docker", "Kubernetes", "AWS", "CI/CD", "Linux"],
        "bonus_skills": ["Terraform", "Ansible", "Python", "Bash", "Prometheus"],
        "levels": {
            "entry": {"years": "0-1", "add_skills": ["Docker", "Linux", "Git"]},
            "mid": {"years": "2-3", "add_skills": ["Kubernetes", "Terraform", "Monitoring"]},
            "senior": {"years": "5+", "add_skills": ["Architecture", "Cost Optimisation", "SRE"]},
        },
    },
    {
        "path_id": "mobile_dev",
        "title": "Mobile Developer",
        "description": "Build iOS and Android applications",
        "core_skills": ["React Native", "JavaScript", "TypeScript"],
        "bonus_skills": ["Swift", "Kotlin", "Flutter", "Firebase"],
        "levels": {
            "entry": {"years": "0-1", "add_skills": ["React Native", "REST APIs"]},
            "mid": {"years": "2-3", "add_skills": ["Performance", "Testing", "CI/CD"]},
            "senior": {"years": "5+", "add_skills": ["Architecture", "App Store", "Mentoring"]},
        },
    },
]


@dataclass
class CareerStep:
    level: str
    skills_to_acquire: list[str]


@dataclass
class CareerPath:
    path_id: str
    title: str
    description: str
    alignment_score: float
    match_percentage: float
    required_skills: list[str]
    user_has: list[str]
    user_missing: list[str]
    current_level: str
    steps: list[CareerStep]
    timeline: str
    salary_range: str = "₹6-20 LPA"
    growth_rate: str = "+18%"
    open_positions: int = 12000
    why_fits: str = ""
    top_skill_to_learn: str = ""


class CareerPathPredictor:
    def __init__(self, db: Session):
        self.db = db

    def get_paths_for_user(self, user_id: int) -> list[CareerPath]:
        user_skills = self._get_user_skills(user_id)
        experience_count = self._get_experience_count(user_id)

        paths: list[CareerPath] = []
        for path in CAREER_PATHS_CATALOG:
            score = self._score_path(user_skills, path)
            paths.append(self._build_career_path(path, user_skills, experience_count, score))

        paths.sort(key=lambda p: p.alignment_score, reverse=True)
        top = paths[:5]
        if len(top) < 3:
            return paths
        return top

    def _get_user_skills(self, user_id: int) -> list[str]:
        resume = self.db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()
        if not resume:
            return []
        skills = self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id)).scalars().all()
        return [s for s in skills if s]

    def _get_experience_count(self, user_id: int) -> int:
        return (
            self.db.execute(select(func.count()).select_from(Experience).where(Experience.user_id == user_id))
            .scalar_one()
        )

    def _determine_level(self, experience_count: int) -> str:
        if experience_count <= 1:
            return "Entry"
        if experience_count <= 3:
            return "Mid"
        return "Senior"

    def _score_path(self, user_skills: list[str], path: dict) -> float:
        user_set = {s.lower() for s in user_skills}
        core = path["core_skills"]
        core_matches = sum(1 for s in core if s.lower() in user_set)
        core_score = core_matches / len(core) if core else 0.0
        bonus_matches = sum(1 for s in path["bonus_skills"] if s.lower() in user_set)
        bonus_score = min(1.0, core_score + (bonus_matches * 0.05))
        return round(bonus_score, 4)

    def _build_career_path(
        self,
        path_catalog_entry: dict,
        user_skills: list[str],
        experience_count: int,
        alignment_score: float,
    ) -> CareerPath:
        user_set = {s.lower() for s in user_skills}
        required = path_catalog_entry["core_skills"]
        user_has = [s for s in required if s.lower() in user_set]
        user_missing = [s for s in required if s.lower() not in user_set]
        current_level = self._determine_level(experience_count)

        steps = [
            CareerStep(level="Entry (0-1 yr)", skills_to_acquire=path_catalog_entry["levels"]["entry"]["add_skills"]),
            CareerStep(level="Mid (2-3 yrs)", skills_to_acquire=path_catalog_entry["levels"]["mid"]["add_skills"]),
            CareerStep(level="Senior (5+ yrs)", skills_to_acquire=path_catalog_entry["levels"]["senior"]["add_skills"]),
        ]

        timeline = {
            "Entry": "Entry (0-1 yr)",
            "Mid": "Mid (2-3 yrs)",
            "Senior": "Senior (5+ yrs)",
        }[current_level]

        return CareerPath(
            path_id=path_catalog_entry["path_id"],
            title=path_catalog_entry["title"],
            description=path_catalog_entry["description"],
            alignment_score=alignment_score,
            match_percentage=round(alignment_score * 100, 2),
            required_skills=required,
            user_has=user_has,
            user_missing=user_missing,
            current_level=current_level,
            steps=steps,
            timeline=timeline,
        )



