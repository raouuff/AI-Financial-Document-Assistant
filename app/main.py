"""AI Financial Document Assistant — FastAPI application."""
from __future__ import annotations

import csv
import io
import json
import secrets
from datetime import date
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import categorizer, db, extractor, summary, validator
from .config import (
    ALLOWED_MIME, EXPORT_DIR, UPLOAD_DIR, demo_active, BASE_DIR,
)

app = FastAPI(title="AI Financial Document Assistant", version="1.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
db.init_db()

# In-memory staging area: upload -> review/edit -> confirm/discard.
# (localhost prototype; staged records are not persisted until confirmed)
STAGED: dict[str, dict] = {}

# Fields the user may edit on a staged extraction
EDITABLE_FIELDS = {
    "doc_type", "doc_date", "vendor", "invoice_number", "description",
    "amount", "currency", "tax_amount", "category",
}


# ----------------------------------------------------------------- dashboard
@app.get("/", response_class=HTMLResponse)
def index():
    return (BASE_DIR / "static" / "index.html").read_text()


@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mode": "demo" if demo_active() else "real",
        "today": date.today().isoformat(),
    }


# ------------------------------------------------------------------- upload
def _save_upload(file: UploadFile) -> tuple[Path, str]:
    mime = file.content_type or ""
    if mime not in ALLOWED_MIME:
        raise HTTPException(
            415, f"Unsupported file type '{mime}'. "
                 f"Allowed: {', '.join(sorted(ALLOWED_MIME))}"
        )
    data = file.file.read()
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(413, "File too large (max 15 MB).")
    if not data:
        raise HTTPException(400, "Empty file.")
    dest = UPLOAD_DIR / Path(file.filename).name
    dest.write_bytes(data)
    return dest, mime


@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    """Stage a document: extract -> categorize -> validate, but DON'T store yet.

    The returned staging token must be confirmed (/api/staged/{token}/confirm)
    or discarded (/api/staged/{token}/discard) before the tracker changes.
    """
    path, mime = _save_upload(file)
    try:
        extracted = extractor.extract(path, mime)
    except extractor.ExtractionError as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(422, str(exc)) from exc
    except Exception as exc:  # noqa: BLE001 — surface LLM/network issues clearly
        path.unlink(missing_ok=True)
        raise HTTPException(502, f"Extraction failed: {exc}") from exc

    record = {
        **extracted,
        "doc_filename": path.name,
        "doc_hash": extractor.file_hash(path),
        "file_path": str(path),
    }
    flags = validator.de_dupe(validator.validate(record))
    token = secrets.token_urlsafe(8)
    STAGED[token] = record
    return {
        "staging_token": token,
        "record": record,
        "flags": flags,
        "note": "Staged — edit if needed, then Confirm to add it to the tracker.",
    }


def _apply_edits(record: dict, edits: dict) -> dict:
    """Merge user edits into a staged record (with light normalization)."""
    merged = dict(record)
    for k, v in (edits or {}).items():
        if k not in EDITABLE_FIELDS:
            continue
        if k == "amount" or k == "tax_amount":
            try:
                merged[k] = round(float(v), 2) if v not in (None, "", "null") else None
            except (TypeError, ValueError):
                raise HTTPException(400, f"{k} must be a number.")
        elif k == "currency":
            v = str(v or "").strip().upper()
            merged[k] = v if len(v) == 3 else None
        elif k == "doc_type":
            merged[k] = v if v in ("invoice", "receipt", "unknown") else "unknown"
        elif k == "category":
            merged[k] = categorizer.categorize(v, merged.get("description") or "")
        else:
            merged[k] = str(v).strip() if v is not None else ""
    return merged


@app.post("/api/staged/{token}/confirm")
def confirm_staged(token: str, body: dict):
    """User reviewed (and possibly edited) the extraction -> store in tracker."""
    rec = STAGED.get(token)
    if rec is None:
        raise HTTPException(
            404, "Staged extraction not found — it was already confirmed, "
                 "discarded, or the server restarted. Please upload again."
        )
    merged = _apply_edits(rec, body.get("edits"))
    flags = validator.de_dupe(validator.validate(merged))
    stored = db.insert_expense(merged, flags, merged)
    STAGED.pop(token, None)
    return stored


@app.post("/api/staged/{token}/discard")
def discard_staged(token: str):
    """User rejects the extraction -> nothing is stored, upload is removed."""
    rec = STAGED.pop(token, None)
    if rec is None:
        raise HTTPException(404, "Staged extraction not found.")
    Path(rec["file_path"]).unlink(missing_ok=True)
    return {"ok": True, "discarded": rec["doc_filename"]}


# ------------------------------------------------------------------ records
@app.get("/api/expenses")
def expenses(status: str | None = None):
    return db.list_expenses(status)


@app.get("/api/expenses/{expense_id}")
def get_expense(expense_id: int):
    rec = db.get_expense(expense_id)
    if not rec:
        raise HTTPException(404, "Record not found.")
    return rec


@app.patch("/api/expenses/{expense_id}")
def edit_expense(expense_id: int, updates: dict):
    """Human fixes a flagged field -> re-validate the record."""
    rec = db.get_expense(expense_id)
    if not rec:
        raise HTTPException(404, "Record not found.")
    merged = {**rec, **{k: v for k, v in updates.items() if k in validator.FLAG_TYPES or True}}
    flags = validator.de_dupe(validator.validate(merged))
    updated = db.update_expense(expense_id, updates, flags)
    if updated is None:
        raise HTTPException(404, "Record not found.")
    return updated


@app.post("/api/expenses/{expense_id}/status")
def set_status(expense_id: int, body: dict):
    status = (body.get("status") or "").strip()
    if status not in ("pending_review", "approved", "rejected"):
        raise HTTPException(400, "status must be pending_review|approved|rejected")
    updated = db.update_expense(expense_id, {"status": status})
    if updated is None:
        raise HTTPException(404, "Record not found.")
    return updated


# ------------------------------------------------------------------ summary
@app.get("/api/summary")
def financial_summary():
    return summary.build_summary()


@app.get("/api/summary.md")
@app.get("/api/summary/markdown")
def financial_summary_md():
    return PlainTextResponse(summary.to_markdown(summary.build_summary()))


# -------------------------------------------------------------------- export
@app.get("/api/export/csv", response_class=PlainTextResponse)
def export_csv():
    rows = db.list_expenses()
    buf = io.StringIO()
    cols = [
        "id", "status", "doc_type", "doc_filename", "doc_date", "vendor",
        "invoice_number", "description", "category", "amount", "currency",
        "tax_amount", "confidence", "flags",
    ]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        r = {**r, "flags": "; ".join(
            f"{f['type']}:{f['message']}" for f in r.get("flags", [])
        )}
        w.writerow(r)
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"Content-Disposition":
                                      'attachment; filename="expense_tracker.csv"'})


@app.exception_handler(HTTPException)
async def http_error(request, exc: HTTPException):  # keep responses JSON
    return JSONResponse({"error": exc.detail}, status_code=exc.status_code)
