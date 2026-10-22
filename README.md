# LostLink

LostLink is an **LLM-powered lost-and-found system**. Users describe a lost or found item in their own words, in any language. The system extracts structured information, searches the database, and uses an LLM to rank the most likely matches with a short explanation.

## Why LostLink?

Traditional lost-and-found systems use fixed forms or keyword search. But people describe the same item in different ways:

> *"navy metal bottle"* vs. *"dark blue water bottle"*

A keyword search cannot match these two reports. LostLink uses an LLM to understand what the user means, so reports can be matched even when they use different words or different languages.

## Key Features

- **Natural-language reports** – no forms to fill in; just describe the item.
- **Any language** – a report in Chinese can match a report in English.
- **Hybrid matching** – SQL quickly narrows down the candidates, then the LLM compares the details.
- **Explained results** – every match comes with a score (0–100) and a short reason.
- **Hidden features against false claims** – details only the owner knows (e.g. initials under a lid) are used for matching but never shown to anyone.
- **Lost ↔ found only** – a `lost` report only searches `found` records, and a `found` report only searches `lost` records.

## Technologies Used

- **Model:** `gpt-oss-120b` via the [Groq API](https://console.groq.com), with strict structured output (JSON schema)
- **Database:** SQLite
- **User interface:** Gradio
- **Development environment:** Google Colab / local Python
- **Collaboration:** GitHub

## How It Works

```text
User description (any language)
      ↓
① LLM extracts structured fields (category, color, location, date, features)
      ↓
② Save the report to the SQLite database
      ↓
③ SQL retrieves up to 10 candidates
   (opposite report type, same category & location, date within 7 days)
      ↓
④ LLM compares all candidates in one request → score 0–100 + reason
      ↓
Top 3 matches
```

**Why combine SQL and an LLM?** SQL is fast and cheap, so it filters the database down to a few candidates. The LLM is slower but understands meaning, so it makes the final comparison. This keeps the cost per report constant even when the database grows.

### Example

Input (lost report):

> I lost my navy metal water bottle at Ångström on October 11, near the vending machines. It has a white mountain sticker and QT is written under the lid.

What the LLM extracts:

```json
{
  "item_category": "water_bottle",
  "main_color": "blue",
  "general_location": "angstrom_laboratory",
  "event_date": "2026-10-11",
  "detailed_location": "near the vending machines",
  "feature_description": "metal bottle with a white mountain sticker",
  "hidden_feature": "QT written under the lid"
}
```

"navy" is mapped to the allowed color `blue`, and "QT under the lid" is stored as a hidden feature. SQL then finds the blue bottle reported as found at Ångström (the black bottle found there is filtered out by color), and the LLM scores it:

> **Score 95** – *All key details align: the dark blue metal bottle, vending-machine area, same date, white mountain sticker and the QT marking under the lid all match, with no contradictions.*

The reason mentions "QT" only because the user wrote it. The LLM is instructed never to reveal a hidden feature that the user did not mention, so nobody can learn it from a search result.

### Scoring rubric

| Score | Meaning |
|---|---|
| 90–100 | Specific details agree (same stickers, marks, hidden feature) |
| 60–89 | Most details agree, a few are missing or vague |
| 30–59 | Compatible but too generic to tell |
| 0–29 | Clear contradictions |

Matches below 30 are not shown.

## Project Structure

```text
LostLink/
├── app.py                 # Gradio interface and integration
├── database.py            # SQLite storage and SQL candidate retrieval
├── llm.py                 # LLM extraction and scoring
├── seed.py                # Demo records loaded when the database is empty
├── data/
│   └── seed_data.ipynb    # Notebook used to prepare the demo data
├── eval/
│   ├── eval_data.py       # Evaluation set (14 found reports, 20 lost queries)
│   └── run_eval.py        # Evaluation script with baselines
├── tests/
│   ├── test_llm.py        # Offline unit tests (fake LLM, no API key needed)
│   └── test_pipeline_live.py  # End-to-end test with the real model
├── LostLink_Demo.ipynb    # Run the app in Google Colab
├── requirements.txt
└── .env.example
```

### `database.py`

SQLite operations on one table, `items`:

```python
init_db()                       # create the table
insert_item(item)               # validate and store a report
get_all_items()                 # list all reports
get_candidates(item, limit=10)  # SQL candidate retrieval
update_status(item_id, status)  # open / matched / closed
```

### `llm.py`

LLM extraction and matching:

```python
extract_item(user_text, report_type)           # text -> structured item
score_candidates(item, candidates)             # score all candidates in one request
find_top_matches(item, candidates, top_k=3)    # sort and return the best matches
```

The LLM can only choose categories, colors and locations from fixed lists, because the SQL search uses exact matching. Invalid values are checked again in Python and fall back to `other` / `unknown`.

### `app.py`

Connects everything in a Gradio web interface:

```python
item       = extract_item(user_text, report_type)
item_id    = insert_item(item)
candidates = get_candidates(item)
matches    = find_top_matches(item, candidates)
```

- **Report an item** tab: describe an item and see the extracted fields and the top 3 matches.
- **Database** tab: see all reports (hidden features are never displayed) and mark a report as matched.

## How to Run

### Google Colab

1. Open `LostLink_Demo.ipynb` in Colab.
2. Add your Groq key under **Secrets** (key icon on the left) with the name `GROQ_API_KEY`. A free key is available at https://console.groq.com.
3. Run the cells in order and open the `*.gradio.live` link.

### Locally

```bash
pip install -r requirements.txt
cp .env.example .env        # then add your GROQ_API_KEY
python app.py               # open http://127.0.0.1:7860
```

The database is created automatically and filled with demo records on first start. To reset it, delete `data/lostlink.db`.

### Tests and evaluation

```bash
python tests/test_llm.py             # offline unit tests
python tests/test_pipeline_live.py   # end-to-end test (needs API key)
python eval/run_eval.py --offline    # baselines only
python eval/run_eval.py              # full evaluation (needs API key)
```



## Limitations and Future Work

- The SQL filter is strict: a wrong category or location removes the correct report. Related categories (e.g. `bag` / `backpack`) could be allowed.
- Weekday dates ("last Friday") are sometimes resolved one day off; adding the weekday to the prompt would help.
- Very vague reports can still get a match; the system could ask the user for more details instead.
- Reports are sent to an external API, and the prototype has no user login. Ownership should be verified by staff before an item is handed over.

## Team

| Member | Main file | Responsibility |
|---|---|---|
| Member 1 | `database.py` | SQLite table design, insertion and candidate retrieval, demo data |
| Member 2 | `llm.py` | LLM extraction, scoring and ranking, tests, evaluation |
| Member 3 | `app.py` | Gradio interface, integration, Colab notebook |

Never upload API keys or personal data.
