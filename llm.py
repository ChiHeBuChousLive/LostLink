import json
import os
from datetime import date

# Load GROQ_API_KEY and LOSTLINK_MODEL from a local .env file if present.
# In Colab there is no .env, so set the variables with os.environ instead.
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass


# Model can be changed without touching the code:
#   os.environ["LOSTLINK_MODEL"] = "openai/gpt-oss-20b"
MODEL = os.environ.get("LOSTLINK_MODEL", "openai/gpt-oss-120b")


# Controlled vocabularies.
# database.get_candidates() uses exact SQL matching on item_category,
# general_location and main_color, so the LLM must only output these values.
# Keep these lists in sync with the seed data in data/seed_data.ipynb.
ITEM_CATEGORIES = [
    "electronics",
    "bags_and_luggage",
    "clothing",
    "footwear",
    "personal_accessories",
    "jewelry_and_watches",
    "cards_and_documents",
    "keys_and_access_items",
    "books_and_stationery",
    "drinkware_and_food_containers",
    "health_and_beauty",
    "sports_and_outdoor",
    "toys_and_hobbies",
    "tools_and_equipment",
    "household_items",
    "other",
]

COLORS = [
    "black",
    "white",
    "grey",
    "blue",
    "red",
    "green",
    "yellow",
    "orange",
    "pink",
    "purple",
    "brown",
    "beige",
    "silver",
    "gold",
    "multicolor",
    "unknown",
]

LOCATIONS = [
    "angstrom_laboratory",
    "ekonomikum",
    "carolina_rediviva",
    "blasenhus",
    "biomedical_centre",
    "english_park_campus",
    "university_main_building",
    "segerstedt_building",
    "uppsala_central_station",
    "other",
]


EXTRACTION_SYSTEM_PROMPT = f"""You extract structured information from lost-and-found reports at Uppsala University.

The user describes an item they lost or found. Return one JSON object.

Field rules:
- item_category: the closest value from the allowed list. Use "other" only if nothing fits.
- main_color: the dominant color, mapped to the closest base color in the allowed list
  (navy / dark blue / light blue -> "blue", light grey / dark grey -> "grey").
  Mention the exact shade in feature_description instead. Use "unknown" if no color is given.
- general_location: the building or area from the allowed list. Use "other" if it is not in the list.
- event_date: the date the item was lost or found, as YYYY-MM-DD. Resolve relative dates
  ("yesterday", "last Monday") using today's date. Use an empty string if no date is given.
- detailed_location: where exactly inside the location (room, floor, near what). Empty string if not given.
- feature_description: visible features someone would notice at a glance (material, brand,
  stickers, scratches, exact shade). Empty string if not given.
- hidden_feature: details that are not visible at a glance and would help verify the real owner
  (writing inside a lid, items inside a pocket, engravings, contents). Empty string if not given.
  Anything written or placed under, inside or behind a part of the item belongs here,
  NOT in feature_description. Never put the same detail in both fields.

Only use information stated in the description. Do not invent details.
Write detailed_location, feature_description and hidden_feature in English.

Allowed item_category values: {", ".join(ITEM_CATEGORIES)}
Allowed main_color values: {", ".join(COLORS)}
Allowed general_location values: {", ".join(LOCATIONS)}
"""

EXTRACTION_SCHEMA = {
    "type": "object",
    "properties": {
        "item_category": {"type": "string", "enum": ITEM_CATEGORIES},
        "main_color": {"type": "string", "enum": COLORS},
        "general_location": {"type": "string", "enum": LOCATIONS},
        "event_date": {"type": "string"},
        "detailed_location": {"type": "string"},
        "feature_description": {"type": "string"},
        "hidden_feature": {"type": "string"},
    },
    "required": [
        "item_category",
        "main_color",
        "general_location",
        "event_date",
        "detailed_location",
        "feature_description",
        "hidden_feature",
    ],
    "additionalProperties": False,
}


SCORING_SYSTEM_PROMPT = """You are the matching engine of a university lost-and-found system.

You receive one report (the "query") and a list of candidate reports of the opposite type
(a lost report is compared with found reports, and the other way round).
The candidates were already pre-filtered by category and location, so focus on the details.

For every candidate, give a score from 0 to 100 for how likely it is the same physical item:
- 90-100: specific details agree (same stickers, same marks, same hidden feature) and nothing contradicts.
- 60-89: most details agree, a few are missing or vague.
- 30-59: compatible but too generic to tell, or a minor conflict.
- 0-29: clear contradictions (different brand, different marks, different hidden feature).

Compare color shade, detailed location, date, visible features and hidden features.
A matching hidden feature is strong evidence. A conflicting hidden feature is strong evidence against.
Missing information is not a contradiction.
People often misremember dates, so a difference of one or two days is only a minor issue.

Write a short reason (one or two sentences) for each candidate.
The reason will be shown to the person who wrote the query, so NEVER reveal or quote a
candidate's hidden_feature in the reason. Say for example "the hidden feature matches"
or "the hidden feature does not match" instead.

Return a result for every candidate id you were given.
"""

SCORING_SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "score": {"type": "integer"},
                    "reason": {"type": "string"},
                },
                "required": ["id", "score", "reason"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["results"],
    "additionalProperties": False,
}

# Fields sent to the LLM when comparing reports.
COMPARE_FIELDS = (
    "id",
    "raw_description",
    "item_category",
    "main_color",
    "general_location",
    "event_date",
    "detailed_location",
    "feature_description",
    "hidden_feature",
)


_client = None


