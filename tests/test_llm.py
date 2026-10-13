"""
Offline tests for llm.py. The LLM call is replaced by a fake function,
so no API key is needed.

Run from the repository root:
    python tests/test_llm.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database
import llm


def fake_extraction(system, user_content, schema, reasoning_effort="medium"):
    return {
        "item_category": "water_bottle",
        "main_color": "navy",  # not in vocabulary -> should become "unknown"
        "general_location": "angstrom_laboratory",
        "event_date": "2026-10-12",
        "detailed_location": "Near the vending machines",
        "feature_description": "Navy metal bottle with a white mountain sticker",
        "hidden_feature": "",
    }


def test_extract_item():
    llm._call_llm = fake_extraction
    item = llm.extract_item("  I lost my bottle.  ", "lost")

    assert item["report_type"] == "lost"
    assert item["raw_description"] == "I lost my bottle."
    assert item["main_color"] == "unknown"
    assert item["hidden_feature"] is None
    assert item["status"] == "open"

    try:
        llm.extract_item("text", "stolen")
        assert False, "invalid report_type should raise"
    except ValueError:
        pass


def test_pipeline_with_database():
    db_path = Path(tempfile.mkdtemp()) / "test.db"
    database.init_db(db_path)

    found = {
        "report_type": "found",
        "raw_description": "Found a blue bottle.",
        "item_category": "water_bottle",
        "main_color": "blue",
        "general_location": "angstrom_laboratory",
        "event_date": "2026-10-11",
        "status": "open",
    }
    id_a = database.insert_item(found, db_path)
    id_b = database.insert_item({**found, "raw_description": "Another bottle."}, db_path)
    id_c = database.insert_item({**found, "raw_description": "Third bottle."}, db_path)

    lost = {**found, "report_type": "lost", "raw_description": "Lost a blue bottle."}
    candidates = database.get_candidates(lost, db_path=db_path)
    assert len(candidates) == 3

    def fake_scoring(system, user_content, schema, reasoning_effort="medium"):
        # Hidden features must be sent to the LLM for comparison.
        assert "hidden_feature" in user_content
        return {
            "results": [
                {"id": id_a, "score": 40, "reason": "Generic match."},
                {"id": id_b, "score": 150, "reason": "Strong match."},  # clamped to 100
                {"id": 9999, "score": 99, "reason": "Unknown id, ignored."},
                # id_c missing -> score 0
            ]
        }

    llm._call_llm = fake_scoring

    matches = llm.find_top_matches(lost, candidates, top_k=3, min_score=30)

    assert [m["id"] for m in matches] == [id_b, id_a]
    assert matches[0]["score"] == 100
    assert matches[0]["raw_description"] == "Another bottle."

    scores = llm.score_candidates(lost, candidates)
    assert {s["id"]: s["score"] for s in scores}[id_c] == 0

    assert llm.find_top_matches(lost, []) == []


if __name__ == "__main__":
    test_extract_item()
    test_pipeline_with_database()
    print("All tests passed.")
