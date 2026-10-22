"""
Evaluation set for LostLink.

FOUND_POOL: found reports stored in the database before the evaluation.
    F1-F5 are the demo records from seed.py; F6-F14 are extra records,
    several of them deliberate near-duplicates (same category, location and
    color) so that the matcher has to rely on the detailed features.

QUERIES: lost reports written by the team. Each query has
    - text:     the natural-language report
    - match:    key of the found record it should match, or None
    - gold:     expected extracted fields (None = ambiguous, not scored)
    - tag:      what the query tests

All relative dates are resolved against TODAY.
"""

from seed import SEED_ITEMS

TODAY = "2026-10-13"


def _found(category, color, location, event_date, raw, detailed, visible, hidden):
    return {
        "report_type": "found",
        "raw_description": raw,
        "item_category": category,
        "main_color": color,
        "general_location": location,
        "event_date": event_date,
        "detailed_location": detailed,
        "feature_description": visible,
        "hidden_feature": hidden,
    }


_seed_found = [item for item in SEED_ITEMS if item["report_type"] == "found"]

FOUND_POOL = {f"F{i + 1}": item for i, item in enumerate(_seed_found)}

FOUND_POOL.update({
    "F6": _found(
        "water_bottle", "blue", "angstrom_laboratory", "2026-10-12",
        "Found a blue plastic water bottle in the Angstrom Laboratory on October 12, 2026, on a bench in the corridor outside lecture hall 80101. It has the Uppsala University logo printed on it and no stickers. The name 'Erik' is written on the bottom.",
        "On a bench in the corridor outside lecture hall 80101",
        "Blue plastic bottle with the Uppsala University logo printed on it, no stickers",
        "The name 'Erik' is written on the bottom",
    ),
    "F7": _found(
        "headphone_case", "grey", "carolina_rediviva", "2026-10-11",
        "A light grey earbud case was found at Carolina Rediviva on October 11, 2026, on a desk in the group study room. It looks almost new, without scratches. Inside the lid there is a small sticker with the letters 'JS'.",
        "On a desk in the group study room",
        "Light grey earbud case in almost new condition, no scratches",
        "A small sticker with the letters 'JS' inside the lid",
    ),
    "F8": _found(
        "wallet", "black", "ekonomikum", "2026-10-12",
        "Found a black leather wallet in the Ekonomikum cafeteria on October 12, 2026, under a table near the window. The leather is worn at the corners. It contains a library card with the initials 'K.L.'.",
        "Under a table near the window in the cafeteria",
        "Black leather wallet, worn at the corners",
        "Contains a library card with the initials 'K.L.'",
    ),
    "F9": _found(
        "keys", "red", "angstrom_laboratory", "2026-10-12",
        "I found a bunch of keys outside entrance 10 at the Angstrom Laboratory on October 12, 2026. Three keys on a red lanyard with a small bottle opener attached. One of the keys has a blue rubber cover.",
        "On the ground outside entrance 10",
        "Three keys on a red lanyard with a small bottle opener",
        "One of the keys has a blue rubber cover",
    ),
    "F10": _found(
        "umbrella", "blue", "blasenhus", "2026-10-08",
        "A dark blue umbrella was left in the entrance hall of Blasenhus on October 8, 2026. It has a white plastic handle and one torn panel. The strap has a small tag with the number '14'.",
        "Entrance hall, next to the stairs",
        "Dark blue umbrella with a white plastic handle and one torn panel",
        "A small tag with the number '14' on the strap",
    ),
    "F11": _found(
        "jacket", "black", "biomedical_centre", "2026-10-09",
        "Found a black rain jacket, size M, in lecture room B22 at the Biomedical Centre on October 9, 2026. The main zipper is broken. There is a bus ticket in the left pocket.",
        "Lecture room B22, on the back of a chair",
        "Black rain jacket, size M, broken main zipper",
        "A bus ticket in the left pocket",
    ),
    "F12": _found(
        "laptop", "silver", "carolina_rediviva", "2026-10-10",
        "A silver laptop was found in the main reading room of Carolina Rediviva on October 10, 2026. It has a cat sticker on the lid and a cracked bottom-left corner. The lock screen shows a photo of a lighthouse.",
        "Main reading room, on a desk near the entrance",
        "Silver laptop with a cat sticker on the lid and a cracked bottom-left corner",
        "The lock screen shows a photo of a lighthouse",
    ),
    "F13": _found(
        "phone", "black", "uppsala_central_station", "2026-10-11",
        "Found a black smartphone at Uppsala Central Station on October 11, 2026, on a bench at platform 4. The screen is cracked in the top-right corner. The lock screen shows a photo of a golden retriever.",
        "On a bench at platform 4",
        "Black smartphone with a cracked screen in the top-right corner",
        "The lock screen shows a photo of a golden retriever",
    ),
    "F14": _found(
        "glasses", "black", "segerstedt_building", "2026-10-10",
        "Found a pair of black reading glasses in a brown case in the Segerstedt building on October 10, 2026, on the reception counter. The name of an optician is printed inside the case.",
        "On the reception counter",
        "Black reading glasses in a brown case",
        "An optician's name is printed inside the case",
    ),
})


