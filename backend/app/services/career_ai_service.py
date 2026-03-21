import logging
import json
from groq import Groq
from app.config import settings

logger = logging.getLogger(__name__)

client = Groq(api_key=settings.GROQ_API_KEY)


def generate_career_insights(
    user_skills: list[str],
    career_paths: list[dict],
) -> dict:
    """
    Use Groq AI to generate personalized career insights for each path.
    Returns a dict keyed by path_id with salary, growth, and explanation.
    """
    skills_text = ", ".join(user_skills[:20]) if user_skills else "general programming skills"
    paths_text = "\n".join([
        f"- {p['path_id']}: {p['title']} (match: {p['match_percentage']}%, has: {', '.join(p['user_has'])}, missing: {', '.join(p['user_missing'])})"
        for p in career_paths
    ])

    prompt = f"""You are a career advisor for Indian tech students. Given a student's skills and career paths, generate realistic insights.

Student skills: {skills_text}

Career paths being considered:
{paths_text}

For each career path, provide realistic Indian market data. Return ONLY a JSON object like this:
{{
  \"path_id_here\": {{
    \"salary_range\": \"₹6-18 LPA\",
    \"growth_rate\": \"+22%\",
    \"open_positions\": 15000,
    \"why_fits\": \"One sentence explaining why this fits the student's skills\",
    \"top_skill_to_learn\": \"Most important missing skill to focus on\"
  }}
}}

Be specific to Indian market. Salary in LPA. Growth rate as percentage. Open positions as realistic number.
Return ONLY the JSON, no explanation, no markdown."""

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.3,
        )
        content = response.choices[0].message.content.strip()
        # Clean any markdown if present
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        return json.loads(content)
    except Exception as e:
        logger.error(f"Career AI insights error: {e}")
        # Return fallback data
        return {
            p['path_id']: {
                "salary_range": "₹6-20 LPA",
                "growth_rate": "+18%",
                "open_positions": 12000,
                "why_fits": f"Your {', '.join(p['user_has'][:2])} skills align well with this path.",
                "top_skill_to_learn": p['user_missing'][0] if p['user_missing'] else "System Design"
            }
            for p in career_paths
        }

