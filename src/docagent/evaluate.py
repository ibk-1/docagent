"""Field-level scoring of extracted invoices against the ground truth."""
from __future__ import annotations

import re
from collections import defaultdict
from decimal import Decimal, InvalidOperation

from .schema import FIELDS
from .tools import normalize_iban, parse_amount, parse_date

DATE_FIELDS = {"invoice_date", "due_date"}
AMOUNT_FIELDS = {"net_amount", "vat_amount", "gross_amount"}


def normalize(field: str, value) -> str | None:
    """Bring a value into the canonical form used by the gold labels.

    Normalisation only removes formatting differences (spaces, case, "€" vs
    "EUR", "19 %" vs "19"). It never fixes a wrong value: an unresolved
    relative date or a misread amount still counts as an error.
    """
    if value is None:
        return None
    s = str(value).strip()
    if s == "" or s.lower() in {"null", "none", "n/a"}:
        return None
    if field in DATE_FIELDS:
        return parse_date(s) if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", s) else s
    if field in AMOUNT_FIELDS:
        return parse_amount(s)
    if field == "vat_rate":
        s = s.replace("%", "").replace(",", ".").strip()
        try:
            d = Decimal(s)
        except InvalidOperation:
            return None
        return str(int(d)) if d == d.to_integral_value() else str(d.normalize())
    if field in {"iban", "seller_vat_id"}:
        return re.sub(r"[\s.\-]", "", s).upper()
    if field == "currency":
        return {"€": "EUR", "EURO": "EUR"}.get(s.upper(), s.upper())
    # names and invoice numbers: ignore case and repeated whitespace only
    return re.sub(r"\s+", " ", s).casefold()


def score_document(pred: dict | None, gold: dict) -> dict[str, bool]:
    pred = pred or {}
    return {f: normalize(f, pred.get(f)) == normalize(f, gold.get(f)) for f in FIELDS}


def summarize(results: list[dict]) -> dict:
    """Aggregate per-document results.

    Each result needs ``gold``, ``pred`` (dict or None if the output was not
    valid JSON), ``tags`` and optionally ``latency_s`` and ``steps``.
    """
    n = len(results)
    field_hits = defaultdict(int)
    tag_hits: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    exact = valid = 0
    errors: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        if r.get("pred") is not None:
            valid += 1
        s = score_document(r.get("pred"), r["gold"])
        for f, ok in s.items():
            field_hits[f] += ok
            if not ok and len(errors[f]) < 5:
                errors[f].append({"id": r.get("id"), "gold": r["gold"].get(f),
                                  "pred": (r.get("pred") or {}).get(f)})
        all_ok = all(s.values())
        exact += all_ok
        for t in r.get("tags", []):
            tag_hits[t][0] += all_ok
            tag_hits[t][1] += 1
    lat = sorted(r["latency_s"] for r in results if r.get("latency_s") is not None)
    return {
        "n": n,
        "valid_json": valid / n if n else 0.0,
        "exact_match": exact / n if n else 0.0,
        "field_accuracy": {f: field_hits[f] / n for f in FIELDS} if n else {},
        "exact_match_by_tag": {t: h / c for t, (h, c) in sorted(tag_hits.items())},
        "median_latency_s": lat[len(lat) // 2] if lat else None,
        "error_examples": dict(errors),
    }
