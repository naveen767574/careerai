from groq import Groq

from app.config import settings
from app.models.builder_session import BuilderSession


OPTIMIZE_BULLET_PROMPT = """
Rewrite this resume bullet point to be more impactful, specific, and ATS-friendly.
Use strong action verbs. Quantify impact where possible (use placeholders like [X%] if exact numbers are unknown).
Keep it to one line, under 20 words.

Original: {bullet}
Role context: {role_context}

Respond with ONLY the improved bullet point text. No explanation.
"""


class ResumeOptimizer:
    def __init__(self, db=None):
        api_key = getattr(settings, "GROQ_API_KEY", None)
        self.client = Groq(api_key=api_key) if api_key else None
        self.db = db

    def optimize_bullet(self, bullet: str, role_context: str = "") -> str:
        if not self.client:
            return bullet
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are a resume optimization assistant."},
                    {"role": "user", "content": OPTIMIZE_BULLET_PROMPT.format(bullet=bullet, role_context=role_context)},
                ],
                max_tokens=60,
            )
            content = response.choices[0].message.content.strip()
            return content or bullet
        except Exception:
            return bullet

    def optimize_all_bullets(self, session: BuilderSession) -> dict:
        resume_data = session.resume_data or {}
        role_context = resume_data.get("career_interests", "")
        optimized = 0

        for key in ["experience", "projects"]:
            items = resume_data.get(key) or []
            new_items = []
            for item in items:
                improved = self.optimize_bullet(str(item), role_context)
                if improved != str(item):
                    optimized += 1
                new_items.append(improved)
            resume_data[key] = new_items

        session.resume_data = resume_data
        if self.db:
            self.db.add(session)
            self.db.commit()
        return {"optimized_count": optimized, "message": "Bullets optimized successfully"}

    def calculate_ats_score(self, resume_data: dict) -> dict:
        structure_score = 0
        keyword_score = 0
        completeness_score = 0
        feedback = []

        has_name = bool(resume_data.get("name"))
        has_email = bool(resume_data.get("email"))
        has_phone = bool(resume_data.get("phone"))
        has_education = bool(resume_data.get("education"))
        has_skills = bool(resume_data.get("skills"))
        has_experience = bool(resume_data.get("experience"))
        has_projects = bool(resume_data.get("projects"))

        if has_name and has_email and has_phone:
            structure_score += 10
        if has_education:
            structure_score += 10
        if has_skills:
            structure_score += 8
        if has_experience or has_projects:
            structure_score += 7

        skills = resume_data.get("skills") or []
        skill_count = len(skills)
        if skill_count >= 10:
            keyword_score = 40
        elif skill_count >= 7:
            keyword_score = 30
        elif skill_count >= 4:
            keyword_score = 20
        elif skill_count >= 1:
            keyword_score = 10
        else:
            keyword_score = 0

        if resume_data.get("linkedin") or resume_data.get("portfolio"):
            completeness_score += 5
        if resume_data.get("career_interests"):
            completeness_score += 5
        if resume_data.get("certifications"):
            completeness_score += 5
        if resume_data.get("achievements"):
            completeness_score += 5
        if resume_data.get("projects"):
            completeness_score += 5

        total_score = min(structure_score + keyword_score + completeness_score, 100)

        if not has_skills:
            feedback.append("Add a skills section with at least 7 relevant technologies.")
        if not has_education:
            feedback.append("Include your education details for better ATS completeness.")
        if not (has_experience or has_projects):
            feedback.append("Add at least one project or experience entry to strengthen your profile.")
        if skill_count and skill_count < 7:
            feedback.append("List more technical skills to improve keyword matching.")
        if not resume_data.get("career_interests"):
            feedback.append("Specify target roles to help align your resume with job searches.")

        if len(feedback) < 2:
            feedback.append("Quantify your impact in experience bullets where possible.")
        if len(feedback) > 3:
            feedback = feedback[:3]

        return {
            "total_score": int(total_score),
            "structure_score": int(structure_score),
            "keyword_score": int(keyword_score),
            "completeness_score": int(completeness_score),
            "feedback": feedback,
        }
