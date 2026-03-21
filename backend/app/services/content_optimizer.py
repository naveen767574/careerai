import json

from groq import Groq

from app.config import settings


HEADLINE_PROMPT = """
Generate 3 LinkedIn headline variants for this person. Each variant must be under 220 characters.

Current headline: {current_headline}
Target roles: {target_roles}
Top skills: {top_skills}
University/Company (if any): {institution}
Extra feedback: {feedback}

Generate exactly 3 variants:
1. Keyword-Rich: Pack in role title + 3 top skills + seeking signal
2. Achievement-Led: Lead with what they build/do, then role + university
3. Role-Focused: Clear role aspiration + differentiator + availability

Respond ONLY as JSON:
{{
  "keyword_rich": "...",
  "achievement_led": "...",
  "role_focused": "..."
}}
"""

ABOUT_PROMPT = """
Write a compelling LinkedIn About section (150-200 words) for this person.

Their background:
- Skills: {skills}
- Experience: {experience_summary}
- Projects: {projects_summary}
- Target roles: {target_roles}
- Current about (if any): {current_about}
- Feedback: {feedback}

Instructions:
- Open with a strong hook (not "I am a...")
- Mention 2-3 specific skills or technologies they use
- Reference one notable project or achievement
- Close with what they're looking for (internship/role)
- Professional but personable tone
- No emojis, no bullet points

Respond with ONLY the about section text.
"""

BULLET_IMPROVE_PROMPT = """
Improve this LinkedIn experience bullet point to be more impactful and specific.

Original: {bullet}
Role context: {role_context}
Feedback: {feedback}

Requirements:
- Start with a strong action verb
- Include measurable impact where possible (use [X%] as placeholder if unknown)
- Keep it under 20 words
- Be specific, not generic

Respond with ONLY the improved bullet point.
"""


class ContentOptimizer:
    def __init__(self):
        api_key = getattr(settings, "GROQ_API_KEY", None)
        self.client = Groq(api_key=api_key) if api_key else None

    def rewrite_headline(self, current: str, resume_data: dict, target_roles: list[str], feedback: str = "") -> dict:
        top_skills = resume_data.get("skills", [])[:5]
        institution = ""
        education = resume_data.get("education") or []
        if education:
            institution = str(education[0])

        if not self.client:
            return self._fallback_headlines(target_roles)

        prompt = HEADLINE_PROMPT.format(
            current_headline=current or "",
            target_roles=", ".join(target_roles) if target_roles else "",
            top_skills=", ".join(top_skills),
            institution=institution,
            feedback=feedback or "none",
        )
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You write LinkedIn headlines."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=300,
            )
            content = response.choices[0].message.content
            data = json.loads(content)
            if isinstance(data, dict):
                return {
                    "keyword_rich": data.get("keyword_rich", ""),
                    "achievement_led": data.get("achievement_led", ""),
                    "role_focused": data.get("role_focused", ""),
                }
        except Exception:
            pass
        return self._fallback_headlines(target_roles)

    def write_about_section(self, resume_data: dict, target_roles: list[str], current_about: str = "", feedback: str = "") -> str:
        if not self.client:
            return ""

        experience_summary = ""
        experiences = resume_data.get("experience", [])
        if experiences:
            experience_summary = "; ".join([str(e) for e in experiences[:2]])

        projects_summary = ""
        projects = resume_data.get("projects", [])
        if projects:
            projects_summary = ", ".join([str(p) for p in projects[:2]])

        prompt = ABOUT_PROMPT.format(
            skills=", ".join(resume_data.get("skills", [])),
            experience_summary=experience_summary,
            projects_summary=projects_summary,
            target_roles=", ".join(target_roles) if target_roles else "",
            current_about=current_about or "",
            feedback=feedback or "none",
        )
        try:
            response = self.client.chat.completions.create(
                model="llama-3.1-8b-instant",
                messages=[
                    {"role": "system", "content": "You write LinkedIn About sections."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=400,
            )
            return response.choices[0].message.content.strip()
        except Exception:
            return ""

    def enhance_experience_bullets(self, bullets: list[str], role_context: str, feedback: str = "") -> dict:
        results = {}
        for idx, bullet in enumerate(bullets[:6]):
            improved = bullet
            if self.client:
                try:
                    response = self.client.chat.completions.create(
                        model="llama-3.1-8b-instant",
                        messages=[
                            {"role": "system", "content": "You optimize LinkedIn bullets."},
                            {"role": "user", "content": BULLET_IMPROVE_PROMPT.format(bullet=bullet, role_context=role_context, feedback=feedback or "none")},
                        ],
                        max_tokens=60,
                    )
                    improved = response.choices[0].message.content.strip() or bullet
                except Exception:
                    improved = bullet
            results[str(idx)] = {"original": bullet, "improved": improved}
        return results

    def suggest_skills_optimization(
        self,
        linkedin_skills: list[str],
        resume_skills: list[str],
        skill_trends: list[dict],
    ) -> dict:
        linkedin_lower = {s.lower() for s in linkedin_skills if s}
        add = [s for s in resume_skills if s and s.lower() not in linkedin_lower][:10]

        generic = {"teamwork", "communication", "microsoft office", "problem solving", "leadership"}
        remove = [s for s in linkedin_skills if s and s.lower() in generic]

        trending = []
        for trend in skill_trends or []:
            if trend.get("trend") == "rising":
                name = str(trend.get("skill_name", "")).strip()
                if name and name.lower() in linkedin_lower and name not in trending:
                    trending.append(name)

        reorder = trending + [s for s in linkedin_skills if s not in trending]

        return {
            "add": add,
            "remove": remove,
            "reorder": reorder,
        }

    def _fallback_headlines(self, target_roles: list[str]) -> dict:
        role = target_roles[0] if target_roles else "Professional"
        return {
            "keyword_rich": f"{role} | Open to opportunities",
            "achievement_led": f"Building impactful projects | Aspiring {role}",
            "role_focused": f"{role} candidate focused on growth",
        }
