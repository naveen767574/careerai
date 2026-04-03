import logging
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.internship import Internship
from app.models.internship_skill import InternshipSkill
from app.models.recommendation import Recommendation
from app.models.resume import Resume
from app.models.skill import Skill

logger = logging.getLogger(__name__)


@dataclass
class InternshipRecommendation:
    internship_id: int
    title: str
    company: str
    location: str
    application_url: str
    similarity_score: float
    match_percentage: float
    matched_skills: list[str]
    missing_skills: list[str]
    match_label: str


class RecommendationEngine:
    VECTORIZER_CONFIG = {
        "max_features": 500,
        "ngram_range": (1, 2),
        "stop_words": "english",
        "lowercase": True,
    }
    SIMILARITY_THRESHOLD = 0.3
    TOP_N = 20

    def __init__(self, db: Session):
        self.db = db
        self.vectorizer = TfidfVectorizer(**self.VECTORIZER_CONFIG)

    def get_recommendations(self, user_id: int, limit: int = 20) -> list[InternshipRecommendation]:
        try:
            resume = self.db.execute(select(Resume).where(Resume.user_id == user_id)).scalar_one_or_none()
            if not resume:
                return []

            user_skill_text = self._get_user_skill_text(user_id)
            if not user_skill_text:
                return []

            internship_texts = self._get_internship_skill_texts()
            if not internship_texts:
                return []

            user_vector, internship_ids = self._vectorize(user_skill_text, internship_texts)
            if not internship_ids:
                return []

            internship_vectors = self.vectorizer.transform([internship_texts[i] for i in internship_ids])
            scores = self._calculate_similarity(user_vector, internship_vectors)

            results: list[InternshipRecommendation] = []
            user_skills = self._get_user_skills(user_id)

            for internship_id, score in zip(internship_ids, scores):
                if score < self.SIMILARITY_THRESHOLD:
                    continue
                internship = self.db.get(Internship, internship_id)
                if not internship:
                    continue
                required_skills = self._get_internship_skills(internship_id)
                matched, missing, match_pct = self._compute_skill_overlap(user_skills, required_skills)
                results.append(
                    InternshipRecommendation(
                        internship_id=internship.id,
                        title=internship.title,
                        company=internship.company,
                        location=internship.location,
                        application_url=internship.application_url,
                        similarity_score=float(score),
                        match_percentage=match_pct,
                        matched_skills=matched,
                        missing_skills=missing,
                        match_label=self._get_match_label(float(score)),
                    )
                )

            results.sort(key=lambda r: r.similarity_score, reverse=True)
            results = results[: min(limit, self.TOP_N)]
            self._persist_recommendations(user_id, results)
            return results
        except Exception as exc:
            logger.error("recommendation_error user_id=%s error=%s", user_id, type(exc).__name__)
            return []

    def _get_user_skill_text(self, user_id: int) -> str:
        skills = self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id)).scalars().all()
        return " ".join(s.lower() for s in skills if s) if skills else ""

    def _get_internship_skill_texts(self) -> dict[int, str]:
        rows = (
            self.db.query(Internship.id, InternshipSkill.skill_name)
            .join(InternshipSkill, InternshipSkill.internship_id == Internship.id)
            .filter(Internship.is_active == True)
            .all()
        )
        texts: dict[int, list[str]] = {}
        for internship_id, skill_name in rows:
            if not skill_name:
                continue
            texts.setdefault(internship_id, []).append(skill_name.lower())
        result = {k: " ".join(v) for k, v in texts.items() if v}

        # Fallback: if no skills tagged, use title + description
        if not result:
            internships = self.db.query(Internship).filter(Internship.is_active == True).all()
            for i in internships:
                text = f"{i.title or ''} {i.description or ''}".lower()
                if text.strip():
                    result[i.id] = text
        return result

    def _vectorize(self, user_text: str, internship_texts: dict[int, str]) -> tuple[np.ndarray, list[int]]:
        internship_ids = list(internship_texts.keys())
        if not internship_ids:
            return np.array([]), []
        corpus = [user_text] + [internship_texts[i] for i in internship_ids]
        tfidf_matrix = self.vectorizer.fit_transform(corpus)
        user_vector = tfidf_matrix[0]
        return user_vector, internship_ids

    def _calculate_similarity(self, user_vector: np.ndarray, internship_vectors: np.ndarray) -> np.ndarray:
        if internship_vectors.shape[0] == 0:
            return np.array([])
        return cosine_similarity(user_vector, internship_vectors).flatten()

    def _get_match_label(self, score: float) -> str:
        if score >= 0.7:
            return "Excellent"
        if score >= 0.5:
            return "Good"
        if score >= 0.3:
            return "Fair"
        return "Filtered"

    def _compute_skill_overlap(
        self,
        user_skills: list[str],
        required_skills: list[str],
    ) -> tuple[list[str], list[str], float]:
        user_set = {s.lower() for s in user_skills}
        required_set = {s.lower() for s in required_skills}
        matched = sorted([s for s in required_skills if s.lower() in user_set])
        missing = sorted([s for s in required_skills if s.lower() not in user_set])
        match_percentage = 0.0
        if required_set:
            match_percentage = (len(matched) / len(required_set)) * 100
        return matched, missing, round(match_percentage, 2)

    def _get_user_skills(self, user_id: int) -> list[str]:
        return self.db.execute(select(Skill.skill_name).where(Skill.user_id == user_id)).scalars().all()

    def _get_internship_skills(self, internship_id: int) -> list[str]:
        return (
            self.db.execute(select(InternshipSkill.skill_name).where(InternshipSkill.internship_id == internship_id))
            .scalars()
            .all()
        )

    def _persist_recommendations(self, user_id: int, recommendations: list[InternshipRecommendation]) -> None:
        existing = (
            self.db.execute(select(Recommendation).where(Recommendation.user_id == user_id)).scalars().all()
        )
        existing_map = {r.internship_id: r for r in existing}

        for rec in recommendations:
            record = existing_map.get(rec.internship_id)
            if record:
                record.similarity_score = rec.similarity_score
                record.match_percentage = rec.match_percentage
                self.db.add(record)
            else:
                self.db.add(
                    Recommendation(
                        user_id=user_id,
                        internship_id=rec.internship_id,
                        similarity_score=rec.similarity_score,
                        match_percentage=rec.match_percentage,
                    )
                )
        self.db.commit()

    def refresh_for_user(self, user_id: int) -> dict:
        from app.services.embedding_service import normalize_score
        import sqlalchemy

        # Get user's resume embedding
        resume = self.db.query(Resume).filter(Resume.user_id == user_id).first()
        if not resume:
            return {"recommendations": 0}

        # Check if resume has embedding
        resume_emb = self.db.execute(
            sqlalchemy.text("SELECT embedding FROM resumes WHERE id = :id"),
            {"id": resume.id}
        ).scalar()

        if resume_emb is None:
            # Fallback to old TF-IDF method
            return self._refresh_tfidf(user_id)

        # Use vector similarity to find top matches
        results = self.db.execute(sqlalchemy.text("""
            SELECT id,
                   1 - (embedding <=> (SELECT embedding FROM resumes WHERE user_id = :uid)) as raw_score
            FROM internships
            WHERE embedding IS NOT NULL
            AND is_active = true
            ORDER BY embedding <=> (SELECT embedding FROM resumes WHERE user_id = :uid)
            LIMIT 50
        """), {"uid": user_id}).fetchall()

        # Delete old recommendations
        self.db.query(Recommendation).filter(
            Recommendation.user_id == user_id
        ).delete()

        # Save new recommendations with real scores
        count = 0
        for row in results:
            display_score = normalize_score(float(row.raw_score))
            if display_score < 55:  # Skip very low matches
                continue
            rec = Recommendation(
                user_id=user_id,
                internship_id=row.id,
                match_percentage=display_score,
                similarity_score=float(row.raw_score),
            )
            self.db.add(rec)
            count += 1

        self.db.commit()
        return {"recommendations": count}

    def _refresh_tfidf(self, user_id: int) -> dict:
        self.db.execute(delete(Recommendation).where(Recommendation.user_id == user_id))
        self.db.commit()
        recs = self.get_recommendations(user_id, limit=self.TOP_N)
        return {"recommendations": len(recs)}


