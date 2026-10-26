from docagent.tools import (
    add_days, check_totals, de_vat_id_check_digit, iban_check_digits, iban_valid,
    parse_amount, parse_date, resolve_due_date, vat_id_valid,
)


def test_parse_date_formats():
    assert parse_date("14.10.2026") == "2026-10-14"
    assert parse_date("14.10.26") == "2026-10-14"
    assert parse_date("2026-10-14") == "2026-10-14"
    assert parse_date("14/10/2026") == "2026-10-14"
    assert parse_date("14. Oktober 2026") == "2026-10-14"
    assert parse_date("3. März 2026") == "2026-03-03"
    assert parse_date("14 October 2026") == "2026-10-14"
    assert parse_date("October 14, 2026") == "2026-10-14"
    assert parse_date("Okt. 14 2026") == "2026-10-14"
    assert parse_date("10/14/2026", dayfirst=False) == "2026-10-14"


def test_parse_date_rejects_garbage():
    assert parse_date("") is None
    assert parse_date("Kundennummer 48213") is None
    assert parse_date("31.02.2026") is None  # no such day


def test_due_date_terms():
    d = "2026-10-05"
    assert resolve_due_date(d, "Zahlbar innerhalb von 14 Tagen ohne Abzug.") == "2026-10-19"
    assert resolve_due_date(d, "Payment is due within 30 days of the invoice date.") == "2026-11-04"
    assert resolve_due_date(d, "Der Rechnungsbetrag ist sofort nach Erhalt ohne Abzug fällig.") == d
    assert resolve_due_date(d, "Payment due upon receipt.") == d
    assert resolve_due_date(d, "Bitte überweisen Sie den Betrag bis zum 30.11.2026.") == "2026-11-30"


def test_due_date_skonto_uses_net_period():
    d = "2026-10-05"
    assert resolve_due_date(d, "Zahlbar innerhalb von 10 Tagen mit 2 % Skonto oder innerhalb von 30 Tagen netto.") == "2026-11-04"
    assert resolve_due_date(d, "2% discount if paid within 10 days, otherwise net 30 days.") == "2026-11-04"


def test_add_days_crosses_month_and_year():
    assert add_days("2026-12-20", 14) == "2027-01-03"


def test_parse_amount():
    assert parse_amount("1.234,56 €") == "1234.56"
    assert parse_amount("€1,234.56") == "1234.56"
    assert parse_amount("EUR 12,345.00") == "12345.00"
    assert parse_amount("980") == "980.00"
    assert parse_amount("1 234,50") == "1234.50"
    assert parse_amount("12.503,19 EUR") == "12503.19"
    assert parse_amount("n/a") is None


def test_check_totals():
    r = check_totals("100.00", "19", vat="19.00", gross="119.00")
    assert r["vat_ok"] and r["gross_ok"]
    assert check_totals("10506.88", "19")["expected_vat_amount"] == "1996.31"
    assert check_totals("100", "7", gross="110.00")["gross_ok"] is False


def test_iban():
    assert iban_valid("DE89 3704 0044 0532 0130 00")  # well-known example IBAN
    assert not iban_valid("DE89 3704 0044 0532 0130 01")
    bban = "370400440532013000"
    assert "DE" + iban_check_digits("DE", bban) + bban == "DE89370400440532013000"


def test_de_vat_id():
    first8 = "13649382"
    vat = f"DE{first8}{de_vat_id_check_digit(first8)}"
    assert vat_id_valid(vat)
    assert vat_id_valid(vat[:2] + " " + vat[2:5] + " " + vat[5:8] + " " + vat[8:])
    wrong = vat[:-1] + str((int(vat[-1]) + 1) % 10)
    assert not vat_id_valid(wrong)
