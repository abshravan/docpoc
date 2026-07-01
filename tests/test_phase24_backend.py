"""Tests for Phase 2-4 backend: papers, proposals, ruleset approval + firewall."""

import io

import pytest

flask = pytest.importorskip("flask")

from epl_cds.contracts import Facts
from tests.fixtures import make_stub_llm

APPROVED_YAML = """
version: "approved-test-v1"
name: "Approved Test"
source: "unit test"
status: "draft"
rules:
  - id: crl_no_cardiac
    tier: diagnostic
    description: "Crown-rump length >= threshold with no cardiac activity."
    citation: "test"
    verify: true
    params:
      crl_mm: 6.0
"""

UNKNOWN_YAML = """
version: "novel-v1"
name: "Novel"
source: "unit test"
status: "draft"
rules:
  - id: brand_new_sign
    tier: diagnostic
    description: "A criterion the engine cannot execute."
    citation: "test"
    verify: true
    params:
      threshold_mm: 3.0
"""


@pytest.fixture
def client(tmp_path):
    from webapp.app import create_app

    app = create_app(
        llm_fn=make_stub_llm(Facts(crl_mm=6.0, cardiac_activity=False, embryo_visible=True)),
        data_dir=str(tmp_path),
    )
    app.testing = True
    return app.test_client()


def test_upload_paper_ingests_into_corpus(client):
    before = len(client.get("/api/papers").get_json()["sources"])
    data = {"file": (io.BytesIO(b"The CRL diagnostic cutoff is 7 mm with no heartbeat."), "p.txt")}
    resp = client.post("/api/papers", data=data, content_type="multipart/form-data")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["chunks_added"] >= 1
    sources = client.get("/api/papers").get_json()["sources"]
    assert len(sources) == before + 1
    assert any("p" in s for s in sources)


def test_proposals_add_and_list(client):
    assert client.get("/api/proposals").get_json()["proposals"] == []
    resp = client.post(
        "/api/proposals",
        json={"name": "Subchorionic hematoma size", "description": "x", "citation": "y"},
    )
    assert resp.get_json()["ok"] is True
    props = client.get("/api/proposals").get_json()["proposals"]
    assert len(props) == 1
    assert props[0]["name"] == "Subchorionic hematoma size"
    assert props[0]["status"] == "proposed"


def test_approve_threshold_ruleset_makes_it_selectable(client):
    resp = client.post(
        "/api/authoring/approve", json={"yaml": APPROVED_YAML, "approver": "Dr. Test"}
    )
    assert resp.status_code == 200
    assert resp.get_json()["activated"] is True

    # It now appears in the ruleset list...
    versions = {r["version"] for r in client.get("/api/rulesets").get_json()["rulesets"]}
    assert "approved-test-v1" in versions

    # ...and drives the engine: CRL 6mm no cardiac is diagnostic under it (>=6),
    # but only suspicious under SRU 2013 (>=7).
    facts = {"crl_mm": 6.0, "cardiac_activity": False, "embryo_visible": True}
    approved = client.post(
        "/api/evaluate", json={"facts": facts, "ruleset_version": "approved-test-v1"}
    ).get_json()
    sru = client.post(
        "/api/evaluate", json={"facts": facts, "ruleset_version": "v1"}
    ).get_json()
    assert approved["determination"] == "diagnostic_of_loss"
    assert sru["determination"] == "suspicious_for_loss"


def test_approve_rejects_unknown_criteria(client):
    # Firewall: novel executable logic can't be approved into the engine.
    resp = client.post(
        "/api/authoring/approve", json={"yaml": UNKNOWN_YAML, "approver": "Dr. Test"}
    )
    assert resp.status_code == 422
    assert "brand_new_sign" in resp.get_json()["error"]


def test_approve_requires_approver(client):
    resp = client.post("/api/authoring/approve", json={"yaml": APPROVED_YAML})
    assert resp.status_code == 400


def test_rulesets_include_rules_for_grid(client):
    rulesets = client.get("/api/rulesets").get_json()["rulesets"]
    sru = next(r for r in rulesets if r["version"] == "v1")
    assert len(sru["rules"]) == 12
    assert any(rule["id"] == "crl_no_cardiac" for rule in sru["rules"])
