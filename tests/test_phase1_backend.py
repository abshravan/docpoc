"""Tests for Phase 1 backend: OCR file extract, ruleset select, advisory chat."""

import io
import json

import pytest

flask = pytest.importorskip("flask")

from epl_cds.contracts import Facts
from tests.fixtures import make_stub_llm


def _fake_ocr(text: str):
    def _ocr(data: bytes, content_type: str) -> str:
        return text
    return _ocr


@pytest.fixture
def client():
    from webapp.app import create_app

    facts = Facts(crl_mm=9.0, cardiac_activity=False, embryo_visible=True)
    app = create_app(llm_fn=make_stub_llm(facts), ocr_fn=_fake_ocr("CRL 9mm, no FHR"))
    app.testing = True
    return app.test_client()


@pytest.fixture
def client_no_ocr():
    from webapp.app import create_app

    app = create_app(llm_fn=None, ocr_fn=None)
    app.config["EPL_OCR_FN"] = None
    app.config["EPL_LLM_FN"] = None
    app.testing = True
    return app.test_client()


def test_config_reports_ocr_and_chat(client):
    cfg = client.get("/api/config").get_json()
    assert cfg["ocr_enabled"] is True
    assert cfg["chat_enabled"] is True


def test_file_extract_ocrs_then_extracts(client):
    data = {"file": (io.BytesIO(b"fake-image-bytes"), "scan.png")}
    resp = client.post("/api/extract/file", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["ocr_text"] == "CRL 9mm, no FHR"
    # The stub llm returns the injected facts regardless of prompt.
    assert body["facts"]["crl_mm"] == 9.0


def test_file_extract_requires_file(client):
    resp = client.post("/api/extract/file", data={}, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_file_extract_503_without_ocr(client_no_ocr):
    data = {"file": (io.BytesIO(b"x"), "scan.png")}
    resp = client_no_ocr.post("/api/extract/file", data=data, content_type="multipart/form-data")
    assert resp.status_code == 503


def test_evaluate_honors_selected_ruleset(client):
    # MSD 18 no embryo: SRU (v1) -> suspicious; legacy strict -> diagnostic.
    facts = {"msd_mm": 18, "embryo_visible": False}
    sru = client.post("/api/evaluate", json={"facts": facts, "ruleset_version": "v1"}).get_json()
    legacy = client.post(
        "/api/evaluate",
        json={"facts": facts, "ruleset_version": "legacy-strict-example-v1"},
    ).get_json()
    assert sru["determination"] == "suspicious_for_loss"
    assert legacy["determination"] == "diagnostic_of_loss"
    assert legacy["ruleset_label"] == "Legacy strict (EXAMPLE)"


def test_chat_is_advisory_and_grounded(client):
    resp = client.post(
        "/api/chat",
        json={
            "messages": [{"role": "user", "content": "What does the CRL threshold mean here?"}],
            "facts": {"crl_mm": 9.0, "cardiac_activity": False},
        },
    )
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["advisory"] is True
    assert "citations" in body


def test_chat_requires_messages(client):
    assert client.post("/api/chat", json={"messages": []}).status_code == 400


def test_chat_503_without_model(client_no_ocr):
    resp = client_no_ocr.post("/api/chat", json={"messages": [{"role": "user", "content": "hi"}]})
    assert resp.status_code == 503
