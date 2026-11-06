"""LLM-Extraktion des Nettobetrags mit Pydantic-Validierung.

Ablauf pro Dokument:
1. Das Modell antwortet im JSON-Modus: ``{"total_net": <Zahl oder null>}``.
2. Die Antwort wird gegen ``ExtractedTotal`` validiert (Pydantic).
3. Ist das JSON kaputt oder unvollstaendig, liest ein Regex-Fallback den
   ersten Betrag aus der Rohantwort.
4. Gelingt beides nicht, ist das Ergebnis ``None``. Die Toleranzpruefung
   behandelt das als "manuell pruefen" und gibt nie automatisch frei.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any, Optional, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from logging_config import get_logger

logger = get_logger("extraction")

LLM_MODEL = os.getenv("CONFIRMAI_LLM_MODEL", "mistral:latest")


class ExtractedTotal(BaseModel):
    """Schema der Modellantwort."""

    model_config = ConfigDict(extra="ignore")

    total_net: Optional[float] = Field(
        default=None,
        ge=0,
        description="Netto-Gesamtsumme des Dokuments in Euro, null wenn nicht auffindbar.",
    )

    @field_validator("total_net", mode="before")
    @classmethod
    def _coerce_amount(cls, value: Any) -> Any:
        # Modelle liefern Betraege gern als String ("12.480,00 €").
        if isinstance(value, str):
            return parse_amount(value)
        return value


def parse_amount(text: str) -> Optional[float]:
    """Parst den ersten Betrag aus einem Text.

    Unterstuetzt deutsche (1.234,56) und englische (1,234.56) Schreibweisen.
    Gibt ``None`` zurueck, wenn kein Betrag gefunden wird.
    """
    match = re.search(r"\d[\d.,]*\d|\d", text or "")
    if not match:
        return None
    raw = match.group(0)
    if "," in raw and "." in raw:
        if raw.rfind(",") > raw.rfind("."):
            raw = raw.replace(".", "").replace(",", ".")  # 1.234,56
        else:
            raw = raw.replace(",", "")  # 1,234.56
    elif "," in raw:
        whole, _, decimals = raw.rpartition(",")
        # "1234,5" / "1234,56" -> Dezimalkomma, "12,480" -> Tausenderpunkt
        if raw.count(",") == 1 and 0 < len(decimals) <= 2:
            raw = f"{whole}.{decimals}"
        else:
            raw = raw.replace(",", "")
    elif "." in raw:
        _, _, decimals = raw.rpartition(".")
        # "1.200" / "12.480.000" -> deutsche Tausenderpunkte, "12350.5" -> Dezimalpunkt
        if raw.count(".") > 1 or len(decimals) == 3:
            raw = raw.replace(".", "")
    try:
        return float(raw)
    except ValueError:
        return None


@dataclass(frozen=True)
class ExtractionOutcome:
    value: Optional[float]
    method: str  # "schema" | "regex_fallback" | "failed"
    raw_response: str


class AsyncChatModel(Protocol):
    async def ainvoke(self, messages: Any) -> Any: ...


def build_prompt(context: str, field_name: str) -> str:
    return f"""Du bist ein praeziser Finanz- und Einkaufspruefer.
Analysiere den folgenden Dokumenten-Kontext und extrahiere exakt den gesuchten Wert.

FELD: {field_name}

REGELN:
- Gesucht ist der Gesamtbetrag bzw. die Endsumme des Dokuments (Netto-Summe aller Positionen).
- Gib NICHT einzelne Positionspreise oder Einzelpreise aus.
- Verwende nur eine Zahl, die im Kontext tatsaechlich vorkommt. Erfinde keinen Wert.
- Antworte ausschliesslich mit JSON in genau dieser Form:
  {{"total_net": 1234.56}}
- Punkt als Dezimaltrenner, kein Waehrungssymbol. Ist kein Betrag auffindbar: {{"total_net": null}}

DOKUMENTEN-KONTEXT:
{context}

ANTWORT (JSON):"""


def parse_model_response(raw_text: str) -> ExtractionOutcome:
    """Validiert die Modellantwort, mit Regex-Fallback."""
    try:
        parsed = ExtractedTotal.model_validate_json(raw_text)
        if parsed.total_net is not None:
            return ExtractionOutcome(parsed.total_net, "schema", raw_text)
    except ValidationError as exc:
        logger.warning(
            "LLM response failed schema validation, trying regex fallback",
            extra={"fields": {"errors": exc.error_count(), "raw": raw_text[:200]}},
        )

    fallback = parse_amount(raw_text)
    if fallback is not None:
        return ExtractionOutcome(fallback, "regex_fallback", raw_text)
    return ExtractionOutcome(None, "failed", raw_text)


def _is_grounded(value: float, context: str) -> bool:
    """Prueft, ob der Betrag im Kontext vorkommt (deutsch oder englisch formatiert)."""
    en = f"{value:,.2f}"
    de = en.replace(",", "X").replace(".", ",").replace("X", ".")
    plain = f"{value:.2f}"
    return any(s in context for s in (en, de, plain, plain.replace(".", ",")))


async def extract_total(model: AsyncChatModel, context: str, field_name: str, doc_label: str) -> ExtractionOutcome:
    """Fragt das Modell asynchron nach der Nettosumme eines Dokuments."""
    from langchain_core.messages import HumanMessage

    response = await model.ainvoke([HumanMessage(content=build_prompt(context, field_name))])
    raw_text = str(getattr(response, "content", response)).strip()
    outcome = parse_model_response(raw_text)

    fields = {"doc": doc_label, "method": outcome.method, "value": outcome.value}
    if outcome.value is None:
        logger.warning("Could not extract net total", extra={"fields": fields})
    else:
        fields["grounded"] = _is_grounded(outcome.value, context)
        if not fields["grounded"]:
            logger.warning("Extracted value not found verbatim in document context", extra={"fields": fields})
        logger.info("Extracted net total", extra={"fields": fields})
    return outcome
