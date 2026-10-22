"""
Evaluate LostLink against simple baselines on eval/eval_data.py.

Run from the repository root:
    python eval/run_eval.py --offline    # baselines only, no API key needed
    python eval/run_eval.py              # baselines + LLM pipeline (needs GROQ_API_KEY)

A query counts as correct when the system's prediction equals the expected
found record, or when it predicts "no match" for a query without a match.
The LLM pipeline predicts the top candidate if its score is >= ACCEPT_SCORE,
otherwise "no match". Results are written to eval/results.json.
"""

import argparse
import json
import math
import re
import statistics
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import database
import llm
from eval_data import FOUND_POOL, QUERIES, TODAY

ACCEPT_SCORE = 60
FIELDS = ("item_category", "main_color", "general_location", "event_date")


# ---------- setup ----------

def build_db():
    db_path = Path(tempfile.mkdtemp()) / "eval.db"
    database.init_db(db_path)
    key_by_id = {}
    for key, item in FOUND_POOL.items():
        key_by_id[database.insert_item(item, db_path)] = key
    return db_path, key_by_id


def gold_item(query):
    """The query with the expected fields, as if extraction were perfect."""
    gold = query["gold"]
    return {
        "report_type": "lost",
        "raw_description": query["text"],
        "item_category": gold["item_category"],
        "main_color": gold["main_color"],
        # An ambiguous location cannot be filled in by hand either.
        "general_location": gold["general_location"] or "other",
        "event_date": gold["event_date"],
    }


# ---------- TF-IDF baseline ----------

STOPWORDS = set("""a an the i my me it its is was were on in at of to and or with
there this that has have had near by for from be been one some""".split())


def tokenize(text):
    return [t for t in re.findall(r"\w+", text.lower()) if t not in STOPWORDS]


class TfIdf:
    def __init__(self, documents):
        self.n = len(documents)
        self.df = Counter(t for doc in documents for t in set(tokenize(doc)))

    def vector(self, text):
        tf = Counter(tokenize(text))
        return {t: c * math.log((1 + self.n) / (1 + self.df.get(t, 0))) for t, c in tf.items()}

    def similarity(self, a, b):
        va, vb = self.vector(a), self.vector(b)
        dot = sum(w * vb.get(t, 0) for t, w in va.items())
        norm = math.sqrt(sum(w * w for w in va.values())) * math.sqrt(sum(w * w for w in vb.values()))
        return dot / norm if norm else 0.0


# ---------- metrics ----------

def summarize(name, rows):
    """rows: list of {"expected", "ranked": [(key, score), ...], "pred"}."""
    pos = [r for r in rows if r["expected"]]
    neg = [r for r in rows if not r["expected"]]
    return {
        "system": name,
        "accuracy": sum(r["pred"] == r["expected"] for r in rows) / len(rows),
        "hit_at_1": sum(r["pred"] == r["expected"] for r in pos) / len(pos),
        "recall_at_3": sum(r["expected"] in [k for k, _ in r["ranked"][:3]] for r in pos) / len(pos),
        "rejection": sum(r["pred"] is None for r in neg) / len(neg),
    }


def with_best_threshold(name, rows):
    """Pick the similarity threshold that maximises accuracy (an upper bound for the baseline)."""
    best = None
    for tau in sorted({0.0} | {s for r in rows for _, s in r["ranked"][:1]}):
        trial = [{**r, "pred": r["ranked"][0][0] if r["ranked"] and r["ranked"][0][1] >= tau else None}
                 for r in rows]
        result = summarize(name, trial)
        if best is None or result["accuracy"] > best[0]["accuracy"]:
            best = (result, trial, tau)
    result, trial, tau = best
    result["threshold"] = round(tau, 3)
    return result, trial


# ---------- systems ----------

def run_sql_only(db_path, key_by_id):
    rows = []
    for q in QUERIES:
        candidates = database.get_candidates(gold_item(q), db_path=db_path)
        ranked = [(key_by_id[c["id"]], None) for c in candidates]
        rows.append({"expected": q["match"], "ranked": ranked, "pred": ranked[0][0] if ranked else None})
    return summarize("SQL filter only (most recent)", rows), rows


