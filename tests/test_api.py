"""API-Tests mit FastAPIs TestClient; Indexierung und Abgleich sind gefakt."""

import pytest
from fastapi.testclient import TestClient

import api

PDF_BYTES = b"%PDF-1.4\n% confirmAI test\n"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(api, "index_single_document", lambda path, persist_dir: None)

    async def fake_verify(price_tolerance_eur, ab_persist_dir, invoice_persist_dir, log):
        log.append({"time": "00:00:00", "type": "result", "message": "130.00 > 5.00 -> NEGATIVE"})
        return {
            "status": "NEGATIVE",
            "invoice_price": 12480.0,
            "ab_price": 12350.0,
            "difference": 130.0,
            "discrepancies": ["Preisabweichung"],
            "needs_review": False,
        }

    monkeypatch.setattr(api, "averify_invoice_vs_ab", fake_verify)
    api.JOBS.clear()
    api.RULES["price_tolerance_eur"] = 5.0
    return TestClient(api.app)


def _files(ab_name="AB_4500123456.pdf", inv_name="RE-2026-10871.pdf"):
    return {
        "ab_file": (ab_name, PDF_BYTES, "application/pdf"),
        "invoice_file": (inv_name, PDF_BYTES, "application/pdf"),
    }


def test_health(client):
    assert client.get("/api/v1/health").json()["status"] == "ok"


def test_rules_roundtrip(client):
    assert client.put("/api/v1/rules", json={"price_tolerance_eur": 2.5}).status_code == 200
    assert client.get("/api/v1/rules").json() == {"price_tolerance_eur": 2.5}


def test_rules_reject_negative_tolerance(client):
    assert client.put("/api/v1/rules", json={"price_tolerance_eur": -1}).status_code == 422


def test_verification_lifecycle(client):
    created = client.post("/api/v1/verifications", files=_files())
    assert created.status_code == 202
    run_id = created.json()["run_id"]

    # TestClient fuehrt Background-Tasks vor der Rueckgabe aus.
    snapshot = client.get(f"/api/v1/verifications/{run_id}").json()
    assert snapshot["state"] == "completed"
    assert [s["status"] for s in snapshot["steps"]] == ["done", "done", "done"]
    assert snapshot["result"]["status"] == "NEGATIVE"
    assert snapshot["result"]["ab_number"] == "AB 4500123456"
    assert snapshot["result"]["invoice_number"] == "RE-2026-10871"
    assert snapshot["result"]["needs_review"] is False


def test_non_pdf_upload_is_rejected(client):
    files = _files(inv_name="Rechnung.docx")
    response = client.post("/api/v1/verifications", files=files)
    assert response.status_code == 400
    assert "must be a PDF" in response.json()["detail"]


def test_negative_tolerance_on_upload_is_rejected(client):
    response = client.post("/api/v1/verifications", files=_files(), data={"price_tolerance_eur": "-3"})
    assert response.status_code == 422


def test_empty_upload_is_rejected(client):
    files = _files()
    files["ab_file"] = ("AB_1.pdf", b"", "application/pdf")
    assert client.post("/api/v1/verifications", files=files).status_code == 400


def test_pipeline_error_is_reported_in_job(client, monkeypatch):
    def boom(path, persist_dir):
        raise ValueError("kein lesbarer Text")

    monkeypatch.setattr(api, "index_single_document", boom)
    run_id = client.post("/api/v1/verifications", files=_files()).json()["run_id"]
    snapshot = client.get(f"/api/v1/verifications/{run_id}").json()

    assert snapshot["state"] == "error"
    assert "kein lesbarer Text" in snapshot["error"]
    assert snapshot["steps"][0]["status"] == "error"


def test_unknown_run_returns_404(client):
    assert client.get("/api/v1/verifications/doesnotexist").status_code == 404
