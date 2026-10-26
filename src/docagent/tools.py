"""Deterministic helpers.

Small LLMs read documents well but are unreliable at calendar arithmetic,
number formats and checksums (see the on-device LLM benchmark this project
builds on). These functions do that part exactly. The agent calls them as
tools, and the evaluator uses them to normalise values.
"""
from __future__ import annotations

import re
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

MONTHS = {
    # German
    "januar": 1, "jänner": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10, "november": 11,
    "dezember": 12,
    # English
    "january": 1, "february": 2, "march": 3, "may": 5, "june": 6, "july": 7,
    "october": 10, "december": 12,
}
# Abbreviations ("Okt.", "Oct", "Sept.")
for _name, _num in list(MONTHS.items()):
    MONTHS.setdefault(_name[:3], _num)
MONTHS["sept"] = 9


# --------------------------------------------------------------------------- dates
def parse_date(text: str, dayfirst: bool = True) -> str | None:
    """Turn a printed date into YYYY-MM-DD.

    Handles "14.10.2026", "14.10.26", "2026-10-14", "14/10/2026",
    "14. Oktober 2026", "14 October 2026", "October 14, 2026", "Okt. 14 2026".
    Slashed dates are read day-first unless ``dayfirst=False`` (US style).
    Returns None when nothing date-like is found.
    """
    if not text:
        return None
    s = text.strip().lower().replace(",", " ")
    s = re.sub(r"\s+", " ", s)

    m = re.search(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b", s)
    if m:
        return _iso(int(m[1]), int(m[2]), int(m[3]))

    m = re.search(r"\b(\d{1,2})[./](\d{1,2})[./](\d{2,4})\b", s)
    if m:
        a, b, y = int(m[1]), int(m[2]), _year(m[3])
        d, mo = (a, b) if dayfirst else (b, a)
        return _iso(y, mo, d)

    # 14. Oktober 2026 / 14 October 2026
    m = re.search(r"\b(\d{1,2})\.? ([a-zäöü]+)\.? (\d{4})\b", s)
    if m and m[2] in MONTHS:
        return _iso(int(m[3]), MONTHS[m[2]], int(m[1]))

    # October 14 2026
    m = re.search(r"\b([a-zäöü]+)\.? (\d{1,2})(?:st|nd|rd|th)? (\d{4})\b", s)
    if m and m[1] in MONTHS:
        return _iso(int(m[3]), MONTHS[m[1]], int(m[2]))
    return None


def _year(y: str) -> int:
    y_int = int(y)
    return 2000 + y_int if y_int < 100 else y_int


def _iso(y: int, m: int, d: int) -> str | None:
    try:
        return date(y, m, d).isoformat()
    except ValueError:
        return None


def add_days(iso_date: str, days: int) -> str:
    """Add a number of days to an ISO date."""
    return (date.fromisoformat(iso_date) + timedelta(days=int(days))).isoformat()


_TERM_DAYS = re.compile(
    r"(\d{1,3})\s*(?:kalender)?(?:tage|tagen|tag|days|day)\b", re.IGNORECASE
)
_IMMEDIATE = re.compile(
    r"sofort|umgehend|ohne abzug sofort|upon receipt|on receipt|immediately|due now",
    re.IGNORECASE,
)


def resolve_due_date(invoice_date: str, payment_terms: str) -> str | None:
    """Compute the due date from the invoice date and the payment terms.

    "Zahlbar innerhalb von 14 Tagen" -> invoice date + 14 days,
    "payable within 30 days net" -> + 30, "sofort fällig" / "due upon receipt" -> same day.
    With an early-payment discount ("10 Tage 2 % Skonto, 30 Tage netto") the
    longest period is the due date; the shorter one only earns the discount.
    An explicit date in the terms ("zahlbar bis 30.11.2026") wins.
    Returns None if the terms cannot be interpreted.
    """
    if not invoice_date or not payment_terms:
        return None
    explicit = parse_date(payment_terms)
    if explicit:
        return explicit
    periods = [int(m[1]) for m in _TERM_DAYS.finditer(payment_terms)]
    if periods:
        return add_days(invoice_date, max(periods))
    if _IMMEDIATE.search(payment_terms):
        return invoice_date
    return None


# ------------------------------------------------------------------------- amounts
def parse_amount(text: str) -> str | None:
    """Normalise a printed amount to a string with two decimals.

    "1.234,56 €" -> "1234.56", "€1,234.56" -> "1234.56", "EUR 980" -> "980.00",
    "1 234,50" -> "1234.50". The last separator followed by exactly two digits
    is treated as the decimal separator.
    """
    if text is None:
        return None
    s = re.sub(r"[^\d,.\-]", "", str(text).replace(" ", " ").replace(" ", ""))
    if not re.search(r"\d", s):
        return None
    m = re.search(r"[.,](\d{2})$", s)
    if m:
        whole = re.sub(r"[.,]", "", s[: m.start()])
        s = f"{whole}.{m[1]}"
    else:
        s = re.sub(r"[.,]", "", s)
    try:
        return str(Decimal(s).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))
    except InvalidOperation:
        return None


def check_totals(net: str, vat_rate: str, vat: str | None = None, gross: str | None = None) -> dict:
    """Check net, VAT and gross against each other (tolerance one cent).

    Returns the expected VAT and gross amounts and whether the given ones match,
    so the agent can fill in a missing amount or catch a misread one.
    """
    n = Decimal(parse_amount(net))
    rate = Decimal(str(vat_rate).replace("%", "").replace(",", ".").strip())
    exp_vat = (n * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    exp_gross = n + exp_vat
    out = {"expected_vat_amount": str(exp_vat), "expected_gross_amount": str(exp_gross)}
    cent = Decimal("0.01")
    if vat is not None:
        out["vat_ok"] = abs(Decimal(parse_amount(vat)) - exp_vat) <= cent
    if gross is not None:
        out["gross_ok"] = abs(Decimal(parse_amount(gross)) - exp_gross) <= cent
    return out


# ------------------------------------------------------------------ identifiers
def normalize_iban(iban: str | None) -> str | None:
    if not iban:
        return None
    return re.sub(r"\s+", "", iban).upper()


def iban_valid(iban: str) -> bool:
    """ISO 13616 checksum (mod 97)."""
    s = normalize_iban(iban) or ""
    if not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{11,30}", s):
        return False
    rearranged = s[4:] + s[:4]
    digits = "".join(str(int(c, 36)) for c in rearranged)
    return int(digits) % 97 == 1


def iban_check_digits(country: str, bban: str) -> str:
    """Compute the two IBAN check digits for a country code and BBAN."""
    digits = "".join(str(int(c, 36)) for c in bban + country + "00")
    return f"{98 - int(digits) % 97:02d}"


def de_vat_id_check_digit(first8: str) -> int:
    """Check digit of a German USt-IdNr (ISO 7064, MOD 11,10)."""
    product = 10
    for ch in first8:
        total = (int(ch) + product) % 10 or 10
        product = (2 * total) % 11
    check = 11 - product
    return 0 if check == 10 else check


def vat_id_valid(vat_id: str) -> bool:
    """Validate a VAT ID. German IDs get the full checksum, others a format check."""
    s = re.sub(r"[\s.\-]", "", vat_id or "").upper()
    if s.startswith("DE"):
        if not re.fullmatch(r"DE\d{9}", s):
            return False
        return de_vat_id_check_digit(s[2:10]) == int(s[10])
    return bool(re.fullmatch(r"[A-Z]{2}[0-9A-Z]{8,12}", s))
