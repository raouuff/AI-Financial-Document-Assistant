# Technical Documentation — Architecture

## 1. High-level architecture

```
                        ┌────────────────────────────────────────────┐
 User (browser)         │              FastAPI backend               │
 ───────────────►  POST │  ┌─────────┐   ┌───────────┐   ┌─────────┐  │
 PDF / PNG / JPG  /api/ │  │ Extract │──►│ Categorize│──►│Validate │  │
                  upload│  │ (Gemini)│   │ (LLM+ruls)│   │(rules)  │  │
                        │  └─────────┘   └───────────┘   └────┬────┘  │
                        │                                     ▼       │
                        │        ┌──────────────┐      ┌────────────┐  │
   Dashboard ◄───────── │        │  Financial   │◄─────│   SQLite   │  │
 (single HTML page)     │        │   Summary    │      │  Google-   │  │
   /api/summary, /api/  │        └──────────────┘      │ Sheets-    │  │
   export/csv           │                              │ equivalent │  │
                        │  human review loop:          └────────────┘  │
   PATCH /api/expenses/ │  edit fields → re-validate → Approve/Reject  │
   .../status           └────────────────────────────────────────────┘
```

**Design principle:** a small, deterministic pipeline of pure-logic stages
(extract → categorize → validate → persist) wrapped by a thin HTTP layer.
Each stage is a separate module and independently testable; the LLM is used
only where it adds value (reading document pixels and choosing a category),
never for storage or validation logic.

## 2. Technology choices & why

| Layer | Choice | Alternatives considered | Rationale |
|---|---|---|---|
| Extraction | Gemini 2.5 Flash, `response_schema` JSON mode | OpenAI GPT-4o vision, Claude | Free tier, native PDF+image input, schema-constrained JSON output (no brittle prompt-parsing) |
| Framework | Custom Python (FastAPI) | n8n / Make / Zapier | No paid automation account; full control; trivially reproducible (`pip install` + `python run.py`) |
| Storage | SQLite | Google Sheets, Airtable, Notion | "or equivalent" per the spec; zero-credential setup, portability, still exports as CSV for real Sheets import |
| UI | One Jinja-free HTML page + fetch | React/Next | Fastest path to a working, demo-videable interface; no build step |
| Runtime deps | 5 packages in `requirements.txt` | — | Small audit surface, low breakage risk |

## 3. Component details

### 3.1 Extraction (`app/extractor.py`)
- Accepts `application/pdf`, PNG, JPG, WEBP (≤15 MB).
- In **real mode**, sends raw bytes + prompt + JSON schema to
  `client.models.generate_content(...)` with `temperature=0`.
- Fields: `doc_type, document_date (YYYY-MM-DD), vendor, invoice_number,
  description, amount (grand total incl. tax), currency (ISO-3),
  tax_amount, category, extraction_confidence`.
- Prompt explicitly forbids inventing values → missing fields become flags
  rather than hallucinated data.
- `_normalize()` maps any provider output onto a canonical dict, so switching
  LLM providers only touches this file.
- **Demo mode** swaps the LLM call for sidecar JSONs next to the bundled
  samples (`sample_data/*.json`) — identical downstream behavior. Selected via
  `DEMO_MODE=auto|true|false`; `auto` = demo when no key is configured.

### 3.2 Categorization (`app/categorizer.py`)
- Two-tier: (1) the LLM's category, validated against the 6 predefined
  categories; (2) keyword-scoring fallback over description+vendor if the LLM
  value is missing/invalid. This prevents an extraction hiccup from producing
  an unknown category.

### 3.3 Validation (`app/validator.py`)
Three rule families, each producing typed flags `{type, field, severity, message}`:

1. **missing** — date, vendor, amount, currency, description (error);
   invoice number absent (info, since receipts legitimately omit it).
2. **inconsistent** — non-positive amount; tax ≥ total; unparsable or future
   date; unrecognized currency code; category outside the predefined six.
3. **duplicate** — any stored record where:
   - same vendor + same invoice number, **or**
   - identical file hash (re-upload), **or**
   - same vendor + same amount + dates within ±3 days.
   Returns the related record(s) for human judgment in the UI.

### 3.4 Storage (`app/db.py`)
- Single `expenses` table; extracted fields, computed flags (JSON), raw
  extraction payload (audit), file path + SHA-256, review `status`
  (`pending_review|approved|rejected`), timestamps.
- SQL indices on vendor/invoice#/category support duplicate checks.

### 3.5 Human-in-the-loop review
- Every new record starts `pending_review` and appears with its flags.
- `PATCH /api/expenses/{id}` applies the human fix and **re-runs the whole
  validation suite** immediately — correcting the date clears the missing-date
  flag with zero extra clicks.
- Approve/Reject is a single POST; approval is what finance teams see as the
  "accepted" state in the tracker and summary.

### 3.6 Summary (`app/summary.py`)
- Aggregates non-rejected records by **category** (with per-currency breakdown)
  and by **currency**, plus data-quality KPIs (awaiting review, flagged,
  potential duplicates). Rendered as JSON, Markdown, CSV.

## 4. Data flow example (catering receipt)

1. `POST /api/upload` (PNG) → extraction returns `document_date: ""`.
2. Validator → `[missing: doc_date (error), missing: invoice_number (info)]`.
3. Stored as `pending_review`; dashboard shows amber/red flags.
4. Finance user types `2025-12-14`, presses **Save** → `PATCH` →
   re-validation → only the info flag remains.
5. **Approve** → summary and CSV now include the events total.

## 5. Security & privacy

- API key only ever via `.env` (gitignored); no keys in code or docs.
- Uploads stay on the local machine; only the file bytes are sent to the LLM
  provider, matching the task note to avoid confidential data (all bundled
  samples are fictional).
- No auth/HTTPS by design (localhost prototype) — a production version would
  add SSO + object storage + row-level permissions.

## 6. Known limitations & future work

| Limitation | Mitigation today | Future work |
|---|---|---|
| Currency totals not FX-converted | per-currency totals | FX rate service + normalized-baseline column |
| LLM extraction errors on poor scans | flags + human review UI | confidence-gated auto-approval; re-OCR pass |
| Duplicate heuristics imperfect | 3 complementary signals + related-record display | fuzzy vendor matching, embedding similarity |
| Google Sheets not directly connected | CSV export importable into Sheets | gspread service-account writer behind `db.py`'s interface |
| Single-user, no auth | localhost prototype | keycloak/OAuth, audit log |
| Part 2 (content publishing) not implemented | out of scope for this repo | same pattern: extract → generate → human approval → publish |

## 7. Reproducing

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt            # add -r requirements-dev.txt to regen samples
cp .env.example .env                       # set GEMINI_API_KEY (or leave unset → demo mode)
python run.py                              # http://127.0.0.1:8000
python scripts/make_samples.py             # (optional) regenerate sample data
```

API reference at `http://127.0.0.1:8000/docs`; manual test plan in
`docs/TEST_PLAN.md`.
