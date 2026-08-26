# Admin tool: paste raw text (a Reddit thread, a screenshot transcript,
# whatever) and have OpenAI extract structured grade reports out of it, for
# review before adding to the database. Deliberately independent of
# backend/scraper/reddit_scraper.py (gitignored, local-only) so this admin
# feature works regardless of whether that private scraper is present.
import json
import os
from typing import Optional

from openai import OpenAI

EXTRACTION_SYSTEM_PROMPT = (
    "You extract University of Toronto CS-major admission grade reports from "
    "pasted text (a Reddit thread, forum post, or similar). For every "
    "distinct first-hand report of someone's own admit grade (ignore "
    "anything that isn't a first-hand report of a grade that got them in), "
    "extract: `decision_year` (the plain calendar year in which the "
    "admission decision/result described was received — infer from "
    "explicit mentions in the text; if genuinely unclear, use null), "
    "`csc148` (float mark if separately reported, else null), `csc165` "
    "(float mark if separately reported, else null), `average` (float "
    "combined average if reported directly, else null), and `program` — "
    "which specific program the report is about. This is critical: UofT "
    "has several similarly-named but DIFFERENT programs with different, "
    "generally lower cutoffs than the CS major/specialist — Data Science "
    "specialist/major (even when csc148 is mentioned alongside courses like "
    "mat137/sta130), the CS MINOR, and other unrelated programs the person "
    "mentions getting into 'instead'. Set `program` to exactly one of: "
    "'cs_major_or_specialist' (the actual CS major or CS specialist — the "
    "only value that should count toward the CS major cutoff), 'cs_minor', "
    "'ds_specialist_or_major', 'other'. If the text doesn't clearly say "
    "which program, and just discusses csc148/csc165 marks in a POSt/major "
    "context without naming a different program, use "
    "'cs_major_or_specialist'. Respond with strict JSON: {\"reports\": "
    "[{\"decision_year\": int|null, \"csc148\": float|null, \"csc165\": "
    "float|null, \"average\": float|null, \"program\": string}]}"
)

OPENAI_MODEL = "gpt-4o-mini"


def extract_reports_from_text(text: str, openai_api_key: Optional[str] = None) -> list[dict]:
    """Return raw extracted reports: [{decision_year, csc148, csc165,
    average, program}, ...]. Caller is responsible for converting
    decision_year -> our Fall-start year convention and filtering by
    program before using these (same as reddit_scraper.py's approach) —
    this function only does the text -> structured-data step.
    """
    api_key = openai_api_key or os.environ.get("OPENAI_API_KEY_OTHER")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY_OTHER not set — pass openai_api_key= or set the env var")

    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps({"text": text[:20000]})},
        ],
    )
    result = json.loads(response.choices[0].message.content)
    return result.get("reports", [])
