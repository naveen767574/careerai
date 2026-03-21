SCORE_WEIGHTS = {
    "headline": 20,
    "about": 20,
    "experience": 20,
    "skills": 15,
    "projects": 10,
    "education": 10,
    "photo": 5,
}


class ProfileScorer:
    def calculate(self, profile_input: dict, resume_data: dict) -> dict:
        breakdown = {}
        sections_missing = []

        headline = (profile_input.get("headline") or "").strip()
        target_roles = resume_data.get("career_interests", []) or []
        resume_skills = [s.lower() for s in resume_data.get("skills", [])]

        headline_score = 0
        if len(headline) > 10:
            headline_score += 10
        if any(role.lower() in headline.lower() for role in target_roles if role):
            headline_score += 5
        if any(skill in headline.lower() for skill in resume_skills):
            headline_score += 5
        breakdown["headline"] = min(headline_score, SCORE_WEIGHTS["headline"])

        about = (profile_input.get("about") or "").strip()
        about_score = 0
        if len(about) > 50:
            about_score += 10
        if len(about) > 200:
            about_score += 5
        if any(skill in about.lower() for skill in resume_skills):
            about_score += 5
        breakdown["about"] = min(about_score, SCORE_WEIGHTS["about"])

        experience = profile_input.get("experience") or []
        exp_count = len([e for e in experience if str(e).strip()])
        if exp_count >= 2:
            breakdown["experience"] = 20
        elif exp_count == 1:
            breakdown["experience"] = 10
        else:
            breakdown["experience"] = 0

        skills = profile_input.get("skills") or []
        skill_count = len([s for s in skills if str(s).strip()])
        if skill_count >= 10:
            breakdown["skills"] = 15
        elif skill_count >= 5:
            breakdown["skills"] = 10
        elif skill_count >= 1:
            breakdown["skills"] = 5
        else:
            breakdown["skills"] = 0

        projects = profile_input.get("projects") or []
        breakdown["projects"] = 10 if any(str(p).strip() for p in projects) else 0

        education = (profile_input.get("education") or "").strip()
        breakdown["education"] = 10 if len(education) > 5 else 0

        has_photo = profile_input.get("has_photo") is True
        breakdown["photo"] = 5 if has_photo else 0

        for section, score in breakdown.items():
            if score == 0:
                sections_missing.append(section)

        total_score = sum(breakdown.values())

        return {
            "score_breakdown": breakdown,
            "profile_score": int(total_score),
            "sections_missing": sections_missing,
        }
