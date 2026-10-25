"""
core.py — Resume schema, helper utilities, parsing, and scoring logic.
Uses Groq (free) as the AI provider — same OpenAI-compatible interface.
"""

import json
import re
import os
from dotenv import load_dotenv
from openai import OpenAI
from jsonschema import validate, ValidationError

# ── Load .env file so GROQ_API_KEY is available ───────────────────────────
load_dotenv()

# ── Groq client (same OpenAI library, different base_url + key) ───────────
client = OpenAI(
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
)

# ── Resume JSON schema ────────────────────────────────────────────────────
RESUME_SCHEMA = {
    "type": "object",
    "properties": {
        "full_name":          {"type": "string"},
        "email":              {"type": ["string", "null"]},
        "years_experience":   {"type": "integer", "minimum": 0},
        "current_role":       {"type": "string"},
        "technical_skills":   {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1
        },
        "education_level":    {
            "type": "string",
            "enum": ["high_school", "bachelor", "master", "phd", "other"]
        },
        "previous_companies": {"type": "array", "items": {"type": "string"}},
        "languages":          {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "full_name", "years_experience", "current_role",
        "technical_skills", "education_level"
    ],
}

# ── Education rank for comparison ─────────────────────────────────────────
EDUCATION_RANK = {
    "high_school": 0,
    "bachelor":    1,
    "master":      2,
    "phd":         3,
    "other":       0,
}


def safe_parse_json(raw: str) -> dict | None:
    if not raw:
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip())
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def coerce_types(data: dict, schema: dict) -> dict:
    props = schema.get("properties", {})
    coerced = dict(data)
    for field, field_schema in props.items():
        if field not in coerced:
            continue
        val = coerced[field]
        expected_type = field_schema.get("type")
        if expected_type == "integer" and isinstance(val, str):
            try:
                coerced[field] = int(float(val))
            except (ValueError, TypeError):
                pass
        if expected_type == "array" and isinstance(val, str):
            coerced[field] = [s.strip() for s in val.split(",") if s.strip()]
        if "enum" in field_schema and isinstance(val, str):
            coerced[field] = val.lower().strip()
    return coerced


def parse_resume(resume_text: str) -> dict | None:
    try:
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            temperature=0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a resume parser. Extract information strictly from the "
                        "resume text provided. Return ONLY a valid JSON object — "
                        "no markdown, no explanation, no code fences. "
                        "If a field is missing, use null for strings and empty arrays for lists."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Parse this resume and return a JSON object with exactly these fields:\n"
                        "  full_name: string\n"
                        "  email: string or null\n"
                        "  years_experience: integer (total years of professional work)\n"
                        "  current_role: string (most recent job title)\n"
                        "  technical_skills: array of strings (tools, languages, frameworks)\n"
                        "  education_level: one of exactly: high_school / bachelor / master / phd / other\n"
                        "  previous_companies: array of company names\n"
                        "  languages: array of spoken/written languages\n\n"
                        f"Resume:\n{resume_text}"
                    ),
                },
            ],
        )
    except Exception as e:
        return {"_error": f"API call failed: {e}"}

    raw = response.choices[0].message.content
    parsed = safe_parse_json(raw)
    if parsed is None:
        return {"_error": "JSON parse failed — AI returned unexpected format"}

    coerced = coerce_types(parsed, RESUME_SCHEMA)
    try:
        validate(instance=coerced, schema=RESUME_SCHEMA)
        return coerced
    except ValidationError as e:
        return {"_error": f"Schema validation failed: {e.message}"}


def score_candidate(candidate: dict, requirements: dict) -> dict:
    skills_lower = [s.lower() for s in candidate.get("technical_skills", [])]

    exp       = candidate.get("years_experience", 0)
    exp_req   = requirements["min_experience"]
    exp_score = min(30, int((exp / max(exp_req, 1)) * 30))

    req_skills  = requirements["required_skills"]
    req_matches = sum(1 for s in req_skills if s.lower() in skills_lower)
    req_score   = int((req_matches / len(req_skills)) * 40) if req_skills else 0

    pref_skills  = requirements["preferred_skills"]
    pref_matches = sum(1 for s in pref_skills if s.lower() in skills_lower)
    pref_score   = int((pref_matches / len(pref_skills)) * 20) if pref_skills else 0

    edu_level = candidate.get("education_level", "other")
    min_edu   = requirements["min_education"]
    edu_score = 10 if EDUCATION_RANK.get(edu_level, 0) >= EDUCATION_RANK.get(min_edu, 0) else 0

    total = exp_score + req_score + pref_score + edu_score

    if total >= 80:
        recommendation = "STRONG HIRE"
    elif total >= 60:
        recommendation = "PROCEED TO INTERVIEW"
    elif total >= 40:
        recommendation = "MAYBE — NEEDS REVIEW"
    else:
        recommendation = "NOT SUITABLE"

    return {
        "experience_score":  exp_score,
        "required_skills":   req_score,
        "preferred_skills":  pref_score,
        "education":         edu_score,
        "total":             total,
        "recommendation":    recommendation,
        "matched_required":  [s for s in req_skills  if s.lower() in skills_lower],
        "matched_preferred": [s for s in pref_skills if s.lower() in skills_lower],
        "missing_required":  [s for s in req_skills  if s.lower() not in skills_lower],
    }