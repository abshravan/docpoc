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

from datetime import datetime, timezone
from pathlib import Path

import yaml
from flask import Flask, Response, jsonify, render_template, request, send_from_directory
from werkzeug.utils import secure_filename

from epl_cds.contracts import EmbedFn, Facts, LLMFn, OcrFn, Ruleset
from epl_cds.extraction.authoring import AUTHORING_PROMPT_VERSION, draft_ruleset
from epl_cds.extraction.baseline import BASELINE_PROMPT_VERSION, llm_baseline_opinion
from epl_cds.extraction.chat import advisory_chat
from epl_cds.extraction.extractor import ExtractionError, extract_facts
from epl_cds.extraction.ocr import OCRUnavailable
from epl_cds.extraction.prompts import PROMPT_VERSION
from epl_cds.extraction.rag import VectorStore, answer_question, hashing_embed_fn
from epl_cds.knowledge import load_all_rulesets, load_ruleset
from epl_cds.knowledge.validator import RulesetValidationError, validate_ruleset_data
from epl_cds.reasoning.engine import RULE_EVALUATORS, compare_rulesets, evaluate, is_concordant
from epl_cds.registry import ProposedMethod, append_proposal, load_proposals

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


def _ingest_default_corpus(store: VectorStore, papers_dir: Path) -> None:
    """Ingest the shipped example notes plus any uploaded papers."""
    root = Path(__file__).resolve().parents[1]
    example = root / "examples" / "evidence_notes.md"
    if example.exists():
        store.add_text(example.read_text(encoding="utf-8"), example.name)
    if papers_dir.is_dir():
        for path in sorted(papers_dir.glob("*")):
            if path.suffix.lower() in {".md", ".txt"}:
                store.add_text(path.read_text(encoding="utf-8"), path.name)


