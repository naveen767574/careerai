import os

from fastapi import HTTPException, status
from jinja2 import Environment, FileSystemLoader


TEMPLATES_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "templates"))

TEMPLATE_METADATA = {
    "minimal_ats": {
        "name": "Minimal ATS",
        "description": "Clean, ATS-optimised. No columns or tables. Best for traditional companies.",
        "best_for": ["Backend Developer", "Data Analyst", "Software Engineer"],
        "preview_color": "#2D3748",
    },
    "developer_modern": {
        "name": "Developer Modern",
        "description": "Two-column layout with skill tags. Great for tech roles.",
        "best_for": ["Frontend Developer", "Full Stack Developer", "DevOps"],
        "preview_color": "#3182CE",
    },
    "corporate_classic": {
        "name": "Corporate Classic",
        "description": "Traditional format with clean typography. Best for business roles.",
        "best_for": ["Product Manager", "Business Analyst", "Consultant"],
        "preview_color": "#2F855A",
    },
    "student_simple": {
        "name": "Student Simple",
        "description": "Clean and minimal. Perfect for first resume with limited experience.",
        "best_for": ["Any entry-level role", "Internship"],
        "preview_color": "#6B46C1",
    },
    "technical_professional": {
        "name": "Technical Professional",
        "description": "Skills-first layout. Ideal for ML, Data Science, and Systems roles.",
        "best_for": ["ML Engineer", "Data Scientist", "Systems Engineer"],
        "preview_color": "#C05621",
    },
}


class TemplateEngine:
    def __init__(self):
        self.env = Environment(loader=FileSystemLoader(TEMPLATES_DIR))

    def render(self, template_name: str, resume_data: dict) -> str:
        if template_name not in TEMPLATE_METADATA:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid template")
        template = self.env.get_template(f"{template_name}.html")
        return template.render(resume_data=resume_data)

    def recommend(self, resume_data: dict) -> list[dict]:
        interests_raw = resume_data.get("career_interests", "") or ""
        interests = [i.strip().lower() for i in interests_raw.replace("/", ",").split(",") if i.strip()]
        skills = [s.strip().lower() for s in resume_data.get("skills", []) if isinstance(s, str)]

        scored = []
        for template_id, meta in TEMPLATE_METADATA.items():
            score = 0
            best_for_lower = [b.lower() for b in meta.get("best_for", [])]
            for interest in interests:
                if any(interest in b for b in best_for_lower):
                    score += 2
            for skill in skills:
                if any(skill in b for b in best_for_lower):
                    score += 1
            scored.append((template_id, meta, score))

        scored.sort(key=lambda x: x[2], reverse=True)
        top_ids = {t[0] for t in scored[:2]}
        return [
            {
                "template_id": template_id,
                **meta,
                "recommended": template_id in top_ids,
            }
            for template_id, meta, _ in scored
        ]

    def get_all_templates(self) -> list[dict]:
        return [
            {
                "template_id": template_id,
                **meta,
                "recommended": False,
            }
            for template_id, meta in TEMPLATE_METADATA.items()
        ]
