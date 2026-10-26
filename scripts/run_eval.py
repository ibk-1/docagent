"""Run an extractor over the test set and write a results JSON.

    python scripts/run_eval.py --method rules
    python scripts/run_eval.py --method plain --url http://127.0.0.1:8080 --name qwen2.5-1.5b-q4
"""
import argparse
import json
import time
from pathlib import Path

from docagent.baselines import extract_rules
from docagent.evaluate import summarize

ap = argparse.ArgumentParser()
ap.add_argument("--method", choices=["rules", "plain"], required=True)
ap.add_argument("--data", default="data/invoices.jsonl")
ap.add_argument("--url", default="http://127.0.0.1:8080")
ap.add_argument("--name", default=None, help="label for the results file, e.g. the model name")
ap.add_argument("--limit", type=int, default=None)
a = ap.parse_args()

docs = [json.loads(line) for line in open(a.data, encoding="utf-8")][: a.limit]
results = []
for i, d in enumerate(docs, 1):
    if a.method == "rules":
        t0 = time.perf_counter()
        pred = extract_rules(d["text"])
        out = {"pred": pred, "latency_s": time.perf_counter() - t0}
    else:
        from docagent.llm import extract_plain
        out = extract_plain(d["text"], a.url)
    results.append({"id": d["id"], "tags": d["tags"], "gold": d["gold"], **out})
    if i % 25 == 0:
        print(f"{i}/{len(docs)}")

name = a.name or a.method
summary = summarize(results)
Path("results").mkdir(exist_ok=True)
Path("results/raw").mkdir(exist_ok=True)
json.dump(summary, open(f"results/summary_{name}.json", "w"), indent=2, ensure_ascii=False)
json.dump(results, open(f"results/raw/predictions_{name}.json", "w"), indent=1, ensure_ascii=False, default=str)
print(json.dumps({k: summary[k] for k in ("n", "valid_json", "exact_match", "median_latency_s")}, indent=2))
print(json.dumps(summary["field_accuracy"], indent=2))
