"""
Evaluate LostLink against simple baselines.

Run from the repository root:
    python eval/run_eval.py --offline                  # baselines only, no API key needed
    python eval/run_eval.py                            # current llm.py on the main set
    python eval/run_eval.py --version v1 --runs 3      # v1 snapshot (before the fixes), 3 runs
    python eval/run_eval.py --version v2 --runs 3      # v2 snapshot (with the fixes), 3 runs
    python eval/run_eval.py --set heldout --runs 3     # held-out queries (eval/heldout_data.py)

v1 and v2 are frozen copies (eval/llm_v1.py, eval/llm_v2.py) that use the original
fine-grained categories. "current" is llm.py in the repository, which uses broad
categories, so the categories of the evaluation data are mapped for it.

A query counts as correct when the system's prediction equals the expected
found record, or when it predicts "no match" for a query without a match.
The LLM pipeline predicts the top candidate if its score is >= ACCEPT_SCORE,
otherwise "no match". Results are written to eval/results_<version>_<set>.json.
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
from eval_data import FOUND_POOL, QUERIES, TODAY

ACCEPT_SCORE = 60
FIELDS = ("item_category", "main_color", "general_location", "event_date")
METRICS = ("accuracy", "hit_at_1", "recall_at_3", "rejection")


# ---------- setup ----------

def load_set(name):
    """Return (found_pool, queries, today) for the main or the held-out set."""
    if name == "main":
        return FOUND_POOL, QUERIES, TODAY

    try:
        import heldout_data
    except ImportError:
        sys.exit("eval/heldout_data.py not found - write the held-out queries first.")

    if not heldout_data.HELDOUT_QUERIES:
        sys.exit("eval/heldout_data.py has no queries yet - add them to HELDOUT_QUERIES first.")

    pool = {**FOUND_POOL, **getattr(heldout_data, "EXTRA_FOUND", {})}
    return pool, heldout_data.HELDOUT_QUERIES, getattr(heldout_data, "TODAY", TODAY)


def to_broad_categories(pool, queries):
    """Map the fine-grained categories of the evaluation data to llm.py's broad ones."""
    from eval_data import BROAD_CATEGORIES

    pool = {k: {**item, "item_category": BROAD_CATEGORIES[item["item_category"]]} for k, item in pool.items()}
    queries = [
        {**q, "gold": {**q["gold"], "item_category": BROAD_CATEGORIES.get(q["gold"]["item_category"])}}
        for q in queries
    ]
    return pool, queries


def has_gold_fields(queries):
    """The SQL baselines need the expected category and location of every query."""
    return all(q["gold"]["item_category"] for q in queries)


def build_db(pool):
    db_path = Path(tempfile.mkdtemp()) / "eval.db"
    database.init_db(db_path)
    key_by_id = {}
    for key, item in pool.items():
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
        "hit_at_1": sum(r["pred"] == r["expected"] for r in pos) / len(pos) if pos else None,
        "recall_at_3": sum(r["expected"] in [k for k, _ in r["ranked"][:3]] for r in pos) / len(pos) if pos else None,
        "rejection": sum(r["pred"] is None for r in neg) / len(neg) if neg else None,
    }


def with_threshold(name, rows, tau=None):
    """Apply a similarity threshold; if tau is None, pick the one that maximises accuracy."""
    def apply(t):
        return [{**r, "pred": r["ranked"][0][0] if r["ranked"] and r["ranked"][0][1] >= t else None}
                for r in rows]

    if tau is None:
        options = sorted({0.0} | {s for r in rows for _, s in r["ranked"][:1]})
        tau = max(options, key=lambda t: summarize(name, apply(t))["accuracy"])

    trial = apply(tau)
    result = summarize(name, trial)
    result["threshold"] = round(tau, 3)
    return result, trial


def mean_std(values):
    values = [v for v in values if v is not None]
    if not values:
        return None
    return {"mean": statistics.mean(values), "std": statistics.stdev(values) if len(values) > 1 else 0.0}


# ---------- systems ----------

def run_sql_only(queries, db_path, key_by_id):
    rows = []
    for q in queries:
        candidates = database.get_candidates(gold_item(q), db_path=db_path)
        ranked = [(key_by_id[c["id"]], None) for c in candidates]
        rows.append({"expected": q["match"], "ranked": ranked, "pred": ranked[0][0] if ranked else None})
    return summarize("SQL filter only (most recent)", rows), rows


def run_tfidf(queries, pool, db_path, key_by_id, use_sql, tau=None):
    tfidf = TfIdf([item["raw_description"] for item in pool.values()])
    rows = []
    for q in queries:
        if use_sql:
            keys = [key_by_id[c["id"]] for c in database.get_candidates(gold_item(q), db_path=db_path)]
        else:
            keys = list(pool)
        ranked = sorted(((k, tfidf.similarity(q["text"], pool[k]["raw_description"])) for k in keys),
                        key=lambda x: x[1], reverse=True)
        rows.append({"expected": q["match"], "ranked": ranked})
    name = "SQL filter + TF-IDF rerank" if use_sql else "TF-IDF over all records"
    return with_threshold(name, rows, tau)


