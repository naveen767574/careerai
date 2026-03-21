import json

from groq import Groq

from app.config import settings
from app.models.interview_question import InterviewQuestion


TECHNICAL_EVAL_PROMPT = """
Evaluate this technical interview answer. Score it 0-10.

Question: {question}
Skill being tested: {skill_tested}
User's answer: {answer}

Evaluate on: correctness, depth of understanding, clarity, practical relevance.

Scoring guide:
9-10: Excellent - demonstrates deep understanding and practical knowledge
7-8:  Good - solid understanding with minor gaps
5-6:  Adequate - basic understanding but lacks depth
3-4:  Weak - significant gaps or misconceptions
0-2:  Poor - incorrect or irrelevant

Respond ONLY as JSON:
{{
  "score": 0.0,
  "verdict": "Good",
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1"],
  "model_answer": "A strong answer would include...",
  "improvement_tip": "One specific thing to focus on"
}}
"""

BEHAVIORAL_EVAL_PROMPT = """
Evaluate this behavioral/situational interview answer. Score it 0-10.

Question: {question}
User's answer: {answer}

Evaluate on: STAR structure (Situation, Task, Action, Result), specificity, impact clarity, relevance.

Scoring guide:
9-10: Excellent - clear STAR structure, specific, measurable impact
7-8:  Good - mostly structured, good specifics
5-6:  Adequate - some structure but vague on results
3-4:  Weak - missing STAR elements, generic response
0-2:  Poor - off-topic or no real example given

Respond ONLY as JSON:
{{
  "score": 0.0,
  "verdict": "Good",
  "strengths": ["strength 1"],
  "weaknesses": ["weakness 1"],
  "model_answer": "A strong answer would use STAR: ...",
  "improvement_tip": "One specific thing to improve"
}}
"""


class AnswerEvaluator:
    def __init__(self):
        api_key = getattr(settings, "GROQ_API_KEY", None)
        self.client = Groq(api_key=api_key) if api_key else None

    def evaluate(self, question: InterviewQuestion, answer_text: str) -> dict:
        if not self.client:
            return self._default_eval()

        prompt = TECHNICAL_EVAL_PROMPT if question.category in {"technical", "project"} else BEHAVIORAL_EVAL_PROMPT
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You are an interview answer evaluator."},
                    {
                        "role": "user",
                        "content": prompt.format(
                            question=question.question_text,
                            skill_tested=question.skill_tested or "N/A",
                            answer=answer_text,
                        ),
                    },
                ],
                max_tokens=400,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            return {
                "score": float(data.get("score", 5.0)),
                "verdict": data.get("verdict") or self._get_verdict(float(data.get("score", 5.0))),
                "strengths": data.get("strengths") or [],
                "weaknesses": data.get("weaknesses") or [],
                "model_answer": data.get("model_answer") or "",
                "improvement_tip": data.get("improvement_tip") or "",
            }
        except Exception:
            return self._default_eval()

    def _get_verdict(self, score: float) -> str:
        if score >= 9:
            return "Strong"
        if score >= 7:
            return "Good"
        if score >= 5:
            return "Adequate"
        if score >= 3:
            return "Needs Work"
        return "Poor"

    def _default_eval(self) -> dict:
        return {
            "score": 5.0,
            "verdict": "Good",
            "strengths": [],
            "weaknesses": [],
            "model_answer": "",
            "improvement_tip": "",
        }
