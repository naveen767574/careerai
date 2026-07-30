"""
Text normalization for resume extraction + LLM output cleanup.

Two problems this solves:
  1. PDF extraction merges words / drops spaces
     ("ImplementedstrictDomain-DrivenDesign") and splits words across
     hyphenated line breaks ("candi-\ndate").
  2. LLMs sometimes emit fabricated metric placeholders ("[45%]", "[N users]").
"""

import re

# Tech terms whose internal capitalization must NOT be camel-split
# (so "FastAPI" doesn't become "Fast API"). Compared on an alnum-lowercased key.
_PROTECTED = {
    "fastapi", "javascript", "typescript", "postgresql", "mysql", "nosql",
    "mongodb", "github", "gitlab", "graphql", "nodejs", "devops", "oauth",
    "ios", "macos", "openai", "linkedin", "pytorch", "tensorflow", "numpy",
    "scipy", "opencv", "websocket", "restapi", "dynamodb", "bigquery",
    "powerbi", "nextjs", "reactjs", "vuejs", "langchain", "matplotlib",
    "keras", "huggingface", "chatgpt", "llm", "llms", "genai", "mlops",
}


def _fix_token(tok: str) -> str:
    """Split camelCase / merged Capitalized words in a single token."""
    key = re.sub(r"[^a-z0-9]", "", tok.lower())
    if key in _PROTECTED:
        return tok
    # "DrivenDesign" -> "Driven Design"; "strictDomain" -> "strict Domain"
    return re.sub(r"([a-z])([A-Z])", r"\1 \2", tok)


def normalize_resume_text(text: str) -> str:
    """
    Clean extracted resume text so bullets are readable BEFORE the LLM sees them.

    - Joins hyphenated line breaks: "candi-\ndate" -> "candidate".
    - Splits camelCase / merged Capitalized words, preserving known tech terms.
    - Collapses runs of whitespace while preserving line structure.

    NOTE: fully-merged all-lowercase runs with no case boundary
    ("Engineeredamulti") can't be split by regex alone — the word-based PDF
    extraction upstream is what prevents those. This is the second line of defense.
    """
    if not text:
        return text or ""

    # 1) Join words split across a hyphenated line break (do before line split).
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)

    # 2) Per line, per token: collapse spaces + split merged Capitalized words.
    out_lines = []
    for line in text.split("\n"):
        tokens = line.split()  # split() collapses runs of whitespace
        out_lines.append(" ".join(_fix_token(t) for t in tokens))
    return "\n".join(out_lines)


# Bracketed placeholders an LLM might emit: [45%], [X%], [N users], [100k], [TBD]
_PLACEHOLDER_RE = re.compile(r"\[[^\]]*\]")


def strip_fake_metrics(text: str) -> str:
    """
    Remove fabricated metric placeholders and tidy spacing.
    Defense-in-depth: the prompt forbids them, this guarantees none leak through.
    """
    if not text:
        return text or ""
    text = _PLACEHOLDER_RE.sub("", text)          # drop [..] placeholders
    text = re.sub(r"\s+", " ", text).strip()       # collapse whitespace
    text = re.sub(r"\s+([,.;:])", r"\1", text)      # no space before punctuation
    text = re.sub(r"\(\s*\)", "", text).strip()     # drop empty parens left behind
    return text