class DailyLimitReached(Exception):
    pass


def call_with_retry(fn, *args, **kwargs):
    for attempt in range(6):
        try:
            return fn(*args, **kwargs)
        except ValueError:
            raise  # e.g. "not a lost item" - not a temporary error
        except Exception as error:
            # The free tier has a daily token limit; waiting a minute does not help.
            if "tokens per day" in str(error):
                raise DailyLimitReached(str(error)) from error
            if attempt == 5:
                raise
            wait = 10 * (attempt + 1)
            print(f"  retrying in {wait}s after error: {error}")
            time.sleep(wait)


def possible_leaks(reason, query_text, candidates):
    """Words of a candidate's hidden feature that appear in the reason but not in the query.

    Only a hint for manual review: shared words are not always a leak.
    """
    query_words = set(tokenize(query_text))
    reason_words = set(tokenize(reason))
    flagged = set()
    for c in candidates:
        for word in tokenize(c.get("hidden_feature") or ""):
            if len(word) >= 3 and word in reason_words and word not in query_words:
                flagged.add(word)
    return sorted(flagged)


def run_llm(model, queries, db_path, key_by_id, gold_fields, today):
    rows, field_hits, field_total = [], Counter(), Counter()
    extract_times, score_times, candidate_hits = [], [], []

    for i, q in enumerate(queries, 1):
        print(f"  [{i}/{len(queries)}] {q['tag']}")

        if gold_fields:
            item = gold_item(q)
        else:
            start = time.perf_counter()
            try:
                item = call_with_retry(model.extract_item, q["text"], "lost", today=today)
            except ValueError as error:
                # v2 rejects texts that do not look like a lost item: no search, no match.
                extract_times.append(time.perf_counter() - start)
                if q["match"]:
                    candidate_hits.append(False)
                rows.append({"tag": q["tag"], "tags": q.get("tags", []), "text": q["text"],
                             "expected": q["match"], "rejected": str(error), "extracted": {},
                             "candidates": [], "ranked": [], "reasons": [], "leaks": [], "pred": None})
                continue
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
        matches = call_with_retry(model.find_top_matches, item, candidates, top_k=3, min_score=30)
        if candidates:
            score_times.append(time.perf_counter() - start)

        ranked = [(key_by_id[m["id"]], m["score"]) for m in matches]
        pred = ranked[0][0] if ranked and ranked[0][1] >= ACCEPT_SCORE else None
        reasons = [m["reason"] for m in matches]
        rows.append({
            "tag": q["tag"],
            "tags": q.get("tags", []),
            "text": q["text"],
            "expected": q["match"],
            "extracted": {f: item.get(f) for f in (*FIELDS, "feature_description", "hidden_feature")},
            "search": {k: item.get(k) for k in ("search_categories", "search_locations", "date_window_days")},
            "candidates": candidate_keys,
            "ranked": ranked,
            "reasons": reasons,
            "leaks": [possible_leaks(r, q["text"], candidates) for r in reasons],
            "pred": pred,
        })

    name = "Gold fields + LLM rerank" if gold_fields else "LostLink (LLM extract + SQL + LLM rerank)"
    result = summarize(name, rows)
    result["candidate_recall"] = sum(candidate_hits) / len(candidate_hits) if candidate_hits else None
    if not gold_fields:
        result["field_accuracy"] = {f: field_hits[f] / field_total[f] for f in FIELDS if field_total[f]}
        result["extract_latency_s"] = statistics.mean(extract_times)
    result["score_latency_s"] = statistics.mean(score_times) if score_times else None
    return result, rows


def run_repeated(model, queries, db_path, key_by_id, gold_fields, runs, today):
    """Run the LLM pipeline several times and aggregate the metrics.

    If the daily API limit is reached, the completed runs are kept.
    """
    results, details = [], []
    for run in range(1, runs + 1):
        print(f"\nRun {run}/{runs}{' (gold fields)' if gold_fields else ''}")
        try:
            result, rows = run_llm(model, queries, db_path, key_by_id, gold_fields, today)
        except DailyLimitReached as error:
            print(f"\nDaily API limit reached during run {run}; keeping {len(results)} complete run(s).\n{error}")
            break
        results.append(result)
        details.append(rows)

    if not results:
        sys.exit("No complete run - try again when the daily limit has reset.")

    summary = {"system": results[0]["system"], "runs": len(results)}
    for key in (*METRICS, "candidate_recall", "extract_latency_s", "score_latency_s"):
        summary[key] = mean_std([r.get(key) for r in results])
    if not gold_fields and results[0]["field_accuracy"]:
        summary["field_accuracy"] = {f: mean_std([r["field_accuracy"].get(f) for r in results])
                                     for f in results[0]["field_accuracy"]}
    summary["per_run"] = results
    return summary, details


