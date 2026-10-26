"""Synthetic German and English invoices with exact ground truth.

Every document is generated from a known record, so the correct answer for
every field is known without manual labelling, and no real company or person
data is used. The generator deliberately includes the cases that trip models
up in practice:

* relative payment terms ("zahlbar innerhalb von 14 Tagen") that need date arithmetic
* early-payment discounts ("10 Tage 2 % Skonto, 30 Tage netto")
* distractor dates (delivery date, order date) and distractor numbers (customer number)
* invoices where the VAT amount is not printed and must be computed
* German number formats inside English invoices ("1.234,56 EUR")
* reverse-charge invoices with 0 % VAT
"""
from __future__ import annotations

import random
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal

from .tools import add_days, de_vat_id_check_digit, iban_check_digits

# ----------------------------------------------------------------- vocabularies
PREFIX = ["Nordlicht", "Elbtal", "Hanse", "Alster", "Weser", "Isar", "Rheinblick", "Spreewerk",
          "Bergmann", "Falkenstein", "Lindgrün", "Seewind", "Heidekamp", "Moorland", "Sonnfeld",
          "Lachsbach", "Kranich", "Eichenhof", "Brückner", "Wattblick"]
TRADE = {
    "Logistik": ["Palettentransport Hamburg–Bremen", "Lagerung pro Stellplatz und Monat", "Expresszustellung"],
    "Software": ["Lizenz Business-Plan (monatlich)", "Implementierung Schnittstelle", "Support-Stunden"],
    "Maschinenbau": ["Wartung Förderband", "Ersatzteil Antriebsriemen", "Montage vor Ort"],
    "Consulting": ["Beratungstag Prozessanalyse", "Workshop Datenstrategie", "Reisekostenpauschale"],
    "Druckerei": ["Flyer DIN A5, 4/4-farbig", "Visitenkarten 500 Stk.", "Plakat DIN A1"],
    "Elektrotechnik": ["Installation Unterverteilung", "Prüfung nach DGUV V3", "Material Kleinteile"],
    "Datenservice": ["Datenbereinigung pro 1.000 Datensätze", "Cloud-Speicher 1 TB", "Reporting-Paket"],
    "Medien": ["Videoproduktion Imagefilm", "Fotoshooting halbtags", "Schnitt und Farbkorrektur"],
}
TRADE_EN = {
    "Logistik": ["Pallet transport Hamburg to Bremen", "Storage per pallet per month", "Express delivery"],
    "Software": ["Business plan licence (monthly)", "Interface implementation", "Support hours"],
    "Maschinenbau": ["Conveyor maintenance", "Spare part drive belt", "On-site installation"],
    "Consulting": ["Consulting day process analysis", "Data strategy workshop", "Travel expenses (flat)"],
    "Druckerei": ["Flyers A5, full colour", "Business cards 500 pcs", "Poster A1"],
    "Elektrotechnik": ["Distribution board installation", "DGUV V3 safety inspection", "Small parts"],
    "Datenservice": ["Data cleansing per 1,000 records", "Cloud storage 1 TB", "Reporting package"],
    "Medien": ["Corporate video production", "Photo shoot (half day)", "Editing and colour grading"],
}
LEGAL_DE = ["GmbH", "GmbH & Co. KG", "AG", "UG (haftungsbeschränkt)", "e.K."]
BUYER_DE = ["Stadtwerke Lindenau GmbH", "Kaufhaus Brenner KG", "Praxis Dr. Albers", "Hafenbistro Möller",
            "Autohaus Petersen GmbH", "Bäckerei Ohlsen", "Ingenieurbüro Kranz", "Tischlerei Hauke GmbH",
            "Gartenbau Riedel", "Hotel Seeblick GmbH", "Steuerkanzlei Wolter & Partner", "Kita Sonnenkinder e.V."]
BUYER_EN = [("Northbay Trading Ltd", "GB"), ("Van der Berg Logistics B.V.", "NL"), ("Lumière Studio SAS", "FR"),
            ("Kowalski Systems Sp. z o.o.", "PL"), ("Fjord Analytics AS", "NO"), ("Sole Mio Foods S.r.l.", "IT"),
            ("Brightline Media Ltd", "IE"), ("Andersson Bygg AB", "SE")]
STREETS = ["Hafenstraße", "Lindenallee", "Am Markt", "Bahnhofstraße", "Kaiserkai", "Mühlenweg", "Schulstraße",
           "Gartenweg", "Industriestraße", "Elbchaussee", "Neuer Wall", "Ringstraße"]
CITIES = [("20457", "Hamburg"), ("28195", "Bremen"), ("10115", "Berlin"), ("80331", "München"),
          ("50667", "Köln"), ("24103", "Kiel"), ("23552", "Lübeck"), ("30159", "Hannover"),
          ("04109", "Leipzig"), ("70173", "Stuttgart")]