def _get_client():
    """Create the Groq client once. Reads GROQ_API_KEY from the environment."""
    global _client

    if _client is None:
        from groq import Groq

        _client = Groq(timeout=60)

    return _client


def _call_llm(system, user_content, schema, reasoning_effort="medium"):
    """
    Send one request to the LLM and return the parsed JSON object.

    This is the only function that talks to the API, so switching to another
    model provider only requires changing this function.
    """
    client = _get_client()

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {"name": "result", "strict": True, "schema": schema},
        },
        reasoning_effort=reasoning_effort,
        include_reasoning=False,
    )

    text = response.choices[0].message.content

    if not text:
        raise RuntimeError("The model returned an empty response.")

    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError(f"The model did not return valid JSON: {text[:200]}") from error


def _empty_to_none(value):
    if value is None:
        return None

    value = str(value).strip()

    return value or None


def _valid_date(value):
    """Return the date string if it is YYYY-MM-DD, otherwise None."""
    value = _empty_to_none(value)

    if value is None:
        return None

    try:
        date.fromisoformat(value)
    except ValueError:
        return None

    return value


def extract_item(user_text, report_type, today=None):
    """
    Convert a natural-language description into the shared item format.

    Args:
        user_text: The user's description of the lost or found item.
        report_type: "lost" or "found".
        today: Optional date string (YYYY-MM-DD) used to resolve relative dates.
            Defaults to the current date.

    Returns:
        dict: Item ready for database.insert_item().
    """
    if report_type not in ("lost", "found"):
        raise ValueError("report_type must be 'lost' or 'found'")

    if not user_text or not user_text.strip():
        raise ValueError("user_text must not be empty")

    today = today or date.today().isoformat()

    user_content = (
        f"Today's date: {today}\n"
        f"Report type: {report_type}\n\n"
        f"Description:\n{user_text.strip()}"
    )

    data = _call_llm(
        EXTRACTION_SYSTEM_PROMPT,
        user_content,
        EXTRACTION_SCHEMA,
        reasoning_effort="low",
    )

    # Guard against values outside the vocabulary.
    category = data.get("item_category")
    color = data.get("main_color")
    location = data.get("general_location")

    return {
        "report_type": report_type,
        "raw_description": user_text.strip(),
        "item_category": category if category in ITEM_CATEGORIES else "other",
        "main_color": color if color in COLORS else "unknown",
        "general_location": location if location in LOCATIONS else "other",
        "event_date": _valid_date(data.get("event_date")),
        "detailed_location": _empty_to_none(data.get("detailed_location")),
        "feature_description": _empty_to_none(data.get("feature_description")),
        "hidden_feature": _empty_to_none(data.get("hidden_feature")),
        "status": "open",
    }


def _for_llm(record):
    return {field: record.get(field) for field in COMPARE_FIELDS}


def score_candidates(item, candidates):
    """
    Compare one report with all candidates in a single LLM request.

    Args:
        item: The new report (shared item format).
        candidates: List of records from database.get_candidates().
            Each record must have an "id".

    Returns:
        list: One dict per candidate: {"id": int, "score": int, "reason": str},
            in the same order as candidates.
    """
    if not candidates:
        return []

    query = _for_llm(item)
    query.pop("id", None)

    user_content = (
        f"Query ({item.get('report_type')} report):\n"
        f"{json.dumps(query, ensure_ascii=False, indent=2)}\n\n"
        f"Candidates:\n"
        f"{json.dumps([_for_llm(c) for c in candidates], ensure_ascii=False, indent=2)}"
    )

    data = _call_llm(SCORING_SYSTEM_PROMPT, user_content, SCORING_SCHEMA)

    by_id = {}

    for result in data.get("results", []):
        try:
            candidate_id = int(result["id"])
            score = int(result["score"])
        except (KeyError, TypeError, ValueError):
            continue

        by_id[candidate_id] = {
            "id": candidate_id,
            "score": max(0, min(100, score)),
            "reason": str(result.get("reason", "")).strip(),
        }

    # Every candidate gets a result, even if the LLM skipped it.
    return [
        by_id.get(
            c["id"],
            {"id": c["id"], "score": 0, "reason": "The model did not score this candidate."},
        )
        for c in candidates
    ]


def find_top_matches(item, candidates, top_k=3, min_score=30):
    """
    Score all candidates and return the best matches.

    Args:
        item: The new report (shared item format).
        candidates: List of records from database.get_candidates().
        top_k: Maximum number of matches to return.
        min_score: Matches below this score are dropped.

    Returns:
        list: Candidate records sorted by score (highest first). Each record
            gets two extra keys: "score" and "reason".
            Note: records still contain "hidden_feature" - do not show it to users.
    """
    scores = score_candidates(item, candidates)
    score_by_id = {s["id"]: s for s in scores}

    matches = []

    for candidate in candidates:
        result = score_by_id[candidate["id"]]

        if result["score"] < min_score:
            continue

        matches.append(
            {
                **candidate,
                "score": result["score"],
                "reason": result["reason"],
            }
        )

    matches.sort(key=lambda m: m["score"], reverse=True)

    return matches[:top_k]


if __name__ == "__main__":
    # Quick manual test (needs GROQ_API_KEY).
    import sys

    # The Windows terminal may not use UTF-8 by default.
    sys.stdout.reconfigure(encoding="utf-8")

    text = (
        "I lost my navy metal water bottle in the Angstrom Laboratory yesterday, "
        "probably near the vending machines by the main entrance. "
        "It has a white mountain sticker, and QT is written under the lid."
    )

    item = extract_item(text, "lost")
    print(json.dumps(item, ensure_ascii=False, indent=2))
