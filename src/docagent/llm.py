"""Plain LLM extraction: the model reads the invoice and returns all fields at once.

Talks to any OpenAI-compatible chat endpoint. Locally that is
``llama-server`` from llama.cpp (``http://127.0.0.1:8080``). The output is
constrained to the Invoice JSON schema, so failures are about content, not
about broken JSON.

This is the baseline the agent (tools + self-correction) has to beat.
"""
from __future__ import annotations

import json
import time
import urllib.request

from .schema import Invoice

SYSTEM = (
    "You extract data from invoices. Answer only with JSON that matches the schema. "
    "Use null for anything that is not in the document."
)

INSTRUCTIONS = """Extract these fields from the invoice below.

- invoice_number: as printed
- invoice_date: the date the invoice was issued, as YYYY-MM-DD (not the delivery or order date)
- due_date: the date payment is due, as YYYY-MM-DD. If the terms give a number of days, count from the invoice date. With an early-payment discount, use the final net due date.
- seller_name: the company that issued the invoice
- seller_vat_id: the seller's VAT ID (USt-IdNr.) without spaces
- buyer_name: the company the invoice is addressed to
- currency: ISO code, e.g. EUR
- net_amount, vat_amount, gross_amount: numbers with two decimals and a dot, e.g. 1234.50. If the VAT amount is not printed, compute it.
- vat_rate: percent as a number, e.g. 19
- iban: the seller's IBAN without spaces

Invoice:
\"\"\"
{text}
\"\"\""""


def chat(base_url: str, messages: list[dict], model: str = "local", schema: dict | None = None,
         tools: list[dict] | None = None, temperature: float = 0.0, timeout: float = 300) -> dict:
    """One chat-completions request. Returns the raw response JSON."""
    body: dict = {"model": model, "messages": messages, "temperature": temperature}
    if schema is not None:
        body["response_format"] = {"type": "json_schema",
                                   "json_schema": {"name": "invoice", "schema": schema, "strict": True}}
    if tools:
        body["tools"] = tools
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read())


def extract_plain(text: str, base_url: str = "http://127.0.0.1:8080", model: str = "local") -> dict:
    """Extract all fields in one call. Returns {"pred", "latency_s", "usage"}."""
    t0 = time.perf_counter()
    resp = chat(
        base_url,
        [{"role": "system", "content": SYSTEM},
         {"role": "user", "content": INSTRUCTIONS.format(text=text)}],
        model=model,
        schema=Invoice.model_json_schema(),
    )
    latency = time.perf_counter() - t0
    content = resp["choices"][0]["message"].get("content") or ""
    try:
        pred = json.loads(content)
        if not isinstance(pred, dict):
            pred = None
    except json.JSONDecodeError:
        pred = None
    return {"pred": pred, "latency_s": latency, "usage": resp.get("usage", {}), "raw": content}
