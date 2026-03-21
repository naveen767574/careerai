import re
import logging
import requests
from io import BytesIO
from typing import Any

import pdfplumber
from docx import Document
from sqlalchemy import delete, select

from app.database import SessionLocal
from app.models.resume import Resume
from app.models.resume_analysis import ResumeAnalysis
from app.models.skill import Skill
from app.services.skill_extractor import SkillExtractor
from app.services.r2_storage import get_storage

logger = logging.getLogger(__name__)


class ResumeAnalyzer:
    @staticmethod
    def process_resume(resume_id: str, user_id: int) -> None:
        db = SessionLocal()
        try:
            resume = db.execute(
                select(Resume).where(Resume.id == resume_id, Resume.user_id == user_id)
            ).scalar_one_or_none()
            if not resume:
                return
            file_bytes = ResumeAnalyzer._download_file(resume.file_url)
            text = ResumeAnalyzer._extract_text(file_bytes, resume.file_type)
            analysis = ResumeAnalyzer._analyze(text)
            ResumeAnalyzer._persist(db, user_id, resume.id, analysis)
        finally:
            db.close()

    @staticmethod
    def _download_file(file_url: str) -> bytes:
        from app.config import settings
        import re


        headers = {
            "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            "apikey": settings.SUPABASE_SERVICE_KEY,
        }
        try:
            response = requests.get(file_url, headers=headers, timeout=30)
            if response.status_code == 200:
                return response.content
            # Try without auth (public bucket)
            response = requests.get(file_url, timeout=30)
            if response.status_code == 200:
                return response.content
            raise ValueError(f"Failed to download resume: HTTP {response.status_code}")
        except Exception as exc:
            raise ValueError(f"Failed to download resume: {exc}") from exc

    @staticmethod
    def _extract_text(file_bytes: bytes, file_type: str) -> str:
        if file_type == "pdf":
            return ResumeAnalyzer._extract_pdf(file_bytes)
        if file_type == "docx":
            return ResumeAnalyzer._extract_docx(file_bytes)
        raise ValueError("Unsupported file type")

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        try:
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                return "\n".join(page.extract_text() or "" for page in pdf.pages)
        except Exception as exc:
            raise ValueError("Corrupted PDF file") from exc

    @staticmethod
    def _extract_docx(file_bytes: bytes) -> str:
        try:
            doc = Document(BytesIO(file_bytes))
            return "\n".join(p.text for p in doc.paragraphs if p.text)
        except Exception as exc:
            raise ValueError("Corrupted DOCX file") from exc

    @staticmethod
    def _analyze(text: str) -> dict[str, Any]:
        name = ResumeAnalyzer._extract_name(text)
        email = ResumeAnalyzer._first_match(r"[\w\.-]+@[\w\.-]+", text)
        phone = ResumeAnalyzer._first_match(r"\+?\d[\d\s().-]{7,}\d", text)
        sections = ResumeAnalyzer._split_sections(text)

        skills = SkillExtractor.normalize_skills(
            SkillExtractor.extract_skills(sections.get("skills", text))
        )
        education = ResumeAnalyzer._split_lines(sections.get("education", ""))
        experience = ResumeAnalyzer._split_lines(sections.get("experience", ""))
        projects = ResumeAnalyzer._split_lines(sections.get("projects", ""))
        certifications = ResumeAnalyzer._split_lines(sections.get("certifications", ""))

        missing_sections = []
        if not name:
            missing_sections.append("name")
        if not email:
            missing_sections.append("email")
        if not phone:
            missing_sections.append("phone")
        if not skills:
            missing_sections.append("skills")
        if not education:
            missing_sections.append("education")
        if not experience:
            missing_sections.append("experience")
        if not projects:
            missing_sections.append("projects")
        if not certifications:
            missing_sections.append("certifications")

        ats_score = ResumeAnalyzer._score_resume(
            skills=skills,
            education=education,
            experience=experience,
            projects=projects,
            certifications=certifications,
            missing_sections=missing_sections,
        )

        return {
            "name": name,
            "email": email,
            "phone": phone,
            "skills": skills,
            "education": education,
            "experience": experience,
            "projects": projects,
            "certifications": certifications,
            "ats_score": ats_score,
            "missing_sections": missing_sections,
        }

    @staticmethod
    def _extract_name(text: str) -> str | None:
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        if not lines:
            return None
        first = lines[0]
        if len(first.split()) <= 6:
            return first
        return None

    @staticmethod
    def _split_sections(text: str) -> dict[str, str]:
        sections: dict[str, list[str]] = {
            "education": [],
            "experience": [],
            "projects": [],
            "skills": [],
            "certifications": [],
        }
        current = None
        for line in text.splitlines():
            lower = line.strip().lower()
            if "education" in lower:
                current = "education"
                continue
            if "experience" in lower or "employment" in lower:
                current = "experience"
                continue
            if "project" in lower:
                current = "projects"
                continue
            if "skill" in lower:
                current = "skills"
                continue
            if "certification" in lower:
                current = "certifications"
                continue
            if current:
                sections[current].append(line)
        return {k: "\n".join(v) for k, v in sections.items()}

    @staticmethod
    def _split_lines(section_text: str) -> list[str]:
        return [l.strip() for l in section_text.splitlines() if l.strip()]

    @staticmethod
    def _score_resume(
        *,
        skills: list[str],
        education: list[str],
        experience: list[str],
        projects: list[str],
        certifications: list[str],
        missing_sections: list[str],
    ) -> int:
        score = 0
        score += min(len(skills) * 3, 30)
        score += 15 if education else 0
        score += 20 if experience else 0
        score += 10 if projects else 0
        score += 10 if certifications else 0
        score += 15 if not missing_sections else max(0, 15 - len(missing_sections) * 2)
        return min(score, 100)

    @staticmethod
    def _persist(db, user_id: int, resume_id: str, analysis: dict[str, Any]) -> None:
        db.execute(delete(ResumeAnalysis).where(ResumeAnalysis.resume_id == resume_id))
        record = ResumeAnalysis(
            user_id=user_id,
            resume_id=resume_id,
            ats_score=analysis["ats_score"],
            extracted_skills=analysis["skills"],
            missing_sections=analysis["missing_sections"],
            analysis_json=analysis,
        )
        db.add(record)
        db.execute(delete(Skill).where(Skill.user_id == user_id))
        for skill_name in analysis["skills"]:
            if skill_name and skill_name.strip():
                db.add(Skill(user_id=user_id, skill_name=skill_name.strip().lower()))
        db.commit()

        # Generate and save resume embedding for real match scores
        try:
            from app.services.embedding_service import embed_resume
            import sqlalchemy
            skill_names = [s.strip().lower() for s in analysis["skills"] if s and s.strip()]
            if skill_names:
                vector = embed_resume(skills=skill_names)
                db.execute(
                    sqlalchemy.text("UPDATE resumes SET embedding = :vec WHERE id = :id"),
                    {"vec": str(vector), "id": resume_id}
                )
                db.commit()
                logger.info(f"Resume embedding saved for user {user_id} with {len(skill_names)} skills")
        except Exception as e:
            logger.error(f"Resume embedding failed: {e}")
            # Don't fail the whole analysis if embedding fails

    @staticmethod
    def _first_match(pattern: str, text: str) -> str | None:
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(0) if match else None







