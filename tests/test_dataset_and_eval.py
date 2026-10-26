from decimal import ROUND_HALF_UP, Decimal

from docagent.evaluate import normalize, score_document, summarize
from docagent.generate import generate
from docagent.schema import FIELDS
from docagent.tools import iban_valid, vat_id_valid


def test_generation_is_deterministic():
    assert generate(20, seed=1) == generate(20, seed=1)
    assert generate(20, seed=1) != generate(20, seed=2)


def test_gold_labels_are_consistent():
    for d in generate(200, seed=3):
        g = d["gold"]
        assert set(g) == set(FIELDS)
        assert iban_valid(g["iban"])
        assert vat_id_valid(g["seller_vat_id"])
        net, vat, gross = (Decimal(g[k]) for k in ("net_amount", "vat_amount", "gross_amount"))
        assert net + vat == gross
        assert vat == (net * Decimal(g["vat_rate"]) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        assert g["due_date"] >= g["invoice_date"]
        # values that are printed must appear in the text
        assert g["invoice_number"] in d["text"]
        assert g["seller_name"] in d["text"]
        assert g["buyer_name"] in d["text"]


def test_hard_cases_are_present():
    tags = {t for d in generate(300, seed=7) for t in d["tags"]}
    for t in ["terms_relative", "terms_skonto", "terms_immediate", "vat_not_printed",
              "reverse_charge", "date_text", "de_numbers_in_en", "distractor_dates"]:
        assert t in tags


def test_normalize_only_removes_formatting():
    assert normalize("net_amount", "1.234,50 €") == "1234.50"
    assert normalize("vat_rate", "19 %") == "19"
    assert normalize("vat_rate", 19.0) == "19"
    assert normalize("iban", "de89 3704 0044 0532 0130 00") == "DE89370400440532013000"
    assert normalize("due_date", "14.10.2026") == "2026-10-14"
    assert normalize("due_date", "within 14 days") is None  # unresolved terms stay wrong
    assert normalize("buyer_name", "  Bäckerei  Ohlsen ") == "bäckerei ohlsen"


def test_score_and_summary():
    d = generate(1, seed=5)[0]
    perfect = score_document(d["gold"], d["gold"])
    assert all(perfect.values())
    s = summarize([{"id": "a", "tags": ["x"], "gold": d["gold"], "pred": d["gold"]},
                   {"id": "b", "tags": ["x"], "gold": d["gold"], "pred": None}])
    assert s["exact_match"] == 0.5 and s["valid_json"] == 0.5
    assert s["exact_match_by_tag"]["x"] == 0.5
