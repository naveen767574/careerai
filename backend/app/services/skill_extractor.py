import re
from typing import Iterable

import spacy

nlp = spacy.load("en_core_web_sm")

SKILL_KEYWORDS = {
    "python",
    "java",
    "javascript",
    "typescript",
    "c++",
    "c#",
    "go",
    "rust",
    "sql",
    "postgresql",
    "mysql",
    "mongodb",
    "redis",
    "docker",
    "kubernetes",
    "aws",
    "gcp",
    "azure",
    "fastapi",
    "django",
    "flask",
    "react",
    "node",
    "nodejs",
    "html",
    "css",
    "git",
    "linux",
    "pandas",
    "numpy",
    "scikit-learn",
    "tensorflow",
    "pytorch",
    "nlp",
}


class SkillExtractor:
    @staticmethod
    def extract_skills(text: str) -> list[str]:
        doc = nlp(text)
        tokens = [t.text.lower() for t in doc if not t.is_stop and t.is_alpha]
        text_lower = text.lower()

        skills = set()
        for skill in SKILL_KEYWORDS:
            if re.search(r"\b" + re.escape(skill) + r"\b", text_lower):
                skills.add(skill)
        for token in tokens:
            if token in SKILL_KEYWORDS:
                skills.add(token)
        return sorted(skills)

    @staticmethod
    def normalize_skills(skills: Iterable[str]) -> list[str]:
        normalized = {s.strip().lower() for s in skills if s and s.strip()}
        return sorted(normalized)
