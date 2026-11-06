"""Deterministische Toleranzpruefung (keine KI in diesem Modul).

Die Geschaeftsregel ist bewusst vom LLM getrennt: Das Modell liefert nur
Zahlen, die Entscheidung POSITIVE/NEGATIVE trifft ausschliesslich dieser
Code. Dadurch ist die Entscheidung reproduzierbar und vollstaendig testbar.

Fail-safe: Fehlt ein Betrag (Extraktion gescheitert), wird nie automatisch
freigegeben. Das Ergebnis ist dann NEGATIVE mit dem Hinweis auf manuelle
Pruefung.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import List, Optional

CENT = Decimal("0.01")

POSITIVE = "POSITIVE"
NEGATIVE = "NEGATIVE"


def to_money(value: float | int | str | Decimal) -> Decimal:
    """Wandelt einen Betrag verlustfrei in Euro-Cent-Genauigkeit um."""
    return Decimal(str(value)).quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class ToleranceEvaluation:
    status: str
    ab_price: Optional[Decimal]
    invoice_price: Optional[Decimal]
    tolerance: Decimal
    difference: Optional[Decimal]
    within_tolerance: bool
    discrepancies: List[str] = field(default_factory=list)

    @property
    def abs_difference(self) -> Optional[Decimal]:
        return None if self.difference is None else abs(self.difference)


def evaluate_price_tolerance(
    ab_price: Optional[float | Decimal],
    invoice_price: Optional[float | Decimal],
    price_tolerance_eur: float | Decimal,
) -> ToleranceEvaluation:
    """Vergleicht Rechnungs- und AB-Betrag gegen die erlaubte Toleranz.

    Die Grenze ist inklusiv: Eine Abweichung genau in Hoehe der Toleranz ist
    noch POSITIVE.
    """
    tolerance = to_money(price_tolerance_eur)
    if tolerance < 0:
        raise ValueError("price_tolerance_eur darf nicht negativ sein.")

    missing = [
        label
        for label, value in (("Auftragsbestätigung", ab_price), ("Rechnung", invoice_price))
        if value is None
    ]
    if missing:
        return ToleranceEvaluation(
            status=NEGATIVE,
            ab_price=None if ab_price is None else to_money(ab_price),
            invoice_price=None if invoice_price is None else to_money(invoice_price),
            tolerance=tolerance,
            difference=None,
            within_tolerance=False,
            discrepancies=[
                f"Nettobetrag konnte nicht aus folgendem Dokument gelesen werden: {name}. "
                "Bitte manuell prüfen."
                for name in missing
            ],
        )

    ab = to_money(ab_price)
    invoice = to_money(invoice_price)
    difference = invoice - ab
    within = abs(difference) <= tolerance

    discrepancies: List[str] = []
    if not within:
        discrepancies.append(
            f"Preisabweichung: Rechnung ({invoice:.2f} €) weicht um {abs(difference):.2f} € "
            f"von der Auftragsbestätigung ({ab:.2f} €) ab "
            f"(erlaubte Toleranz: {tolerance:.2f} €)."
        )

    return ToleranceEvaluation(
        status=POSITIVE if within else NEGATIVE,
        ab_price=ab,
        invoice_price=invoice,
        tolerance=tolerance,
        difference=difference,
        within_tolerance=within,
        discrepancies=discrepancies,
    )
