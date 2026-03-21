from dataclasses import dataclass

from groq import Groq
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.cover_letter_draft import CoverLetterDraft
from app.models.experience import Experience
from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.project import Project
from app.models.resume import Resume
from app.models.skill import Skill
from app.models.user import User


@dataclass
class WriterOutput:
    draft_id: int
    internship_id: int
    content: str
    status: str


WRITER_PROMPT = """
Write a professional cover letter for this job application.

Candidate profile:
- Name: {name}
- Skills: {skills}
- Relevant experience: {relevant_experience}
- Relevant projects: {relevant_projects}

Job listing:
- Title: {title}
- Company: {company}
- Required skills: {required_skills}
- Description: {description_excerpt}

Instructions:
- Open with a specific hook referencing the company or role (not "I am writing to express...")
- Mention 2-3 specific experiences or projects relevant to this role
- Reference required skills naturally within sentences, not as a list
- Close with a confident, specific call to action
- Length: 250-300 words, professional tone
- Do NOT use generic filler phrases
"""


class WriterAgent:
    def __init__(self, db: Session):
        self.db = db
        self.client = Groq(api_key=settings.GROQ_API_KEY)

    def draft(self, user_id: int, internship_id: int) -> WriterOutput:
        internship = self.db.execute(select(Internship).where(Internship.id == internship_id)).scalar_one_or_none()
        if not internship:
            raise ValueError("Internship not found")

        resume = self.db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()
        if not resume:
            raise ValueError("No resume found")

        data = self._get_user_resume_data(user_id)
        required_skills = (
            self.db.execute(select(InternshipSkill.skill_name).where(InternshipSkill.internship_id == internship_id))
            .scalars()
            .all()
        )

        prompt = WRITER_PROMPT.format(
            name=data.get("name", ""),
            skills=", ".join(data.get("skills", [])),
            relevant_experience="; ".join(data.get("relevant_experience", [])),
            relevant_projects="; ".join(data.get("relevant_projects", [])),
            title=internship.title,
            company=internship.company,
            required_skills=", ".join(required_skills),
            description_excerpt=self._get_description_excerpt(internship),
        )

        response = self.client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
        )
        content = response.choices[0].message.content

        draft = CoverLetterDraft(
            user_id=user_id,
            internship_id=internship_id,
            content=content,
            status="draft",
        )
        self.db.add(draft)
        self.db.commit()
        self.db.refresh(draft)

        return WriterOutput(
            draft_id=draft.id,
            internship_id=internship_id,
            content=content,
            status=draft.status,
        )

    def _get_user_resume_data(self, user_id: int) -> dict:
        user = self.db.execute(select(User).where(User.id == user_id)).scalar_one_or_none()
        skills = self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id)).scalars().all()
        experiences = (
            self.db.execute(select(Experience).where(Experience.user_id == user_id).order_by(Experience.start_date.desc()))
            .scalars()
            .all()
        )
        projects = (
            self.db.execute(select(Project).where(Project.user_id == user_id)).scalars().all()
        )

        exp_list = []
        for exp in experiences:
            desc = (exp.description or "")[:100]
            exp_list.append(f"{exp.role or 'Role'} at {exp.company or 'Company'}: {desc}")

        proj_list = []
        for proj in projects:
            desc = (proj.description or "")[:100]
            proj_list.append(f"{proj.name or 'Project'}: {desc}")

        return {
            "name": user.name if user else "",
            "skills": skills,
            "relevant_experience": exp_list,
            "relevant_projects": proj_list,
        }

    def _get_description_excerpt(self, internship) -> str:
        return (internship.description or "")[:300]
