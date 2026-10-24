"""
Held-out evaluation set, written by the team after the v2 fixes.

The original data is kept unchanged in eval/heldout_raw.json. It was written
with placeholder enum values, so this file maps item_category, main_color and
general_location of the found records to the real vocabularies in llm.py.
Nothing else is changed: descriptions, dates, features and match labels are
taken from the JSON as they are.

    python eval/run_eval.py --set heldout --version v1 --runs 3
    python eval/run_eval.py --set heldout --version v2 --runs 3

The held-out found records are added to the 14 found records of the main set,
so every held-out query is searched in the full database of 34 records.
"""

import json
from pathlib import Path

RAW = json.loads(Path(__file__).with_name("heldout_raw.json").read_text(encoding="utf-8"))

TODAY = RAW["meta"]["today"]

# Placeholder category -> llm.ITEM_CATEGORIES. "electronics" and "accessories"
# cover several real categories, so the mapping is per record: (case_id, index).
CATEGORY_MAP = {
    (1, 0): "headphone_case",   # electronics: white wireless earbud charging case
    (1, 1): "headphone_case",   # electronics: white AirPods case
    (2, 0): "backpack",         # bags: black backpack
    (2, 1): "backpack",         # bags: black rucksack
    (3, 0): "keys",             # keys
    (3, 1): "keys",             # keys
    (4, 0): "umbrella",         # umbrellas
    (4, 1): "umbrella",         # umbrellas
    (5, 0): "phone",            # electronics: iPhone
    (5, 1): "phone",            # electronics: Samsung phone
    (6, 0): "id_card",          # wallets_cards: student card
    (6, 1): "id_card",          # wallets_cards: student card
    (7, 0): "jacket",           # clothing: puffer jacket
    (7, 1): "jacket",           # clothing: puffer jacket
    (8, 0): "jewelry",          # accessories: necklace
    (8, 1): "jewelry",          # accessories: charm bracelet
    (9, 0): "glasses",          # accessories: prescription glasses
    (9, 1): "glasses",          # accessories: sunglasses
    (10, 0): "charger",         # electronics: laptop charger
    (10, 1): "charger",         # electronics: laptop charger
}

# Placeholder color -> llm.COLORS. Only the values used in the data.
COLOR_MAP = {
    "black": "black",
    "white": "white",
    "red": "red",
    "green": "green",
    "brown": "brown",
    "silver": "silver",
    "gold": "gold",
    "navy": "blue",
}

# Placeholder location -> llm.LOCATIONS. Places without their own value
# in the vocabulary become "other", as the extraction prompt prescribes.
LOCATION_MAP = {
    "angstrom": "angstrom_laboratory",
    "ekonomikum": "ekonomikum",
    "carolina_rediviva": "carolina_rediviva",
    "blasenhus": "blasenhus",
    "segerstedthuset": "segerstedt_building",
    "bmc": "biomedical_centre",
    "engelska_parken": "english_park_campus",
    "central_station": "uppsala_central_station",
    "itc_polacksbacken": "other",
    "nations_area": "other",
    "studentstaden": "other",
}

# Query types used to group the results, taken from each case's notes.
TAGS = {
    1: ["synonym", "relative date"],
    2: ["non-English", "vague date"],
    3: ["non-English", "uncertain location", "weekday date"],
    4: ["short / generic", "vague date"],
    5: ["uncertain location", "weekday date"],
    6: ["no match", "non-English", "uncertain location", "vague date"],
    7: ["uncertain location", "synonym", "messy text"],
    8: ["no match", "near-miss"],
    9: ["non-English", "synonym", "vague date"],
    10: ["no match", "near-miss", "relative date"],
}


def _found_record(case_id, index, record):
    return {
        "report_type": "found",
        "raw_description": record["raw_description"],
        "item_category": CATEGORY_MAP[(case_id, index)],
        "main_color": COLOR_MAP[record["main_color"]],
        "general_location": LOCATION_MAP[record["general_location"]],
        "event_date": record["event_date"],
        "feature_description": record["feature_description"],
        "hidden_feature": record["hidden_feature"],
    }


EXTRA_FOUND = {}
HELDOUT_QUERIES = []

for case in RAW["cases"]:
    match = None
    for index, record in enumerate(case["found_records"]):
        key = f"H{case['case_id']}.{index + 1}"
        EXTRA_FOUND[key] = _found_record(case["case_id"], index, record)
        if record["is_correct_match"]:
            match = key

    HELDOUT_QUERIES.append({
        "tag": f"case {case['case_id']}",
        "tags": TAGS[case["case_id"]],
        "language": case["query_language"],
        "text": case["query_text"],
        "match": match if case["has_match"] else None,
        # The JSON has no expected extraction for the queries, so fields are not scored.
        "gold": {"item_category": None, "main_color": None, "general_location": None, "event_date": None},
    })
