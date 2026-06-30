"""Flask app for the EPL-CDS clinician-facing demo.

Endpoints:
  GET  /              the two-panel demo page
  POST /api/extract   {note}  -> {facts}        (LLM; 503 if no provider)
  POST /api/evaluate  {facts} -> {determination, fired_rules, rationale, ...}

The engine endpoint is pure and always available; the extract endpoint is the
only one that touches a model, and only if an llm_fn was injected/configured.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict
from typing import Any, Iterator, Optional

from pathlib import Path

from flask import Flask, Response, jsonify, render_template, request, send_from_directory

from epl_cds.contracts import Facts, LLMFn, Ruleset
from epl_cds.extraction.baseline import BASELINE_PROMPT_VERSION, llm_baseline_opinion
from epl_cds.extraction.extractor import ExtractionError, extract_facts
from epl_cds.extraction.prompts import PROMPT_VERSION
from epl_cds.knowledge import load_ruleset
from epl_cds.reasoning.engine import evaluate

# Canonical AG-UI protocol event types (subset we emit). See https://ag-ui.com.
AGUI_EVENTS = {
    "RUN_STARTED": "RUN_STARTED",
    "RUN_FINISHED": "RUN_FINISHED",
    "RUN_ERROR": "RUN_ERROR",
    "TEXT_MESSAGE_START": "TEXT_MESSAGE_START",
    "TEXT_MESSAGE_CONTENT": "TEXT_MESSAGE_CONTENT",
    "TEXT_MESSAGE_END": "TEXT_MESSAGE_END",
    "STATE_SNAPSHOT": "STATE_SNAPSHOT",
}


def _sse(event: dict[str, Any]) -> str:
    """Encode one AG-UI event as a Server-Sent Events frame."""
    return f"data: {json.dumps(event)}\n\n"

_BOOL_FIELDS = {"cardiac_activity", "embryo_visible", "yolk_sac_visible", "amnion_visible"}
_INT_FIELDS = {"days_since_sac_without_yolk", "days_since_sac_with_yolk", "days_since_lmp"}
_FLOAT_FIELDS = {"crl_mm", "msd_mm", "yolk_sac_diameter_mm"}


class FactsInputError(ValueError):
    """Raised when a posted facts payload cannot be coerced into Facts."""


def facts_from_payload(payload: Any) -> Facts:
    """Build Facts from a JSON object, treating "" / missing as None.

    Defensive: the form posts typed JSON, but we re-coerce server-side so the
    deterministic engine only ever sees clean, typed values.
    """
    if not isinstance(payload, dict):
        raise FactsInputError("facts payload must be an object")
    known = set(Facts.field_names())
    kwargs: dict[str, Any] = {}
    for key, value in payload.items():
        if key not in known:
            continue
        if value is None or value == "":
            continue
        kwargs[key] = _coerce(key, value)
    return Facts(**kwargs)


def _coerce(key: str, value: Any) -> Any:
    if key in _BOOL_FIELDS:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            low = value.strip().lower()
            if low in {"true", "yes", "present"}:
                return True
            if low in {"false", "no", "absent"}:
                return False
        raise FactsInputError(f"{key!r} must be true/false")
    if key in _INT_FIELDS:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise FactsInputError(f"{key!r} must be an integer")
    if key in _FLOAT_FIELDS:
        try:
            return float(value)
        except (TypeError, ValueError):
            raise FactsInputError(f"{key!r} must be a number")
    raise FactsInputError(f"unexpected field {key!r}")  # pragma: no cover


def create_app(
    llm_fn: Optional[LLMFn] = None,
    ruleset: Optional[Ruleset] = None,
    *,
    extractor_model: str = "configured-provider",
) -> Flask:
    """Application factory.

    `llm_fn` is injected (tests pass a stub). If None, the app tries to resolve
    one from the environment; if that also yields nothing, extraction is
    disabled and the UI falls back to manual fact entry.
    """
    app = Flask(__name__)
    rules = ruleset if ruleset is not None else load_ruleset()

    resolved_llm = llm_fn
    if resolved_llm is None:
        # Resolve lazily so importing this module never needs a provider SDK.
        from epl_cds.extraction.providers import default_llm_fn_from_env

        resolved_llm = default_llm_fn_from_env()

    app.config["EPL_RULESET"] = rules
    app.config["EPL_LLM_FN"] = resolved_llm
    app.config["EPL_EXTRACTOR_MODEL"] = extractor_model

    cors_origin = os.environ.get("EPL_CORS_ORIGIN", "*")

    @app.after_request
    def _add_cors(resp):
        # Allow the Vite dev server (separate origin) to call the API.
        resp.headers["Access-Control-Allow-Origin"] = cors_origin
        resp.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
        return resp

    # Single-process production: serve the built React SPA when EPL_SERVE_FRONTEND=1
    # and a build exists. Dev uses the Vite server (port 5173) against this API.
    dist_dir = Path(__file__).resolve().parents[1] / "frontend" / "dist"
    serve_frontend = os.environ.get("EPL_SERVE_FRONTEND") == "1" and (dist_dir / "index.html").exists()

    @app.get("/")
    def index():
        if serve_frontend:
            return send_from_directory(dist_dir, "index.html")
        # Lightweight no-build fallback (also what the test suite exercises).
        return render_template(
            "index.html",
            ruleset_version=rules.version,
            ruleset_status=rules.status,
            prompt_version=PROMPT_VERSION,
            fact_fields=list(Facts.field_names()),
            extraction_enabled=resolved_llm is not None,
            extractor_model=extractor_model,
        )

    if serve_frontend:

        @app.get("/assets/<path:filename>")
        def assets(filename: str):
            return send_from_directory(dist_dir / "assets", filename)

    @app.post("/api/extract")
    def api_extract():
        llm = app.config["EPL_LLM_FN"]
        if llm is None:
            return (
                jsonify(
                    error="Extraction is not configured. Set a provider "
                    "(e.g. ANTHROPIC_API_KEY) or enter facts manually."
                ),
                503,
            )
        data = request.get_json(silent=True) or {}
        note = (data.get("note") or "").strip()
        if not note:
            return jsonify(error="No report text provided."), 400
        try:
            facts = extract_facts(note, llm)
        except ExtractionError as exc:
            return jsonify(error=f"Could not parse model output: {exc}"), 502
        return jsonify(facts=asdict(facts), prompt_version=PROMPT_VERSION)

    @app.post("/api/evaluate")
    def api_evaluate():
        data = request.get_json(silent=True) or {}
        try:
            facts = facts_from_payload(data.get("facts", {}))
        except FactsInputError as exc:
            return jsonify(error=str(exc)), 400

        result = evaluate(facts, app.config["EPL_RULESET"])

        # Attach citations for the rules that fired (decision-support context).
        rules_by_id = {r.id: r for r in app.config["EPL_RULESET"].rules}
        fired = [
            {
                "id": rid,
                "tier": rules_by_id[rid].tier,
                "description": rules_by_id[rid].description,
                "citation": rules_by_id[rid].citation,
            }
            for rid in result.fired_rule_ids
        ]
        return jsonify(
            determination=result.determination.value,
            fired_rules=fired,
            rationale=result.rationale,
            ruleset_version=result.ruleset_version,
            facts=asdict(facts),
        )

    @app.get("/api/config")
    def api_config():
        return jsonify(
            extraction_enabled=app.config["EPL_LLM_FN"] is not None,
            extractor_model=extractor_model,
            ruleset_version=rules.version,
            ruleset_status=rules.status,
            prompt_version=PROMPT_VERSION,
            baseline_prompt_version=BASELINE_PROMPT_VERSION,
            fact_fields=list(Facts.field_names()),
        )

    @app.post("/api/baseline")
    def api_baseline():
        """NON-AUTHORITATIVE LLM opinion for research comparison only.

        This never influences /api/evaluate; the deterministic engine remains the
        sole source of the determination.
        """
        llm = app.config["EPL_LLM_FN"]
        if llm is None:
            return jsonify(error="No model configured for the LLM baseline."), 503
        data = request.get_json(silent=True) or {}
        note = (data.get("note") or "").strip()
        if not note:
            return jsonify(error="No report text provided."), 400
        opinion = llm_baseline_opinion(note, llm, model=extractor_model)
        return jsonify(
            determination=opinion.determination.value if opinion.determination else None,
            rationale=opinion.rationale,
            model=opinion.model,
            prompt_version=opinion.prompt_version,
            authoritative=False,
        )

    @app.post("/api/agui/extract")
    def api_agui_extract():
        """Stream extraction as AG-UI protocol events (SSE).

        The agent proposes Facts as shared state (STATE_SNAPSHOT); the React
        Verify-facts panel binds to that state. The human edits it before the
        deterministic engine ever runs.
        """
        llm = app.config["EPL_LLM_FN"]
        data = request.get_json(silent=True) or {}
        note = (data.get("note") or "").strip()
        thread_id = data.get("threadId") or uuid.uuid4().hex
        run_id = data.get("runId") or uuid.uuid4().hex

        def stream() -> Iterator[str]:
            yield _sse({"type": "RUN_STARTED", "threadId": thread_id, "runId": run_id})
            msg_id = uuid.uuid4().hex
            yield _sse({"type": "TEXT_MESSAGE_START", "messageId": msg_id, "role": "assistant"})

            if llm is None:
                yield _sse({
                    "type": "TEXT_MESSAGE_CONTENT",
                    "messageId": msg_id,
                    "delta": "No model configured — enter facts manually.",
                })
                yield _sse({"type": "TEXT_MESSAGE_END", "messageId": msg_id})
                yield _sse({
                    "type": "RUN_ERROR",
                    "message": "Extraction is not configured.",
                    "code": "no_provider",
                })
                return

            if not note:
                yield _sse({"type": "TEXT_MESSAGE_END", "messageId": msg_id})
                yield _sse({"type": "RUN_ERROR", "message": "No report text provided."})
                return

            yield _sse({
                "type": "TEXT_MESSAGE_CONTENT",
                "messageId": msg_id,
                "delta": f"Extracting facts with {extractor_model}…",
            })
            yield _sse({"type": "TEXT_MESSAGE_END", "messageId": msg_id})

            try:
                facts = extract_facts(note, llm)
            except ExtractionError as exc:
                yield _sse({"type": "RUN_ERROR", "message": f"Could not parse model output: {exc}"})
                return

            # The proposed facts become the agent's shared state.
            yield _sse({
                "type": "STATE_SNAPSHOT",
                "snapshot": {"facts": asdict(facts), "promptVersion": PROMPT_VERSION},
            })
            yield _sse({"type": "RUN_FINISHED", "threadId": thread_id, "runId": run_id})

        return Response(
            stream(),
            mimetype="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
                "Connection": "keep-alive",
            },
        )

    return app


# `python -m webapp` / `flask --app webapp.app run` entrypoint.
def main() -> None:  # pragma: no cover - manual run
    import os

    app = create_app()
    app.run(
        host=os.environ.get("EPL_HOST", "127.0.0.1"),
        port=int(os.environ.get("EPL_PORT", "5000")),
        debug=os.environ.get("EPL_DEBUG") == "1",
    )


if __name__ == "__main__":  # pragma: no cover
    main()
