import pytest
from pydantic import ValidationError

from extraction import ExtractedTotal, parse_amount, parse_model_response


@pytest.mark.parametrize(
    "text, expected",
    [
        ("12350.00", 12350.0),
        ("12.350,00 €", 12350.0),
        ("12,350.00", 12350.0),
        ("Summe: 1.200", 1200.0),  # deutscher Tausenderpunkt ohne Nachkommastellen
        ("1.234.567,89", 1234567.89),
        ("1234,5", 1234.5),
        ("12,480", 12480.0),
        ("42", 42.0),
        ("0,99", 0.99),
    ],
)
def test_parse_amount_handles_german_and_english_formats(text, expected):
    assert parse_amount(text) == pytest.approx(expected)


@pytest.mark.parametrize("text", ["", ".", "kein Betrag gefunden", None])
def test_parse_amount_returns_none_without_number(text):
    assert parse_amount(text) is None


def test_schema_accepts_string_amounts():
    assert ExtractedTotal.model_validate({"total_net": "12.480,00 €"}).total_net == 12480.0


def test_schema_rejects_negative_totals():
    with pytest.raises(ValidationError):
        ExtractedTotal.model_validate({"total_net": -5})


def test_valid_json_uses_schema_path():
    outcome = parse_model_response('{"total_net": 12480.0}')
    assert (outcome.value, outcome.method) == (12480.0, "schema")


def test_extra_keys_are_ignored():
    outcome = parse_model_response('{"total_net": 99.5, "currency": "EUR", "note": "ok"}')
    assert outcome.value == 99.5


def test_invalid_json_falls_back_to_regex():
    outcome = parse_model_response("Antwort: 12.480,00")
    assert (outcome.value, outcome.method) == (12480.0, "regex_fallback")


def test_null_without_any_number_fails_cleanly():
    outcome = parse_model_response('{"total_net": null}')
    assert outcome.value is None
    assert outcome.method == "failed"
