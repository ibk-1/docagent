"""Write the synthetic test set to data/invoices.jsonl (deterministic)."""
import argparse
import json
from pathlib import Path

from docagent.generate import generate

ap = argparse.ArgumentParser()
ap.add_argument("--n", type=int, default=300)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--out", default="data/invoices.jsonl")
a = ap.parse_args()
docs = generate(a.n, a.seed)
Path(a.out).parent.mkdir(parents=True, exist_ok=True)
with open(a.out, "w", encoding="utf-8") as f:
    for d in docs:
        f.write(json.dumps(d, ensure_ascii=False) + "\n")
print(f"wrote {len(docs)} invoices to {a.out}")
