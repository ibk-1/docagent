# docagent: when does a small LLM need tools to read an invoice?

A tool-using LLM agent that extracts structured data from **German and English invoices**, runs **locally** with llama.cpp, and is measured field by field against exact ground truth.

```
"Zahlbar innerhalb von 10 Tagen mit 2 % Skonto oder innerhalb von 30 Tagen netto."
Rechnungsdatum 11.02.26   →   {"invoice_date": "2026-02-11", "due_date": "2026-03-13", ...}
```

**Why this project exists.** My [on-device LLM benchmark](https://github.com/ibk-1/ondevice-llm-bench) found that small models read German well but fail at calendar arithmetic: most errors of Qwen2.5 1.5B were relative dates like "übermorgen" turned into the wrong day. Invoices are full of exactly this kind of work: payment terms in days, early-payment discounts, VAT that has to be computed, IBAN and VAT ID checksums. This project tests the obvious fix. Let the model read, and let deterministic tools do the arithmetic and the checks.

> **Status: work in progress (milestone 1 of 4).** The dataset, tools, evaluation and a rule-based baseline are done and tested. LLM and agent results come next. No numbers below are invented: every table is produced by `scripts/run_eval.py`.

## Plan

| Milestone | What | Status |
|---|---|---|
| 1 | Synthetic DE/EN invoice set with exact labels, deterministic tools, field-level evaluation, rule baseline, tests + CI | done |
| 2 | Plain LLM extraction with local models (Qwen2.5 1.5B / 7B, Llama 3.2) via `llama-server` | next |
| 3 | Agent: tool calling (date, amount, totals, IBAN/VAT checks), self-correction loop, routing from a small to a larger local model, step-by-step traces | |
| 4 | MCP server (`extract_invoice`, `resolve_due_date`, `check_totals`, ...), FastAPI endpoint, Docker, a small set of realistic documents, write-up | |

## The test set

`data/invoices.jsonl`: 300 invoices (about 60 % German, 40 % English), generated from known records with `scripts/make_dataset.py` (seed 7). No real company or personal data. Each document carries tags so results can be broken down by difficulty:

| Tag | What makes it hard |
|---|---|
| `terms_relative` | due date given as "innerhalb von 14 Tagen" / "within 30 days": needs date arithmetic |
| `terms_skonto` | early-payment discount: the due date is the *net* period, not the discount period |
| `terms_immediate` | "sofort fällig" / "due upon receipt": due date = invoice date |
| `vat_not_printed` | only net, rate and gross are printed: the VAT amount has to be computed |
| `reverse_charge` | EU B2B invoice with 0 % VAT |
| `distractor_dates` | delivery and order dates next to the invoice date |
| `date_text` | "14. Oktober 2026", "October 14, 2026" |
| `de_numbers_in_en` | English invoice with German number format ("1.234,56 EUR") |

Every gold label is checked by the tests: IBANs and German VAT IDs have valid checksums, net + VAT = gross, and every printed value appears in the text.

## Results so far

Rule-based baseline (regular expressions + the deterministic tools), 300 invoices:

| Method | Exact match (all 12 fields) | Weakest field |
|---|---|---|
| Rules + tools | 74.3 % | VAT amount 74.3 % (fails whenever it is not printed) |

The rules get every printed field right because the synthetic layouts are regular. This is the known limit of a generated test set, and the reason milestone 4 adds a small set of realistic, messier documents. Where rules break even here is anything that needs reasoning over the document, such as computing a VAT amount that is not printed.

## Run it

```bash
pip install -e ".[dev]"
pytest -q                                   # 16 tests
python scripts/make_dataset.py              # writes data/invoices.jsonl
python scripts/run_eval.py --method rules   # baseline

# LLM (milestone 2): start a local model, then evaluate it
llama-server -m models/qwen2.5-1.5b-instruct-q4_k_m.gguf -ngl 99 --port 8080
python scripts/run_eval.py --method plain --name qwen2.5-1.5b-q4
```

| File | Purpose |
|---|---|
| `src/docagent/schema.py` | the 12 extracted fields (pydantic) |
| `src/docagent/generate.py` | synthetic invoice generator with ground truth |
| `src/docagent/tools.py` | dates, payment terms, amounts, totals, IBAN and VAT ID checks |
| `src/docagent/evaluate.py` | field-level scoring, breakdown by tag, error examples |
| `src/docagent/baselines.py` | rule-based extractor |
| `src/docagent/llm.py` | plain LLM extraction via any OpenAI-compatible endpoint, JSON-schema constrained |

## License

MIT
