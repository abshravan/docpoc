"""Tests for the demo web app — fully offline via an injected stub llm_fn."""

import pytest

flask = pytest.importorskip("flask")  # skip if Flask isn't installed

from epl_cds.contracts import Facts
from tests.fixtures import make_stub_llm, stub_llm


@pytest.fixture
def client_with_llm():
    from webapp.app import create_app

    facts = Facts(crl_mm=9.0, cardiac_activity=False, embryo_visible=True)
    app = create_app(llm_fn=make_stub_llm(facts))
    app.testing = True
    return app.test_client()


@pytest.fixture
def client_no_llm():
    from webapp.app import create_app

    app = create_app(llm_fn=None, ruleset=None)
    # Force extraction-disabled regardless of environment.
    app.config["EPL_LLM_FN"] = None
    app.testing = True
    return app.test_client()


def test_index_renders(client_with_llm):
    resp = client_with_llm.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "not a medical device" in body
    assert "Deterministic" in body


def test_extract_returns_facts(client_with_llm):
    resp = client_with_llm.post("/api/extract", json={"note": "CRL 9mm, no FHR."})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["facts"]["crl_mm"] == 9.0
    assert data["facts"]["cardiac_activity"] is False


def test_extract_requires_note(client_with_llm):
    resp = client_with_llm.post("/api/extract", json={"note": "  "})
    assert resp.status_code == 400


def test_evaluate_is_deterministic_and_diagnostic(client_with_llm):
    resp = client_with_llm.post(
        "/api/evaluate",
        json={"facts": {"crl_mm": 7.0, "cardiac_activity": False, "embryo_visible": True}},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["determination"] == "diagnostic_of_loss"
    assert any(r["id"] == "crl_no_cardiac" for r in data["fired_rules"])
    assert data["fired_rules"][0]["citation"]  # citation surfaced


def test_evaluate_boundary_suspicious(client_with_llm):
    resp = client_with_llm.post(
        "/api/evaluate",
        json={"facts": {"crl_mm": 6.9, "cardiac_activity": False, "embryo_visible": True}},
    )
    assert resp.get_json()["determination"] == "suspicious_for_loss"


def test_evaluate_blank_fields_are_unknown(client_with_llm):
    resp = client_with_llm.post(
        "/api/evaluate", json={"facts": {"crl_mm": "", "cardiac_activity": ""}}
    )
    assert resp.get_json()["determination"] == "no_criteria_met"


def test_evaluate_rejects_bad_type(client_with_llm):
    resp = client_with_llm.post(
        "/api/evaluate", json={"facts": {"crl_mm": "not-a-number"}}
    )
    assert resp.status_code == 400


def test_extract_disabled_without_provider(client_no_llm):
    resp = client_no_llm.post("/api/extract", json={"note": "anything"})
    assert resp.status_code == 503
    # Deterministic engine still works with manual facts.
    ev = client_no_llm.post(
        "/api/evaluate", json={"facts": {"msd_mm": 25, "embryo_visible": False}}
    )
    assert ev.get_json()["determination"] == "diagnostic_of_loss"
