import re
from datetime import datetime
from typing import List, Optional, TypedDict

from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.messages import HumanMessage

model = ChatOllama(model="mistral:latest", temperature=0)
embeddings = OllamaEmbeddings(model="nomic-embed-text")


class VerificationResult(TypedDict):
    status: str
    invoice_price: float
    ab_price: float
    difference: float
    discrepancies: List[str]


def _stamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


def _parse_amount(text: str) -> float:
    """Parst den ersten Zahlenwert aus einer Modellantwort.

    Unterstuetzt deutsche (1.234,56) und englische (1,234.56) Schreibweisen,
    damit ein Ausdruck wie '.' nicht zu einem float()-Fehler fuehrt.
    """
    match = re.search(r"\d[\d.,]*\d|\d", text)
    if not match:
        return 0.0
    raw = match.group(0)
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")
        else:
            raw = raw.replace(",", "")
    elif "," in raw:
        whole, _, decimals = raw.partition(",")
        raw = f"{whole}.{decimals}" if 0 < len(decimals) <= 2 else raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return 0.0


def extract_value_from_context(context: str, field_name: str) -> float:
    """Nutzt Mistral und Regex, um einen spezifischen numerischen Wert zu extrahieren."""
    prompt = f"""Du bist ein praeziser Finanz- und Einkaufspruefer.
Analysiere den folgenden Dokumenten-Kontext und extrahiere exakt den gesuchten Wert.

FELD: {field_name}

REGELN:
- Gesucht ist der Gesamtbetrag bzw. die Endsumme des Dokuments (Netto-Summe aller Positionen).
- Gib NICHT einzelne Positionspreise oder Einzelpreise aus.
- Gib ausschliesslich den numerischen Betrag als Dezimalzahl aus (Punkt als Dezimaltrenner).
- Verwende nur eine Zahl, die im Kontext tatsaechlich vorkommt. Erfinde keinen Wert.
- Gib keine Erklaerung, kein Waehrungssymbol und keinen weiteren Text aus.

DOKUMENTEN-KONTEXT:
{context}

ANTWORT:"""
    response = model.invoke([HumanMessage(content=prompt)])
    raw_text = response.content.strip()

    return _parse_amount(raw_text)


def verify_invoice_vs_ab(
    price_tolerance_eur: float = 0.0,
    ab_persist_dir: str = "./chroma_ab_db",
    invoice_persist_dir: str = "./chroma_invoice_db",
    log: Optional[List[dict]] = None,
) -> VerificationResult:
    """
    Lädt getrennt die AB- und Rechnungs-Datenbanken, extrahiert die Preise
    und prüft sie gegen die konfigurierte Toleranz.

    `log` ist eine optionale, geteilte Liste, an die jeder Schritt einen
    Zeitstempel-Eintrag anhängt (für die Toleranz-Log-Anzeige im Frontend).
    """
    if log is None:
        log = []

    # 1. Auftragsbestätigung (AB) aus ihrer eigenen DB abfragen
    ab_vectorstore = Chroma(persist_directory=ab_persist_dir, embedding_function=embeddings)
    ab_docs = ab_vectorstore.similarity_search("Gesamtbetrag netto Endsumme Summe aller Positionen", k=4)
    ab_docs = sorted(ab_docs, key=lambda doc: doc.metadata.get("page", 0))
    ab_context = "\n".join([doc.page_content for doc in ab_docs])
    ab_price = extract_value_from_context(ab_context, "Gesamtbetrag netto der Auftragsbestätigung")
    log.append({"time": _stamp(), "type": "extract", "message": f"ab.total_net = {ab_price:.2f}"})

    # 2. Rechnung aus ihrer eigenen DB abfragen
    invoice_vectorstore = Chroma(persist_directory=invoice_persist_dir, embedding_function=embeddings)
    invoice_docs = invoice_vectorstore.similarity_search("Rechnungsbetrag netto Endsumme Total Summe aller Positionen", k=4)
    invoice_docs = sorted(invoice_docs, key=lambda doc: doc.metadata.get("page", 0))
    invoice_context = "\n".join([doc.page_content for doc in invoice_docs])
    invoice_price = extract_value_from_context(invoice_context, "Rechnungsbetrag netto der Rechnung")
    log.append({"time": _stamp(), "type": "extract", "message": f"invoice.total_net = {invoice_price:.2f}"})

    # 3. Deterministischer Toleranz-Abgleich
    difference = round(invoice_price - ab_price, 2)
    abs_difference = abs(difference)
    log.append({"time": _stamp(), "type": "compare", "message": f"abs_diff = {abs_difference:.2f}"})

    discrepancies: List[str] = []
    if abs_difference > price_tolerance_eur:
        discrepancies.append(
            f"Preisabweichung: Rechnung ({invoice_price:.2f} €) weicht um {abs_difference:.2f} € "
            f"von der Auftragsbestätigung ({ab_price:.2f} €) ab "
            f"(erlaubte Toleranz: {price_tolerance_eur:.2f} €)."
        )

    status = "NEGATIVE" if discrepancies else "POSITIVE"
    operator = ">" if abs_difference > price_tolerance_eur else "<="
    log.append({
        "time": _stamp(),
        "type": "result",
        "message": f"{abs_difference:.2f} {operator} {price_tolerance_eur:.2f} -> {status}",
    })

    return {
        "status": status,
        "invoice_price": invoice_price,
        "ab_price": ab_price,
        "difference": difference,
        "discrepancies": discrepancies,
    }