def run_tfidf(db_path, key_by_id, use_sql):
    tfidf = TfIdf([item["raw_description"] for item in FOUND_POOL.values()])
    rows = []
    for q in QUERIES:
        if use_sql:
            keys = [key_by_id[c["id"]] for c in database.get_candidates(gold_item(q), db_path=db_path)]
        else:
            keys = list(FOUND_POOL)
        ranked = sorted(((k, tfidf.similarity(q["text"], FOUND_POOL[k]["raw_description"])) for k in keys),
                        key=lambda x: x[1], reverse=True)
        rows.append({"expected": q["match"], "ranked": ranked})
    name = "SQL filter + TF-IDF rerank" if use_sql else "TF-IDF over all records"
    return with_best_threshold(name, rows)


def call_with_retry(fn, *args, **kwargs):
    for attempt in range(4):
        try:
            return fn(*args, **kwargs)
        except Exception as error:
            if attempt == 3:
                raise
            print(f"  retrying after error: {error}")
            time.sleep(5 * (attempt + 1))


def run_llm(db_path, key_by_id, gold_fields):
    rows, field_hits, field_total = [], Counter(), Counter()
    extract_times, score_times, candidate_hits = [], [], []

    for i, q in enumerate(QUERIES, 1):
        print(f"[{i}/{len(QUERIES)}] {q['tag']}")

        if gold_fields:
            item = gold_item(q)
        else:
            start = time.perf_counter()
            item = call_with_retry(llm.extract_item, q["text"], "lost", today=TODAY)
            extract_times.append(time.perf_counter() - start)
            for field in FIELDS:
                if q["gold"][field] is not None:
                    field_total[field] += 1
                    field_hits[field] += item[field] == q["gold"][field]

        candidates = database.get_candidates(item, db_path=db_path)
        candidate_keys = [key_by_id[c["id"]] for c in candidates]
        if q["match"]:
            candidate_hits.append(q["match"] in candidate_keys)

        start = time.perf_counter()
        matches = call_with_retry(llm.find_top_matches, item, candidates, top_k=3, min_score=30)
        if candidates:
            score_times.append(time.perf_counter() - start)

        ranked = [(key_by_id[m["id"]], m["score"]) for m in matches]
        pred = ranked[0][0] if ranked and ranked[0][1] >= ACCEPT_SCORE else None
        rows.append({
            "tag": q["tag"],
            "text": q["text"],
            "expected": q["match"],
            "extracted": {f: item.get(f) for f in FIELDS},
            "candidates": candidate_keys,
            "ranked": ranked,
            "reasons": [m["reason"] for m in matches],
            "pred": pred,
        })

    name = "Gold fields + LLM rerank" if gold_fields else "LostLink (LLM extract + SQL + LLM rerank)"
    result = summarize(name, rows)
    result["candidate_recall"] = sum(candidate_hits) / len(candidate_hits)
    if not gold_fields:
        result["field_accuracy"] = {f: field_hits[f] / field_total[f] for f in FIELDS}
        result["extract_latency_s"] = statistics.mean(extract_times)
    result["score_latency_s"] = statistics.mean(score_times)
    return result, rows


# ---------- main ----------

def print_table(results):
    print("\n{:<45} {:>6} {:>6} {:>6} {:>6}".format("System", "Acc", "Hit@1", "R@3", "Rej"))
    for r in results:
        print("{:<45} {:>6.2f} {:>6.2f} {:>6.2f} {:>6.2f}".format(
            r["system"], r["accuracy"], r["hit_at_1"], r["recall_at_3"], r["rejection"]))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="only run the baselines")
    args = parser.parse_args()

    db_path, key_by_id = build_db()
    n_pos = sum(1 for q in QUERIES if q["match"])
    print(f"{len(FOUND_POOL)} found records, {len(QUERIES)} lost queries "
          f"({n_pos} with a match, {len(QUERIES) - n_pos} without)")

    results, details = [], {}
    for name, (result, rows) in [
        ("sql_only", run_sql_only(db_path, key_by_id)),
        ("tfidf", run_tfidf(db_path, key_by_id, use_sql=False)),
        ("sql_tfidf", run_tfidf(db_path, key_by_id, use_sql=True)),
    ]:
        results.append(result)
        details[name] = rows

    if not args.offline:
        print(f"\nModel: {llm.MODEL}")
        for name, gold_fields in [("lostlink", False), ("gold_llm", True)]:
            result, rows = run_llm(db_path, key_by_id, gold_fields)
            results.append(result)
            details[name] = rows

    print_table(results)
    for r in results:
        extra = {k: v for k, v in r.items() if k not in ("system", "accuracy", "hit_at_1", "recall_at_3", "rejection")}
        if extra:
            print(f"{r['system']}: {extra}")

    out = Path(__file__).with_name("results.json")
    out.write_text(json.dumps({"model": llm.MODEL, "results": results, "details": details},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
