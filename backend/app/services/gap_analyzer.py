class GapAnalyzer:
    def analyze(self, profile_input: dict, resume_data: dict, skill_trends: list[dict] | None = None) -> dict:
        linkedin_skills = profile_input.get("skills") or []
        resume_skills = resume_data.get("skills") or []
        missing_skills = self.find_missing_skills(linkedin_skills, resume_skills)

        skills_to_highlight = []
        if skill_trends:
            for trend in skill_trends:
                skill_name = str(trend.get("skill_name", "")).strip()
                if not skill_name:
                    continue
                if skill_name.lower() in [s.lower() for s in resume_skills] and skill_name.lower() not in [s.lower() for s in linkedin_skills]:
                    skills_to_highlight.append(skill_name)

        headline_strength = self.assess_headline_strength(
            profile_input.get("headline", ""),
            resume_data.get("career_interests", []) or [],
        )

        sections_missing = []
        if len((profile_input.get("headline") or "").strip()) == 0:
            sections_missing.append("headline")
        if len((profile_input.get("about") or "").strip()) < 50:
            sections_missing.append("about")
        if not (profile_input.get("experience") or []):
            sections_missing.append("experience")
        if not (profile_input.get("skills") or []):
            sections_missing.append("skills")
        if not (profile_input.get("projects") or []):
            sections_missing.append("projects")
        if len((profile_input.get("education") or "").strip()) < 5:
            sections_missing.append("education")
        if profile_input.get("has_photo") is not True:
            sections_missing.append("photo")

        return {
            "missing_skills": missing_skills,
            "skills_to_highlight": skills_to_highlight,
            "headline_strength": headline_strength,
            "sections_missing": sections_missing,
            "resume_skills_count": len(resume_skills),
            "linkedin_skills_count": len(linkedin_skills),
        }

    def find_missing_skills(self, linkedin_skills: list[str], resume_skills: list[str]) -> list[str]:
        linkedin_lower = {s.lower() for s in linkedin_skills if s}
        missing = [s for s in resume_skills if s and s.lower() not in linkedin_lower]
        return missing

    def assess_headline_strength(self, headline: str, target_roles: list[str]) -> str:
        if not headline or len(headline.strip()) < 20:
            return "weak"
        headline_lower = headline.lower()
        roles_lower = [r.lower() for r in target_roles if r]
        if not any(role in headline_lower for role in roles_lower):
            return "generic"
        if any(skill in headline_lower for skill in ["python", "react", "sql", "aws", "docker", "fastapi", "javascript"]):
            return "strong"
        return "generic"
