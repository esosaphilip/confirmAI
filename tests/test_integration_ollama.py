"""End-to-end-Test gegen ein echtes, lokal laufendes Ollama.

Wird nur mit ``pytest -m integration`` ausgefuehrt und uebersprungen, wenn
Ollama nicht erreichbar ist. Nutzt die Beispiel-PDFs aus ``sample_docs/``.
"""

import os
import urllib.request

import pytest

pytestmark = pytest.mark.integration

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAMPLES = os.path.join(ROOT, "sample_docs")


def _ollama_up() -> bool:
    url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    try:
        with urllib.request.urlopen(f"{url}/api/tags", timeout=2):
            return True
    except OSError:
        return False


@pytest.mark.skipif(not _ollama_up(), reason="Ollama is not running")
@pytest.mark.parametrize(
    "invoice, expected",
    [("RE-2026-10871.pdf", "NEGATIVE"), ("RE-2026-10872.pdf", "POSITIVE")],
)
async def test_sample_documents_end_to_end(tmp_path, invoice, expected):
    from indexing import index_single_document
    from vergleicher import averify_invoice_vs_ab

    ab_db, inv_db = str(tmp_path / "ab"), str(tmp_path / "inv")
    index_single_document(os.path.join(SAMPLES, "AB_4500123456.pdf"), ab_db)
    index_single_document(os.path.join(SAMPLES, invoice), inv_db)

    result = await averify_invoice_vs_ab(5.0, ab_db, inv_db)

    assert result["status"] == expected
    assert result["ab_price"] == pytest.approx(12350.0)
