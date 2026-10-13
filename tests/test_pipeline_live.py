"""
End-to-end test of database.py + llm.py with the real LLM (needs GROQ_API_KEY in .env).

It uses a temporary database, so data/lostlink.db is never touched.

Run from the repository root:
    python tests/test_pipeline_live.py
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import database
import llm


# Same records as data/seed_data.ipynb, but with colors mapped to the
# base colors used by llm.py (dark_blue -> blue, light_grey -> grey).
SEED_ITEMS = [
    {
        "report_type": "found",
        "raw_description": "I found a dark blue metal water bottle in the Angstrom Laboratory on October 11, 2026. It was standing on the floor beside the vending machines near the main entrance. The bottle has several small scratches near the bottom and a white mountain-shaped sticker on one side. When I opened the lid, I noticed the initials 'QT' written in black marker underneath it.",
        "item_category": "water_bottle",
        "main_color": "blue",
        "general_location": "angstrom_laboratory",
        "event_date": "2026-10-11",
        "detailed_location": "On the floor beside the vending machines near the main entrance",
        "feature_description": "Metal bottle with small scratches near the bottom and a white mountain-shaped sticker",
        "hidden_feature": "The initials 'QT' are written in black marker underneath the lid",
    },
    {
        "report_type": "found",
        "raw_description": "A black reusable water bottle was found in the Angstrom Laboratory on October 11, 2026. It was left on a table in the student study area on the second floor, close to a wall socket. The bottle has a silver cap, a faded university logo, and a noticeable dent on its left side. There is also a small red star sticker on the inside of the cap.",
        "item_category": "water_bottle",
        "main_color": "black",
        "general_location": "angstrom_laboratory",
        "event_date": "2026-10-11",
        "detailed_location": "On a table in the second-floor student study area near a wall socket",
        "feature_description": "Reusable bottle with a silver cap, faded university logo, and a dent on the left side",
        "hidden_feature": "A small red star sticker is attached to the inside of the cap",
    },
    {
        "report_type": "found",
        "raw_description": "I found a black backpack at Ekonomikum on October 12, 2026. It was under a chair near the back-left corner of the main lecture hall. The backpack has two front pockets, grey zipper cords, and a small tear on the right shoulder strap. Inside the smallest front pocket, there is a green keyring shaped like a leaf.",
        "item_category": "backpack",
        "main_color": "black",
        "general_location": "ekonomikum",
        "event_date": "2026-10-12",
        "detailed_location": "Under a chair in the back-left corner of the main lecture hall",
        "feature_description": "Backpack with two front pockets, grey zipper cords, and a small tear on the right shoulder strap",
        "hidden_feature": "A green leaf-shaped keyring is inside the smallest front pocket",
    },
    {
        "report_type": "found",
        "raw_description": "A black laptop backpack was found at Ekonomikum on October 12, 2026. It was placed beside a printer in the computer room on the ground floor. The bag has a reflective strip across the front, a blue zipper pull, and some dried mud near the bottom. The padded laptop compartment contains a handwritten label with the number '27'.",
        "item_category": "backpack",
        "main_color": "black",
        "general_location": "ekonomikum",
        "event_date": "2026-10-12",
        "detailed_location": "Beside a printer in the ground-floor computer room",
        "feature_description": "Laptop backpack with a reflective front strip, blue zipper pull, and dried mud near the bottom",
        "hidden_feature": "A handwritten label with the number '27' is inside the padded laptop compartment",
    },
    {
        "report_type": "found",
        "raw_description": "I found a light grey wireless headphone case at the Carolina Rediviva library on October 10, 2026. It was lying between two chairs in the reading area near the windows. The case has a thin blue ink mark on the front and a small crack beside the charging port. Under the removable silicone cover, the letters 'AL' are written in pencil.",
        "item_category": "headphone_case",
        "main_color": "grey",
        "general_location": "carolina_rediviva",
        "event_date": "2026-10-10",
        "detailed_location": "Between two chairs in the reading area near the windows",
        "feature_description": "Wireless headphone case with a blue ink mark and a small crack beside the charging port",
        "hidden_feature": "The letters 'AL' are written in pencil under the removable silicone cover",
    },
]


# Each test: a lost report and the seed record (1-based) it should match, or None.
TEST_CASES = [
    (
        "I lost my navy metal bottle at Angstrom on Oct 11, near the vending machines "
        "by the entrance. It has a white mountain sticker and QT under the lid.",
        1,
    ),
    (
        "Lost my black backpack in Ekonomikum on 12 October, I was sitting in the back "
        "of the big lecture hall. The right strap is a bit torn and my leaf keyring is inside.",
        3,
    ),
    (
        "我10月10日在Carolina Rediviva图书馆靠窗的阅读区丢了一个浅灰色的耳机盒，"
        "充电口旁边有一道小裂缝，硅胶套下面用铅笔写了AL。",
        5,
    ),
    (
        "I lost a red umbrella at Angstrom yesterday.",
        None,
    ),
]


def main():
    db_path = Path(tempfile.mkdtemp()) / "pipeline_test.db"
    database.init_db(db_path)

    seed_ids = [database.insert_item(item, db_path) for item in SEED_ITEMS]
    print(f"Inserted {len(seed_ids)} found records into {db_path}\n")

    passed = 0

    for text, expected in TEST_CASES:
        expected_id = seed_ids[expected - 1] if expected else None

        print("=" * 70)
        print("Lost report:", text)

        item = llm.extract_item(text, "lost", today="2026-10-13")
        print(
            "Extracted:  ",
            item["item_category"],
            item["main_color"],
            item["general_location"],
            item["event_date"],
        )

        database.insert_item(item, db_path)
        candidates = database.get_candidates(item, db_path=db_path)
        print("Candidates: ", [c["id"] for c in candidates])

        matches = llm.find_top_matches(item, candidates)

        for m in matches:
            print(f"  #{m['id']}  score {m['score']}  {m['reason']}")

        top_id = matches[0]["id"] if matches and matches[0]["score"] >= 60 else None
        ok = top_id == expected_id
        passed += ok

        print("Expected:   ", expected_id, "| Got:", top_id, "|", "PASS" if ok else "FAIL")

    print("=" * 70)
    print(f"{passed}/{len(TEST_CASES)} cases passed")


if __name__ == "__main__":
    main()