CITIES_EN = {"GB": ("London EC1A 1BB", "United Kingdom"), "NL": ("1012 AB Amsterdam", "Netherlands"),
             "FR": ("75002 Paris", "France"), "PL": ("00-001 Warszawa", "Poland"), "NO": ("0150 Oslo", "Norway"),
             "IT": ("20121 Milano", "Italy"), "IE": ("Dublin 2", "Ireland"), "SE": ("111 22 Stockholm", "Sweden")}
EU = {"NL", "FR", "PL", "IT", "IE", "SE"}  # reverse charge possible for B2B within the EU

MONTHS_DE = ["Januar", "Februar", "März", "April", "Mai", "Juni", "Juli", "August", "September",
             "Oktober", "November", "Dezember"]
MONTHS_EN = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
             "October", "November", "December"]


# -------------------------------------------------------------------- formatting
def fmt_date(d: date, lang: str, style: str) -> str:
    if style == "iso":
        return d.isoformat()
    if lang == "de":
        if style == "text":
            return f"{d.day}. {MONTHS_DE[d.month - 1]} {d.year}"
        if style == "short":
            return d.strftime("%d.%m.%y")
        return d.strftime("%d.%m.%Y")
    if style == "text":
        return f"{d.day} {MONTHS_EN[d.month - 1]} {d.year}"
    if style == "us_text":
        return f"{MONTHS_EN[d.month - 1]} {d.day}, {d.year}"
    return d.strftime("%d/%m/%Y")


def fmt_amount(x: Decimal, style: str) -> str:
    q = x.quantize(Decimal("0.01"))
    whole, frac = f"{q:.2f}".split(".")
    groups = f"{int(whole):,}"
    if style in ("de_eur", "de_sym"):
        num = groups.replace(",", ".") + "," + frac
        return f"{num} €" if style == "de_sym" else f"{num} EUR"
    if style == "en_sym":
        return f"€{groups}.{frac}"
    return f"EUR {groups}.{frac}"


def money(x) -> Decimal:
    return Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# ------------------------------------------------------------------ identifiers
def make_iban(rng: random.Random) -> tuple[str, str]:
    bban = "".join(str(rng.randint(0, 9)) for _ in range(18))
    iban = "DE" + iban_check_digits("DE", bban) + bban
    printed = " ".join(iban[i:i + 4] for i in range(0, len(iban), 4))
    return iban, printed


def make_de_vat_id(rng: random.Random) -> tuple[str, str]:
    first8 = str(rng.randint(1, 9)) + "".join(str(rng.randint(0, 9)) for _ in range(7))
    vat = f"DE{first8}{de_vat_id_check_digit(first8)}"
    printed = vat if rng.random() < 0.6 else f"DE {vat[2:5]} {vat[5:8]} {vat[8:]}"
    return vat, printed


def make_invoice_number(rng: random.Random, d: date) -> str:
    style = rng.choice(["re", "slash", "inv", "short"])
    if style == "re":
        return f"RE-{d.year}-{rng.randint(100, 9999):05d}"
    if style == "slash":
        return f"{d.year}/{rng.randint(1, 4999):04d}"
    if style == "inv":
        return f"INV-{rng.randint(10000, 99999)}"
    return f"R{d.strftime('%y%m')}-{rng.randint(1, 999):03d}"


