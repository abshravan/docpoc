"use strict";

const BOOL_FIELDS = new Set([
  "cardiac_activity", "embryo_visible", "yolk_sac_visible", "amnion_visible",
]);
const INT_FIELDS = new Set([
  "days_since_sac_without_yolk", "days_since_sac_with_yolk", "days_since_lmp",
]);

const form = document.getElementById("facts-form");
const extractBtn = document.getElementById("extract-btn");
const evaluateBtn = document.getElementById("evaluate-btn");
const extractMsg = document.getElementById("extract-msg");
const resultEl = document.getElementById("result");

const TIER_LABEL = {
  diagnostic_of_loss: "Diagnostic of pregnancy loss",
  suspicious_for_loss: "Suspicious for loss",
  no_criteria_met: "No criteria met",
};
const FOLLOWUP = {
  diagnostic_of_loss:
    "Published diagnostic criteria are met. This is decision support, not an " +
    "order — clinical correlation and confirmation remain with the care team.",
  suspicious_for_loss:
    "Follow-up imaging is recommended. This tier never implies treatment.",
  no_criteria_met:
    "No diagnostic or suspicious criteria met on the documented findings.",
};

// --- Extraction (LLM) ---------------------------------------------------- //
if (extractBtn) {
  extractBtn.addEventListener("click", async () => {
    const note = document.getElementById("note").value.trim();
    setMsg("");
    if (!note) { setMsg("Paste a report first.", true); return; }
    extractBtn.disabled = true;
    extractBtn.textContent = "Extracting…";
    try {
      const resp = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ note }),
      });
      const data = await resp.json();
      if (!resp.ok) { setMsg(data.error || "Extraction failed.", true); return; }
      fillForm(data.facts);
      setMsg("Facts proposed by the model — verify them before running the engine.");
    } catch (e) {
      setMsg("Network error: " + e.message, true);
    } finally {
      extractBtn.disabled = false;
      extractBtn.textContent = "Extract facts →";
    }
  });
}

// --- Evaluate (deterministic engine) ------------------------------------- //
evaluateBtn.addEventListener("click", async () => {
  const facts = readForm();
  evaluateBtn.disabled = true;
  try {
    const resp = await fetch("/api/evaluate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ facts }),
    });
    const data = await resp.json();
    if (!resp.ok) { renderError(data.error || "Evaluation failed."); return; }
    renderResult(data);
  } catch (e) {
    renderError("Network error: " + e.message);
  } finally {
    evaluateBtn.disabled = false;
  }
});

function fillForm(facts) {
  for (const [k, v] of Object.entries(facts)) {
    const el = form.elements[k];
    if (!el) continue;
    el.value = v === null || v === undefined ? "" : String(v);
  }
}

function readForm() {
  const facts = {};
  for (const el of form.elements) {
    if (!el.name) continue;
    const raw = el.value.trim();
    if (raw === "") continue; // unknown / not documented
    if (BOOL_FIELDS.has(el.name)) facts[el.name] = raw === "true";
    else if (INT_FIELDS.has(el.name)) facts[el.name] = parseInt(raw, 10);
    else facts[el.name] = parseFloat(raw);
  }
  return facts;
}

function renderResult(data) {
  const tier = data.determination;
  let html = `<span class="badge ${tier}">${TIER_LABEL[tier] || tier}</span>`;
  html += `<p class="rationale">${escapeHtml(data.rationale)}</p>`;
  if (data.fired_rules.length) {
    html += "<h3>Criteria met</h3>";
    for (const r of data.fired_rules) {
      html += `<div class="rule"><div class="rid">${escapeHtml(r.id)} ` +
        `<small>(${escapeHtml(r.tier)})</small></div>` +
        `<div>${escapeHtml(r.description)}</div>` +
        `<div class="cite">${escapeHtml(r.citation)}</div></div>`;
    }
  }
  html += `<div class="followup">${escapeHtml(FOLLOWUP[tier] || "")}</div>`;
  html += `<div class="cite">Ruleset ${escapeHtml(data.ruleset_version)}</div>`;
  resultEl.className = "";
  resultEl.innerHTML = html;
}

function renderError(msg) {
  resultEl.className = "msg error";
  resultEl.textContent = msg;
}

function setMsg(text, isError) {
  extractMsg.textContent = text;
  extractMsg.className = "msg" + (isError ? " error" : "");
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}
