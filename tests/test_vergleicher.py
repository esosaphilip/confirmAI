"""Tests der Toleranzlogik und des Abgleichs (ohne Ollama, ohne Chroma)."""

from decimal import Decimal

import pytest

from tolerance import NEGATIVE, POSITIVE, evaluate_price_tolerance
from vergleicher import averify_invoice_vs_ab


# --------------------------------------------------------------------------- #
# Deterministische Toleranzpruefung
# --------------------------------------------------------------------------- #
def test_deviation_within_tolerance_is_positive():
    result = evaluate_price_tolerance(ab_price=12350.00, invoice_price=12352.40, price_tolerance_eur=5.0)

    assert result.status == POSITIVE
    assert result.difference == Decimal("2.40")
    assert result.within_tolerance
    assert result.discrepancies == []


def test_deviation_outside_tolerance_is_negative():
    result = evaluate_price_tolerance(ab_price=12350.00, invoice_price=12480.00, price_tolerance_eur=5.0)

    assert result.status == NEGATIVE
    assert result.difference == Decimal("130.00")
    assert len(result.discrepancies) == 1
    assert "130.00 €" in result.discrepancies[0]


def test_deviation_exactly_at_tolerance_is_positive():
    # Grenze inklusiv; mit float-Arithmetik waere 0.1 + 0.2 hier ein Problem.
    result = evaluate_price_tolerance(ab_price=100.10, invoice_price=105.10, price_tolerance_eur=5.00)
    assert result.status == POSITIVE


def test_one_cent_over_tolerance_is_negative():
    result = evaluate_price_tolerance(ab_price=100.00, invoice_price=105.01, price_tolerance_eur=5.00)
    assert result.status == NEGATIVE


def test_invoice_below_ab_counts_as_deviation_too():
    result = evaluate_price_tolerance(ab_price=1000.00, invoice_price=980.00, price_tolerance_eur=5.0)

    assert result.status == NEGATIVE
    assert result.difference == Decimal("-20.00")
    assert result.abs_difference == Decimal("20.00")


def test_zero_tolerance_requires_exact_match():
    assert evaluate_price_tolerance(500.00, 500.00, 0).status == POSITIVE
    assert evaluate_price_tolerance(500.00, 500.01, 0).status == NEGATIVE


@pytest.mark.parametrize("ab, invoice", [(None, 12480.0), (12350.0, None), (None, None)])
def test_missing_amount_never_auto_approves(ab, invoice):
    result = evaluate_price_tolerance(ab, invoice, price_tolerance_eur=1_000_000)

    assert result.status == NEGATIVE
    assert result.difference is None
    assert not result.within_tolerance
    assert all("manuell prüfen" in msg for msg in result.discrepancies)


def test_negative_tolerance_is_rejected():
    with pytest.raises(ValueError):
        evaluate_price_tolerance(100.0, 100.0, -1)


# --------------------------------------------------------------------------- #
# Kompletter Abgleich mit gefaktem LLM-Output
# --------------------------------------------------------------------------- #
async def test_verification_positive_with_valid_llm_json(fake_pipeline):
    fake_pipeline('{"total_net": 12350.00}', '{"total_net": 12352.40}')
    log: list[dict] = []

    result = await averify_invoice_vs_ab(5.0, "ab_db", "invoice_db", log=log)

    assert result["status"] == "POSITIVE"
    assert result["difference"] == pytest.approx(2.40)
    assert result["needs_review"] is False
    assert log[-1]["message"] == "2.40 <= 5.00 -> POSITIVE"


async def test_verification_negative_with_valid_llm_json(fake_pipeline):
    fake_pipeline('{"total_net": 12350.00}', '{"total_net": 12480.00}')
    log: list[dict] = []

    result = await averify_invoice_vs_ab(5.0, "ab_db", "invoice_db", log=log)

    assert result["status"] == "NEGATIVE"
    assert result["difference"] == pytest.approx(130.0)
    assert log[-1]["message"] == "130.00 > 5.00 -> NEGATIVE"


async def test_missing_field_in_llm_output_falls_back_cleanly(fake_pipeline):
    # Modell liefert JSON ohne das Pflichtfeld bzw. null -> manuelle Pruefung.
    fake_pipeline('{"total": "unbekannt"}', '{"total_net": null}')
    log: list[dict] = []

    result = await averify_invoice_vs_ab(5.0, "ab_db", "invoice_db", log=log)

    assert result["status"] == "NEGATIVE"
    assert result["needs_review"] is True
    assert len(result["discrepancies"]) == 2
    assert "manual review" in log[-1]["message"]


async def test_broken_json_uses_regex_fallback(fake_pipeline):
    fake_pipeline("Die Summe beträgt 12.350,00 €", '{"total_net": "12.352,40"}')
    log: list[dict] = []

    result = await averify_invoice_vs_ab(5.0, "ab_db", "invoice_db", log=log)

    assert result["status"] == "POSITIVE"
    assert result["ab_price"] == pytest.approx(12350.0)
    assert result["invoice_price"] == pytest.approx(12352.40)
    assert any("regex_fallback" in entry["message"] for entry in log)


async def test_both_documents_are_queried(fake_pipeline):
    model = fake_pipeline('{"total_net": 1}', '{"total_net": 1}')
    await averify_invoice_vs_ab(0, "ab_db", "invoice_db")
    assert model.calls == 2