# ---------- main ----------

def fmt(value):
    if value is None:
        return "   -  "
    if isinstance(value, dict):
        return f"{value['mean']:.2f}±{value['std']:.2f}"
    return f"{value:.2f}"


def print_table(results):
    print("\n{:<45} {:>10} {:>10} {:>10} {:>10}".format("System", "Acc", "Hit@1", "R@3", "Rej"))
    for r in results:
        print("{:<45} {:>10} {:>10} {:>10} {:>10}".format(r["system"], *(fmt(r[m]) for m in METRICS)))


def group_by_tag(queries, details):
    """Number of correct predictions per query type, per system (LLM runs averaged)."""
    tags = sorted({t for q in queries for t in q.get("tags", [])})
    if not tags:
        return {}

    def correct(rows, i):
        return rows[i]["pred"] == rows[i]["expected"]

    groups = {}
    for tag in tags:
        idx = [i for i, q in enumerate(queries) if tag in q.get("tags", [])]
        groups[tag] = {"n": len(idx)}
        for name, rows in details.items():
            runs = rows if rows and isinstance(rows[0], list) else [rows]
            groups[tag][name] = statistics.mean(sum(correct(r, i) for i in idx) for r in runs)
    return groups


def print_groups(groups):
    if not groups:
        return
    systems = [k for k in next(iter(groups.values())) if k != "n"]
    print("\nCorrect / total per query type (LLM: mean over runs)")
    print("{:<22} ".format("Type") + " ".join(f"{s:>10}" for s in systems))
    for tag, g in groups.items():
        print("{:<22} ".format(tag) + " ".join(f"{g[s]:>6.1f}/{g['n']:<3}" for s in systems))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--offline", action="store_true", help="only run the baselines")
    parser.add_argument("--version", choices=["v1", "v2", "current"], default="current",
                        help="v1 = before the fixes, v2 = with the fixes (both fine-grained "
                             "categories), current = llm.py in the repository (broad categories)")
    parser.add_argument("--set", choices=["main", "heldout"], default="main")
    parser.add_argument("--runs", type=int, default=1, help="repeat the LLM pipeline this many times")
    parser.add_argument("--gold", action="store_true", help="also run the gold-fields ablation")
    args = parser.parse_args()

    pool, queries, today = load_set(args.set)
    if args.version == "current":
        pool, queries = to_broad_categories(pool, queries)
    db_path, key_by_id = build_db(pool)
    n_pos = sum(1 for q in queries if q["match"])
    print(f"Set '{args.set}': {len(pool)} found records, {len(queries)} lost queries "
          f"({n_pos} with a match, {len(queries) - n_pos} without), today = {today}")

    # On the held-out set the TF-IDF threshold tuned on the main set is reused.
    tau = None
    if args.set == "heldout":
        main_db, main_keys = build_db(FOUND_POOL)
        tau = run_tfidf(QUERIES, FOUND_POOL, main_db, main_keys, use_sql=False)[0]["threshold"]
        print(f"TF-IDF threshold from the main set: {tau}")

    baselines = [("tfidf", run_tfidf(queries, pool, db_path, key_by_id, use_sql=False, tau=tau))]
    if has_gold_fields(queries):
        baselines += [
            ("sql_only", run_sql_only(queries, db_path, key_by_id)),
            ("sql_tfidf", run_tfidf(queries, pool, db_path, key_by_id, use_sql=True, tau=tau)),
        ]
    else:
        print("No expected fields for the queries: SQL-based baselines are skipped.")

    results, details = [], {}
    for name, (result, rows) in baselines:
        results.append(result)
        details[name] = rows

    model = None
    if not args.offline:
        if args.version == "v1":
            import llm_v1 as model
        elif args.version == "v2":
            import llm_v2 as model
        else:
            import llm as model
        print(f"\nPipeline {args.version}, model: {model.MODEL}")

        for name, gold_fields in [("lostlink", False)] + ([("gold_llm", True)] if args.gold else []):
            summary, rows = run_repeated(model, queries, db_path, key_by_id, gold_fields, args.runs, today)
            results.append(summary)
            details[name] = rows

    print_table(results)
    for r in results:
        extra = {k: v for k, v in r.items() if k not in ("system", "per_run", *METRICS)}
        if extra:
            print(f"{r['system']}: {json.dumps(extra, default=str)}")

    groups = group_by_tag(queries, details)
    print_groups(groups)

    # Offline runs have no LLM results and must not overwrite a real results file.
    name = "offline" if args.offline else args.version
    out = Path(__file__).with_name(f"results_{name}_{args.set}.json")
    out.write_text(json.dumps({"version": args.version, "set": args.set, "today": today,
                               "model": model.MODEL if model else None,
                               "results": results, "by_type": groups, "details": details},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to {out}")


if __name__ == "__main__":
    main()
