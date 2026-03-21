import re

TECH_SKILLS = [
    "Python", "Java", "JavaScript", "TypeScript", "React", "Node.js",
    "FastAPI", "Django", "Flask", "PostgreSQL", "MySQL", "MongoDB",
    "Docker", "Kubernetes", "AWS", "Git", "REST", "API", "SQL",
    "TensorFlow", "PyTorch", "scikit-learn", "pandas", "NumPy",
    "HTML", "CSS", "Vue", "Angular", "Spring", "Redis", "GraphQL",
    "Linux", "Bash", "C++", "Go", "Rust", "Swift", "Kotlin",
    "Machine Learning", "Deep Learning", "NLP", "Data Science",
    "CI/CD", "Agile", "Scrum", "Jira", "Figma", "Excel",
]


class DescriptionExtractor:
    def __init__(self) -> None:
        self._skill_map = {s.lower(): s for s in TECH_SKILLS}

    def extract_skills(self, description: str) -> list[str]:
        desc = description.lower()
        matches = []
        for key, value in self._skill_map.items():
            if re.search(r"\b" + re.escape(key) + r"\b", desc):
                matches.append(value)
        return sorted(set(matches))
