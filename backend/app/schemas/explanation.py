"""
app/schemas/explanation.py

Phase 3 — Grounded Explanation System: the output contract.

The LLM is only ever allowed to talk ABOUT skills we already computed
deterministically. These models define the SHAPE; explanation_service defines
the GROUNDING (every referenced skill must be a member of the input sets).

Same principle as Phase 2 skill extraction:
    THE LLM SUGGESTS. OUR DATA DECIDES TRUTH.
"""
from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field, field_validator


class SkillReason(BaseModel):
    """Why one MATCHED skill helps in this specific role."""

    skill: str
    explanation: str

    @field_validator("skill")
    @classmethod
    def _norm_skill(cls, v: str) -> str:
        return (v or "").strip().lower()

    @field_validator("explanation")
    @classmethod
    def _norm_explanation(cls, v: str) -> str:
        return (v or "").strip()


class SkillGapAdvice(BaseModel):
    """Actionable advice for one MISSING skill."""

    skill: str
    advice: str

    @field_validator("skill")
    @classmethod
    def _norm_skill(cls, v: str) -> str:
        return (v or "").strip().lower()

    @field_validator("advice")
    @classmethod
    def _norm_advice(cls, v: str) -> str:
        return (v or "").strip()


class ExplanationOutput(BaseModel):
    """
    The full explanation payload. This is what the LLM must return, what we
    validate, what we cache, and what the API serves.
    """

    matched_skill_explanations: List[SkillReason] = Field(default_factory=list)
    missing_skill_advice: List[SkillGapAdvice] = Field(default_factory=list)
    summary: str = ""

    @field_validator("summary")
    @classmethod
    def _norm_summary(cls, v: str) -> str:
        return (v or "").strip()


class ExplanationResponse(BaseModel):
    """
    API envelope. Carries the DETERMINISTIC score straight through — the
    explanation layer never computes, adjusts, or regenerates it.
    """

    internship_id: int
    title: Optional[str] = None
    company: Optional[str] = None

    # Deterministic, computed upstream by the scoring engine. Read-only here.
    match_score: float
    match_label: Optional[str] = None

    matched_skills: List[str] = Field(default_factory=list)
    missing_skills: List[str] = Field(default_factory=list)

    explanation: ExplanationOutput

    # Observability: did this come from cache / LLM / deterministic fallback?
    source: str = "llm"
