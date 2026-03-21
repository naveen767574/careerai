import json

from groq import Groq

from app.config import settings
from app.models.interview_answer import InterviewAnswer
from app.models.interview_question import InterviewQuestion
from app.models.interview_session import InterviewSession


RESOURCE_RECOMMENDATION_PROMPT = """
Based on this interview performance, recommend 3 specific learning resources.

Role: {role_title}
Weak areas: {weak_areas}
Score: {overall_score}/100

Return ONLY a JSON array of 3 strings, each being a specific resource:
["Resource name and URL or platform", ...]

Examples of good resources:
- "CS50's Introduction to Computer Science - cs50.harvard.edu"
- "System Design Primer - github.com/donnemartin/system-design-primer"
- "LeetCode Top 150 Interview Questions - leetcode.com"
"""


class FeedbackReporter:
    def __init__(self):
        api_key = getattr(settings, "GROQ_API_KEY", None)
        self.client = Groq(api_key=api_key) if api_key else None

    def compile(
        self,
        session: InterviewSession,
        questions: list[InterviewQuestion],
        answers: list[InterviewAnswer],
        internship,
    ) -> dict:
        scores = [a.score or 0.0 for a in answers]
        overall_score = (sum(scores) / len(scores)) * 10 if scores else 0.0

        tech_scores = [a.score or 0.0 for a, q in self._pair_answers(answers, questions) if q.category in {"technical", "project"}]
        beh_scores = [a.score or 0.0 for a, q in self._pair_answers(answers, questions) if q.category in {"behavioral", "situational"}]

        technical_score = (sum(tech_scores) / len(tech_scores)) * 10 if tech_scores else 0.0
        behavioral_score = (sum(beh_scores) / len(beh_scores)) * 10 if beh_scores else 0.0

        readiness_level = self._get_readiness_level(overall_score)

        strengths = self._collect_list(answers, "strengths")
        weaknesses = self._collect_list(answers, "weaknesses")

        top_strengths = strengths[:3] if strengths else []
        top_improvements = weaknesses[:3] if weaknesses else []

        recommended_resources = self._get_resources(internship.title if internship else "Internship", top_improvements, overall_score)

        return {
            "session_id": session.session_id,
            "user_id": session.user_id,
            "internship_id": session.internship_id,
            "overall_score": round(overall_score, 2),
            "technical_score": round(technical_score, 2),
            "behavioral_score": round(behavioral_score, 2),
            "readiness_level": readiness_level,
            "top_strengths": top_strengths,
            "top_improvements": top_improvements,
            "recommended_resources": recommended_resources,
            "readiness_message": self._get_readiness_message(readiness_level),
        }

    def _get_resources(self, role_title: str, weak_areas: list[str], overall_score: float) -> list[str]:
        if not self.client:
            return self._fallback_resources()
        prompt = RESOURCE_RECOMMENDATION_PROMPT.format(
            role_title=role_title,
            weak_areas=", ".join(weak_areas) if weak_areas else "General interview prep",
            overall_score=int(overall_score),
        )
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You recommend learning resources."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            if isinstance(data, list) and len(data) == 3:
                return [str(x) for x in data]
        except Exception:
            pass
        return self._fallback_resources()

    def _get_readiness_level(self, score: float) -> str:
        if score >= 75:
            return "Ready"
        if score >= 55:
            return "Almost Ready"
        return "Needs Prep"

    def _get_readiness_message(self, level: str) -> str:
        if level == "Ready":
            return "You're well-prepared for this role!"
        if level == "Almost Ready":
            return "A few improvements will get you there."
        return "Focus on the key areas below before applying."

    def _collect_list(self, answers: list[InterviewAnswer], field: str) -> list[str]:
        items: list[str] = []
        for answer in answers:
            values = getattr(answer, field, None) or []
            for v in values:
                v_str = str(v).strip()
                if v_str and v_str not in items:
                    items.append(v_str)
        return items

    def _pair_answers(self, answers: list[InterviewAnswer], questions: list[InterviewQuestion]) -> list[tuple[InterviewAnswer, InterviewQuestion]]:
        q_map = {q.id: q for q in questions}
        pairs = []
        for a in answers:
            q = q_map.get(a.question_id)
            if q:
                pairs.append((a, q))
        return pairs

    def _fallback_resources(self) -> list[str]:
        return [
            "LeetCode Top Interview Questions - leetcode.com",
            "freeCodeCamp Interview Prep - freecodecamp.org",
            "Coursera Interview Skills - coursera.org",
        ]