def explain_match(
    internship_title: str,
    internship_company: str,
    user_skills: str,
    matched_skills: list,
    missing_skills: list,
    user_experience: str = "",
    user_projects: str = "",
) -> dict:
    import json
    try:
        from groq import Groq
        from app.config import settings
        groq_client = Groq(api_key=settings.GROQ_API_KEY)
    except Exception as exc:
        logger.error("groq_client_error error=%s", type(exc).__name__)
        return {
            "match_reasons": ["Strong skill alignment with role requirements"],
            "missing_skills": list(missing_skills)[:3] if missing_skills else [],
            "next_actions": ["Review job description carefully", "Update resume with relevant projects"],
        }

    messages = [
        {
            "role": "system",
            "content": """You are a precise and practical career advisor.

You MUST follow ALL rules:

1. Only use:
   - user_skills
   - matched_skills
   - missing_skills
   - user_projects
   - user_experience

2. DO NOT invent or assume any skills or tools not provided.

3. Write like a human mentor, NOT a machine.

4. Avoid repetitive phrases like:
   - 'matches requirement'
   - 'aligns with role'

5. Instead:
   - Explain WHY a skill is useful in this role

Example:
BAD:
'Python matches the role'

GOOD:
'Your Python skills help in building backend logic for this role'

6. For missing_skills:
   - Expand generic terms into slightly more meaningful ones
   - BUT stay within given inputs

Example:
If input is 'api'
Output can be:
'API development using FastAPI or Flask'

7. Tip MUST be:
   - Specific
   - Actionable
   - Based ONLY on missing_skills

Example:
'Build a REST API using FastAPI and connect it to a PostgreSQL database'

8. Keep:
   - max 3 match_reasons
   - each under 15 words
   - concise but meaningful

Return JSON only:
{
  "match_reasons": ["..."],
  "missing_skills": ["..."],
  "tip": "..."
}"""
        },
        {
            "role": "user",
            "content": f"""
Internship: {internship_title} at {internship_company}
User skills: {user_skills}
User experience: {user_experience}
User projects: {user_projects}
Matched: {', '.join(matched_skills) if matched_skills else 'None'}
Missing: {', '.join(missing_skills) if missing_skills else 'None'}
"""
        }
    ]

    try:
        #logger.warning("FINAL PROMPT SENT: %s", messages)
        response = groq_client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=messages,
            temperature=0.7,
            max_tokens=400,
            response_format={"type": "json_object"}
        )

        content = response.choices[0].message.content.strip()
        logger.info("Raw LLM response: %s", content)

        # Strip markdown fences if present
        if '```' in content:
            content = content.split('```')[1]
            if content.startswith('json'):
                content = content[4:]
            content = content.strip()

        # Find JSON boundaries
        start = content.find('{')
        end = content.rfind('}') + 1
        if start != -1 and end > start:
            content = content[start:end]

        result = json.loads(content)

        return {
            "match_reasons": result.get("match_reasons", [])[:3],
            "missing_skills": result.get("missing_skills", [])[:3],
            "tip": result.get("tip", "Review the job description carefully.")
        }

    except Exception as e:
        logger.error("groq_explain_error error=%s", e)
        return {
            "match_reasons": ["Strong skill alignment with role requirements"],
            "missing_skills": list(missing_skills)[:3] if missing_skills else [],
            "tip": "Update your resume with relevant projects and skills."
        }
