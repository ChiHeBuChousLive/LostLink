"""
Demo records loaded by app.py when the database is empty.

Colors use the base colors from llm.COLORS (e.g. "blue", not "dark_blue"),
otherwise database.get_candidates() cannot match them.

Dates are relative to today, so demo queries that say "yesterday" always fall
inside the 7-day SQL window, no matter on which day the demo is run.
"""

from datetime import date, timedelta


def _days_ago(n):
    return (date.today() - timedelta(days=n)).isoformat()


SEED_ITEMS = [
    # ---------- found reports ----------
    {
        "report_type": "found",
        "raw_description": "I found a dark blue metal water bottle in the Angstrom Laboratory. It was standing on the floor beside the vending machines near the main entrance. The bottle has several small scratches near the bottom and a white mountain-shaped sticker on one side. When I opened the lid, I noticed the initials 'QT' written in black marker underneath it.",
        "item_category": "drinkware_and_food_containers",
        "main_color": "blue",
        "general_location": "angstrom_laboratory",
        "event_date": _days_ago(1),
        "detailed_location": "On the floor beside the vending machines near the main entrance",
        "feature_description": "Dark blue metal water bottle with small scratches near the bottom and a white mountain-shaped sticker",
        "hidden_feature": "The initials 'QT' are written in black marker underneath the lid",
    },
    {
        "report_type": "found",
        "raw_description": "A black reusable water bottle was found in the Angstrom Laboratory. It was left on a table in the student study area on the second floor, close to a wall socket. The bottle has a silver cap, a faded university logo, and a noticeable dent on its left side. There is also a small red star sticker on the inside of the cap.",
        "item_category": "drinkware_and_food_containers",
        "main_color": "black",
        "general_location": "angstrom_laboratory",
        "event_date": _days_ago(1),
        "detailed_location": "On a table in the second-floor student study area near a wall socket",
        "feature_description": "Black reusable water bottle with a silver cap, faded university logo, and a dent on the left side",
        "hidden_feature": "A small red star sticker is attached to the inside of the cap",
    },
    {
        "report_type": "found",
        "raw_description": "I found a black backpack at Ekonomikum. It was under a chair near the back-left corner of the main lecture hall. The backpack has two front pockets, grey zipper cords, and a small tear on the right shoulder strap. Inside the smallest front pocket, there is a green keyring shaped like a leaf.",
        "item_category": "bags_and_luggage",
        "main_color": "black",
        "general_location": "ekonomikum",
        "event_date": _days_ago(1),
        "detailed_location": "Under a chair in the back-left corner of the main lecture hall",
        "feature_description": "Black backpack with two front pockets, grey zipper cords, and a small tear on the right shoulder strap",
        "hidden_feature": "A green leaf-shaped keyring is inside the smallest front pocket",
    },
    {
        "report_type": "found",
        "raw_description": "A black laptop backpack was found at Ekonomikum. It was placed beside a printer in the computer room on the ground floor. The bag has a reflective strip across the front, a blue zipper pull, and some dried mud near the bottom. The padded laptop compartment contains a handwritten label with the number '27'.",
        "item_category": "bags_and_luggage",
        "main_color": "black",
        "general_location": "ekonomikum",
        "event_date": _days_ago(1),
        "detailed_location": "Beside a printer in the ground-floor computer room",
        "feature_description": "Black laptop backpack with a reflective front strip, blue zipper pull, and dried mud near the bottom",
        "hidden_feature": "A handwritten label with the number '27' is inside the padded laptop compartment",
    },
    {
        "report_type": "found",
        "raw_description": "I found a light grey wireless headphone case at the Carolina Rediviva library. It was lying between two chairs in the reading area near the windows. The case has a thin blue ink mark on the front and a small crack beside the charging port. Under the removable silicone cover, the letters 'AL' are written in pencil.",
        "item_category": "electronics",
        "main_color": "grey",
        "general_location": "carolina_rediviva",
        "event_date": _days_ago(2),
        "detailed_location": "Between two chairs in the reading area near the windows",
        "feature_description": "Light grey wireless headphone case with a blue ink mark and a small crack beside the charging port",
        "hidden_feature": "The letters 'AL' are written in pencil under the removable silicone cover",
    },
    {
        "report_type": "found",
        "raw_description": "Found a black iPhone at the Biomedical Centre (BMC), on a bench outside lecture hall B42. It is in a clear plastic case with a cinema ticket tucked behind the phone. The lock screen shows a photo of a golden retriever.",
        "item_category": "electronics",
        "main_color": "black",
        "general_location": "biomedical_centre",
        "event_date": _days_ago(1),
        "detailed_location": "On a bench outside lecture hall B42",
        "feature_description": "Black iPhone in a clear plastic case",
        "hidden_feature": "A cinema ticket is tucked behind the phone inside the case; the lock screen shows a golden retriever",
    },
    # ---------- lost reports (so "found" reports have something to match) ----------
    {
        "report_type": "lost",
        "raw_description": "I lost my black folding umbrella at Carolina Rediviva, probably in the umbrella stand by the entrance. It has a curved wooden handle and one bent spoke. My name tag 'M. Berg' is tied to the strap.",
        "item_category": "personal_accessories",
        "main_color": "black",
        "general_location": "carolina_rediviva",
        "event_date": _days_ago(3),
        "detailed_location": "Umbrella stand by the entrance",
        "feature_description": "Black folding umbrella with a curved wooden handle and one bent spoke",
        "hidden_feature": "A name tag 'M. Berg' is tied to the strap",
    },
    {
        "report_type": "lost",
        "raw_description": "Lost my keys at the Angstrom Laboratory, somewhere near entrance 10. Three keys on a red lanyard with a small bottle opener. One key has a blue rubber cover.",
        "item_category": "keys_and_access_items",
        "main_color": "red",
        "general_location": "angstrom_laboratory",
        "event_date": _days_ago(1),
        "detailed_location": "Near entrance 10",
        "feature_description": "Keys: three keys on a red lanyard with a small bottle opener",
        "hidden_feature": "One key has a blue rubber cover",
    },
]