def _extract_paper_text(raw: bytes, content_type: str, name: str, ocr) -> str:
    """Get text from an uploaded paper: decode text files, OCR PDFs/images."""
    ct = (content_type or "").lower()
    lname = name.lower()
    if lname.endswith((".txt", ".md")) or ct.startswith("text/"):
        return raw.decode("utf-8", errors="ignore")
    if ocr is not None and ("pdf" in ct or ct.startswith("image/") or lname.endswith(".pdf")):
        try:
            return ocr(raw, content_type)
        except OCRUnavailable:
            return ""
    # Last resort: try to decode as text.
    return raw.decode("utf-8", errors="ignore")

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
    embed_fn: Optional[EmbedFn] = None,
    evidence_corpus: Optional[list[tuple[str, str]]] = None,
    ocr_fn: Optional[OcrFn] = None,
    data_dir: Optional[str] = None,
) -> Flask:
    """Application factory.

    `llm_fn` is injected (tests pass a stub). If None, the app tries to resolve
    one from the environment; if that also yields nothing, extraction is
    disabled and the UI falls back to manual fact entry.
    """
    app = Flask(__name__)
    rules = ruleset if ruleset is not None else load_ruleset()

    # Runtime data locations (gitignored). Tests pass a tmp data_dir.
    base_data = Path(data_dir) if data_dir else Path("data")
    papers_dir = base_data / "papers"
    approved_rulesets_dir = base_data / "rulesets"
    proposals_path = base_data / "proposed_methods.jsonl"

    def _load_rulesets():
        rs = load_all_rulesets(extra_dirs=[approved_rulesets_dir])
        return rs, {r.version: r for r in rs}

    # All rulesets: packaged + clinician-approved, for comparison and selection.
    all_rulesets, rulesets_by_version = _load_rulesets()

    resolved_llm = llm_fn
    if resolved_llm is None:
        # Resolve lazily so importing this module never needs a provider SDK.
        from epl_cds.extraction.providers import default_llm_fn_from_env

        resolved_llm = default_llm_fn_from_env()

    # RAG evidence store: a real embedding model if configured, else the
    # offline hashing embedder so retrieval always works without a network.
    resolved_embed = embed_fn
    embed_provider = "injected"
    if resolved_embed is None:
        from epl_cds.extraction.providers import default_embed_fn_from_env

        resolved_embed = default_embed_fn_from_env()
        embed_provider = "ollama" if resolved_embed is not None else "offline-hashing"
    if resolved_embed is None:
        resolved_embed = hashing_embed_fn()
    store = VectorStore(resolved_embed)
    if evidence_corpus is not None:
        for text, source in evidence_corpus:
            store.add_text(text, source)
    else:
        _ingest_default_corpus(store, papers_dir)

    # OCR for uploaded files (Tesseract). None when unavailable — the UI then
    # falls back to pasted text / manual entry.
    resolved_ocr = ocr_fn
    if resolved_ocr is None:
        from epl_cds.extraction.ocr import default_ocr_fn

        resolved_ocr = default_ocr_fn()

    def _rebuild_rulesets():
        nonlocal all_rulesets, rulesets_by_version
        all_rulesets, rulesets_by_version = _load_rulesets()

    app.config["EPL_RULESET"] = rules
    app.config["EPL_LLM_FN"] = resolved_llm
    app.config["EPL_EXTRACTOR_MODEL"] = extractor_model
    app.config["EPL_STORE"] = store
    app.config["EPL_OCR_FN"] = resolved_ocr

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

        @app.get("/<path:path>")
        def spa_fallback(path: str):
            # Client-side routes (e.g. /flow) fall back to the SPA shell.
            if path.startswith("api/"):
                from flask import abort

                abort(404)
            return send_from_directory(dist_dir, "index.html")

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

    @app.post("/api/extract/file")
    def api_extract_file():
        """OCR an uploaded scan file to text, then extract facts from that text.

        OCR is preprocessing; the LLM still only produces facts. Returns the OCR
        text (for the clinician to see) plus extracted facts when a model is set.
        """
        ocr = app.config["EPL_OCR_FN"]
        if ocr is None:
            return jsonify(error="OCR is not available on the server (install tesseract)."), 503
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify(error="No file uploaded."), 400
        try:
            text = ocr(upload.read(), upload.mimetype or "")
        except OCRUnavailable as exc:
            return jsonify(error=f"OCR failed: {exc}"), 502
        text = text.strip()
        result: dict[str, Any] = {"ocr_text": text}
        llm = app.config["EPL_LLM_FN"]
        if llm is not None and text:
            try:
                result["facts"] = asdict(extract_facts(text, llm))
                result["prompt_version"] = PROMPT_VERSION
            except ExtractionError as exc:
                result["extract_error"] = f"Could not parse model output: {exc}"
        return jsonify(**result)

    def _select_ruleset(version: Optional[str]) -> Ruleset:
        if version and version in rulesets_by_version:
            return rulesets_by_version[version]
        return app.config["EPL_RULESET"]

    @app.post("/api/evaluate")
    def api_evaluate():
        data = request.get_json(silent=True) or {}
        try:
            facts = facts_from_payload(data.get("facts", {}))
        except FactsInputError as exc:
            return jsonify(error=str(exc)), 400

        ruleset = _select_ruleset(data.get("ruleset_version"))
        result = evaluate(facts, ruleset)

        # Attach citations for the rules that fired (decision-support context).
        rules_by_id = {r.id: r for r in ruleset.rules}
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
            ruleset_label=ruleset.label,
            facts=asdict(facts),
        )

    @app.post("/api/chat")
    def api_chat():
        """Advisory clinician<->model chat. Never changes the determination."""
        llm = app.config["EPL_LLM_FN"]
        if llm is None:
            return jsonify(error="No model configured for chat."), 503
        data = request.get_json(silent=True) or {}
        messages = data.get("messages") or []
        if not isinstance(messages, list) or not messages:
            return jsonify(error="No messages provided."), 400
        facts = data.get("facts") if isinstance(data.get("facts"), dict) else None
        reply = advisory_chat(messages, facts, app.config["EPL_STORE"], llm)
        return jsonify(
            answer=reply.answer,
            advisory=True,
            citations=[{"source": c.source, "text": c.text} for c in reply.citations],
        )

    @app.get("/api/config")
    def api_config():
        return jsonify(
            extraction_enabled=app.config["EPL_LLM_FN"] is not None,
            ocr_enabled=app.config["EPL_OCR_FN"] is not None,
            chat_enabled=app.config["EPL_LLM_FN"] is not None,
            extractor_model=extractor_model,
            ruleset_version=rules.version,
            ruleset_status=rules.status,
            prompt_version=PROMPT_VERSION,
            baseline_prompt_version=BASELINE_PROMPT_VERSION,
            fact_fields=list(Facts.field_names()),
        )

    @app.get("/api/ruleset")
    def api_ruleset():
        """Expose the frozen ruleset so the UI's decision flowchart sources its
        thresholds from the YAML (clinical truth), never from hardcoded values."""
        return jsonify(
            version=rules.version,
            status=rules.status,
            rules=[
                {
                    "id": r.id,
                    "tier": r.tier,
                    "description": r.description,
                    "citation": r.citation,
                    "params": dict(r.params),
                }
                for r in rules.rules
            ],
        )

    @app.get("/api/evidence/status")
    def api_evidence_status():
        return jsonify(
            enabled=store.size > 0,
            chunks=store.size,
            sources=store.sources,
            embed_provider=embed_provider,
            synthesis=resolved_llm is not None,
        )

    @app.post("/api/evidence")
    def api_evidence():
        """Retrieve cited passages for a question and (if a model is available)
        synthesize a grounded answer. Explainability only — no determination."""
        if store.size == 0:
            return jsonify(error="No evidence corpus is loaded."), 503
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or "").strip()
        if not question:
            return jsonify(error="No question provided."), 400
        ans = answer_question(question, store, llm_fn=resolved_llm)
        return jsonify(
            answer=ans.answer,
            synthesized=ans.synthesized,
            prompt_version=ans.prompt_version,
            citations=[{"source": c.source, "text": c.text} for c in ans.citations],
        )

    @app.post("/api/authoring/draft")
    def api_authoring_draft():
        """Draft a candidate ruleset from pasted source text (human review only).

        Returns UNVERIFIED YAML with verify:true on every rule. Never activates a
        ruleset and never writes to the live knowledge path — promotion is a
        deliberate human step after expert sign-off.
        """
        llm = app.config["EPL_LLM_FN"]
        if llm is None:
            return jsonify(error="No model configured for ruleset drafting."), 503
        data = request.get_json(silent=True) or {}
        source_text = (data.get("source_text") or "").strip()
        if not source_text:
            return jsonify(error="No source text provided."), 400
        draft = draft_ruleset(
            source_text,
            llm,
            name=str(data.get("name") or "Drafted ruleset"),
            version=str(data.get("version") or "draft-v1"),
            source_label=str(data.get("source_label") or "pasted source text"),
        )
        return jsonify(
            yaml=draft.yaml_text,
            rule_count=draft.rule_count,
            warnings=draft.warnings,
            prompt_version=draft.prompt_version,
            proposals=draft.proposals,
            activated=False,
        )

    @app.post("/api/authoring/approve")
    def api_authoring_approve():
        """Approve a threshold-only draft into a selectable ruleset.

        FIREWALL GUARD: only rulesets whose every rule id has a coded engine
        evaluator can be approved. A draft that references a novel criterion is
        rejected — that path goes to the proposals queue for a developer, not to
        the live engine. Records the approver + timestamp for the audit trail.
        """
        data = request.get_json(silent=True) or {}
        yaml_text = data.get("yaml") or ""
        approver = str(data.get("approver") or "").strip()
        if not yaml_text.strip():
            return jsonify(error="No ruleset YAML provided."), 400
        if not approver:
            return jsonify(error="An approver name is required (sign-off record)."), 400
        try:
            parsed = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            return jsonify(error=f"Invalid YAML: {exc}"), 400
        try:
            validate_ruleset_data(parsed)
        except RulesetValidationError as exc:
            return jsonify(error=f"Ruleset failed validation: {exc}"), 400

        unknown = sorted({r["id"] for r in parsed["rules"] if r["id"] not in RULE_EVALUATORS})
        if unknown:
            return (
                jsonify(
                    error=(
                        "Cannot approve: these criteria have no coded engine "
                        f"evaluator and cannot be executed safely: {unknown}. "
                        "Queue them as proposals for implementation instead."
                    )
                ),
                422,
            )

        version = str(parsed.get("version") or "").strip()
        if version in rulesets_by_version:
            return jsonify(error=f"Ruleset version {version!r} already exists."), 409

        stamp = datetime.now(timezone.utc).isoformat()
        parsed["status"] = f"APPROVED by {approver} on {stamp}. " + str(parsed.get("status", ""))
        approved_rulesets_dir.mkdir(parents=True, exist_ok=True)
        safe_name = secure_filename(version) or "approved"
        (approved_rulesets_dir / f"{safe_name}.yaml").write_text(
            yaml.safe_dump(parsed, sort_keys=False), encoding="utf-8"
        )
        _rebuild_rulesets()
        return jsonify(activated=True, version=version, label=parsed.get("name") or version)

    @app.get("/api/proposals")
    def api_proposals():
        methods = load_proposals(proposals_path)
        return jsonify(
            proposals=[
                {
                    "name": m.name,
                    "description": m.description,
                    "citation": m.citation,
                    "status": m.status,
                    "created_at": m.created_at,
                }
                for m in methods
            ]
        )

    @app.post("/api/proposals")
    def api_add_proposal():
        """Queue a novel criterion as a NON-EXECUTABLE proposal for a developer."""
        data = request.get_json(silent=True) or {}
        name = str(data.get("name") or "").strip()
        if not name:
            return jsonify(error="A proposal name is required."), 400
        append_proposal(
            proposals_path,
            ProposedMethod(
                name=name,
                description=str(data.get("description") or "").strip(),
                citation=str(data.get("citation") or "").strip(),
            ),
        )
        return jsonify(ok=True)

    @app.get("/api/papers")
    def api_papers():
        return jsonify(sources=store.sources)

    @app.post("/api/papers")
    def api_upload_paper():
        """Ingest an uploaded reference paper into the RAG corpus (evidence + chat)."""
        upload = request.files.get("file")
        if upload is None or not upload.filename:
            return jsonify(error="No file uploaded."), 400
        raw = upload.read()
        name = secure_filename(upload.filename) or "paper"
        text = _extract_paper_text(raw, upload.mimetype or "", name, app.config["EPL_OCR_FN"])
        if not text.strip():
            return jsonify(error="Could not extract text from the file."), 422
        papers_dir.mkdir(parents=True, exist_ok=True)
        (papers_dir / f"{name}.txt").write_text(text, encoding="utf-8")
        added = store.add_text(text, name)
        return jsonify(source=name, chunks_added=added, total_chunks=store.size)

    @app.get("/api/rulesets")
    def api_rulesets():
        return jsonify(
            rulesets=[
                {
                    "label": rs.label,
                    "version": rs.version,
                    "status": rs.status,
                    "rule_count": len(rs.rules),
                    "rules": [
                        {
                            "id": r.id,
                            "tier": r.tier,
                            "description": r.description,
                            "citation": r.citation,
                            "params": dict(r.params),
                        }
                        for r in rs.rules
                    ],
                }
                for rs in all_rulesets
            ]
        )

    @app.post("/api/compare")
    def api_compare():
        """Run the case through every curated ruleset and report concordance.

        Deterministic comparison only — independent engine verdicts, no voting
        and no LLM. Shows the clinician where guidelines agree or diverge.
        """
        data = request.get_json(silent=True) or {}
        try:
            facts = facts_from_payload(data.get("facts", {}))
        except FactsInputError as exc:
            return jsonify(error=str(exc)), 400

        entries = compare_rulesets(facts, all_rulesets)
        rules_by_version = {rs.version: {r.id: r for r in rs.rules} for rs in all_rulesets}
        return jsonify(
            concordant=is_concordant(entries),
            entries=[
                {
                    "label": e.ruleset_label,
                    "version": e.ruleset_version,
                    "determination": e.result.determination.value,
                    "rationale": e.result.rationale,
                    "fired_rules": [
                        {
                            "id": rid,
                            "tier": rules_by_version[e.ruleset_version][rid].tier,
                            "description": rules_by_version[e.ruleset_version][rid].description,
                            "citation": rules_by_version[e.ruleset_version][rid].citation,
                        }
                        for rid in e.result.fired_rule_ids
                    ],
                }
                for e in entries
            ],
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