# ---------------------------------------------------------------------- record
def make_record(rng: random.Random, lang: str) -> dict:
    trade = rng.choice(list(TRADE))
    seller = f"{rng.choice(PREFIX)} {trade} {rng.choice(LEGAL_DE)}"
    inv_date = date(2026, 1, 5) + timedelta(days=rng.randint(0, 288))
    if lang == "de":
        buyer, buyer_country = rng.choice(BUYER_DE), "DE"
    else:
        buyer, buyer_country = rng.choice(BUYER_EN)
    reverse_charge = lang == "en" and buyer_country in EU and rng.random() < 0.35
    # 7 % (reduced rate) only for printed matter; everything else is 19 %
    vat_rate = 0 if reverse_charge else (rng.choice([7, 19]) if trade == "Druckerei" else 19)

    items = []
    names = TRADE[trade] if lang == "de" else TRADE_EN[trade]
    for name in rng.sample(names, k=rng.randint(1, len(names))):
        qty = rng.choice([1, 1, 2, 3, 4, 5, 8, 10, 12, 20])
        unit = money(rng.uniform(15, 1800))
        items.append((name, qty, unit, money(unit * qty)))
    net = money(sum(i[3] for i in items))
    vat = money(net * vat_rate / 100)
    gross = net + vat

    seller_city = rng.choice(CITIES)
    iban, iban_printed = make_iban(rng)
    vat_id, vat_id_printed = make_de_vat_id(rng)

    term_kind = rng.choices(["explicit", "relative", "skonto", "immediate"], weights=[3, 4, 2, 1])[0]
    days = rng.choice([7, 10, 14, 21, 30, 45, 60]) if term_kind == "relative" else 30
    if term_kind == "explicit":
        due = add_days(inv_date.isoformat(), rng.choice([14, 21, 30]))
    elif term_kind == "immediate":
        due = inv_date.isoformat()
    else:
        due = add_days(inv_date.isoformat(), days)

    return {
        "lang": lang, "trade": trade, "items": items, "term_kind": term_kind, "days": days,
        "reverse_charge": reverse_charge, "buyer_country": buyer_country,
        "iban_printed": iban_printed, "vat_id_printed": vat_id_printed,
        "delivery_date": inv_date - timedelta(days=rng.randint(1, 20)),
        "order_date": inv_date - timedelta(days=rng.randint(21, 60)),
        "customer_no": f"{rng.randint(10000, 99999)}",
        "seller_addr": f"{rng.choice(STREETS)} {rng.randint(1, 120)}, {' '.join(seller_city)}",
        "seller_city": seller_city[1],
        "bank": f"{rng.choice(['Sparkasse', 'Volksbank', 'Commerzbank', 'Deutsche Bank', 'GLS Bank'])} {seller_city[1]}",
        "buyer_addr": (f"{rng.choice(STREETS)} {rng.randint(1, 120)}\n{' '.join(rng.choice(CITIES))}"
                       if lang == "de" else "\n".join(CITIES_EN[buyer_country])),
        "gold": {
            "invoice_number": make_invoice_number(rng, inv_date),
            "invoice_date": inv_date.isoformat(),
            "due_date": due,
            "seller_name": seller,
            "seller_vat_id": vat_id,
            "buyer_name": buyer,
            "currency": "EUR",
            "net_amount": str(net),
            "vat_rate": str(vat_rate),
            "vat_amount": str(vat),
            "gross_amount": str(gross),
            "iban": iban,
        },
    }


