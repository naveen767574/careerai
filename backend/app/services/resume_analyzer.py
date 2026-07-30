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
            raw = ResumeAnalyzer._extract_pdf(file_bytes)
        elif file_type == "docx":
            raw = ResumeAnalyzer._extract_docx(file_bytes)
        else:
            raise ValueError("Unsupported file type")
        # Normalize spacing / hyphenation before any downstream parsing.
        from app.services.text_normalizer import normalize_resume_text
        return normalize_resume_text(raw)

    @staticmethod
    def _extract_pdf(file_bytes: bytes) -> str:
        """
        Reconstruct text from positioned WORDS rather than extract_text().

        extract_text() frequently drops spaces between glyphs, producing merged
        words like "Engineeredamulti-turnconversationalsystem". extract_words()
        tokenizes by position, so joining tokens with a single space guarantees
        readable spacing. Falls back to extract_text() if word extraction fails.
        """
        from collections import defaultdict
        try:
            with pdfplumber.open(BytesIO(file_bytes)) as pdf:
                page_texts = []
                for page in pdf.pages:
                    try:
                        words = page.extract_words(use_text_flow=True, keep_blank_chars=False)
                    except Exception:
                        words = []
                    if words:
                        # Group words into visual lines by their vertical position.
                        rows: dict = defaultdict(list)
                        for w in words:
                            rows[round(float(w["top"]))].append(w)
                        line_strs = []
                        for top in sorted(rows):
                            row = sorted(rows[top], key=lambda w: float(w["x0"]))
                            line_strs.append(" ".join(w["text"] for w in row))
                        page_texts.append("\n".join(line_strs))
                    else:
                        page_texts.append(page.extract_text() or "")
                return "\n".join(page_texts)
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
        # ── Skills quality (0–35) ─────────────────────────────────────────────
        skill_count = len(skills)
        if skill_count >= 12:
            skills_score = 35
        elif skill_count >= 8:
            skills_score = 28
        elif skill_count >= 5:
            skills_score = 20
        elif skill_count >= 2:
            skills_score = 10
        else:
            skills_score = 0

        # ── Section presence (0–30) ───────────────────────────────────────────
        section_score = (
            (10 if education else 0)
            + (12 if experience else 0)
            + (8 if projects else 0)
        )

        # ── Content quality (0–25) ────────────────────────────────────────────
        # Check for quantification (numbers) and strong action verbs in bullets.
        # These lines come from _split_lines so they still include titles/dates,
        # but any number (year counts) and any action verb (first word) still
        # provides a useful signal at section-level granularity.
        all_lines = experience + projects
        _STRONG_VERBS = {
            "built", "designed", "implemented", "developed", "created", "led",
            "engineered", "architected", "automated", "optimized", "deployed",
            "launched", "shipped", "improved", "reduced", "delivered",
            "streamlined", "integrated", "migrated", "refactored", "scaled",
        }
        has_numbers = any(
            any(ch.isdigit() for ch in line) for line in all_lines
        )
        has_action_verb = any(
            line.split()[0].lower().rstrip(".,") in _STRONG_VERBS
            for line in all_lines
            if line.split()
        )
        quality_score = (
            (12 if has_numbers else 0)
            + (8 if has_action_verb else 0)
            + (5 if certifications else 0)
        )

        total = skills_score + section_score + quality_score
        # Completeness penalty — capped at –10 so a missing cert doesn't crater
        # an otherwise strong resume.
        penalty = min(len(missing_sections) * 2, 10)
        # Hard ceiling at 92: a perfect 100 requires signals (LinkedIn, portfolio,
        # references) we don't validate. This keeps the score credible.
        return min(max(0, total - penalty), 92)

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







