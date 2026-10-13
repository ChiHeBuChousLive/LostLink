# LostLink

LostLink is a simple **LLM + database lost-and-found system**. Users describe a lost or found item in natural language. The system extracts structured information, searches the database, and returns the possible matches.

## Technologies Used

- **Development environment:** Google Colab
- **Model:** (Wait to be choosed)
- **Database:** SQLite
- **User interface:** Gradio(Can be changed)
- **Collaboration and submission:** GitHub
- **Core non-trivial feature:** Structured information extraction + SQL candidate retrieval + LLM-based semantic reranking

## Project Flow

（This is an initial project plan and may change during development！！！）

```text
User description
      ↓
LLM extracts structured attributes(json)
      ↓
Save report to database
      ↓
SQL retrieves possible candidates(use general attribute)
      ↓
LLM compares and scores candidates(use all information)
      ↓
Return Top matches
```

A `lost` report only searches `found` records, and a `found` report only searches `lost` records.

## Project Structure

(This is an initial project plan and may change during development !!!!)

```text
LostLink/
├── app.py
├── database.py
├── llm.py
├── data/
│   └── lostlink.db
│   └── seed_data.ipynb
├── LostLink_Demo.ipynb
├── requirements.txt
└── README.md
```

### `database.py`

Responsible for SQLite operations:

- Create the `items` table
- Insert lost/found reports
- Retrieve candidate records with SQL
- Update record status

Main functions like(can be changed during development):

```python
init_db()
insert_item(item)
get_candidates(item, limit=10)
update_status(item_id, status)
```

### `llm.py`

Responsible for LLM extraction and matching:

- Convert user descriptions into structured JSON
- Compare a report with candidate records
- Give each candidate a score and reason
- Sort and return the Top matches

Main functions(can be changed during development):

```python
extract_item(user_text, report_type)
score_candidates(item, candidates)
find_top_matches(item, candidates, top_k=?)
```

### `app.py`

Responsible for the Gradio(or something else) interface and final integration:

```python
item = extract_item(user_text, report_type)
item_id = insert_item(item)
candidates = get_candidates(item)
matches = find_top_matches(item, candidates)
```

The final integration happens in `app.py`(or can be changed):

```text
        app.py
       ↙      ↘
database.py  llm.py
```

### `LostLink_Demo.ipynb`

Used in Google Colab to:

1. Clone the GitHub repository
2. Install dependencies
3. Set the API key
4. Run `app.py`

## Team Responsibilities

### Member 1: Database

**Main file:** `database.py`

- Design the SQLite table
- Implement insertion and candidate retrieval
- Prepare sample lost/found records
- Test database functions

### Member 2: LLM and Matching

**Main file:** `llm.py`

Use functions to realize this process

```text
User description
→ LLM extracts structured attributes as JSON
→ database.py uses general attributes to retrieve candidates with SQL
→ All retrieved candidates are sent to the LLM in one request
→ LLM compares detailed features, scores, and ranks all candidates
→ Top matches are returned
```

### Member 3: Interface and Integration

**Main files:** `app.py` 

- Build the Gradio page(can use something else)
- Connect `database.py` and `llm.py`
- Display extracted fields and matches
- Maybe responsible the pdf report

All members should test the final integrated system together.

## Shared Data Format

All files should use the same item format:（subjected to be changed）

```python
item = {
    "report_type": "lost",
    "raw_description": "...",
    "item_category": "water_bottle",
    "main_color": "black",
    "general_location": "angstrom_laboratory",
    "event_date": "2026-10-11",
    "detailed_location": "...",
    "feature_description": "...",
    "hidden_feature": "...",
    "status": "open"
}
```

Agree on function inputs and outputs before developing separately. Never upload API keys or personal data.
