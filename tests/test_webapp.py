"""Tests for the demo web app — fully offline via an injected stub llm_fn."""

import json

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


def test_config_endpoint(client_with_llm):
    data = client_with_llm.get("/api/config").get_json()
    assert data["extraction_enabled"] is True
    assert data["ruleset_version"] == "v1"
    assert "crl_mm" in data["fact_fields"]


def test_ruleset_endpoint(client_with_llm):
    data = client_with_llm.get("/api/ruleset").get_json()
    assert data["version"] == "v1"
    ids = {r["id"] for r in data["rules"]}
    assert "crl_no_cardiac" in ids
    crl = next(r for r in data["rules"] if r["id"] == "crl_no_cardiac")
    assert crl["params"]["crl_mm"] == 7.0
    assert crl["tier"] == "diagnostic"


def test_authoring_draft_disabled_without_provider(client_no_llm):
    assert client_no_llm.post("/api/authoring/draft", json={"source_text": "x"}).status_code == 503


def test_authoring_draft_requires_source(client_with_llm):
    assert client_with_llm.post("/api/authoring/draft", json={"source_text": " "}).status_code == 400


def test_authoring_draft_returns_unactivated_yaml(client_with_llm):
    # The stub llm returns Facts JSON (no "rules" key), so 0 rules — but the
    # endpoint must still return draft YAML and never activate anything.
    resp = client_with_llm.post("/api/authoring/draft", json={"source_text": "a paper"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["activated"] is False
    assert "DO NOT USE" in data["yaml"]


def test_evidence_status_uses_default_corpus(client_with_llm):
    data = client_with_llm.get("/api/evidence/status").get_json()
    assert data["enabled"] is True
    assert data["chunks"] > 0
    assert any("evidence" in s for s in data["sources"])


def test_evidence_query_returns_citations(client_with_llm):
    resp = client_with_llm.post("/api/evidence", json={"question": "CRL threshold for no heartbeat?"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["citations"]
    # The stub llm returns Facts JSON, but synthesis is still attempted; the
    # citations are what matter for grounding.
    assert "synthesized" in data


def test_evidence_requires_question(client_with_llm):
    assert client_with_llm.post("/api/evidence", json={"question": " "}).status_code == 400


def test_rulesets_list_endpoint(client_with_llm):
    data = client_with_llm.get("/api/rulesets").get_json()
    labels = {r["label"] for r in data["rulesets"]}
    assert "SRU 2013" in labels
    assert len(data["rulesets"]) >= 2


def test_compare_endpoint_flags_divergence(client_with_llm):
    resp = client_with_llm.post(
        "/api/compare", json={"facts": {"msd_mm": 18, "embryo_visible": False}}
    )
    data = resp.get_json()
    assert data["concordant"] is False
    dets = {e["label"]: e["determination"] for e in data["entries"]}
    assert dets["SRU 2013"] == "suspicious_for_loss"


def test_cors_header_present(client_with_llm):
    resp = client_with_llm.get("/api/config")
    assert resp.headers["Access-Control-Allow-Origin"] == "*"


def test_baseline_endpoint(client_with_llm):
    # The stub llm returns Facts JSON, which has no "determination" key, so the
    # baseline can't parse a tier -> None. That's fine; we assert it's labeled
    # non-authoritative and reports the prompt version.
    resp = client_with_llm.post("/api/baseline", json={"note": "CRL 9mm, no FHR"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["authoritative"] is False
    assert data["prompt_version"]


def test_baseline_disabled_without_provider(client_no_llm):
    assert client_no_llm.post("/api/baseline", json={"note": "x"}).status_code == 503


def _read_sse(resp):
    events = []
    for chunk in resp.get_data(as_text=True).split("\n\n"):
        chunk = chunk.strip()
        if chunk.startswith("data: "):
            events.append(json.loads(chunk[len("data: "):]))
    return events


def test_agui_extract_streams_facts_as_state(client_with_llm):
    resp = client_with_llm.post("/api/agui/extract", json={"note": "CRL 9mm, no FHR"})
    assert resp.status_code == 200
    assert resp.mimetype == "text/event-stream"
    events = _read_sse(resp)
    types = [e["type"] for e in events]
    assert types[0] == "RUN_STARTED"
    assert "STATE_SNAPSHOT" in types
    assert types[-1] == "RUN_FINISHED"
    snapshot = next(e for e in events if e["type"] == "STATE_SNAPSHOT")
    assert snapshot["snapshot"]["facts"]["crl_mm"] == 9.0


def test_agui_extract_emits_run_error_without_provider(client_no_llm):
    resp = client_no_llm.post("/api/agui/extract", json={"note": "x"})
    events = _read_sse(resp)
    assert any(e["type"] == "RUN_ERROR" for e in events)
