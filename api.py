import os
import re
import shutil
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from indexing import index_single_document
from vergleicher import verify_invoice_vs_ab

RUNS_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "runs")
MAX_UPLOAD_BYTES = 20 * 1024 * 1024  # 20 MB

app = FastAPI(
    title="confirmAI - Invoice & AB Matcher",
    version="2.1",
    description=(
        "Automatisierter Dokumenten-Abgleich. Nimmt AB- und Rechnungs-PDFs per Upload entgegen, "
        "indexiert sie getrennt und prüft die Preise gegen die konfigurierte Toleranz."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-Memory-Zustand (fuer einen einzelnen Prozess ausreichend; fuer Mehrbenutzer
# muesste dies durch einen persistenten Store ersetzt werden).
RULES: Dict[str, float] = {"price_tolerance_eur": 5.0}
JOBS: Dict[str, Dict[str, Any]] = {}


# --------------------------------------------------------------------------- #
# Schemas
# --------------------------------------------------------------------------- #
class RuleConfig(BaseModel):
    price_tolerance_eur: float = Field(default=5.0, ge=0, description="Erlaubte Preisabweichung in Euro")


class Step(BaseModel):
    id: int
    key: str
    title: str
    description: str
    status: str  # queued | running | done | error


class LogEntry(BaseModel):
    time: str
    type: str
    message: str


class VerificationResult(BaseModel):
    status: str  # POSITIVE | NEGATIVE
    invoice_price: float
    ab_price: float
    difference: float
    tolerance: float
    discrepancies: List[str]
    ab_number: Optional[str] = None
    invoice_number: Optional[str] = None
    ab_filename: Optional[str] = None
    invoice_filename: Optional[str] = None
    checked_at: str


class JobSnapshot(BaseModel):
    run_id: str
    state: str  # running | completed | error
    steps: List[Step]
    log: List[LogEntry]
    result: Optional[VerificationResult] = None
    error: Optional[str] = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _initial_steps() -> List[Dict[str, Any]]:
    return [
        {
            "id": 1,
            "key": "index_ab",
            "title": "Indexing the AB",
            "description": "Reading layout, line items, unit prices and totals from the order confirmation.",
            "status": "queued",
        },
        {
            "id": 2,
            "key": "index_invoice",
            "title": "Indexing the invoice",
            "description": "Extracting the same fields from the invoice so both documents line up.",
            "status": "queued",
        },
        {
            "id": 3,
            "key": "evaluate",
            "title": "Running the tolerance evaluator",
            "description": "Deterministic price comparison of invoice vs. AB. No AI judgement in this step.",
            "status": "queued",
        },
    ]


def _set_step(job: Dict[str, Any], key: str, status: str) -> None:
    for step in job["steps"]:
        if step["key"] == key:
            step["status"] = status
            return


def _log(job: Dict[str, Any], entry_type: str, message: str) -> None:
    job["log"].append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "type": entry_type,
        "message": message,
    })


def _doc_number(filename: str, kind: str) -> str:
    """Leitet eine Anzeige-Dokumentnummer aus dem Dateinamen ab."""
    stem = os.path.splitext(os.path.basename(filename))[0]
    if kind == "ab":
        match = re.search(r"AB[_\-\s]?(\d{4,})", stem, re.IGNORECASE)
        if match:
            return f"AB {match.group(1)}"
    else:
        match = re.search(r"(RE|RECH|INV)[_\-]?(\d[\w\-]*)", stem, re.IGNORECASE)
        if match:
            return f"{match.group(1).upper()}-{match.group(2)}"
    return stem


async def _save_upload(upload: UploadFile, dest_dir: str, dest_name: str) -> str:
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, dest_name)
    size = 0
    with open(dest, "wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_UPLOAD_BYTES:
                out.close()
                os.remove(dest)
                raise HTTPException(status_code=413, detail=f"{upload.filename} is larger than 20 MB.")
            out.write(chunk)
    if size == 0:
        os.remove(dest)
        raise HTTPException(status_code=400, detail=f"{upload.filename} is empty.")
    return dest


def _run_job(
    run_id: str,
    ab_path: str,
    invoice_path: str,
    ab_name: str,
    invoice_name: str,
    ab_dir: str,
    invoice_dir: str,
    tolerance: float,
) -> None:
    """Laeuft im Hintergrund-Thread und aktualisiert den Job-Zustand schrittweise."""
    job = JOBS[run_id]
    run_dir = os.path.dirname(ab_path)
    try:
        _log(job, "config", f"price_tolerance_eur = {tolerance:.2f}")

        _set_step(job, "index_ab", "running")
        index_single_document(ab_path, persist_directory=ab_dir)
        _set_step(job, "index_ab", "done")
        _log(job, "index", f"AB indexed from {ab_name}")

        _set_step(job, "index_invoice", "running")
        index_single_document(invoice_path, persist_directory=invoice_dir)
        _set_step(job, "index_invoice", "done")
        _log(job, "index", f"invoice indexed from {invoice_name}")

        _set_step(job, "evaluate", "running")
        result = verify_invoice_vs_ab(
            price_tolerance_eur=tolerance,
            ab_persist_dir=ab_dir,
            invoice_persist_dir=invoice_dir,
            log=job["log"],
        )
        _set_step(job, "evaluate", "done")

        job["result"] = {
            "status": result["status"],
            "invoice_price": result["invoice_price"],
            "ab_price": result["ab_price"],
            "difference": result["difference"],
            "tolerance": tolerance,
            "discrepancies": result["discrepancies"],
            "ab_number": _doc_number(ab_name, "ab"),
            "invoice_number": _doc_number(invoice_name, "invoice"),
            "ab_filename": ab_name,
            "invoice_filename": invoice_name,
            "checked_at": datetime.now().strftime("%d.%m.%Y · %H:%M"),
        }
        job["state"] = "completed"
    except Exception as exc:  # noqa: BLE001 - Fehler sollen im Job sichtbar werden
        job["state"] = "error"
        job["error"] = str(exc)
        for step in job["steps"]:
            if step["status"] in ("running", "queued"):
                step["status"] = "error"
        _log(job, "error", str(exc))
    finally:
        shutil.rmtree(run_dir, ignore_errors=True)


# --------------------------------------------------------------------------- #
# Routes
# --------------------------------------------------------------------------- #
@app.get("/api/v1/health")
def health() -> Dict[str, str]:
    return {"status": "ok", "model": "mistral:latest", "embeddings": "nomic-embed-text"}


@app.get("/api/v1/rules", response_model=RuleConfig)
def get_rules() -> RuleConfig:
    return RuleConfig(**RULES)


@app.put("/api/v1/rules", response_model=RuleConfig)
def update_rules(payload: RuleConfig) -> RuleConfig:
    RULES["price_tolerance_eur"] = payload.price_tolerance_eur
    return RuleConfig(**RULES)


@app.post("/api/v1/verifications", response_model=JobSnapshot, status_code=202)
async def create_verification(
    background: BackgroundTasks,
    ab_file: UploadFile = File(..., description="Auftragsbestätigung (AB) als PDF"),
    invoice_file: UploadFile = File(..., description="Rechnung als PDF"),
    price_tolerance_eur: Optional[float] = Form(None),
) -> JobSnapshot:
    for upload in (ab_file, invoice_file):
        if not upload.filename or not upload.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail=f"{upload.filename or 'file'} must be a PDF.")

    tolerance = RULES["price_tolerance_eur"] if price_tolerance_eur is None else price_tolerance_eur

    run_id = uuid.uuid4().hex[:12]
    run_dir = os.path.join(RUNS_ROOT, run_id)
    ab_name = ab_file.filename or "ab.pdf"
    invoice_name = invoice_file.filename or "invoice.pdf"
    ab_path = await _save_upload(ab_file, run_dir, "ab.pdf")
    invoice_path = await _save_upload(invoice_file, run_dir, "invoice.pdf")

    JOBS[run_id] = {
        "run_id": run_id,
        "state": "running",
        "steps": _initial_steps(),
        "log": [],
        "result": None,
        "error": None,
    }
    background.add_task(
        _run_job,
        run_id,
        ab_path,
        invoice_path,
        ab_name,
        invoice_name,
        os.path.join(run_dir, "ab_db"),
        os.path.join(run_dir, "invoice_db"),
        tolerance,
    )
    return JobSnapshot(**JOBS[run_id])


@app.get("/api/v1/verifications/{run_id}", response_model=JobSnapshot)
def get_verification(run_id: str) -> JobSnapshot:
    job = JOBS.get(run_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Unknown run_id '{run_id}'.")
    return JobSnapshot(**job)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api:app", host="127.0.0.1", port=8000, reload=True)
