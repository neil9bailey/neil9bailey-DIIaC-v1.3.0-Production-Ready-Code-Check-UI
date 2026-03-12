import express from "express";
import cors from "cors";
import fs from "fs";
import path from "path";
import crypto from "crypto";
import { fileURLToPath } from "url";
import { spawn, spawnSync } from "child_process";
import OpenAI from "openai";
import { requireRole } from "./auth/rbac.js";
import { entraAuth, isEntraEnabled, getAuthMode } from "./auth/entra.js";
import { isCopilotConfigured } from "./llm-ingestion/providers/copilot.js";
import { ingestRouter } from "./llm-ingestion/ingestRouter.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function loadLocalEnvFile() {
  const envPath = path.join(__dirname, ".env");
  if (!fs.existsSync(envPath)) return;
  const raw = fs.readFileSync(envPath, "utf8");
  for (const line of raw.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const idx = trimmed.indexOf("=");
    const key = trimmed.slice(0, idx).trim();
    const value = trimmed.slice(idx + 1).trim();
    if (key && process.env[key] === undefined) {
      process.env[key] = value;
    }
  }
}

loadLocalEnvFile();

const app = express();
const PORT = 3001;

const WORKSPACE = "/workspace";
const HUMAN_INPUT_DIR = `${WORKSPACE}/artefacts/human-input`;
const DECISION_PACK_BASE = `${WORKSPACE}/artefacts/decision-packs`;
const LEDGER_PATH = `${WORKSPACE}/ledger/ledger.jsonl`;
const KEYS_DIR = `${WORKSPACE}/contracts/keys`;
const PUBLIC_KEYS_PATH = `${KEYS_DIR}/public_keys.json`;
const BRIDGE_STATE_PATH = process.env.BRIDGE_STATE_PATH || `${WORKSPACE}/state/operations_state.json`;
const MAX_INTERCEPT_EVENTS = 10000;

const SIGNING_ENABLED = process.env.SIGNING_ENABLED !== "false";
const SIGNING_KEY_ID = process.env.SIGNING_KEY_ID || "ephemeral-local-ed25519";


fs.mkdirSync(HUMAN_INPUT_DIR, { recursive: true });
fs.mkdirSync(DECISION_PACK_BASE, { recursive: true });
fs.mkdirSync(path.dirname(LEDGER_PATH), { recursive: true });
fs.mkdirSync(KEYS_DIR, { recursive: true });

function loadOrCreateSigningKeyPair() {
  const pem = process.env.SIGNING_PRIVATE_KEY_PEM;
  if (pem) {
    const privateKey = crypto.createPrivateKey(pem);
    const publicKey = crypto.createPublicKey(privateKey);
    return { privateKey, publicKey, keyMode: "configured" };
  }
  const { privateKey, publicKey } = crypto.generateKeyPairSync("ed25519");
  return { privateKey, publicKey, keyMode: "ephemeral" };
}

const { publicKey: signingPublicKey, keyMode: signingKeyMode } = loadOrCreateSigningKeyPair();

if (!fs.existsSync(PUBLIC_KEYS_PATH)) {
  const pubDer = signingPublicKey.export({ type: "spki", format: "der" });
  fs.writeFileSync(
    PUBLIC_KEYS_PATH,
    JSON.stringify(
      {
        keys: [
          {
            key_id: SIGNING_KEY_ID,
            algorithm: "Ed25519",
            public_key_b64: Buffer.from(pubDer).toString("base64"),
          },
        ],
      },
      null,
      2,
    ),
  );
}

const LLM_ENABLED = process.env.LLM_INGESTION_ENABLED === "true";
const LLM_STUB_ENABLED = process.env.LLM_STUB_ENABLED === "true";
const LLM_PROVIDER_MODE = "copilot_only";

const COPILOT_MODEL = process.env.COPILOT_MODEL || "gpt-4o";
const copilotClient = (LLM_ENABLED && process.env.GITHUB_TOKEN)
  ? new OpenAI({ baseURL: "https://models.inference.ai.azure.com", apiKey: process.env.GITHUB_TOKEN })
  : null;

function normalizeProviderName(rawProvider) {
  if (typeof rawProvider !== "string") return "Copilot";
  if (rawProvider.trim().toLowerCase() === "copilot") return "Copilot";
  return "Copilot";
}

function enforceProviderMode(requestedProvider) {
  if (typeof requestedProvider === "string" && requestedProvider.trim()) {
    const normalizedInput = requestedProvider.trim().toLowerCase();
    if (normalizedInput !== "copilot") {
      return { ok: false, provider: "Copilot", error: "provider_locked_to_copilot" };
    }
  }
  return { ok: true, provider: normalizeProviderName(requestedProvider), error: null };
}

const devFrontendPorts = new Set(["5173", "5174"]);
if (process.env.FRONTEND_HOST_PORT) {
  devFrontendPorts.add(String(process.env.FRONTEND_HOST_PORT).trim());
}
const devLocalOrigins = [...devFrontendPorts]
  .filter((port) => /^\d+$/.test(port))
  .flatMap((port) => [`http://localhost:${port}`, `http://127.0.0.1:${port}`]);

const allowedOrigins = new Set([
  ...(process.env.APP_ENV !== "production" ? devLocalOrigins : []),
  ...(process.env.ALLOWED_ORIGINS
    ? process.env.ALLOWED_ORIGINS.split(",").map((s) => s.trim()).filter(Boolean)
    : []),
]);

app.use(cors({
  origin(origin, cb) {
    if (!origin || allowedOrigins.has(origin)) return cb(null, true);
    return cb(new Error("Not allowed by CORS"));
  },
  allowedHeaders: ["Content-Type", "x-role", "Authorization"]
}));

// Security headers
app.use((_req, res, next) => {
  res.setHeader("X-Content-Type-Options", "nosniff");
  res.setHeader("X-Frame-Options", "DENY");
  res.setHeader("X-XSS-Protection", "1; mode=block");
  res.setHeader("Referrer-Policy", "strict-origin-when-cross-origin");
  next();
});

// Entra ID JWT authentication (no-op when AUTH_MODE is not entra_jwt_*)
app.use(entraAuth());

app.use(express.json({ limit: "1mb" }));
app.use("/api/ingest", ingestRouter);

/* ================= HEALTH ================= */

app.get("/health", (_req, res) => {
  return res.json({
    status: "OK",
    service: "backend-ui-bridge",
    auth_mode: getAuthMode(),
    timestamp: new Date().toISOString(),
  });
});

app.get("/readiness", async (_req, res) => {
  const checks = {
    bridge_state_writable: false,
    runtime_reachable: false,
  };

  try {
    const stateDir = path.dirname(BRIDGE_STATE_PATH);
    fs.mkdirSync(stateDir, { recursive: true });
    fs.accessSync(stateDir, fs.constants.W_OK);
    checks.bridge_state_writable = true;
  } catch (_err) {
    checks.bridge_state_writable = false;
  }

  try {
    await ensurePythonRuntime();
    const health = await queryPython("/health");
    checks.runtime_reachable = health.ok;
  } catch (_err) {
    checks.runtime_reachable = false;
  }

  const ready = checks.bridge_state_writable && checks.runtime_reachable;
  return res.status(ready ? 200 : 503).json({
    status: ready ? "READY" : "NOT_READY",
    checks,
    timestamp: new Date().toISOString(),
  });
});

/* ================= SANITISATION ================= */

function sanitizeExecId(raw) {
  return String(raw).replace(/[^a-zA-Z0-9\-]/g, "");
}

/* ================= HASHING ================= */

function sha256(input) {
  return crypto.createHash("sha256").update(input).digest("hex");
}

function stableJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((v) => stableJson(v)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${stableJson(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}

/* ================= LEDGER ================= */

function ensureLedger() {
  if (!fs.existsSync(LEDGER_PATH)) fs.writeFileSync(LEDGER_PATH, "");
}

function getLastHash() {
  ensureLedger();
  const raw = fs.readFileSync(LEDGER_PATH, "utf8").trim();
  if (!raw) return "GENESIS";
  const lines = raw.split("\n").filter(Boolean);
  return JSON.parse(lines[lines.length - 1]).record_hash;
}

function appendLedger(record) {
  const full = { ...record, previous_hash: getLastHash() };
  const record_hash = sha256(stableJson(full));
  const sealed = { ...full, record_hash };
  fs.appendFileSync(LEDGER_PATH, JSON.stringify(sealed) + "\n");
  return sealed;
}

/* ================= TRUST ================= */

app.get("/trust", requireRole(["admin", "standard", "customer"]), async (_req, res) => {
  try {
    await ensurePythonRuntime();
    const trust = await queryPython("/trust/status");
    if (!trust.ok) {
      return res.status(trust.status).json({
        error: "trust_status_unavailable",
        details: trust.body,
      });
    }

    const payload = trust.body || {};
    const records = Number(payload.ledger_records || 0);
    const ledgerRoot = payload.latest_merkle_root || payload.latest_record_hash || "GENESIS";

    return res.json({
      valid: Boolean(payload.ledger_chain_valid),
      records,
      ledger_root: ledgerRoot,
      frozen: true,
    });
  } catch (err) {
    return res.status(502).json({
      error: "trust_proxy_error",
      details: process.env.APP_ENV === "development" ? String(err) : undefined,
    });
  }
});

/* ================= HUMAN INPUT ================= */

app.post("/api/human-input",
  requireRole(["admin", "standard", "customer"]),
  (req, res) => {
    fs.mkdirSync(HUMAN_INPUT_DIR, { recursive: true });
    const id = Date.now();
    const filePath = path.join(HUMAN_INPUT_DIR, `${id}.json`);
    fs.writeFileSync(filePath, JSON.stringify(req.body, null, 2));
    res.json({ saved: `${id}.json` });
  }
);

/* ================= R/P ENFORCEMENT ================= */

function enforceSections(reportJSON, reasoning_level, policy_level) {

  const reasoningMap = {
    R0: ["executive_summary"],
    R1: ["executive_summary"],
    R2: ["executive_summary", "strategic_context"],
    R3: ["executive_summary", "strategic_context", "market_analysis"],
    R4: ["executive_summary", "strategic_context", "market_analysis", "risk_matrix"],
    R5: [
      "executive_summary",
      "strategic_context",
      "market_analysis",
      "risk_matrix",
      "financial_model",
      "scenario_analysis",
      "implementation_roadmap",
      "governance_implications",
      "vendor_scoring",
      "board_recommendation"
    ]
  };

  const policyMap = {
    P0: [],
    P1: [],
    P2: ["risk_matrix"],
    P3: ["regulatory_position"],
    P4: ["audit_trail"],
    P5: ["trace_manifest"]
  };

  const required = new Set([
    ...(reasoningMap[reasoning_level] || reasoningMap.R2),
    ...(policyMap[policy_level] || [])
  ]);

  const enforced = [];

  for (const section of required) {
    if (!reportJSON[section]) {
      reportJSON[section] = {
        enforced: true,
        note: `Section required by ${reasoning_level}/${policy_level} but not provided by AI`
      };
      enforced.push(section);
    }
  }

  return {
    report: reportJSON,
    enforced_sections: enforced
  };
}

/* ================= AI GENERATION ================= */

function isPlaceholderVendorName(name) {
  const key = String(name || "").toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
  if (!key) return true;
  if (/^vendor [a-z0-9]+$/.test(key)) return true;
  if (/^provider [a-z0-9]+$/.test(key)) return true;
  if (/^candidate [a-z0-9]+$/.test(key)) return true;
  if (/^vendor (alpha|beta|gamma|delta|one|two|three|four|five)$/.test(key)) return true;
  return key === "vendor" || key === "provider" || key === "candidate";
}

function extractVendorOptionNames(report) {
  const names = [];
  if (!report || typeof report !== "object") return names;
  const sections = [
    report.vendor_scoring,
    report.board_recommendation,
    report.options,
    report.solution_options,
    report.recommendations,
    report.market_analysis,
  ];
  for (const section of sections) {
    if (!section) continue;
    let items = section;
    if (typeof items === "object" && !Array.isArray(items)) {
      if (Array.isArray(items.options)) items = items.options;
      else if (Array.isArray(items.vendors)) items = items.vendors;
      else continue;
    }
    if (!Array.isArray(items)) continue;
    for (const item of items) {
      if (typeof item === "string") {
        const name = item.trim();
        if (name) names.push(name);
        continue;
      }
      if (item && typeof item === "object") {
        const candidate = item.vendor || item.name || item.solution || item.option || item.provider;
        if (typeof candidate === "string" && candidate.trim()) {
          names.push(candidate.trim());
        }
      }
    }
  }
  return [...new Set(names)];
}

function hasSufficientVendorSpecificity(report) {
  const names = extractVendorOptionNames(report);
  const specific = names.filter((name) => !isPlaceholderVendorName(name));
  return specific.length >= 2;
}

function normalizeEvidenceRefs(rawRefs) {
  if (!Array.isArray(rawRefs)) return [];
  const refs = [];
  for (const ref of rawRefs) {
    if (typeof ref !== "string") continue;
    const trimmed = ref.trim();
    if (!trimmed) continue;
    refs.push(trimmed.slice(0, 1024));
  }
  return [...new Set(refs)];
}

function ensureAuditTrailTimestamp(report, capturedAtIso = new Date().toISOString()) {
  const normalized = report && typeof report === "object" ? { ...report } : {};
  const auditTrail = (normalized.audit_trail && typeof normalized.audit_trail === "object")
    ? { ...normalized.audit_trail }
    : {};
  const providerTimestamp = typeof auditTrail.timestamp === "string" ? auditTrail.timestamp.trim() : "";
  auditTrail.timestamp = capturedAtIso;
  if (providerTimestamp) {
    auditTrail.provider_reported_timestamp = providerTimestamp;
  }
  auditTrail.governance_timestamp_source = "bridge_ingest_utc";
  normalized.audit_trail = auditTrail;
  return normalized;
}

async function callProviderForJson(systemPrompt, userPayload) {
  if (!copilotClient) {
    throw new Error("Copilot provider selected but GITHUB_TOKEN is not configured.");
  }
  const response = await copilotClient.chat.completions.create({
    model: COPILOT_MODEL,
    messages: [
      { role: "system", content: systemPrompt },
      { role: "user", content: JSON.stringify(userPayload) },
    ],
    temperature: 0,
    response_format: { type: "json_object" },
  });
  const text = response.choices[0]?.message?.content;
  if (!text) throw new Error("Copilot returned empty response");
  return JSON.parse(text);
}

async function generateAI(context, reasoning_level, policy_level, _provider = "Copilot") {

  const reasoningMap = {
    R0: ["executive_summary"],
    R1: ["executive_summary"],
    R2: ["executive_summary", "strategic_context"],
    R3: ["executive_summary", "strategic_context", "market_analysis"],
    R4: ["executive_summary", "strategic_context", "market_analysis", "risk_matrix"],
    R5: [
      "executive_summary",
      "strategic_context",
      "market_analysis",
      "risk_matrix",
      "financial_model",
      "scenario_analysis",
      "implementation_roadmap",
      "governance_implications",
      "vendor_scoring",
      "board_recommendation"
    ]
  };

  const policyMap = {
    P0: [],
    P1: [],
    P2: ["risk_matrix"],
    P3: ["regulatory_position"],
    P4: ["audit_trail"],
    P5: ["trace_manifest"]
  };

  const requiredSections = Array.from(
    new Set([
      ...(reasoningMap[reasoning_level] || reasoningMap.R2),
      ...(policyMap[policy_level] || [])
    ])
  );

  const systemPrompt = `
You are an enterprise strategy and technology advisory AI. Your analysis will be
governed by the DIIaC (Decision Intelligence Infrastructure as Code) accountability
layer - you provide the thinking, DIIaC makes it defensible.

Analyse the user's intent and return STRICT JSON only.
The word JSON must appear in your output.

You MUST include these top-level sections at minimum:
${requiredSections.join(", ")}

Each section must be a structured JSON object with substantive, detailed content
drawn from your analysis of the user's specific request.

For vendor/solution recommendations, include an "options" array within your
"vendor_scoring" or "board_recommendation" section. Each option should have:
- "vendor" or "name": the solution or vendor name
- "focus" or "rationale": why this option fits the user's stated requirements
- "strengths": key advantages
- "risks": key risks or concerns
You MUST include at least 2 real commercial vendor names.
Do NOT use placeholder labels like "Vendor A", "Vendor B", "Option 1", or "Provider X".

For risk analysis, be specific to the user's domain, regulatory environment,
and stated constraints.

Provide detailed, board-ready, professionally structured content that directly
addresses the user's specific scenario - not generic templates.

Do NOT include markdown.
Do NOT include commentary.
Return a valid JSON object only.
`;

  if (!copilotClient) {
    if (LLM_STUB_ENABLED) {
      return {
        executive_summary: {
          overview: "Deterministic LLM stub synthesis from human intent context.",
          source: "llm_stub"
        },
        strategic_context: {
          intent_excerpt: JSON.stringify(context).slice(0, 500),
        },
        board_recommendation: {
          decision: "Use deterministic governed compile output as the authoritative decision pack.",
        }
      };
    }
    throw new Error(
      "Copilot provider selected but GITHUB_TOKEN is not configured. " +
      "Pull secrets from Azure Key Vault: bash scripts/pull-keyvault-secrets.sh"
    );
  }

  const initial = await callProviderForJson(systemPrompt, context);
  if (hasSufficientVendorSpecificity(initial)) {
    return initial;
  }

  const repairPrompt = `
You are revising a prior JSON response for enterprise governance quality.
Return STRICT JSON only.
Preserve the same top-level sections from the prior response.
You MUST set "vendor_scoring.options" and "board_recommendation.options" with at least 3 real commercial vendor names relevant to the context.
Do NOT use placeholders such as "Vendor A", "Vendor B", "Option 1", or "Provider X".
Keep rationale/strengths/risks concise and specific.
Return a valid JSON object only.
`;
  try {
    const repaired = await callProviderForJson(repairPrompt, {
      context,
      previous_output: initial,
      quality_issue: "placeholder_or_missing_vendor_specificity",
    });
    if (hasSufficientVendorSpecificity(repaired)) {
      return repaired;
    }
  } catch (_err) {
    // Fall back to initial response if repair path fails.
  }

  return initial;
}
async function pythonPost(pathname, body) {
  await ensurePythonRuntime();
  const r = await fetch(`${activePythonBase}${pathname}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });
  const ct = r.headers.get("content-type") || "application/json";
  const payload = ct.includes("application/json") ? await r.json() : await r.text();
  return { ok: r.ok, status: r.status, payload };
}

/* ================= POLICY IMPACT ================= */

app.post("/api/impact/policy",
  requireRole(["admin"]),
  (req, res) => {

    const { policy_level } = req.body;

    const severityMap = {
      P0: "LOW",
      P1: "LOW",
      P2: "MEDIUM",
      P3: "MEDIUM",
      P4: "HIGH",
      P5: "CRITICAL"
    };

    res.json({
      severity: severityMap[policy_level] || "LOW",
      impacted_controls: policy_level === "P0" ? 0 : 3,
      findings: 0,
      evaluated_at: new Date().toISOString()
    });
  }
);

app.post("/api/llm-governed-compile", requireRole(["admin"]), async (req, res) => {
  try {
    const REQUIRED_GOVERNANCE_MODES = [
      "FIRST-PRINCIPLES MODE",
      "DEVIL'S ADVOCATE MODE",
      "CONSTRAINTS-FIRST MODE",
    ];
    const profileLockId = (process.env.DIIAC_PROFILE_LOCK_ID || "").trim();
    const knownProfileIds = new Set();
    try {
      for (const p of loadContractBusinessProfiles()) {
        const id = typeof p?.profile_id === "string" ? p.profile_id.trim() : "";
        if (id) knownProfileIds.add(id);
      }
    } catch (_err) {
      // Safe fallback: skip lock validation if profile contracts are unavailable.
    }
    const normalizeGovernanceModes = (rawModes) => {
      const requested = Array.isArray(rawModes)
        ? rawModes.filter((m) => typeof m === "string" && m.trim()).map((m) => m.trim())
        : [];
      const deduped = [];
      for (const mode of requested) {
        if (!deduped.includes(mode)) deduped.push(mode);
      }
      const added = [];
      for (const requiredMode of REQUIRED_GOVERNANCE_MODES) {
        if (!deduped.includes(requiredMode)) {
          deduped.push(requiredMode);
          added.push(requiredMode);
        }
      }
      return { modes: deduped, added };
    };

    let {
      provider = "Copilot",
      reasoning_level = "R4",
      policy_level = "P4",
      profile_id = "it_enterprise_profile_v1",
      schema_id = "GENERAL_SOLUTION_BOARD_REPORT_V1",
      role = "CIO",
      domain = "enterprise-strategy",
      assertions = [],
      evidence_refs = [],
      governance_modes = [],
      human_intent,
      execution_context_id,
    } = req.body || {};
    const providerDecision = enforceProviderMode(provider);
    if (!providerDecision.ok) {
      return res.status(400).json({
        error: providerDecision.error,
        provider_mode: LLM_PROVIDER_MODE,
        allowed_provider: providerDecision.provider,
      });
    }
    provider = providerDecision.provider;

    const requestedProfileId = (typeof profile_id === "string" && profile_id.trim())
      ? profile_id.trim()
      : "it_enterprise_profile_v1";
    const lockIsValid = profileLockId && knownProfileIds.has(profileLockId);
    const effectiveProfileId = lockIsValid ? profileLockId : requestedProfileId;
    const profileOverridden = Boolean(lockIsValid && requestedProfileId !== effectiveProfileId);
    const normalizedGovernance = normalizeGovernanceModes(governance_modes);

    if (typeof human_intent === "string" && human_intent.trim()) {
      if (human_intent.length > 100000) {
        return res.status(400).json({ error: "intent_too_large", message: "Human intent exceeds 100KB limit." });
      }
      const id = Date.now();
      fs.writeFileSync(path.join(HUMAN_INPUT_DIR, `${id}.json`), JSON.stringify({ raw_text: human_intent.trim() }, null, 2));
    }

    const files = fs.readdirSync(HUMAN_INPUT_DIR).filter((f) => f.endsWith(".json"));
    if (!files.length) {
      return res.status(400).json({ error: "no_human_intent", message: "Submit Human Intent before running compile." });
    }

    const latest = files.sort().reverse()[0];
    const contextRaw = fs.readFileSync(path.join(HUMAN_INPUT_DIR, latest), "utf8");
    const context = JSON.parse(contextRaw);

    const aiReportRaw = await generateAI(context, reasoning_level, policy_level, provider);
    const bridgeAuditTimestamp = new Date().toISOString();
    const aiReport = ensureAuditTrailTimestamp(aiReportRaw, bridgeAuditTimestamp);
    const llmOutputHash = sha256(stableJson(aiReport));
    const contextId = execution_context_id || `ctx-llm-${llmOutputHash.slice(0, 20)}`;
    const assertionList = Array.isArray(assertions) && assertions.length
      ? assertions.filter((a) => typeof a === "string" && a.trim()).map((a) => a.trim())
      : [`LLM synthesis hash ${llmOutputHash.slice(0, 12)}`, `Provider ${provider}`];
    const userEvidenceRefs = normalizeEvidenceRefs(evidence_refs);
    const compileEvidenceRefs = [...new Set([...userEvidenceRefs, `llm-output-${llmOutputHash.slice(0, 16)}`])];

    const compilePayload = {
      execution_context_id: contextId,
      profile_id: effectiveProfileId,
      schema_id,
      reasoning_level,
      policy_level,
      governance_modes: normalizedGovernance.modes,
      role,
      domain,
      assertions: assertionList,
      non_negotiables: ["deterministic-governance"],
      risk_flags: ["llm-hallucination-risk"],
      evidence_refs: compileEvidenceRefs,
      // Pass full LLM analysis to the governance pipeline so
      // board report content is driven by LLM output, not templates
      llm_analysis: aiReport || null,
      llm_provider: provider,
      llm_audit_timestamp: bridgeAuditTimestamp,
    };
    const compile = await pythonPost("/api/governed-compile", compilePayload);
    if (!compile.ok) {
      return res.status(compile.status).json({ error: "governed_compile_failed", details: compile.payload });
    }

    return res.json({
      mode: "llm_governed_compile",
      provider,
      llm_output_hash: llmOutputHash,
      llm_audit_timestamp: bridgeAuditTimestamp,
      llm_provider_reported_timestamp: aiReport?.audit_trail?.provider_reported_timestamp || null,
      llm_sections: Object.keys(aiReport || {}),
      execution_context_id: contextId,
      role_submission_strategy: "inline_payload_or_existing_context_role_bundle",
      profile_id_requested: requestedProfileId,
      profile_id_effective: effectiveProfileId,
      profile_lock_active: Boolean(lockIsValid),
      profile_overridden: profileOverridden,
      governance_modes_requested: Array.isArray(governance_modes)
        ? governance_modes.filter((m) => typeof m === "string" && m.trim()).map((m) => m.trim())
        : [],
      governance_modes_effective: normalizedGovernance.modes,
      governance_modes_auto_added: normalizedGovernance.added,
      compile: compile.payload,
    });
  } catch (err) {
    console.error("llm_governed_compile_failed:", err);
    return res.status(500).json({ error: "llm_governed_compile_failed", message: String(err?.message || err) });
  }
});


/* ================= REPORTS ================= */

function localExecutionArtifactDirs(execId) {
  return [
    path.join(WORKSPACE, "artifacts", execId),
    path.join(DECISION_PACK_BASE, execId, "artefacts"),
    path.join(DECISION_PACK_BASE, execId, "artifacts"),
  ];
}

function listLocalExecutionReports(execId) {
  const reports = new Set();
  for (const dirPath of localExecutionArtifactDirs(execId)) {
    try {
      if (!fs.existsSync(dirPath) || !fs.statSync(dirPath).isDirectory()) continue;
      for (const entry of fs.readdirSync(dirPath, { withFileTypes: true })) {
        if (entry.isFile()) reports.add(entry.name);
      }
    } catch (_err) {
      // Continue scanning remaining directories.
    }
  }
  return [...reports].sort();
}

function resolveLocalExecutionReportPath(execId, fileName) {
  const safeName = path.basename(fileName);
  if (!safeName || safeName !== fileName) return { invalidPath: true, path: null };

  for (const dirPath of localExecutionArtifactDirs(execId)) {
    try {
      if (!fs.existsSync(dirPath) || !fs.statSync(dirPath).isDirectory()) continue;
      const root = path.resolve(dirPath);
      const target = path.resolve(dirPath, safeName);
      if (!target.startsWith(`${root}${path.sep}`)) {
        continue;
      }
      if (fs.existsSync(target) && fs.statSync(target).isFile()) {
        return { invalidPath: false, path: target };
      }
    } catch (_err) {
      // Continue scanning remaining directories.
    }
  }

  return { invalidPath: false, path: null };
}

app.get("/executions/:execution_id/reports",
  requireRole(["admin", "standard", "customer"]),
  (req, res, next) => {
    const execId = sanitizeExecId(req.params.execution_id);
    const reports = listLocalExecutionReports(execId);
    if (!reports.length) return next();
    return res.json({ execution_id: execId, reports });
  },
  (req, res) => proxyToPython(req, res, `/executions/${sanitizeExecId(req.params.execution_id)}/reports`)
);

app.get("/executions/:execution_id/reports/:file",
  requireRole(["admin", "standard", "customer"]),
  (req, res, next) => {

    const fileName = String(req.params.file || "");
    const execId = sanitizeExecId(req.params.execution_id);
    const resolved = resolveLocalExecutionReportPath(execId, fileName);
    if (resolved.invalidPath) return res.status(400).json({ error: "invalid_path" });
    if (!resolved.path) return next();

    return res.sendFile(resolved.path);
  },
  (req, res) => proxyToPython(req, res, `/executions/${sanitizeExecId(req.params.execution_id)}/reports/${path.basename(req.params.file)}`)
);



/* ================= PYTHON GOVERNANCE PROXY ================= */

const PYTHON_BASE = process.env.PYTHON_BASE_URL || "http://127.0.0.1:8000";
const PYTHON_BASE_FALLBACKS = [
  "http://localhost:8000",
  "http://governance-runtime:8000",
];
const PYTHON_AUTOSTART = process.env.PYTHON_AUTOSTART === "true";
let activePythonBase = PYTHON_BASE;
const REPO_ROOT = path.resolve(__dirname, "..");

function defaultBusinessProfiles() {
  return [
    {
      profile_id: "it_enterprise_profile_v1",
      sector: "IT_ENTERPRISE",
      jurisdiction: "GLOBAL",
      risk_appetite: "MEDIUM",
      default_reasoning_level: "R3",
      default_policy_level: "P3",
      allowed_schemas: ["GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1", "SLA_SCHEDULE_V1"],
      required_controls: ["zero_trust", "audit_trail"],
      required_sections: ["Executive Summary", "Context", "Risk Register", "Success Metrics", "Down-Select Recommendation"],
      scoring_weights: { security: 0.25, resilience: 0.2, interoperability: 0.2, operations: 0.15, commercial: 0.2 },
    },
    {
      profile_id: "finance_profile_v1",
      sector: "FINANCE",
      jurisdiction: "UK",
      risk_appetite: "LOW",
      default_reasoning_level: "R4",
      default_policy_level: "P5",
      allowed_schemas: ["GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1", "SLA_SCHEDULE_V1"],
      required_controls: ["zero_trust", "audit_trail", "psirt_governance"],
      required_sections: ["Executive Summary", "Context", "Risk Register", "Success Metrics", "Down-Select Recommendation"],
      scoring_weights: { security: 0.3, resilience: 0.25, interoperability: 0.15, operations: 0.1, commercial: 0.2 },
    },
    {
      profile_id: "healthcare_profile_v1",
      sector: "HEALTHCARE",
      jurisdiction: "UK",
      risk_appetite: "LOW",
      default_reasoning_level: "R4",
      default_policy_level: "P5",
      allowed_schemas: ["GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1", "SLA_SCHEDULE_V1"],
      required_controls: ["zero_trust", "audit_trail", "patient_safety"],
      required_sections: ["Executive Summary", "Context", "Risk Register", "Success Metrics", "Down-Select Recommendation"],
      scoring_weights: { security: 0.25, resilience: 0.25, interoperability: 0.15, operations: 0.15, commercial: 0.2 },
    },
    {
      profile_id: "transport_profile_v1",
      sector: "TRANSPORT",
      jurisdiction: "UK",
      risk_appetite: "LOW",
      default_reasoning_level: "R4",
      default_policy_level: "P4",
      allowed_schemas: ["GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1", "SLA_SCHEDULE_V1"],
      required_controls: ["zero_trust", "audit_trail", "psirt_governance"],
      required_sections: ["Executive Summary", "Context", "Risk Register", "Success Metrics", "Down-Select Recommendation"],
      scoring_weights: { security: 0.25, resilience: 0.2, interoperability: 0.2, operations: 0.15, commercial: 0.2 },
    },
    {
      profile_id: "it_service_provider_profile_v1",
      sector: "IT_SERVICE_PROVIDER",
      jurisdiction: "GLOBAL",
      risk_appetite: "MEDIUM",
      default_reasoning_level: "R4",
      default_policy_level: "P3",
      allowed_schemas: ["GENERAL_SOLUTION_BOARD_REPORT_V1", "RFQ_TEMPLATE_V1", "SLA_SCHEDULE_V1"],
      required_controls: ["zero_trust", "audit_trail", "multi_tenancy"],
      required_sections: ["Executive Summary", "Context", "Risk Register", "Success Metrics", "Down-Select Recommendation"],
      scoring_weights: { security: 0.2, resilience: 0.2, interoperability: 0.15, operations: 0.2, commercial: 0.25 },
    },
  ];
}

function loadContractBusinessProfiles() {
  const profileDirs = [
    path.join(REPO_ROOT, "contracts", "business-profiles"),
    path.join(process.cwd(), "contracts", "business-profiles"),
    path.join("/workspace", "contracts", "business-profiles"),
  ];

  for (const profilesDir of profileDirs) {
    if (!fs.existsSync(profilesDir)) continue;
    const files = fs.readdirSync(profilesDir).filter((name) => name.endsWith(".json")).sort();
    if (!files.length) continue;
    return files.map((name) => JSON.parse(fs.readFileSync(path.join(profilesDir, name), "utf8")));
  }

  return defaultBusinessProfiles();
}

let pyProc = null;
let pyStarting = null;

async function probePythonBases() {
  const candidates = [PYTHON_BASE, ...PYTHON_BASE_FALLBACKS.filter((b) => b !== PYTHON_BASE)];
  for (const base of candidates) {
    try {
      const r = await fetch(`${base}/health`);
      if (r.ok) {
        activePythonBase = base;
        return true;
      }
    } catch (_e) {
    }
  }
  return false;
}

async function ensurePythonRuntime() {
  if (await probePythonBases()) return;

  if (!PYTHON_AUTOSTART) {
    throw new Error(`python runtime not reachable at ${PYTHON_BASE} (fallbacks: ${PYTHON_BASE_FALLBACKS.join(', ')})`);
  }

  if (pyProc && !pyProc.killed) return;
  if (pyStarting) return pyStarting;

  pyStarting = new Promise((resolve) => {
    pyProc = spawn("python3", ["app.py"], {
      cwd: REPO_ROOT,
      env: {
        ...process.env,
        STRICT_DETERMINISTIC_MODE: process.env.STRICT_DETERMINISTIC_MODE || "true",
      },
      stdio: ["ignore", "pipe", "pipe"],
    });

    pyProc.stdout.on("data", () => {});
    pyProc.stderr.on("data", () => {});
    pyProc.on("exit", () => {
      pyProc = null;
    });

    const deadline = Date.now() + 8000;
    const poll = async () => {
      if (await probePythonBases()) return resolve();
      if (Date.now() > deadline) return resolve();
      setTimeout(poll, 300);
    };
    poll();
  }).finally(() => {
    pyStarting = null;
  });

  return pyStarting;
}

async function proxyToPython(req, res, targetPath) {
  try {
    await ensurePythonRuntime();
    const query = req.originalUrl.includes("?") ? req.originalUrl.slice(req.originalUrl.indexOf("?")) : "";
    const url = `${activePythonBase}${targetPath}${query}`;

    const headers = {
      "content-type": req.headers["content-type"] || "application/json",
    };

    // Inject ADMIN_API_TOKEN for admin routes so Python backend accepts the request
    if (targetPath.startsWith("/admin") && process.env.ADMIN_API_TOKEN) {
      headers["authorization"] = `Bearer ${process.env.ADMIN_API_TOKEN}`;
    }

    const init = {
      method: req.method,
      headers,
    };

    if (!["GET", "HEAD"].includes(req.method) && req.body && Object.keys(req.body).length) {
      init.body = JSON.stringify(req.body);
    }

    const r = await fetch(url, init);
    const ct = r.headers.get("content-type") || "application/json";
    res.status(r.status);
    res.setHeader("content-type", ct);

    if (ct.includes("application/json")) {
      const json = await r.json();
      return res.json(json);
    }

    const buf = Buffer.from(await r.arrayBuffer());
    return res.send(buf);
  } catch (err) {
    return res.status(502).json({ error: "python_proxy_error", details: process.env.APP_ENV === "development" ? String(err) : undefined });
  }
}



async function queryPython(pathname) {
  const headers = {};
  // Inject ADMIN_API_TOKEN for admin routes so Python backend accepts the request
  if (pathname.startsWith("/admin") && process.env.ADMIN_API_TOKEN) {
    headers["authorization"] = `Bearer ${process.env.ADMIN_API_TOKEN}`;
  }
  const r = await fetch(`${activePythonBase}${pathname}`, { headers });
  const ct = r.headers.get("content-type") || "application/json";
  const body = ct.includes("application/json") ? await r.json() : await r.text();
  return { ok: r.ok, status: r.status, body };
}

function localDbStatusSnapshot() {
  const dbPath = process.env.DIIAC_DB_PATH || `${WORKSPACE}/state/diiac.sqlite3`;
  let exists = false;
  let size_bytes = 0;
  let mtime = null;

  try {
    if (fs.existsSync(dbPath)) {
      const st = fs.statSync(dbPath);
      exists = true;
      size_bytes = st.size;
      mtime = st.mtime.toISOString();
    }
  } catch (_e) {
  }

  return {
    db_path: dbPath,
    exists,
    size_bytes,
    mtime,
    tables: {},
    integrity: { ok: true, mode: "bridge_fallback", key_registry_ok: SIGNING_ENABLED && Boolean(signingPublicKey) },
  };
}

async function resolveDbStatus() {
  try {
    await ensurePythonRuntime();
    const dbStatus = await queryPython("/admin/db/status");
    if (dbStatus.ok) return dbStatus;
    if (dbStatus.status !== 404) return dbStatus;
  } catch (_e) {
  }

  return {
    ok: true,
    status: 200,
    body: localDbStatusSnapshot(),
  };
}

app.get("/admin/status/services", requireRole(["admin"]), async (_req, res) => {
  try {
    await ensurePythonRuntime();
    const [health, trust, metrics, dbStatus] = await Promise.all([
      queryPython("/admin/health"),
      queryPython("/trust/status"),
      queryPython("/admin/metrics"),
      resolveDbStatus(),
    ]);

    return res.json({
      timestamp: new Date().toISOString(),
      services: {
        python_runtime: { reachable: health.ok, status: health.status, details: health.body },
        trust_ledger: { reachable: trust.ok, status: trust.status, details: trust.body },
        metrics: { reachable: metrics.ok, status: metrics.status, details: metrics.body },
        db: { reachable: dbStatus.ok, status: dbStatus.status, details: dbStatus.body },
      },
      overall_ok: health.ok && trust.ok && metrics.ok && dbStatus.ok,
    });
  } catch (err) {
    return res.status(502).json({ error: "service_status_unavailable", details: process.env.APP_ENV === "development" ? String(err) : undefined });
  }
});

app.get("/admin/status/containers", requireRole(["admin"]), (_req, res) => {
  try {
    // Hardcoded command â€” never accept shell commands from environment variables
    const out = spawnSync("docker", ["ps", "--format", "{{json .}}"], { encoding: "utf-8", timeout: 5000 });
    if (out.status !== 0) {
      return res.json({
        available: false,
        command: "docker ps",
        error: (out.stderr || out.stdout || "docker status unavailable").trim(),
        containers: [],
      });
    }
    const lines = (out.stdout || "").trim().split("\n").filter(Boolean);
    const containers = lines.map((line) => {
      try {
        return JSON.parse(line);
      } catch (_e) {
        return { raw: line };
      }
    });
    return res.json({ available: true, command: "docker ps", containers });
  } catch (err) {
    return res.json({ available: false, error: String(err), containers: [] });
  }
});

/* ================= EXPORT ================= */

app.get("/decision-pack/:execution_id/export",
  requireRole(["admin"]),
  async (req, res) => {
    try {
      await ensurePythonRuntime();
      const query = req.originalUrl.includes("?") ? req.originalUrl.slice(req.originalUrl.indexOf("?")) : "";

      const execId = sanitizeExecId(req.params.execution_id);
      const primary = await fetch(`${activePythonBase}/decision-pack/${execId}/export${query}`);
      if (primary.ok) {
        const ct = primary.headers.get("content-type") || "application/octet-stream";
        const buf = Buffer.from(await primary.arrayBuffer());
        res.status(primary.status);
        res.setHeader("content-type", ct);
        return res.send(buf);
      }

      if (primary.status === 404) {
        const fallback = await fetch(`${activePythonBase}/decision-pack/${execId}/export-signed${query}`);
        if (fallback.ok) {
          const ct = fallback.headers.get("content-type") || "application/octet-stream";
          if (ct.includes("application/json")) {
            const meta = await fallback.json();
            const zipPath = meta?.zip_path;
            if (zipPath && fs.existsSync(zipPath)) {
              res.status(200);
              res.setHeader("content-type", "application/zip");
              res.setHeader("content-disposition", `attachment; filename=decision-pack_${execId}.zip`);
              return res.send(fs.readFileSync(zipPath));
            }
            return res.status(502).json({
              error: "python_proxy_error",
              details: "runtime export-signed metadata returned without readable zip artifact",
              runtime_response: meta,
            });
          }
          const buf = Buffer.from(await fallback.arrayBuffer());
          res.status(fallback.status);
          res.setHeader("content-type", ct);
          return res.send(buf);
        }
      }

      const text = await primary.text();
      return res.status(primary.status).send(text || "Export unavailable");
    } catch (err) {
      return res.status(502).json({ error: "python_proxy_error", details: process.env.APP_ENV === "development" ? String(err) : undefined });
    }
  }
);





app.post("/verify/pack",
  requireRole(["admin", "standard", "customer"]),
  (req, res) => proxyToPython(req, res, "/verify/pack")
);

/* ================= EXTENDED GOVERNANCE ENDPOINTS ================= */

app.get("/api/business-profiles", requireRole(["admin", "standard", "customer"]), async (req, res) => {
  try {
    await ensurePythonRuntime();
    return proxyToPython(req, res, "/api/business-profiles");
  } catch (_err) {
    try {
      const profiles = loadContractBusinessProfiles();
      if (!profiles.length) {
        return res.status(502).json({
          error: "python_proxy_error",
          details: "python runtime unavailable; returning built-in business profile defaults failed",
        });
      }
      return res.json({
        profiles,
        profiles_count: profiles.length,
        source: "contracts_fallback",
      });
    } catch (fallbackErr) {
      return res.status(502).json({ error: "python_proxy_error", details: String(fallbackErr) });
    }
  }
});
app.post("/api/human-input/role", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, "/api/human-input/role"));
app.post("/api/governed-compile", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/api/governed-compile"));
app.get("/executions/:execution_id/trace-map", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${sanitizeExecId(req.params.execution_id)}/trace-map`));
app.get("/executions/:execution_id/scoring", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${sanitizeExecId(req.params.execution_id)}/scoring`));
app.get("/executions/:execution_id/merkle", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${sanitizeExecId(req.params.execution_id)}/merkle`));
app.get("/executions/:execution_id/merkle/proof/:artefact_name", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${sanitizeExecId(req.params.execution_id)}/merkle/proof/${req.params.artefact_name}`));
app.get("/verify/public-keys", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, "/verify/public-keys"));
app.get("/verify/execution/:execution_id", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/verify/execution/${sanitizeExecId(req.params.execution_id)}`));
app.post("/verify/merkle-proof", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, "/verify/merkle-proof"));
app.get("/decision-pack/:execution_id/export-signed", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/decision-pack/${sanitizeExecId(req.params.execution_id)}/export-signed`));
app.get("/admin/health", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/health"));
app.get("/admin/metrics", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/metrics"));
app.get("/admin/db/status", requireRole(["admin"]), async (_req, res) => {
  const dbStatus = await resolveDbStatus();
  return res.status(dbStatus.status).json(dbStatus.body);
});
app.get("/admin/db/table/:table", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/db/table/${req.params.table}`));
app.post("/admin/db/maintenance/compact", requireRole(["admin"]), async (_req, res) => {
  try {
    await ensurePythonRuntime();
    const compact = await queryPython("/admin/db/maintenance/compact");
    if (compact.ok) return res.status(compact.status).json(compact.body);
    if (compact.status !== 404) return res.status(compact.status).json(compact.body);
  } catch (_e) {
  }
  return res.json({ compacted: false, mode: "bridge_fallback", note: "No runtime DB compact endpoint available." });
});
app.get("/trust/status", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, "/trust/status"));
app.get("/admin/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/logs"));
app.get("/admin/executions/:execution_id/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/executions/${sanitizeExecId(req.params.execution_id)}/logs`));
app.post("/admin/audit-export", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/audit-export"));
app.get("/admin/audit-export/:export_id/download", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/audit-export/${req.params.export_id}/download`));
app.get("/admin/audit/exports", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/audit/exports"));

/* ================= AUTH STATUS ================= */

app.get("/auth/status", (_req, res) => {
  const appEnv = (process.env.APP_ENV || "production").toLowerCase();
  const entraEnforced = isEntraEnabled() || appEnv === "production";
  res.json({
    auth_mode: getAuthMode(),
    entra_enabled: entraEnforced,
    tenant_id: entraEnforced ? (process.env.ENTRA_EXPECTED_TENANT_ID || null) : null,
    audience: entraEnforced ? (process.env.ENTRA_EXPECTED_AUDIENCE || null) : null,
    llm_provider_mode: LLM_PROVIDER_MODE,
  });
});

app.get("/auth/me", requireRole(["admin", "standard", "customer", "viewer"]), (req, res) => {
  // Returns the authenticated user's identity and resolved RBAC context.
  // Used by the frontend after MSAL login to confirm role resolution.
  const auth = req.entraAuth || {};
  res.json({
    name: auth.name || req.actor?.name || "unknown",
    email: auth.email || req.actor?.email || null,
    role: auth.role || req.actor?.role || null,
    subroles: auth.subroles || [],
    groups: auth.groups || [],
    tenant_id: auth.tenant_id || null,
    token_type: auth.token_type || req.actor?.token_type || "unknown",
    auth_mode: getAuthMode(),
  });
});

app.get("/auth/callback", (req, res) => {
  // OIDC redirect callback â€” returns code/state for interactive test clients
  const { code, state, error, error_description } = req.query;
  if (error) {
    return res.status(400).json({ error, error_description });
  }
  return res.json({
    message: "Authorization code received. Exchange this for a token using your OIDC client.",
    code: code || null,
    state: state || null,
  });
});

/* ================= COPILOT GOVERNANCE INTERCEPT ================= */

app.post("/api/intercept/request",
  requireRole(["admin", "standard", "customer"]),
  async (req, res) => {
    try {
      const {
        copilot_request_id,
        prompt,
        context: interceptContext,
        source = "copilot",
        action,
        block_reason,
        requires_approval,
      } = req.body || {};

      if (!prompt || typeof prompt !== "string" || !prompt.trim()) {
        return res.status(400).json({
          error: "invalid_intercept_payload",
          message: "prompt is required and must be a non-empty string.",
        });
      }

      const interceptId = copilot_request_id || crypto.randomUUID();
      const actor = req.actor || {};
      const interceptTimestamp = new Date().toISOString();
      const promptHash = sha256(prompt.trim());
      const trendBlockReason = (
        typeof block_reason === "string" && block_reason.trim()
          ? block_reason.trim()
          : (typeof interceptContext?.block_reason === "string" && interceptContext.block_reason.trim()
            ? interceptContext.block_reason.trim()
            : null)
      );
      const rawTrendAction = action
        || interceptContext?.action
        || (requires_approval === true
          ? "REQUIRE_APPROVAL"
          : (trendBlockReason ? "RESTRICT" : "ALLOW"));
      const trendAction = normalizeTrendAction(rawTrendAction, ["ALLOW", "RESTRICT", "REQUIRE_APPROVAL"], "ALLOW");
      recordInterceptEvent("request", {
        intercept_id: interceptId,
        source,
        action: trendAction,
        block_reason: trendBlockReason,
        actor_role: actor.role || "unknown",
      });

      // Record intercept in ledger
      const ledgerEntry = appendLedger({
        type: "COPILOT_INTERCEPT",
        intercept_id: interceptId,
        source,
        actor_subject: actor.subject || "unknown",
        actor_role: actor.role || "unknown",
        prompt_hash: promptHash,
        timestamp: interceptTimestamp,
      });

      return res.json({
        intercept_id: interceptId,
        status: "intercepted",
        source,
        actor: {
          subject: actor.subject,
          name: actor.name,
          role: actor.role,
          tenant_id: actor.tenant_id,
          token_type: actor.token_type,
        },
        prompt_hash: promptHash,
        ledger_hash: ledgerEntry.record_hash,
        intercepted_at: interceptTimestamp,
        governance_policy: "COPILOT_GOVERNANCE_V1",
        governance_action: trendAction,
        block_reason: trendBlockReason,
      });
    } catch (err) {
      return res.status(500).json({ error: "intercept_failed", details: process.env.APP_ENV === "development" ? String(err) : undefined });
    }
  }
);

app.post("/api/intercept/response",
  requireRole(["admin", "standard", "customer"]),
  async (req, res) => {
    try {
      const {
        intercept_id,
        response_text,
        model,
        confidence,
        action,
        block_reason,
      } = req.body || {};

      if (!intercept_id || !response_text) {
        return res.status(400).json({
          error: "invalid_response_payload",
          message: "intercept_id and response_text are required.",
        });
      }

      const actor = req.actor || {};
      const responseTimestamp = new Date().toISOString();
      const responseHash = sha256(typeof response_text === "string" ? response_text : JSON.stringify(response_text));
      const trendBlockReason = (typeof block_reason === "string" && block_reason.trim()) ? block_reason.trim() : null;
      const rawTrendAction = action || (trendBlockReason ? "REMEDIATE" : "ALLOW");
      const trendAction = normalizeTrendAction(rawTrendAction, ["ALLOW", "REMEDIATE"], "ALLOW");
      recordInterceptEvent("response", {
        intercept_id,
        action: trendAction,
        block_reason: trendBlockReason,
        model: model || "unknown",
      });

      const ledgerEntry = appendLedger({
        type: "COPILOT_RESPONSE",
        intercept_id,
        actor_subject: actor.subject || "unknown",
        actor_role: actor.role || "unknown",
        response_hash: responseHash,
        model: model || "unknown",
        confidence: confidence != null ? confidence : null,
        timestamp: responseTimestamp,
      });

      return res.json({
        intercept_id,
        status: "response_recorded",
        actor: {
          subject: actor.subject,
          name: actor.name,
          role: actor.role,
        },
        response_hash: responseHash,
        ledger_hash: ledgerEntry.record_hash,
        recorded_at: responseTimestamp,
        governance_action: trendAction,
        block_reason: trendBlockReason,
      });
    } catch (err) {
      return res.status(500).json({ error: "response_record_failed", details: process.env.APP_ENV === "development" ? String(err) : undefined });
    }
  }
);

app.post("/api/intercept/approval",
  requireRole(["admin"]),
  async (req, res) => {
    try {
      const {
        intercept_id,
        decision,
        justification,
      } = req.body || {};

      if (!intercept_id || !decision) {
        return res.status(400).json({
          error: "invalid_approval_payload",
          message: "intercept_id and decision (approve|reject|escalate) are required.",
        });
      }

      const validDecisions = ["approve", "reject", "escalate"];
      if (!validDecisions.includes(decision)) {
        return res.status(400).json({
          error: "invalid_decision",
          message: `decision must be one of: ${validDecisions.join(", ")}`,
        });
      }

      const actor = req.actor || {};
      const approvalTimestamp = new Date().toISOString();
      recordInterceptEvent("approval", {
        intercept_id,
        decision: String(decision).toLowerCase(),
        actor_role: actor.role || "unknown",
      });

      const ledgerEntry = appendLedger({
        type: "COPILOT_APPROVAL",
        intercept_id,
        decision,
        justification: justification || null,
        actor_subject: actor.subject || "unknown",
        actor_role: actor.role || "unknown",
        timestamp: approvalTimestamp,
      });

      return res.json({
        intercept_id,
        status: "decision_recorded",
        decision,
        actor: {
          subject: actor.subject,
          name: actor.name,
          role: actor.role,
        },
        ledger_hash: ledgerEntry.record_hash,
        decided_at: approvalTimestamp,
      });
    } catch (err) {
      return res.status(500).json({ error: "approval_failed", details: process.env.APP_ENV === "development" ? String(err) : undefined });
    }
  }
);

/* ================= ADMIN: INTEGRATIONS HEALTH ================= */

const configChangeRequests = [];
const approvalQueue = [];
const interceptEvents = [];
const bridgeStateMeta = {
  mode: "memory",
  path: BRIDGE_STATE_PATH,
  loaded_at: null,
  last_persisted_at: null,
  last_error: null,
};

function replaceArray(target, source) {
  target.splice(0, target.length, ...(Array.isArray(source) ? source : []));
}

function persistOperationsState() {
  try {
    fs.mkdirSync(path.dirname(BRIDGE_STATE_PATH), { recursive: true });
    const now = new Date().toISOString();
    const snapshot = {
      schema_version: 1,
      saved_at: now,
      config_change_requests: configChangeRequests,
      approval_queue: approvalQueue,
      intercept_events: interceptEvents.slice(-MAX_INTERCEPT_EVENTS),
    };
    const tmp = `${BRIDGE_STATE_PATH}.tmp`;
    fs.writeFileSync(tmp, JSON.stringify(snapshot, null, 2));
    fs.renameSync(tmp, BRIDGE_STATE_PATH);
    bridgeStateMeta.mode = "persisted";
    bridgeStateMeta.last_persisted_at = now;
    bridgeStateMeta.last_error = null;
    return true;
  } catch (err) {
    bridgeStateMeta.mode = "degraded_memory";
    bridgeStateMeta.last_error = String(err);
    console.error("Bridge state persistence failed:", err);
    return false;
  }
}

function loadOperationsState() {
  try {
    fs.mkdirSync(path.dirname(BRIDGE_STATE_PATH), { recursive: true });
    if (!fs.existsSync(BRIDGE_STATE_PATH)) {
      persistOperationsState();
      bridgeStateMeta.loaded_at = new Date().toISOString();
      return;
    }
    const raw = fs.readFileSync(BRIDGE_STATE_PATH, "utf8").trim();
    const parsed = raw ? JSON.parse(raw) : {};
    replaceArray(configChangeRequests, parsed.config_change_requests);
    replaceArray(approvalQueue, parsed.approval_queue);
    replaceArray(interceptEvents, parsed.intercept_events);
    if (interceptEvents.length > MAX_INTERCEPT_EVENTS) {
      interceptEvents.splice(0, interceptEvents.length - MAX_INTERCEPT_EVENTS);
    }
    bridgeStateMeta.mode = "persisted";
    bridgeStateMeta.loaded_at = new Date().toISOString();
    bridgeStateMeta.last_persisted_at = parsed.saved_at || null;
    bridgeStateMeta.last_error = null;
  } catch (err) {
    bridgeStateMeta.mode = "degraded_memory";
    bridgeStateMeta.loaded_at = new Date().toISOString();
    bridgeStateMeta.last_error = String(err);
    console.error("Bridge state load failed; continuing with in-memory state:", err);
  }
}

function recordInterceptEvent(type, details) {
  interceptEvents.push({ type, timestamp: new Date().toISOString(), ...details });
  if (interceptEvents.length > MAX_INTERCEPT_EVENTS) {
    interceptEvents.splice(0, interceptEvents.length - MAX_INTERCEPT_EVENTS);
  }
  persistOperationsState();
}

function getBridgePersistenceStatus() {
  if (bridgeStateMeta.mode === "persisted" && !bridgeStateMeta.last_error) return "OK";
  if (bridgeStateMeta.mode === "degraded_memory") return "DEGRADED";
  return "MEMORY_ONLY";
}

function normalizeTrendAction(rawAction, allowedActions, fallbackAction) {
  const normalized = typeof rawAction === "string" ? rawAction.trim().toUpperCase() : "";
  return allowedActions.includes(normalized) ? normalized : fallbackAction;
}

loadOperationsState();

app.get("/admin/integrations/health", requireRole(["admin"]), async (_req, res) => {
  try {
    const entraHealth = {
      status: isEntraEnabled() ? "PASS" : "WARN",
      auth_mode: getAuthMode(),
      tenant_id: isEntraEnabled() ? (process.env.ENTRA_EXPECTED_TENANT_ID ? "configured" : "missing") : "n/a",
      audience: isEntraEnabled() ? (process.env.ENTRA_EXPECTED_AUDIENCE ? "configured" : "missing") : "n/a",
      oidc_discovery: isEntraEnabled() ? (process.env.ENTRA_EXPECTED_TENANT_ID ? "OK" : "missing") : "n/a",
      role_map_loaded: isEntraEnabled(),
      issuer_pinning: isEntraEnabled() && process.env.ENTRA_EXPECTED_ISSUERS ? "ON" : "OFF",
    };

    const anyLlmConfigured = Boolean(copilotClient);
    const activeModels = [
      ...(Boolean(copilotClient) ? [COPILOT_MODEL] : []),
    ];
    const llmHealth = {
      status: (LLM_ENABLED && anyLlmConfigured) ? "PASS" : (LLM_STUB_ENABLED ? "WARN" : "FAIL"),
      ingestion_enabled: LLM_ENABLED,
      api_key: anyLlmConfigured ? "configured" : "missing",
      stub_mode: LLM_STUB_ENABLED,
      provider_mode: LLM_PROVIDER_MODE,
      model: activeModels.length > 0 ? activeModels.join(", ") : (LLM_STUB_ENABLED ? "stub" : "none"),
      copilot: {
        configured: Boolean(copilotClient),
        api_key: (LLM_ENABLED && process.env.GITHUB_TOKEN) ? "configured" : "missing",
        model: COPILOT_MODEL,
      },
    };

    const pendingApprovals = approvalQueue.filter((a) => a.status === "PENDING_APPROVAL");
    const persistenceStatus = getBridgePersistenceStatus();
    const approvalOpsHealth = {
      status: persistenceStatus === "OK" ? "PASS" : "WARN",
      pending_count: pendingApprovals.length,
      persistence: persistenceStatus,
      persistence_path: bridgeStateMeta.path,
      persistence_loaded_at: bridgeStateMeta.loaded_at,
      persistence_last_persisted_at: bridgeStateMeta.last_persisted_at,
      persistence_error: bridgeStateMeta.last_error,
      last_decision_sla: pendingApprovals.length > 0
        ? `${Math.round((Date.now() - new Date(pendingApprovals[0].requested_at).getTime()) / 60000)}m`
        : "n/a",
    };

    let pythonStatus = "UNKNOWN";
    let trustStatus = "UNKNOWN";
    let dbIntegrity = "UNKNOWN";
    let replayStatus = "UNKNOWN";
    try {
      const alive = await probePythonBases();
      pythonStatus = alive ? "PASS" : "FAIL";
      if (alive) {
        try { const t = await queryPython("/trust/status"); trustStatus = t.ok ? "PASS" : "FAIL"; } catch (_e) { trustStatus = "FAIL"; }
        try { const d = await resolveDbStatus(); dbIntegrity = d.ok ? "PASS" : "FAIL"; } catch (_e) { dbIntegrity = "FAIL"; }
        replayStatus = "PASS";
      }
    } catch (_e) { pythonStatus = "FAIL"; }

    const statuses = [entraHealth.status, llmHealth.status, approvalOpsHealth.status, pythonStatus, trustStatus, dbIntegrity];
    let globalStatus = "PASS";
    if (statuses.includes("FAIL")) globalStatus = "FAIL";
    else if (statuses.includes("WARN")) globalStatus = "WARN";

    return res.json({
      timestamp: new Date().toISOString(),
      global_status: globalStatus,
      critical_alerts: statuses.filter((s) => s === "FAIL").length,
      open_approvals: pendingApprovals.length,
      drift: "LOW",
      entra_identity: entraHealth,
      llm_integration: llmHealth,
      approval_ops: approvalOpsHealth,
      runtime: { python: pythonStatus, trust_ledger: trustStatus, db_integrity: dbIntegrity, replay_verifier: replayStatus },
    });
  } catch (err) {
    return res.status(500).json({ error: "integrations_health_failed", details: process.env.APP_ENV === "development" ? String(err) : undefined });
  }
});

/* ================= ADMIN: TREND SUMMARY ================= */

app.get("/admin/integrations/summary/trends", requireRole(["admin"]), (_req, res) => {
  const windowHours = parseInt(_req.query.window) || 24;
  const cutoff = Date.now() - (windowHours * 60 * 60 * 1000);
  const recentEvents = interceptEvents.filter((e) => new Date(e.timestamp).getTime() > cutoff);

  const requestIntercepts = recentEvents.filter((e) => e.type === "request");
  const responseEvents = recentEvents.filter((e) => e.type === "response");
  const allowCount = requestIntercepts.filter((e) => e.action === "ALLOW").length;
  const restrictCount = requestIntercepts.filter((e) => e.action === "RESTRICT").length;
  const requireApprovalCount = requestIntercepts.filter((e) => e.action === "REQUIRE_APPROVAL").length;
  const totalRequests = allowCount + restrictCount + requireApprovalCount || 1;
  const responseAllow = responseEvents.filter((e) => e.action === "ALLOW").length;
  const responseRemediate = responseEvents.filter((e) => e.action === "REMEDIATE").length;
  const totalResponses = responseAllow + responseRemediate || 1;

  const blockReasons = {};
  recentEvents.filter((e) => e.block_reason).forEach((e) => { blockReasons[e.block_reason] = (blockReasons[e.block_reason] || 0) + 1; });
  const topBlockReasons = Object.entries(blockReasons).sort((a, b) => b[1] - a[1]).slice(0, 5).map(([reason, count]) => ({ reason, count }));

  return res.json({
    window_hours: windowHours, timestamp: new Date().toISOString(),
    request_intercepts: {
      total: requestIntercepts.length,
      allow_count: allowCount,
      allow_pct: Math.round((allowCount / totalRequests) * 100),
      restrict_count: restrictCount,
      restrict_pct: Math.round((restrictCount / totalRequests) * 100),
      require_approval_count: requireApprovalCount,
      require_approval_pct: Math.round((requireApprovalCount / totalRequests) * 100),
    },
    response_governance: {
      total: responseEvents.length,
      allow_count: responseAllow,
      allow_pct: Math.round((responseAllow / totalResponses) * 100),
      remediate_count: responseRemediate,
      remediate_pct: Math.round((responseRemediate / totalResponses) * 100),
    },
    top_block_reasons: topBlockReasons,
  });
});

/* ================= ADMIN: EFFECTIVE CONFIG ================= */

app.get("/admin/config/effective", requireRole(["admin"]), (_req, res) => {
  const anyLlmConfigured = Boolean(copilotClient);
  const activeModels = [
    ...(Boolean(copilotClient) ? [COPILOT_MODEL] : []),
  ];
  const llmModel = activeModels.length > 0 ? activeModels.join(", ") : (LLM_STUB_ENABLED ? "stub" : "none");

  return res.json({
    timestamp: new Date().toISOString(),
    auth: { mode: getAuthMode(), entra_enabled: isEntraEnabled(), tenant_id: process.env.ENTRA_EXPECTED_TENANT_ID || null, audience: process.env.ENTRA_EXPECTED_AUDIENCE || null, issuer_pinning: Boolean(process.env.ENTRA_EXPECTED_ISSUERS) },
    signing: { enabled: SIGNING_ENABLED, key_id: SIGNING_KEY_ID, key_mode: signingKeyMode },
    llm: {
      ingestion_enabled: LLM_ENABLED,
      stub_enabled: LLM_STUB_ENABLED,
      provider_mode: LLM_PROVIDER_MODE,
      model: llmModel,
      api_key_present: anyLlmConfigured,
      copilot: { model: COPILOT_MODEL, api_key_present: Boolean(process.env.GITHUB_TOKEN) },
    },
    tls: { profiles_loaded: 0, cert_expiry_warnings: 0 },
    offload: { targets: [] },
    python_runtime: { base_url: activePythonBase, autostart: PYTHON_AUTOSTART },
    operations_state: {
      mode: bridgeStateMeta.mode,
      persistence: getBridgePersistenceStatus(),
      path: bridgeStateMeta.path,
      loaded_at: bridgeStateMeta.loaded_at,
      last_persisted_at: bridgeStateMeta.last_persisted_at,
      last_error: bridgeStateMeta.last_error,
      counts: {
        config_change_requests: configChangeRequests.length,
        approval_queue: approvalQueue.length,
        intercept_events: interceptEvents.length,
      },
    },
  });
});

/* ================= ADMIN: CONFIG CHANGE REQUESTS ================= */

app.post("/admin/config/change-request", requireRole(["admin"]), (req, res) => {
  const actor = req.actor || {};
  const { field, proposed_value, reason } = req.body || {};
  if (!field || !reason) return res.status(400).json({ error: "invalid_change_request", message: "field and reason are required." });

  const requestId = `cr-${crypto.randomUUID().slice(0, 8)}`;
  const entry = { request_id: requestId, field, proposed_value: proposed_value ?? null, reason, status: "pending", requested_by: actor.subject || "unknown", requested_at: new Date().toISOString(), decided_by: null, decided_at: null, decision: null };
  configChangeRequests.push(entry);
  persistOperationsState();
  appendLedger({ type: "CONFIG_CHANGE_REQUEST", request_id: requestId, field, actor_subject: actor.subject || "unknown", timestamp: entry.requested_at });
  return res.json(entry);
});

app.get("/admin/config/change-history", requireRole(["admin"]), (_req, res) => {
  return res.json({ requests: [...configChangeRequests].reverse(), count: configChangeRequests.length });
});

app.post("/admin/config/change-request/:request_id/decision", requireRole(["admin"]), (req, res) => {
  const actor = req.actor || {};
  const { decision, justification } = req.body || {};
  const entry = configChangeRequests.find((r) => r.request_id === req.params.request_id);
  if (!entry) return res.status(404).json({ error: "not_found" });
  if (!["approve", "reject"].includes(decision)) return res.status(400).json({ error: "invalid_decision" });
  entry.status = decision === "approve" ? "approved" : "rejected";
  entry.decided_by = actor.subject || "unknown";
  entry.decided_at = new Date().toISOString();
  entry.decision = decision;
  entry.justification = justification || null;
  persistOperationsState();
  appendLedger({ type: "CONFIG_CHANGE_DECISION", request_id: req.params.request_id, decision, actor_subject: actor.subject || "unknown", timestamp: entry.decided_at });
  return res.json(entry);
});

/* ================= ADMIN: APPROVAL QUEUE ================= */

app.get("/api/intercept/approval/pending", requireRole(["admin"]), (_req, res) => {
  return res.json({ pending: approvalQueue.filter((a) => a.status === "PENDING_APPROVAL"), count: approvalQueue.filter((a) => a.status === "PENDING_APPROVAL").length });
});

app.post("/api/intercept/approval/submit", requireRole(["admin", "standard", "customer"]), (req, res) => {
  const { execution_id, intercept_id, risk_level, requested_by } = req.body || {};
  const actor = req.actor || {};
  const approvalId = `apr-${crypto.randomUUID().slice(0, 8)}`;
  const entry = { approval_id: approvalId, execution_id: execution_id || null, intercept_id: intercept_id || null, requested_by: requested_by || actor.email || actor.subject || "unknown", risk_level: risk_level || "R3", status: "PENDING_APPROVAL", requested_at: new Date().toISOString(), decided_at: null, decided_by: null, decision: null };
  approvalQueue.push(entry);
  persistOperationsState();
  appendLedger({ type: "APPROVAL_QUEUE_SUBMIT", approval_id: approvalId, intercept_id: intercept_id || null, actor_subject: actor.subject || "unknown", timestamp: entry.requested_at });
  return res.json(entry);
});

app.post("/api/intercept/approval/decide", requireRole(["admin"]), (req, res) => {
  const actor = req.actor || {};
  const { approval_id, decision, justification } = req.body || {};
  const entry = approvalQueue.find((a) => a.approval_id === approval_id);
  if (!entry) return res.status(404).json({ error: "not_found" });
  if (!["approve", "reject", "escalate"].includes(decision)) return res.status(400).json({ error: "invalid_decision" });
  entry.status = decision === "approve" ? "APPROVED" : decision === "reject" ? "REJECTED" : "ESCALATED";
  entry.decided_by = actor.subject || "unknown";
  entry.decided_at = new Date().toISOString();
  entry.decision = decision;
  entry.justification = justification || null;
  persistOperationsState();
  appendLedger({ type: "APPROVAL_QUEUE_DECISION", approval_id, decision, actor_subject: actor.subject || "unknown", timestamp: entry.decided_at });
  return res.json(entry);
});

app.listen(PORT, "0.0.0.0", () => {
  console.log("DIIaC Governance Engine - Deterministic R/P Enforcement Active");
  console.log(`  Auth mode: ${getAuthMode()}`);
  console.log(`  Entra ID: ${isEntraEnabled() ? "ENABLED" : "disabled (legacy header auth)"}`);
});
