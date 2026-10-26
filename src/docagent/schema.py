"""The structured record we extract from an invoice."""
from __future__ import annotations

from typing import Optional

from pydantic import BaseModel, Field

# Order matters: it is the column order in every results table.
FIELDS: list[str] = [
    "invoice_number",
    "invoice_date",
    "due_date",
    "seller_name",
    "seller_vat_id",
    "buyer_name",
    "currency",
    "net_amount",
    "vat_rate",
    "vat_amount",
    "gross_amount",
    "iban",
]


class Invoice(BaseModel):
    """Normalised invoice fields.

    Dates are ISO (YYYY-MM-DD), amounts are strings with exactly two decimals
    ("1234.50"), the VAT rate is a percentage string ("19", "7", "0"), IBAN and
    VAT ID are upper case without spaces.
    """

    invoice_number: Optional[str] = Field(None, description="Invoice number as printed")
    invoice_date: Optional[str] = Field(None, description="Invoice date, YYYY-MM-DD")
    due_date: Optional[str] = Field(None, description="Payment due date, YYYY-MM-DD")
    seller_name: Optional[str] = Field(None, description="Company that issued the invoice")
    seller_vat_id: Optional[str] = Field(None, description="Seller VAT ID, e.g. DE123456789")
    buyer_name: Optional[str] = Field(None, description="Company the invoice is addressed to")
    currency: Optional[str] = Field(None, description="ISO currency code, e.g. EUR")
    net_amount: Optional[str] = Field(None, description="Total before VAT, e.g. 1234.50")
    vat_rate: Optional[str] = Field(None, description="VAT rate in percent, e.g. 19")
    vat_amount: Optional[str] = Field(None, description="VAT amount, e.g. 234.56")
    gross_amount: Optional[str] = Field(None, description="Total including VAT")
    iban: Optional[str] = Field(None, description="Seller IBAN without spaces")
