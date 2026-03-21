import json
from typing import Any

from groq import Groq

from app.config import settings


ROLE_CATEGORIES = {
    "frontend": ["frontend", "react", "vue", "angular", "css", "html", "ui", "javascript"],
    "backend": ["backend", "fastapi", "django", "flask", "api", "node", "java", "spring"],
    "fullstack": ["fullstack", "full stack", "full-stack", "mern", "mean"],
    "data": ["data scientist", "data analyst", "machine learning", "ml", "pandas", "numpy"],
    "devops": ["devops", "cloud", "aws", "docker", "kubernetes", "ci/cd", "infrastructure"],
    "mobile": ["mobile", "ios", "android", "react native", "flutter", "swift", "kotlin"],
    "general": [],
}

QUESTION_GEN_PROMPT = """
Generate exactly {count} {category} interview questions for this role.

Job title: {title}
Required skills: {required_skills}
User's relevant projects: {user_projects}

Question type: {question_type}
Difficulty level: {difficulty}

Difficulty guidelines:
- easy: Basic conceptual questions. Suitable for beginners. Simple and straightforward.
- medium: Requires understanding and some experience. Moderate complexity.
- hard: Advanced scenarios, trade-offs, architecture decisions. Challenging.

Question type guidelines:
- technical: Test specific knowledge of the required skills.
- behavioral: Use STAR format triggers. Ask about past experiences.
- situational: Give a hypothetical scenario relevant to this role.
- project: Ask about the user's specific projects listed above.

Return ONLY a JSON array:
[{{"question_text": "...", "category": "{question_type}", "difficulty": "{difficulty}", "skill_tested": "skill name or null"}}]
"""


