"""Document information extraction via Gemini (real mode) or demo sidecars."""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

from . import categorizer
from .config import (
    ALLOWED_MIME, CATEGORIES, DEMO_MODE, GEMINI_API_KEY, GEMINI_MODEL,
    SAMPLE_DIR, demo_active,
)

EXTRACTION_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "doc_type": {
            "type": "STRING",
            "enum": ["invoice", "receipt", "unknown"],
            "description": "Kind of financial document",
        },
        "document_date": {
            "type": "STRING",
            "description": "Invoice/receipt date as YYYY-MM-DD, or empty string if not found",
        },
        "vendor": {
            "type": "STRING",
            "description": "Vendor or service provider name, or empty string if not found",
        },
        "invoice_number": {
            "type": "STRING",
            "description": "Invoice/receipt number, or empty string if not found",
        },
        "description": {
            "type": "STRING",
            "description": "Short description of what was purchased, or empty string if not found",
        },
        "amount": {
            "type": "NUMBER",
            "description": "Grand total amount paid (numeric). Omit if not found",
        },
        "currency": {
            "type": "STRING",
            "description": "3-letter ISO currency code, or empty string if not found",
        },
        "tax_amount": {
            "type": "NUMBER",
            "description": "Tax or VAT amount (numeric). Omit if not shown on the document",
        },
        "extraction_confidence": {
            "type": "NUMBER",
            "description": "Your overall confidence from 0 to 1",
        },
    },
    "required": ["doc_type", "document_date", "vendor", "invoice_number",
                 "description", "amount", "currency", "extraction_confidence"],
}

PROMPT = f"""You are a financial document processing assistant. Extract the key fields
from this invoice or receipt image/PDF.

Rules:
- Return ONLY the structured object matching the given schema.
- Dates must be normalized to YYYY-MM-DD.
- Currency must be a 3-letter ISO code (e.g. USD, EUR, EGP).
- `amount` is the grand total INCLUDING tax.
- If a field is genuinely not present anywhere on the document, return an
  empty string (or omit numeric fields); never invent values.
- Allowed expense categories are: {", ".join(CATEGORIES)} — also return the single
  best-matching `category` for this expense.
"""

EXTRACTION_SCHEMA_FULL = {
    **EXTRACTION_SCHEMA,
    "properties": {
        **EXTRACTION_SCHEMA["properties"],
        "category": {
            "type": "STRING",
            "enum": CATEGORIES,
            "description": "Best-fitting expense category",
        },
    },
}


class ExtractionError(Exception):
    pass


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# Demo mode: bundled sample docs with pre-baked extractions                     #
# --------------------------------------------------------------------------- #

def _demo_registry() -> dict[str, dict]:
    """filename stem -> pre-baked extraction (kept next to the samples)."""
    out = {}
    for jf in sorted(SAMPLE_DIR.glob("*.json")):
        out[jf.stem] = json.loads(jf.read_text())
    return out


def _demo_extract(path: Path) -> tuple[dict, str | None]:
    reg = _demo_registry()
    baked = reg.get(path.stem) or reg.get("default")
    if baked is None:
        raise ExtractionError(
            f"Demo mode only recognizes bundled sample files in "
            f"{SAMPLE_DIR.name}/ (got '{path.name}'). Use those, or set a "
            f"GEMINI_API_KEY in .env to process real documents."
        )
    data = dict(baked)
    return data, None


# --------------------------------------------------------------------------- #
# Real mode: Gemini                                                            #
# --------------------------------------------------------------------------- #

def _real_extract(path: Path, mime: str) -> tuple[dict, str | None]:
    if not GEMINI_API_KEY:
        raise ExtractionError(
            "No GEMINI_API_KEY configured. Set it in .env, or set "
            "DEMO_MODE=true to use the bundled samples without a key."
        )
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover
        raise ExtractionError(
            "google-genai is not installed. Run: pip install -r requirements.txt"
        ) from exc

    client = genai.Client(api_key=GEMINI_API_KEY)
    resp = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=[
            types.Part.from_bytes(data=path.read_bytes(), mime_type=mime),
            PROMPT,
        ],
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=EXTRACTION_SCHEMA_FULL,
            temperature=0,
        ),
    )
    text = (resp.text or "").strip()
    if not text:
        raise ExtractionError("Gemini returned an empty response.")
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ExtractionError(f"Gemini returned non-JSON output: {text[:200]}") from exc
    return data, None


# --------------------------------------------------------------------------- #
# Public API                                                                   #
# --------------------------------------------------------------------------- #

def extract(path: Path, mime: str) -> dict:
    """Full pipeline step: file -> normalized extraction dict."""
    if mime not in ALLOWED_MIME:
        raise ExtractionError(f"Unsupported file type: {mime}")

    if demo_active():
        data, _err = _demo_extract(path)
    else:
        data, _err = _real_extract(path, mime)

    return _normalize(data)


def _normalize(data: dict) -> dict:
    """Mirror every LLM/demo dict onto one canonical shape used downstream."""
    def s(key: str) -> str:
        v = data.get(key)
        return str(v).strip() if v is not None else ""

    def n(key: str):
        v = data.get(key)
        if v in (None, "", "null"):
            return None
        try:
            return round(float(v), 2)
        except (TypeError, ValueError):
            return None

    doc_type = s("doc_type").lower()
    if doc_type not in ("invoice", "receipt"):
        doc_type = "unknown"

    currency = s("currency").upper()
    currency = currency if len(currency) == 3 else None

    date = s("document_date") or s("date")

    return {
        "doc_type": doc_type,
        "doc_date": date,
        "vendor": s("vendor"),
        "invoice_number": s("invoice_number"),
        "description": s("description"),
        "amount": n("amount"),
        "currency": currency,
        "tax_amount": n("tax_amount"),
        "confidence": n("extraction_confidence") or 0.8,
        # category: LLM value if valid, else rule-based fallback
        "category": categorizer.categorize(s("category"), s("description") + " " + s("vendor")),
        "raw_vendor_text": s("vendor"),
    }