# ---------------------------------------------------------------------- render
def render(rec: dict, rng: random.Random) -> tuple[str, list[str]]:
    g, lang = rec["gold"], rec["lang"]
    tags = [lang, f"terms_{rec['term_kind']}"]

    date_style = rng.choice(["num", "num", "text", "short", "iso"] if lang == "de"
                            else ["num", "text", "us_text", "iso"])
    if date_style in ("text", "us_text"):
        tags.append("date_text")
    if lang == "de":
        amt_style = rng.choice(["de_eur", "de_sym"])
    else:
        amt_style = rng.choice(["en_sym", "en_code", "en_code", "de_eur"])
        if amt_style == "de_eur":
            tags.append("de_numbers_in_en")
    show_vat_line = not rec["reverse_charge"] and rng.random() > 0.2
    if not rec["reverse_charge"] and not show_vat_line:
        tags.append("vat_not_printed")
    if rec["reverse_charge"]:
        tags.append("reverse_charge")
    distractors = rng.random() < 0.75
    if distractors:
        tags.append("distractor_dates")

    D = lambda iso_or_date: fmt_date(  # noqa: E731
        date.fromisoformat(iso_or_date) if isinstance(iso_or_date, str) else iso_or_date, lang, date_style)
    A = lambda x: fmt_amount(Decimal(x), amt_style)  # noqa: E731
    inv_date, due = g["invoice_date"], g["due_date"]
    rate = g["vat_rate"]

    if lang == "de":
        terms = {
            "explicit": f"Bitte überweisen Sie den Betrag bis zum {D(due)}.",
            "relative": f"Zahlbar innerhalb von {rec['days']} Tagen nach Rechnungsdatum ohne Abzug.",
            "skonto": "Zahlbar innerhalb von 10 Tagen mit 2 % Skonto oder innerhalb von 30 Tagen netto.",
            "immediate": "Der Rechnungsbetrag ist sofort nach Erhalt ohne Abzug fällig.",
        }[rec["term_kind"]]
    else:
        terms = {
            "explicit": f"Please pay by {D(due)}.",
            "relative": f"Payment is due within {rec['days']} days of the invoice date.",
            "skonto": "2% discount if paid within 10 days, otherwise net 30 days.",
            "immediate": "Payment due upon receipt.",
        }[rec["term_kind"]]

    item_lines = []
    for name, qty, unit, total in rec["items"]:
        item_lines.append(f"{name:<45} {qty:>3} x {A(unit):>14} {A(total):>14}")

    layout = rng.choice(["a", "b"])
    tags.append(f"layout_{lang}_{layout}")
    L: list[str] = []
    if lang == "de":
        footer = [
            "",
            f"{g['seller_name']} · {rec['seller_addr']}",
            f"Bankverbindung: {rec['bank']} · IBAN {rec['iban_printed']}",
            f"USt-IdNr.: {rec['vat_id_printed']} · Amtsgericht {rec['seller_city']} HRB {rng.randint(10000, 199999)}",
        ]
        if layout == "a":
            L += [g["seller_name"], rec["seller_addr"], "", g["buyer_name"], rec["buyer_addr"], "",
                  "RECHNUNG", "",
                  f"Rechnungsnummer: {g['invoice_number']}",
                  f"Rechnungsdatum: {D(inv_date)}"]
            if distractors:
                L += [f"Lieferdatum: {D(rec['delivery_date'])}", f"Kundennummer: {rec['customer_no']}"]
            L += ["", f"{'Leistung':<45} {'Menge':>3}   {'Einzelpreis':>14} {'Gesamt':>14}", *item_lines, "",
                  f"Nettobetrag: {A(g['net_amount'])}"]
            if show_vat_line:
                L.append(f"zzgl. {rate} % USt.: {A(g['vat_amount'])}")
            L.append(f"Gesamtbetrag: {A(g['gross_amount'])}")
            if not show_vat_line:
                L.append(f"Im Gesamtbetrag sind {rate} % USt. enthalten.")
            L += ["", terms]
        else:
            L += [f"{g['seller_name']} | {rec['seller_addr']}", "",
                  f"An: {g['buyer_name']}, {rec['buyer_addr'].replace(chr(10), ', ')}", ""]
            if distractors:
                L.append(f"Ihre Bestellung vom {D(rec['order_date'])}, Kunden-Nr. {rec['customer_no']}")
            L += [f"Rechnung Nr. {g['invoice_number']} vom {D(inv_date)}", "", *item_lines, "",
                  f"Summe netto {A(g['net_amount'])}"]
            if show_vat_line:
                L.append(f"MwSt. {rate}% {A(g['vat_amount'])}")
                L.append(f"Rechnungsbetrag {A(g['gross_amount'])}")
            else:
                L.append(f"Rechnungsbetrag {A(g['gross_amount'])} (inkl. {rate}% MwSt.)")
            L += ["", f"Zahlungsziel: {terms}"]
        L += footer
    else:
        if rec["reverse_charge"]:
            vat_line = "VAT 0% – reverse charge: VAT to be accounted for by the recipient (Art. 196 VAT Directive)."
        elif show_vat_line:
            vat_line = f"VAT {rate}%: {A(g['vat_amount'])}"
        else:
            vat_line = None  # printed after the total instead
        incl = [] if vat_line or rec["reverse_charge"] else [f"The total includes {rate}% German VAT."]
        if layout == "a":
            L += [g["seller_name"], rec["seller_addr"], "Germany", "", "INVOICE", "",
                  f"Invoice No.: {g['invoice_number']}", f"Invoice date: {D(inv_date)}"]
            if distractors:
                L += [f"Delivery date: {D(rec['delivery_date'])}", f"Customer ID: {rec['customer_no']}"]
            L += ["", "Bill to:", g["buyer_name"], rec["buyer_addr"], "",
                  f"{'Description':<45} {'Qty':>3}   {'Unit price':>14} {'Amount':>14}", *item_lines, "",
                  f"Subtotal: {A(g['net_amount'])}", *([vat_line] if vat_line else []),
                  f"Total due: {A(g['gross_amount'])}", *incl, "",
                  f"Payment terms: {terms}",
                  f"Bank details: {rec['bank']}, IBAN {rec['iban_printed']}",
                  f"VAT ID: {rec['vat_id_printed']}"]
        else:
            L += [f"{g['seller_name']} — {rec['seller_addr']}, Germany",
                  f"VAT reg. no. {rec['vat_id_printed']}", "",
                  f"Invoice # {g['invoice_number']}", f"Date of issue: {D(inv_date)}"]
            if distractors:
                L.append(f"Order date: {D(rec['order_date'])} (ref. {rec['customer_no']})")
            L += [f"Customer: {g['buyer_name']}, {rec['buyer_addr'].replace(chr(10), ', ')}", "",
                  *item_lines, "",
                  f"Net total {A(g['net_amount'])}", *([vat_line] if vat_line else []),
                  f"Amount due {A(g['gross_amount'])}", *incl, "",
                  terms, f"Pay to IBAN {rec['iban_printed']}"]
    return "\n".join(L), tags


def generate(n: int = 300, seed: int = 7, de_share: float = 0.6) -> list[dict]:
    """Generate ``n`` invoices. Same seed, same dataset."""
    rng = random.Random(seed)
    docs = []
    for i in range(n):
        lang = "de" if rng.random() < de_share else "en"
        rec = make_record(rng, lang)
        text, tags = render(rec, rng)
        docs.append({"id": f"inv-{i:04d}", "lang": lang, "tags": tags, "text": text, "gold": rec["gold"]})
    return docs