class QuestionGenerator:
    def __init__(self):
        api_key = getattr(settings, "GROQ_API_KEY", None)
        self.client = Groq(api_key=api_key) if api_key else None

    def generate_question_set(
        self,
        internship,
        required_skills: list[str],
        user_skills: list[str],
        user_projects: list[str],
        experience_level: str,
    ) -> list[dict]:
        role_category = self.detect_role_category(internship.title, required_skills)

        if not self.client:
            return self._get_fallback_questions(role_category)

        questions = []
        # Difficulty progression: Easy -> Medium -> Hard
        # Technical (easy warm-up)
        questions.extend(self._generate_batch("technical", 3, internship, required_skills, user_projects, role_category, difficulty="easy"))
        # Project/Behavioral (medium)
        questions.extend(self._generate_batch("project", 2, internship, required_skills, user_projects, role_category, difficulty="medium"))
        questions.extend(self._generate_batch("behavioral", 3, internship, required_skills, user_projects, role_category, difficulty="medium"))
        # Situational (hard challenge)
        questions.extend(self._generate_batch("situational", 2, internship, required_skills, user_projects, role_category, difficulty="hard"))

        if len(questions) < 10:
            fallback = self._get_fallback_questions(role_category)
            questions.extend([q for q in fallback if q not in questions])

        questions = questions[:10]
        for idx, q in enumerate(questions, start=1):
            q["order_index"] = idx
        return questions

    def detect_role_category(self, title: str, required_skills: list[str]) -> str:
        text = f"{title} {' '.join(required_skills)}".lower()
        best = "general"
        best_hits = 0
        for category, keywords in ROLE_CATEGORIES.items():
            hits = sum(1 for kw in keywords if kw in text)
            if hits > best_hits:
                best_hits = hits
                best = category
        return best

    def _generate_batch(
        self,
        question_type: str,
        count: int,
        internship,
        required_skills: list[str],
        user_projects: list[str],
        role_category: str,
        difficulty: str = "medium",
    ) -> list[dict]:
        if not self.client:
            return []
        prompt = QUESTION_GEN_PROMPT.format(
            count=count,
            category=role_category,
            title=internship.title,
            required_skills=", ".join(required_skills or []),
            user_projects=", ".join(user_projects) if user_projects else "None",
            question_type=question_type,
            difficulty=difficulty,
        )
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an interview question generator."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=800,
            )
            content = response.choices[0].message.content.strip()
            # Strip markdown fences if present
            if '```' in content:
                content = content.split('```')[1]
                if content.startswith('json'):
                    content = content[4:]
            # Find JSON array in content
            start = content.find('[')
            end = content.rfind(']') + 1
            if start >= 0 and end > start:
                content = content[start:end]
            data = json.loads(content)
            if not isinstance(data, list):
                return []
            return [self._normalize_question(item, question_type, difficulty) for item in data][:count]
        except Exception:
            return []
    def _normalize_question(self, item: Any, question_type: str, difficulty: str = "medium") -> dict:
        if not isinstance(item, dict):
            return {
                "question_text": str(item),
                "category": question_type,
                "difficulty": difficulty,
                "skill_tested": None,
            }
        return {
            "question_text": item.get("question_text") or "Describe a relevant experience for this role.",
            "category": item.get("category") or question_type,
            "difficulty": difficulty,
            "skill_tested": item.get("skill_tested"),
        }
    def _get_fallback_questions(self, role_category: str) -> list[dict]:
        base = [
            {"question_text": "Walk me through a recent project and your role in it.", "category": "project", "difficulty": "medium", "skill_tested": None},
            {"question_text": "Tell me about a time you had to debug a tough issue.", "category": "behavioral", "difficulty": "medium", "skill_tested": None},
            {"question_text": "How do you prioritize tasks when deadlines are tight?", "category": "behavioral", "difficulty": "medium", "skill_tested": None},
            {"question_text": "Explain a technical decision you made and the trade-offs.", "category": "technical", "difficulty": "medium", "skill_tested": None},
            {"question_text": "Describe a situation where requirements changed mid-project.", "category": "situational", "difficulty": "medium", "skill_tested": None},
        ]

        role_specific = {
            "frontend": [
                {"question_text": "How do you optimize a web app for performance?", "category": "technical", "difficulty": "medium", "skill_tested": "performance"},
                {"question_text": "How do you manage state in a complex UI?", "category": "technical", "difficulty": "medium", "skill_tested": "state management"},
            ],
            "backend": [
                {"question_text": "How would you design a scalable REST API?", "category": "technical", "difficulty": "medium", "skill_tested": "API design"},
                {"question_text": "Explain how you would model data for a relational database.", "category": "technical", "difficulty": "medium", "skill_tested": "SQL"},
            ],
            "fullstack": [
                {"question_text": "Describe how you would deploy a full stack app to production.", "category": "technical", "difficulty": "medium", "skill_tested": "deployment"},
                {"question_text": "How do you ensure front-end and back-end integration is reliable?", "category": "technical", "difficulty": "medium", "skill_tested": "integration"},
            ],
            "data": [
                {"question_text": "How would you validate a machine learning model?", "category": "technical", "difficulty": "medium", "skill_tested": "model evaluation"},
                {"question_text": "Explain a time you cleaned messy data for analysis.", "category": "project", "difficulty": "medium", "skill_tested": "data cleaning"},
            ],
            "devops": [
                {"question_text": "How do you set up CI/CD for a service?", "category": "technical", "difficulty": "medium", "skill_tested": "CI/CD"},
                {"question_text": "Describe how you would monitor a production system.", "category": "technical", "difficulty": "medium", "skill_tested": "monitoring"},
            ],
            "mobile": [
                {"question_text": "How do you optimize performance in a mobile app?", "category": "technical", "difficulty": "medium", "skill_tested": "mobile performance"},
                {"question_text": "Describe a mobile app feature you shipped end-to-end.", "category": "project", "difficulty": "medium", "skill_tested": None},
            ],
            "general": [
                {"question_text": "What is your approach to learning new technologies?", "category": "behavioral", "difficulty": "medium", "skill_tested": None},
                {"question_text": "Describe how you would handle an ambiguous requirement.", "category": "situational", "difficulty": "medium", "skill_tested": None},
            ],
        }

        extra = role_specific.get(role_category, role_specific["general"])
        questions = base + extra
        while len(questions) < 10:
            questions.append({
                "question_text": "Tell me about a challenging task you completed recently.",
                "category": "behavioral",
                "difficulty": "medium",
                "skill_tested": None,
            })
        questions = questions[:10]
        for idx, q in enumerate(questions, start=1):
            q["order_index"] = idx
        return questions













