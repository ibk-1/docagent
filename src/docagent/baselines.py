"""A rule-based extractor (regular expressions + the deterministic tools).

This is the classic pre-LLM approach and the bar any LLM pipeline has to
clear. It is written against the label vocabulary of common German and
English invoices, not against the generator's code, but because the test
set is synthetic it will look better here than on real documents. The README
reports it with that caveat.
"""
from __future__ import annotations

import re

from .tools import parse_amount, parse_date, resolve_due_date

AMT = r"((?:€|EUR)?\s?-?[\d.,\s]*\d[.,]\d{2}\s?(?:€|EUR)?)"


def _find(patterns: list[str], text: str, flags=re.IGNORECASE | re.MULTILINE) -> str | None:
    for p in patterns:
        m = re.search(p, text, flags)
        if m:
            return m.group(1).strip()
    return None


def extract_rules(text: str) -> dict:
    out: dict = {}
    out["invoice_number"] = _find([
        r"Rechnungs(?:nummer|-Nr\.?)\s*:?\s*([A-Z0-9][\w/\-]+)",
        r"Rechnung Nr\.?\s*([A-Z0-9][\w/\-]+)",
        r"Invoice (?:No\.?|Number|#)\s*:?\s*([A-Z0-9][\w/\-]+)",
    ], text)

    inv_date_raw = _find([
        r"^Rechnungsdatum\s*:?\s*(.+)$",
        r"Rechnung Nr\.?\s*\S+\s+vom\s+(.+)$",
        r"^(?:Invoice date|Date of issue)\s*:?\s*(.+)$",
    ], text)
    out["invoice_date"] = parse_date(inv_date_raw) if inv_date_raw else None

    terms = _find([r"((?:zahlbar|bitte überweisen|der rechnungsbetrag ist|payment|please pay|2% discount)[^\n]*)"], text)
    out["due_date"] = resolve_due_date(out["invoice_date"], terms) if out["invoice_date"] and terms else None

    lines = [line for line in text.splitlines() if line.strip()]
    first = lines[0] if lines else ""
    out["seller_name"] = re.split(r"\s[|—]\s", first)[0].strip() or None

    vat_id = _find([r"(?:USt-IdNr\.?|VAT ID|VAT reg\. no\.)\s*:?\s*([A-Z]{2}[\s\d]{8,14}\d)"], text)
    out["seller_vat_id"] = re.sub(r"\s", "", vat_id) if vat_id else None

    buyer = _find([r"^Bill to:\s*\n(.+)$", r"^Customer:\s*([^,\n]+)", r"^An:\s*([^,\n]+)"], text)
    if buyer is None and len(lines) > 2:
        buyer = lines[2]  # German letter layout: buyer block follows the sender block
    out["buyer_name"] = buyer
    out["currency"] = "EUR" if re.search(r"€|EUR", text) else None

    net = _find([rf"(?:Nettobetrag|Summe netto|Subtotal|Net total)\s*:?\s*{AMT}"], text)
    vat = _find([rf"(?:USt\.|MwSt\. \d+\s?%|VAT \d+%)\s*:?\s*{AMT}"], text)
    gross = _find([rf"(?:Gesamtbetrag|Rechnungsbetrag|Total due|Amount due)\s*:?\s*{AMT}"], text)
    rate = _find([r"(\d{1,2})\s?%\s*(?:USt|MwSt|German VAT)", r"(?:MwSt\.|VAT|USt\.?)\s*(\d{1,2})\s?%"], text)
    out["net_amount"] = parse_amount(net) if net else None
    out["gross_amount"] = parse_amount(gross) if gross else None
    out["vat_rate"] = rate
    out["vat_amount"] = parse_amount(vat) if vat else None

    iban = _find([r"IBAN\s*:?\s*([A-Z]{2}\d{2}(?:\s?[A-Z0-9]{4}){3,7}(?:\s?[A-Z0-9]{1,4})?)"], text)
    out["iban"] = re.sub(r"\s", "", iban) if iban else None
    return out
