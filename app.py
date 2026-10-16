"""
LostLink - Gradio interface and integration.

    item       = llm.extract_item(user_text, report_type)
    item_id    = database.insert_item(item)
    candidates = database.get_candidates(item)
    matches    = llm.find_top_matches(item, candidates)

Run locally:  python app.py          (needs GROQ_API_KEY in .env)
Run in Colab: see LostLink_Demo.ipynb
"""

import os
import traceback

import gradio as gr

import database
import llm
from seed import SEED_ITEMS

TOP_K = 3

MATCH_COLUMNS = ["Rank", "ID", "Score", "Category", "Color", "Location",
                 "Date", "Where exactly", "Visible features", "Why"]

# hidden_feature is deliberately never shown: it is how the real owner proves
# the item is theirs, so revealing it would let anyone claim anything.
DB_COLUMNS = ["ID", "Type", "Status", "Category", "Color", "Location",
              "Date", "Where exactly", "Visible features"]


# ---------- startup ----------

def setup_database():
    """Create the table and load demo records if the database is empty."""
    database.init_db()
    if not database.get_all_items():
        for item in SEED_ITEMS:
            database.insert_item(item)
        print(f"Loaded {len(SEED_ITEMS)} demo records into {database.DB_PATH}")


def check_api_key():
    if not os.environ.get("GROQ_API_KEY"):
        print("WARNING: GROQ_API_KEY is not set - extraction and matching will fail.\n"
              "Locally: copy .env.example to .env and add your key.\n"
              "In Colab: add GROQ_API_KEY under Secrets (key icon on the left).")


# ---------- formatting ----------

def _pretty(value):
    """angstrom_laboratory -> Angstrom laboratory, None -> ''."""
    if value is None:
        return ""
    return str(value).replace("_", " ").capitalize()


def _match_rows(matches):
    return [
        [
            rank,
            m.get("id"),
            m.get("score"),
            _pretty(m.get("item_category")),
            _pretty(m.get("main_color")),
            _pretty(m.get("general_location")),
            m.get("event_date") or "",
            m.get("detailed_location") or "",
            m.get("feature_description") or "",
            m.get("reason") or "",
        ]
        for rank, m in enumerate(matches, start=1)
    ]


def _db_rows():
    return [
        [
            r["id"],
            r["report_type"],
            r["status"],
            _pretty(r["item_category"]),
            _pretty(r["main_color"]),
            _pretty(r["general_location"]),
            r["event_date"] or "",
            r["detailed_location"] or "",
            r["feature_description"] or "",
        ]
        for r in database.get_all_items()
    ]


def _extracted_view(item):
    """What the LLM understood, in the order a user would read it."""
    return {
        "Category": item.get("item_category"),
        "Main color": item.get("main_color"),
        "Location": item.get("general_location"),
        "Date": item.get("event_date"),
        "Where exactly": item.get("detailed_location"),
        "Visible features": item.get("feature_description"),
        "Hidden feature (only used for matching, never shown to others)": item.get("hidden_feature"),
    }


# ---------- event handlers ----------

def handle_report(report_type, user_text, save_report):
    """Full pipeline: extract -> (save) -> retrieve -> rerank."""
    if not user_text or not user_text.strip():
        return {}, [], "⚠️ Please describe the item first.", _db_rows()

    report_type = report_type.lower()
    other_type = "found" if report_type == "lost" else "lost"

    # 1. LLM extraction
    try:
        item = llm.extract_item(user_text, report_type)
    except Exception as e:
        traceback.print_exc()
        return {}, [], f"❌ Could not read the description: {e}", _db_rows()

    view = _extracted_view(item)
    notes = []

    # 2. Save report
    if save_report:
        try:
            item_id = database.insert_item(item)
            notes.append(f"Saved as report **#{item_id}**.")
        except Exception as e:
            traceback.print_exc()
            notes.append(f"Could not save the report ({e}); searching anyway.")
    else:
        notes.append("Search only — report not saved.")

    # 3. SQL candidate retrieval
    try:
        candidates = database.get_candidates(item, limit=10)
    except Exception as e:
        traceback.print_exc()
        return view, [], f"❌ Database search failed: {e}", _db_rows()

    if not candidates:
        notes.append(f"No open {other_type} reports with the same category and location yet.")
        return view, [], " ".join(notes), _db_rows()

    # 4. LLM reranking
    try:
        matches = llm.find_top_matches(item, candidates, top_k=TOP_K)
    except Exception as e:
        traceback.print_exc()
        return view, [], f"❌ Matching failed: {e}", _db_rows()

    if matches:
        notes.append(f"Compared {len(candidates)} candidate(s); "
                     f"{len(matches)} look like possible matches.")
    else:
        notes.append(f"Compared {len(candidates)} candidate(s), but none look like the same item.")

    return view, _match_rows(matches), " ".join(notes), _db_rows()