def _q(tag, text, match, category, color, location, event_date):
    return {
        "tag": tag,
        "text": text,
        "match": match,
        "gold": {
            "item_category": category,
            "main_color": color,
            "general_location": location,
            "event_date": event_date,
        },
    }


QUERIES = [
    # ---------- should match ----------
    _q("synonym color",
       "I lost my navy metal bottle at Angstrom on Oct 11, near the vending machines by the entrance. It has a white mountain sticker and QT under the lid.",
       "F1", "water_bottle", "blue", "angstrom_laboratory", "2026-10-11"),
    _q("relative date, near-duplicate",
       "Lost my blue water bottle in Ångström yesterday, I think on a bench in the corridor. It's plastic with the university logo, and my name Erik is written on the bottom.",
       "F6", "water_bottle", "blue", "angstrom_laboratory", "2026-10-12"),
    _q("near-duplicate",
       "Lost my black backpack in Ekonomikum on 12 October, I was sitting in the back of the big lecture hall. The right strap is a bit torn and my leaf keyring is inside.",
       "F3", "backpack", "black", "ekonomikum", "2026-10-12"),
    _q("weekday date, 'laptop bag'",
       "Has anyone found my laptop bag? It's black, I left it next to the printer in the computer room at Ekonomikum on Monday. Reflective strip on the front, and the number 27 is on a label in the laptop sleeve.",
       "F4", "backpack", "black", "ekonomikum", "2026-10-12"),
    _q("Chinese",
       "我10月10日在Carolina Rediviva图书馆靠窗的阅读区丢了一个浅灰色的耳机盒，充电口旁边有一道小裂缝，硅胶套下面用铅笔写了AL。",
       "F5", "headphone_case", "grey", "carolina_rediviva", "2026-10-10"),
    _q("brand name, near-duplicate",
       "I lost my AirPods case at Carolina Rediviva on October 11, probably in a group study room. It's light grey and quite new. There's a little JS sticker inside the lid.",
       "F7", "headphone_case", "grey", "carolina_rediviva", "2026-10-11"),
    _q("Swedish",
       "Jag tappade min svarta plånbok i Ekonomikum den 12 oktober, troligen i kafeterian. Den är i läder och det finns ett lånekort med initialerna K.L. i den.",
       "F8", "wallet", "black", "ekonomikum", "2026-10-12"),
    _q("relative date",
       "Lost my keys at Ångström yesterday near entrance 10. Three keys on a red lanyard with a bottle opener, one of them has a blue rubber cover.",
       "F9", "keys", "red", "angstrom_laboratory", "2026-10-12"),
    _q("plain",
       "I lost my dark blue umbrella at Blåsenhus on October 8. White handle, one panel is torn, and there is a tag with 14 on the strap.",
       "F10", "umbrella", "blue", "blasenhus", "2026-10-08"),
    _q("abbreviation 'BMC'",
       "I forgot my black rain jacket in a lecture room at BMC last Friday. Size M, the zipper is broken, and there should be a bus ticket in the left pocket.",
       "F11", "jacket", "black", "biomedical_centre", "2026-10-09"),
    _q("informal",
       "lost silver laptop in the carolina library on oct 10!! cat sticker on top, one corner is cracked",
       "F12", "laptop", "silver", "carolina_rediviva", "2026-10-10"),
    _q("plain",
       "I lost my black phone at Uppsala central station on Sunday, probably at platform 4. The screen is cracked in the corner and my lock screen is a photo of my golden retriever.",
       "F13", "phone", "black", "uppsala_central_station", "2026-10-11"),
    _q("sparse details",
       "Lost my glasses in a brown case in the Segerstedt building on October 10.",
       "F14", "glasses", "black", "segerstedt_building", "2026-10-10"),
    _q("ambiguous location",
       "I think I left my headphone case either at the English Park campus or at Carolina Rediviva on October 10. Light grey, crack near the charging port, AL under the silicone cover.",
       "F5", "headphone_case", "grey", None, "2026-10-10"),
    _q("vague date outside 7-day window",
       "I lost my blue metal bottle with a mountain sticker and QT under the lid at Ångström, I think it was around the end of September.",
       "F1", "water_bottle", "blue", "angstrom_laboratory", None),

    # ---------- should NOT match ----------
    _q("no such item",
       "I lost a red umbrella at Angstrom yesterday.",
       None, "umbrella", "red", "angstrom_laboratory", "2026-10-12"),
    _q("near-miss, conflicting features",
       "Lost my black backpack in Ekonomikum on Oct 12. It has a big football club patch on the front and my calculator is inside.",
       None, "backpack", "black", "ekonomikum", "2026-10-12"),
    _q("near-miss, conflicting features",
       "Lost a black thermos bottle at Ångström on October 11. It has a bamboo lid and my name Sara is engraved on the bottom.",
       None, "water_bottle", "black", "angstrom_laboratory", "2026-10-11"),
    _q("no such item",
       "I lost my phone at Ekonomikum on Monday, it's white with a pink case.",
       None, "phone", "white", "ekonomikum", "2026-10-12"),
    _q("too generic",
       "I lost a water bottle at Ångström on October 11.",
       None, "water_bottle", "unknown", "angstrom_laboratory", "2026-10-11"),
]
