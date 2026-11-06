"""Orchestriert Retrieval, LLM-Extraktion und die deterministische Pruefung.

AB und Rechnung werden parallel abgefragt (``asyncio.gather``): Die
Vektor-Suche laeuft in einem Worker-Thread, der LLM-Aufruf ueber
``ainvoke``. So blockiert ein laufender Abgleich den FastAPI-Server nicht.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime
from typing import List, Optional, TypedDict

from extraction import LLM_MODEL, ExtractionOutcome, extract_total
from logging_config import get_logger
from tolerance import evaluate_price_tolerance

logger = get_logger("vergleicher")

EMBED_MODEL = os.getenv("CONFIRMAI_EMBED_MODEL", "nomic-embed-text")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

AB_QUERY = "Gesamtbetrag netto Endsumme Summe aller Positionen"
INVOICE_QUERY = "Rechnungsbetrag netto Endsumme Total Summe aller Positionen"

_model = None
_embeddings = None


def get_model():
    """Erzeugt den Chat-Client erst bei Bedarf (haelt Imports und Tests leicht)."""
    global _model
    if _model is None:
        from langchain_ollama import ChatOllama

        _model = ChatOllama(model=LLM_MODEL, temperature=0, format="json", base_url=OLLAMA_BASE_URL)
    return _model


def get_embeddings():
    global _embeddings
    if _embeddings is None:
        from langchain_ollama import OllamaEmbeddings

        _embeddings = OllamaEmbeddings(model=EMBED_MODEL, base_url=OLLAMA_BASE_URL)
    return _embeddings


class VerificationResult(TypedDict):
    status: str
    invoice_price: float
    ab_price: float
    difference: float
    discrepancies: List[str]
    needs_review: bool


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _retrieve_context(persist_dir: str, query: str, k: int = 4) -> str:
    """Blockierende Chroma-Suche; wird per ``asyncio.to_thread`` aufgerufen."""
    from langchain_community.vectorstores import Chroma

    store = Chroma(persist_directory=persist_dir, embedding_function=get_embeddings())
    docs = store.similarity_search(query, k=k)
    docs = sorted(docs, key=lambda doc: doc.metadata.get("page", 0))
    return "\n".join(doc.page_content for doc in docs)


async def _extract_document_total(persist_dir: str, query: str, field_name: str, doc_label: str) -> ExtractionOutcome:
    context = await asyncio.to_thread(_retrieve_context, persist_dir, query)
    logger.debug("Retrieved context", extra={"fields": {"doc": doc_label, "chars": len(context)}})
    return await extract_total(get_model(), context, field_name, doc_label)


async def averify_invoice_vs_ab(
    price_tolerance_eur: float = 0.0,
    ab_persist_dir: str = "./chroma_ab_db",
    invoice_persist_dir: str = "./chroma_invoice_db",
    log: Optional[List[dict]] = None,
) -> VerificationResult:
    """Extrahiert beide Nettobetraege und prueft sie gegen die Toleranz.

    ``log`` ist eine optionale, geteilte Liste, an die jeder Schritt einen
    Eintrag fuer die Toleranz-Log-Anzeige im Frontend anhaengt.
    """
    if log is None:
        log = []

    ab, invoice = await asyncio.gather(
        _extract_document_total(ab_persist_dir, AB_QUERY, "Gesamtbetrag netto der Auftragsbestätigung", "ab"),
        _extract_document_total(invoice_persist_dir, INVOICE_QUERY, "Rechnungsbetrag netto der Rechnung", "invoice"),
    )

    for label, outcome in (("ab", ab), ("invoice", invoice)):
        shown = "null" if outcome.value is None else f"{outcome.value:.2f}"
        suffix = "" if outcome.method == "schema" else f" ({outcome.method})"
        log.append({"time": _stamp(), "type": "extract", "message": f"{label}.total_net = {shown}{suffix}"})

    evaluation = evaluate_price_tolerance(ab.value, invoice.value, price_tolerance_eur)

    if evaluation.difference is None:
        message = f"extraction incomplete -> {evaluation.status} (manual review)"
        log.append({"time": _stamp(), "type": "result", "message": message})
    else:
        abs_diff = evaluation.abs_difference
        operator = "<=" if evaluation.within_tolerance else ">"
        log.append({"time": _stamp(), "type": "compare", "message": f"abs_diff = {abs_diff:.2f}"})
        log.append({
            "time": _stamp(),
            "type": "result",
            "message": f"{abs_diff:.2f} {operator} {evaluation.tolerance:.2f} -> {evaluation.status}",
        })

    logger.info(
        "Tolerance evaluated",
        extra={"fields": {
            "status": evaluation.status,
            "ab_total_net": evaluation.ab_price,
            "invoice_total_net": evaluation.invoice_price,
            "difference": evaluation.difference,
            "tolerance": evaluation.tolerance,
            "within_tolerance": evaluation.within_tolerance,
        }},
    )

    return {
        "status": evaluation.status,
        "invoice_price": float(evaluation.invoice_price or 0),
        "ab_price": float(evaluation.ab_price or 0),
        "difference": float(evaluation.difference or 0),
        "discrepancies": evaluation.discrepancies,
        "needs_review": evaluation.difference is None,
    }


def verify_invoice_vs_ab(*args, **kwargs) -> VerificationResult:
    """Synchrone Variante fuer Skripte und die Kommandozeile."""
    return asyncio.run(averify_invoice_vs_ab(*args, **kwargs))