def handle_mark_matched(item_id):
    if not item_id:
        return "Enter a report ID first.", _db_rows()
    try:
        ok = database.update_status(int(item_id), "matched")
    except Exception as e:
        traceback.print_exc()
        return f"❌ Update failed: {e}", _db_rows()
    msg = (f"✅ Report #{int(item_id)} marked as matched — it will no longer show up in searches."
           if ok else f"Report #{int(item_id)} not found.")
    return msg, _db_rows()


# ---------- UI ----------

EXAMPLES = [
    ["Lost", "I lost my navy metal water bottle at Ångström yesterday, near the vending machines "
             "by the main entrance. It has a white mountain sticker and QT is written under the lid."],
    ["Lost", "Lost my black backpack in Ekonomikum on 12 October, back of the big lecture hall. "
             "The right strap is a bit torn and my leaf keyring is inside."],
    ["Lost", "我10月10日在Carolina Rediviva图书馆靠窗的阅读区丢了一个浅灰色的耳机盒，充电口旁边有一道小裂缝。"],
    ["Found", "Found a black umbrella with a wooden handle in the umbrella stand at Carolina Rediviva "
              "on October 9. One spoke is bent and there is a name tag on the strap."],
]


def build_ui():
    with gr.Blocks(title="LostLink") as demo:
        gr.Markdown(
            "# 🔎 LostLink\n"
            "Describe a lost or found item in your own words — any language works. "
            "LostLink extracts the key details, searches the database, and ranks possible matches."
        )

        with gr.Tab("Report an item"):
            with gr.Row():
                with gr.Column():
                    report_type = gr.Radio(["Lost", "Found"], value="Lost", label="I have...")
                    user_text = gr.Textbox(
                        lines=5, label="Description",
                        placeholder="What is it, what does it look like, where and when? "
                                    "Mention a detail only the owner would know (e.g. writing inside).",
                    )
                    save_report = gr.Checkbox(value=True, label="Save this report to the database")
                    submit = gr.Button("Find matches", variant="primary")
                    gr.Examples(EXAMPLES, inputs=[report_type, user_text])

                with gr.Column():
                    status = gr.Markdown()
                    extracted = gr.JSON(label="What LostLink understood")

            matches = gr.Dataframe(headers=MATCH_COLUMNS, label=f"Top {TOP_K} possible matches",
                                   wrap=True, interactive=False)

        with gr.Tab("Database"):
            gr.Markdown("All reports. Hidden features are never displayed.")
            db_table = gr.Dataframe(headers=DB_COLUMNS, value=_db_rows,
                                    wrap=True, interactive=False)
            with gr.Row():
                match_id = gr.Number(label="Report ID", precision=0, value=None)
                mark_btn = gr.Button("Mark as matched")
                refresh_btn = gr.Button("Refresh")
            mark_status = gr.Markdown()

        submit.click(handle_report, inputs=[report_type, user_text, save_report],
                     outputs=[extracted, matches, status, db_table])
        mark_btn.click(handle_mark_matched, inputs=match_id, outputs=[mark_status, db_table])
        refresh_btn.click(_db_rows, outputs=db_table)

    return demo


if __name__ == "__main__":
    check_api_key()
    setup_database()
    build_ui().launch(share=True)
