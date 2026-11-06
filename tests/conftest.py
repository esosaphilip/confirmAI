import os
import sys
from types import SimpleNamespace

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)


class FakeChatModel:
    """Stellt ChatOllama nach: antwortet je nach Dokument-Kontext im Prompt."""

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.calls = 0

    async def ainvoke(self, messages):
        self.calls += 1
        prompt = messages[0].content
        for marker, answer in self.responses.items():
            if marker in prompt:
                return SimpleNamespace(content=answer)
        return SimpleNamespace(content='{"total_net": null}')


@pytest.fixture
def fake_pipeline(monkeypatch):
    """Ersetzt Chroma-Retrieval und LLM durch kontrollierbare Fakes.

    Rueckgabe: Funktion ``setup(ab_answer, invoice_answer)``, die die
    Modellantworten fuer AB und Rechnung festlegt.
    """
    import vergleicher

    contexts = {
        "ab_db": "AUFTRAGSBESTAETIGUNG Summe netto 12.350,00 €",
        "invoice_db": "RECHNUNG Summe netto 12.480,00 €",
    }
    monkeypatch.setattr(vergleicher, "_retrieve_context", lambda persist_dir, query, k=4: contexts[persist_dir])

    def setup(ab_answer: str, invoice_answer: str) -> FakeChatModel:
        model = FakeChatModel({"AUFTRAGSBESTAETIGUNG": ab_answer, "RECHNUNG": invoice_answer})
        monkeypatch.setattr(vergleicher, "get_model", lambda: model)
        return model

    return setup
