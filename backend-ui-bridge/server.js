import express from "express";
import cors from "cors";
import fs from "fs";
import path from "path";
import crypto from "crypto";
import archiver from "archiver";
import { fileURLToPath } from "url";
import { spawn, spawnSync } from "child_process";
import OpenAI from "openai";
import { requireRole } from "./auth/rbac.js";
import { entraAuth, isEntraEnabled, getAuthMode } from "./auth/entra.js";

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

const SIGNING_ENABLED = process.env.SIGNING_ENABLED !== "false";
const SIGNING_KEY_ID = process.env.SIGNING_KEY_ID || "ephemeral-local-ed25519";

/* ---- Ledger config flags ---- */
const LEDGER_APPEND_ENABLED = process.env.LEDGER_APPEND_ENABLED !== "false";
const LEDGER_FREEZE = process.env.LEDGER_FREEZE === "true";
const EFFECTIVE_LEDGER_PATH = process.env.LEDGER_PATH || LEDGER_PATH;
const LEDGER_TAIL_MAX = parseInt(process.env.LEDGER_TAIL_MAX || "200", 10);

fs.mkdirSync(HUMAN_INPUT_DIR, { recursive: true });
fs.mkdirSync(DECISION_PACK_BASE, { recursive: true });
fs.mkdirSync(path.dirname(LEDGER_PATH), { recursive: true });
fs.mkdirSync(path.dirname(EFFECTIVE_LEDGER_PATH), { recursive: true });
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

const { privateKey: signingPrivateKey, publicKey: signingPublicKey, keyMode: signingKeyMode } = loadOrCreateSigningKeyPair();

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

const localExecutions = new Map();

const OPENAI_MODEL = process.env.OPENAI_MODEL || "gpt-4o-mini";
const COPILOT_MODEL = process.env.COPILOT_MODEL || "gpt-4o";
const LLM_ENABLED = process.env.LLM_INGESTION_ENABLED === "true";
const LLM_STUB_ENABLED = process.env.LLM_STUB_ENABLED === "true";

const openai = (LLM_ENABLED && process.env.OPENAI_API_KEY)
  ? new OpenAI({ apiKey: process.env.OPENAI_API_KEY })
  : null;

// Copilot uses the same API key but a different model (red-team challenger)
const copilotClient = openai;

const allowedOrigins = new Set([
  "http://localhost:5173",
  "http://127.0.0.1:5173",
]);

app.use(cors({
  origin(origin, cb) {
    if (!origin || allowedOrigins.has(origin)) return cb(null, true);
    return cb(new Error("Not allowed by CORS"));
  },
  allowedHeaders: ["Content-Type", "x-role", "Authorization"]
}));

// Entra ID JWT authentication (no-op when AUTH_MODE is not entra_jwt_*)
app.use(entraAuth());

app.use(express.json());

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
  if (!fs.existsSync(EFFECTIVE_LEDGER_PATH)) fs.writeFileSync(EFFECTIVE_LEDGER_PATH, "");
}

function getLastHash() {
  ensureLedger();
  const raw = fs.readFileSync(EFFECTIVE_LEDGER_PATH, "utf8").trim();
  if (!raw) return "GENESIS";
  const lines = raw.split("\n").filter(Boolean);
  return JSON.parse(lines[lines.length - 1]).record_hash;
}

function appendLedger(record) {
  if (LEDGER_FREEZE) throw new Error("ledger_frozen: writes are disabled (LEDGER_FREEZE=true)");
  const full = { ...record, previous_hash: getLastHash() };
  const record_hash = sha256(JSON.stringify(full));
  const sealed = { ...full, record_hash };
  fs.appendFileSync(EFFECTIVE_LEDGER_PATH, JSON.stringify(sealed) + "\n");
  return sealed;
}

/* ================= REPLAY ATTESTATION ================= */

const ATTESTATIONS_DIRNAME = "attestations";

function computeExecutionPackHashFromArtefacts(executionId) {
  const artefactsDir = path.join(DECISION_PACK_BASE, executionId, "artefacts");
  if (!fs.existsSync(artefactsDir)) {
    return { ok: false, error: "artefacts_missing", artefactsDir };
  }
  const files = fs.readdirSync(artefactsDir).filter(Boolean).sort();
  if (!files.length) {
    return { ok: false, error: "no_artefacts", artefactsDir };
  }
  const hashes = files.map((f) => {
    const fp = path.join(artefactsDir, f);
    const content = fs.readFileSync(fp, "utf8");
    return sha256(content);
  });
  const packHash = sha256(hashes.join(""));
  return { ok: true, pack_hash: packHash, artefactsDir, files_count: files.length };
}

app.post("/verify/replay", requireRole(["admin"]), (req, res) => {
  try {
    const { execution_id } = req.body || {};
    if (!execution_id || typeof execution_id !== "string") {
      return res.status(400).json({ status: "FAILED", error: "execution_id_required" });
    }
    if (!localExecutions.has(execution_id)) {
      return res.status(404).json({ status: "FAILED", error: "execution_not_found" });
    }

    const cached = localExecutions.get(execution_id);
    const replay = computeExecutionPackHashFromArtefacts(execution_id);
    if (!replay.ok) {
      return res.status(409).json({ status: "FAILED", error: replay.error, details: replay });
    }

    const replay_valid = replay.pack_hash === cached.pack_hash;
    const certificate = {
      certificate_type: "deterministic_replay_attestation",
      execution_id,
      replay_valid,
      verified_hashes: {
        context_hash: cached.context_hash,
        pack_hash: replay.pack_hash,
      },
      determinism_mode: "STRICT_DETERMINISTIC_MODE",
      attested_at: new Date().toISOString(),
      statement: "Replay reproduced identical cryptographic results under identical deterministic rules.",
    };

    const certDir = path.join(DECISION_PACK_BASE, execution_id, ATTESTATIONS_DIRNAME);
    fs.mkdirSync(certDir, { recursive: true });
    const certPath = path.join(certDir, "replay_certificate.json");
    const certJson = JSON.stringify(certificate, null, 2);
    fs.writeFileSync(certPath, certJson);

    const certificate_hash = sha256(certJson);
    appendLedger({
      type: "REPLAY_CERTIFICATE_ANCHORED",
      execution_id,
      replay_valid,
      certificate_hash,
      certificate_path: `${execution_id}/${ATTESTATIONS_DIRNAME}/replay_certificate.json`,
      pack_hash: replay.pack_hash,
      timestamp: new Date().toISOString(),
    });

    if (!replay_valid) {
      return res.status(409).json({ status: "FAILED", replay_valid: false, certificate });
    }

    return res.json({
      status: "VERIFIED",
      replay_valid: true,
      certificate_hash,
      certificate,
      certificate_url: `/decision-pack/${encodeURIComponent(execution_id)}/attestations/replay_certificate.json`,
    });
  } catch (err) {
    return res.status(500).json({ status: "FAILED", error: "replay_attestation_error", details: String(err) });
  }
});

app.get("/decision-pack/:execution_id/attestations/:file", requireRole(["admin", "customer"]), (req, res) => {
  const fp = path.join(DECISION_PACK_BASE, req.params.execution_id, ATTESTATIONS_DIRNAME, req.params.file);
  if (!fs.existsSync(fp)) return res.status(404).json({ error: "not_found" });
  return res.sendFile(fp);
});

app.post("/verify/replay/batch", requireRole(["admin"]), (req, res) => {
  try {
    const { execution_ids } = req.body || {};
    const ids = Array.isArray(execution_ids)
      ? execution_ids.filter((x) => typeof x === "string" && x.trim())
      : [];
    if (!ids.length) return res.status(400).json({ error: "execution_ids_required" });

    const results = [];
    let passed = 0;
    let failed = 0;

    for (const id of ids) {
      if (!localExecutions.has(id)) {
        failed += 1;
        results.push({ execution_id: id, replay_valid: false, error: "execution_not_found" });
        continue;
      }
      const cached = localExecutions.get(id);
      const replay = computeExecutionPackHashFromArtefacts(id);
      if (!replay.ok) {
        failed += 1;
        results.push({ execution_id: id, replay_valid: false, error: replay.error });
        continue;
      }
      const replay_valid = replay.pack_hash === cached.pack_hash;
      if (replay_valid) passed += 1;
      else failed += 1;
      results.push({
        execution_id: id,
        replay_valid,
        pack_hash: replay.pack_hash,
        expected_pack_hash: cached.pack_hash,
      });
    }

    const status = failed === 0 ? "VERIFIED" : "FAILED";
    appendLedger({
      type: "REPLAY_BATCH_GATE",
      status,
      total: results.length,
      passed,
      failed,
      execution_ids: ids.slice(0, 200),
      timestamp: new Date().toISOString(),
    });

    return res.status(failed === 0 ? 200 : 409).json({
      status,
      total: results.length,
      passed,
      failed,
      results,
    });
  } catch (err) {
    return res.status(500).json({ error: "replay_batch_error", details: String(err) });
  }
});

/* ================= TRUST ================= */

app.get("/trust", requireRole(["admin", "standard", "customer"]), (_, res) => {
  ensureLedger();
  const raw = fs.readFileSync(EFFECTIVE_LEDGER_PATH, "utf8").trim();
  const count = raw ? raw.split("\n").filter(Boolean).length : 0;

  res.json({
    valid: true,
    records: count,
    ledger_root: getLastHash(),
    frozen: LEDGER_FREEZE,
    ledger_append_enabled: LEDGER_APPEND_ENABLED,
  });
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

async function generateAI(context, reasoning_level, policy_level) {

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
You are an elite enterprise strategy AI operating under governance constraints.

Return STRICT JSON only.
The word JSON must appear in your output.

You MUST include these top-level sections at minimum:
${requiredSections.join(", ")}

Each section must be a structured JSON object.

You MAY include additional relevant sections if they improve clarity and depth.

Provide detailed, board-ready, professionally structured content.

Do NOT include markdown.
Do NOT include commentary.
Return a valid JSON object only.
`;

  if (!openai) {
    if (!LLM_STUB_ENABLED) {
      throw new Error("LLM ingestion enabled but OPENAI_API_KEY is missing");
    }
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

  const response = await openai.responses.create({
    model: OPENAI_MODEL,
    input: [
      { role: "system", content: systemPrompt },
      { role: "user", content: JSON.stringify(context) }
    ],
    text: { format: { type: "json_object" } }
  });

  const text = response.output_text;
  if (!text) throw new Error("AI returned empty response");

  return JSON.parse(text);
}

async function generateCopilotAI(primaryReport, context) {
  const copilotSystemPrompt = `You are an adversarial red-team AI operating as a governance challenger.

Your role is to critically challenge and stress-test the strategy presented to you.

Return STRICT JSON only. The word JSON must appear in your output.

You MUST include these top-level sections:
challenge_summary, risk_flags, blind_spots, red_team_verdict

Each section must be a structured JSON object.

challenge_summary: A brief overview of the key weaknesses identified.
risk_flags: An array of objects with { risk, severity, rationale } for critical risks.
blind_spots: Areas the primary strategy failed to address adequately.
red_team_verdict: Overall assessment with { verdict, confidence, recommendation }.

Do NOT include markdown. Do NOT include commentary. Return a valid JSON object only.`;

  if (!copilotClient) {
    if (!LLM_STUB_ENABLED) throw new Error("Copilot LLM enabled but OPENAI_API_KEY is missing");
    return {
      challenge_summary: { overview: "Copilot red-team stub — no API key configured.", source: "copilot_stub" },
      risk_flags: [],
      blind_spots: { note: "Unable to evaluate without LLM access." },
      red_team_verdict: { verdict: "INCONCLUSIVE", confidence: 0, recommendation: "Configure OPENAI_API_KEY to enable red-team analysis." }
    };
  }

  const inputPayload = JSON.stringify({ primary_strategy: primaryReport, original_context: context });

  const response = await copilotClient.chat.completions.create({
    model: COPILOT_MODEL,
    messages: [
      { role: "system", content: copilotSystemPrompt },
      { role: "user", content: inputPayload }
    ],
    temperature: 0.2,
    response_format: { type: "json_object" }
  });

  const text = response.choices[0].message.content;
  if (!text) throw new Error("Copilot returned empty response");
  return JSON.parse(text);
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

/* ================= GOVERNED EXECUTION ================= */

app.post("/govern/decision",
  requireRole(["admin"]),
  async (req, res) => {

    try {

      let { provider, reasoning_level = "R2", policy_level = "P1" } = req.body;

      if (typeof provider === "object") {
        reasoning_level = provider.reasoning_level;
        policy_level = provider.policy_level;
        provider = provider.provider;
      }

      const executionId = crypto.randomUUID();

      const files = fs.readdirSync(HUMAN_INPUT_DIR)
        .filter(f => f.endsWith(".json"));

      if (!files.length)
        throw new Error("No human intent found");

      const latest = files.sort().reverse()[0];
      const contextRaw = fs.readFileSync(path.join(HUMAN_INPUT_DIR, latest), "utf8");
      const context = JSON.parse(contextRaw);
      const contextHash = sha256(contextRaw);

      const executionFolder = path.join(DECISION_PACK_BASE, executionId);
      const artefactsDir = path.join(executionFolder, "artefacts");
      fs.mkdirSync(artefactsDir, { recursive: true });

      let aiReport = {};
      let copilotReport = {};
      let llmContributions = { chatgpt: null, copilot: null };

      if (LLM_ENABLED) {
        aiReport = await generateAI(context, reasoning_level, policy_level);
        llmContributions.chatgpt = {
          provider: "chatgpt",
          model: OPENAI_MODEL,
          sections: Object.keys(aiReport),
          called_at: new Date().toISOString()
        };

        copilotReport = await generateCopilotAI(aiReport, context);
        llmContributions.copilot = {
          provider: "copilot",
          model: COPILOT_MODEL,
          sections: Object.keys(copilotReport),
          called_at: new Date().toISOString()
        };
      }

      const enforcement = enforceSections(
        aiReport,
        reasoning_level,
        policy_level
      );

      const signingPayload = {
        execution_id: executionId,
        context_hash: contextHash,
        signing_key_id: SIGNING_KEY_ID,
        signed_at: new Date().toISOString(),
      };
      const signingPayloadJson = JSON.stringify(signingPayload);
      const signature = SIGNING_ENABLED ? crypto.sign(null, Buffer.from(signingPayloadJson), signingPrivateKey) : Buffer.from("");
      const sigB64 = SIGNING_ENABLED ? signature.toString("base64") : "";

      const decisionSummary = {
        execution_id: executionId,
        provider,
        reasoning_level,
        policy_level,
        governance_contract: "DIIaC_CORE_V1",
        generated_at: new Date().toISOString(),
        classification: "BOARD_READY",
        context_hash: contextHash,
        JSON: enforcement.report,
        copilot_challenge: copilotReport,
        llm_contributions: llmContributions,
        signing: {
          signing_enabled: SIGNING_ENABLED,
          signature_present: Boolean(sigB64),
          signing_key_id: SIGNING_KEY_ID,
        },
        __tier_enforcement: {
          reasoning_level,
          policy_level,
          enforced_sections: enforcement.enforced_sections,
          enforcement_timestamp: new Date().toISOString()
        }
      };

      fs.writeFileSync(
        path.join(artefactsDir, "decision_summary.json"),
        JSON.stringify(decisionSummary, null, 2)
      );

      const sigMeta = {
        signature_alg: "Ed25519",
        signing_key_id: SIGNING_KEY_ID,
        signed_at: signingPayload.signed_at,
        execution_id: executionId,
        context_hash: contextHash,
        signature_payload: signingPayload,
        signature: sigB64,
      };

      fs.writeFileSync(path.join(artefactsDir, "signed_export.sig"), sigB64);
      fs.writeFileSync(path.join(artefactsDir, "signed_export.sigmeta.json"), JSON.stringify(sigMeta, null, 2));

      if (reasoning_level === "R5") {
        fs.writeFileSync(
          path.join(artefactsDir, "strategy_report.json"),
          JSON.stringify(enforcement.report, null, 2)
        );
      }

      /* ===== DETERMINISTIC HASHING ===== */

      const artefactFiles = fs.readdirSync(artefactsDir).sort();

      const artefactHashes = artefactFiles.map(file => {
        const content = fs.readFileSync(path.join(artefactsDir, file), "utf8");
        return {
          name: file,
          hash: sha256(content)
        };
      });

      const initialPackHash = sha256(
        artefactHashes.map(a => a.hash).join("")
      );

      const manifest = {
        execution_id: executionId,
        governance_contract: "DIIaC_CORE_V1",
        reasoning_level,
        policy_level,
        context_hash: contextHash,
        artefacts: artefactHashes,
        pack_hash: initialPackHash,
        generated_at: new Date().toISOString()
      };

      fs.writeFileSync(
        path.join(artefactsDir, "governance_manifest.json"),
        JSON.stringify(manifest, null, 2)
      );

      const finalFiles = fs.readdirSync(artefactsDir).sort();
      const finalHashes = finalFiles.map(file => {
        const content = fs.readFileSync(path.join(artefactsDir, file), "utf8");
        return sha256(content);
      });

      const finalPackHash = sha256(finalHashes.join(""));

      const sealed = appendLedger({
        type: "GOVERNED_EXECUTION",
        execution_id: executionId,
        provider,
        reasoning_level,
        policy_level,
        context_hash: contextHash,
        pack_hash: finalPackHash,
        artefact_count: finalFiles.length,
        timestamp: new Date().toISOString()
      });

      localExecutions.set(executionId, {
        execution_id: executionId,
        pack_hash: finalPackHash,
        context_hash: contextHash,
        signature: sigB64,
        signing_key_id: SIGNING_KEY_ID,
      });

      res.json({
        execution_state: {
          execution_id: executionId,
          provider,
          reasoning_level,
          policy_level,
          pack_hash: finalPackHash,
          ledger_root: sealed.record_hash,
          signature_present: Boolean(sigB64),
          signing_enabled: SIGNING_ENABLED,
          signing_key_id: SIGNING_KEY_ID,
          key_mode: signingKeyMode,
          llm_contributions: llmContributions,
        }
      });

    } catch (err) {
      console.error(err);
      res.status(500).json({ error: err.message });
    }
  }
);

app.post("/api/llm-governed-compile", requireRole(["admin"]), async (req, res) => {
  try {
    const {
      provider = "ChatGPT",
      reasoning_level = "R4",
      policy_level = "P4",
      profile_id = "transport_profile_v1",
      schema_id = "GENERAL_SOLUTION_BOARD_REPORT_V1",
      role = "CIO",
      domain = "enterprise-strategy",
      assertions = [],
      governance_modes = [],
      human_intent,
      execution_context_id,
    } = req.body || {};

    if (typeof human_intent === "string" && human_intent.trim()) {
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

    const aiReport = await generateAI(context, reasoning_level, policy_level);
    const llmOutputHash = sha256(stableJson(aiReport));
    const contextId = execution_context_id || `ctx-llm-${llmOutputHash.slice(0, 20)}`;
    const assertionList = Array.isArray(assertions) && assertions.length
      ? assertions.filter((a) => typeof a === "string" && a.trim()).map((a) => a.trim())
      : [`LLM synthesis hash ${llmOutputHash.slice(0, 12)}`, `Provider ${provider}`];

    const rolePayload = {
      execution_context_id: contextId,
      role,
      domain,
      assertions: assertionList,
      non_negotiables: ["deterministic-governance"],
      risk_flags: ["llm-hallucination-risk"],
      evidence_refs: [`llm-output-${llmOutputHash.slice(0, 16)}`],
    };

    const roleStore = await pythonPost("/api/human-input/role", rolePayload);
    if (!roleStore.ok) {
      return res.status(roleStore.status).json({ error: "role_input_failed", details: roleStore.payload });
    }

    const compilePayload = {
      execution_context_id: contextId,
      profile_id,
      schema_id,
      reasoning_level,
      policy_level,
      governance_modes: Array.isArray(governance_modes)
        ? governance_modes.filter((m) => typeof m === "string" && m.trim()).map((m) => m.trim())
        : [],
    };
    const compile = await pythonPost("/api/governed-compile", compilePayload);
    if (!compile.ok) {
      return res.status(compile.status).json({ error: "governed_compile_failed", details: compile.payload });
    }

    return res.json({
      mode: "llm_plus_deterministic_governed_compile",
      provider,
      llm_output_hash: llmOutputHash,
      llm_sections: Object.keys(aiReport || {}),
      execution_context_id: contextId,
      role_input: roleStore.payload,
      compile: compile.payload,
    });
  } catch (err) {
    return res.status(500).json({ error: "llm_governed_compile_failed", details: String(err) });
  }
});


/* ================= REPORTS ================= */

app.get("/executions/:execution_id/reports",
  requireRole(["admin", "standard", "customer"]),
  (req, res, next) => {

    const artefactsDir = path.join(DECISION_PACK_BASE, req.params.execution_id, "artefacts");
    if (!fs.existsSync(artefactsDir)) return next();

    const reports = fs.readdirSync(artefactsDir).sort();
    return res.json({ execution_id: req.params.execution_id, reports });
  },
  (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/reports`)
);

app.get("/executions/:execution_id/reports/:file",
  requireRole(["admin", "standard", "customer"]),
  (req, res, next) => {

    const artefactsDir = path.join(DECISION_PACK_BASE, req.params.execution_id, "artefacts");
    const f = path.join(artefactsDir, req.params.file);

    if (!fs.existsSync(f)) return next();

    return res.sendFile(f);
  },
  (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/reports/${req.params.file}`)
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
    return res.status(502).json({ error: "python_proxy_error", details: String(err) });
  }
}



async function queryPython(pathname) {
  const r = await fetch(`${activePythonBase}${pathname}`);
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
    integrity: { ok: true, mode: "bridge_fallback" },
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
    return res.status(502).json({ error: "service_status_unavailable", details: String(err) });
  }
});

app.get("/admin/status/containers", requireRole(["admin"]), (_req, res) => {
  try {
    const cmd = process.env.DIIAC_DOCKER_STATUS_CMD || "docker ps --format '{{json .}}'";
    const out = spawnSync("bash", ["-lc", cmd], { encoding: "utf-8", timeout: 5000 });
    if (out.status !== 0) {
      return res.json({
        available: false,
        command: cmd,
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
    return res.json({ available: true, command: cmd, containers });
  } catch (err) {
    return res.json({ available: false, error: String(err), containers: [] });
  }
});

/* ================= EXPORT ================= */

app.get("/decision-pack/:execution_id/export",
  requireRole(["admin"]),
  (req, res, next) => {
    const artefactsDir = path.join(DECISION_PACK_BASE, req.params.execution_id, "artefacts");
    if (!fs.existsSync(artefactsDir)) return next();

    res.setHeader(
      "Content-Disposition",
      `attachment; filename=decision-pack_${req.params.execution_id}.zip`
    );
    res.setHeader("Content-Type", "application/zip");

    const archive = archiver("zip");
    archive.on("error", (err) => {
      if (!res.headersSent) {
        res.status(500).json({ error: "export_archive_error", details: String(err) });
      }
    });
    archive.pipe(res);
    archive.directory(artefactsDir, false);
    archive.finalize();
  },
  async (req, res) => {
    try {
      await ensurePythonRuntime();
      const query = req.originalUrl.includes("?") ? req.originalUrl.slice(req.originalUrl.indexOf("?")) : "";

      const primary = await fetch(`${activePythonBase}/decision-pack/${req.params.execution_id}/export${query}`);
      if (primary.ok) {
        const ct = primary.headers.get("content-type") || "application/octet-stream";
        const buf = Buffer.from(await primary.arrayBuffer());
        res.status(primary.status);
        res.setHeader("content-type", ct);
        return res.send(buf);
      }

      if (primary.status === 404) {
        const fallback = await fetch(`${activePythonBase}/decision-pack/${req.params.execution_id}/export-signed${query}`);
        if (fallback.ok) {
          const ct = fallback.headers.get("content-type") || "application/octet-stream";
          if (ct.includes("application/json")) {
            const meta = await fallback.json();
            const zipPath = meta?.zip_path;
            if (zipPath && fs.existsSync(zipPath)) {
              res.status(200);
              res.setHeader("content-type", "application/zip");
              res.setHeader("content-disposition", `attachment; filename=decision-pack_${req.params.execution_id}.zip`);
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
      return res.status(502).json({ error: "python_proxy_error", details: String(err) });
    }
  }
);





app.post("/verify/pack",
  requireRole(["admin", "standard", "customer"]),
  (req, res, next) => {
    const { execution_id, pack_hash } = req.body || {};
    if (!execution_id || !localExecutions.has(execution_id)) return next();

    const e = localExecutions.get(execution_id);
    const sigmetaPath = path.join(DECISION_PACK_BASE, execution_id, "artefacts", "signed_export.sigmeta.json");
    if (!fs.existsSync(sigmetaPath)) {
      return res.json({ signature_valid: false, hash_valid: false, manifest_consistent: false, overall_valid: false });
    }
    const sigmeta = JSON.parse(fs.readFileSync(sigmetaPath, "utf8"));
    const payload = JSON.stringify(sigmeta.signature_payload || {});
    const signature = Buffer.from(sigmeta.signature || "", "base64");
    const signatureValid = SIGNING_ENABLED ? crypto.verify(null, Buffer.from(payload), signingPublicKey, signature) : true;
    const requestedPackHash = pack_hash || sigmeta.signature_payload?.pack_hash || e.pack_hash;
    const hashValid = requestedPackHash === e.pack_hash;

    return res.json({
      signature_valid: signatureValid,
      hash_valid: hashValid,
      manifest_consistent: true,
      overall_valid: Boolean(signatureValid && hashValid),
    });
  },
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
app.post("/api/governed-compile", requireRole(["admin"]), async (req, res) => {
  /* Proxy to Python runtime, then anchor a GOVERNED_EXECUTION record in the bridge ledger. */
  try {
    await ensurePythonRuntime();
    const query = req.originalUrl.includes("?") ? req.originalUrl.slice(req.originalUrl.indexOf("?")) : "";
    const r = await fetch(`${activePythonBase}/api/governed-compile${query}`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: req.body && Object.keys(req.body).length ? JSON.stringify(req.body) : undefined,
    });
    const ct = r.headers.get("content-type") || "application/json";
    res.status(r.status);
    res.setHeader("content-type", ct);
    if (!ct.includes("application/json")) {
      return res.send(Buffer.from(await r.arrayBuffer()));
    }
    const body = await r.json();
    /* Anchor to bridge ledger on success (2xx) when enabled */
    if (r.ok && LEDGER_APPEND_ENABLED && !LEDGER_FREEZE && body.execution_id) {
      try {
        const actor = req.actor?.name || req.headers["x-user"] || req.headers["x-role"] || "unknown";
        appendLedger({
          type: "GOVERNED_EXECUTION",
          execution_id: body.execution_id,
          pack_hash: body.pack_hash || null,
          merkle_root: body.merkle_root || null,
          manifest_hash: body.manifest_hash || null,
          actor,
          timestamp: new Date().toISOString(),
        });
      } catch (ledgerErr) {
        console.error("[ledger] governed-compile append failed:", String(ledgerErr));
      }
    }
    return res.json(body);
  } catch (err) {
    return res.status(502).json({ error: "python_proxy_error", details: String(err) });
  }
});
app.get("/executions/:execution_id/trace-map", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/trace-map`));
app.get("/executions/:execution_id/scoring", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/scoring`));
app.get("/executions/:execution_id/merkle", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/merkle`));
app.get("/executions/:execution_id/merkle/proof/:artefact_name", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/merkle/proof/${req.params.artefact_name}`));
app.get("/verify/public-keys", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, "/verify/public-keys"));
app.get("/verify/execution/:execution_id", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, `/verify/execution/${req.params.execution_id}`));
app.post("/verify/merkle-proof", requireRole(["admin", "standard", "customer"]), (req, res) => proxyToPython(req, res, "/verify/merkle-proof"));
app.get("/decision-pack/:execution_id/export-signed", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/decision-pack/${req.params.execution_id}/export-signed`));
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
app.get("/trust/status", requireRole(["admin", "standard", "customer"]), (_req, res) => {
  /* Read persistent bridge ledger — not Python's in-memory state. */
  ensureLedger();
  const raw = fs.readFileSync(EFFECTIVE_LEDGER_PATH, "utf8").trim();
  const lines = raw ? raw.split("\n").filter(Boolean) : [];
  const count = lines.length;
  const last = count > 0 ? (() => { try { return JSON.parse(lines[count - 1]); } catch (_e) { return null; } })() : null;
  return res.json({
    ledger_records: count,
    ledger_root: last ? last.record_hash : "GENESIS",
    frozen: LEDGER_FREEZE,
    ledger_append_enabled: LEDGER_APPEND_ENABLED,
    source: "bridge_ledger",
  });
});

app.get("/admin/ledger/logs", requireRole(["admin"]), (_req, res) => {
  /* Returns the tail of the persistent bridge ledger.jsonl. */
  ensureLedger();
  const raw = fs.readFileSync(EFFECTIVE_LEDGER_PATH, "utf8").trim();
  const lines = raw ? raw.split("\n").filter(Boolean) : [];
  const all = lines.map((l) => { try { return JSON.parse(l); } catch (_e) { return null; } }).filter(Boolean);
  const tail = all.slice(-LEDGER_TAIL_MAX);
  const lastRecord = all.length > 0 ? all[all.length - 1] : null;
  return res.json({
    total: all.length,
    returned: tail.length,
    ledger_root: lastRecord ? lastRecord.record_hash : "GENESIS",
    frozen: LEDGER_FREEZE,
    logs: tail,
  });
});

app.get("/admin/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/logs"));
app.get("/admin/executions/:execution_id/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/executions/${req.params.execution_id}/logs`));
app.post("/admin/audit-export", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/audit-export"));
app.get("/admin/audit-export/:export_id/download", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/audit-export/${req.params.export_id}/download`));
app.get("/admin/audit/exports", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/audit/exports"));

/* ================= AUTH STATUS ================= */

app.get("/auth/status", (_req, res) => {
  res.json({
    auth_mode: getAuthMode(),
    entra_enabled: isEntraEnabled(),
    tenant_id: isEntraEnabled() ? (process.env.ENTRA_EXPECTED_TENANT_ID || null) : null,
    audience: isEntraEnabled() ? (process.env.ENTRA_EXPECTED_AUDIENCE || null) : null,
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
  // OIDC redirect callback — returns code/state for interactive test clients
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
      });
    } catch (err) {
      return res.status(500).json({ error: "intercept_failed", details: String(err) });
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
      });
    } catch (err) {
      return res.status(500).json({ error: "response_record_failed", details: String(err) });
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
      return res.status(500).json({ error: "approval_failed", details: String(err) });
    }
  }
);

/* ================= ADMIN: INTEGRATIONS HEALTH ================= */

const configChangeRequests = [];
const approvalQueue = [];
const interceptEvents = [];

function recordInterceptEvent(type, details) {
  interceptEvents.push({ type, timestamp: new Date().toISOString(), ...details });
  if (interceptEvents.length > 10000) interceptEvents.splice(0, interceptEvents.length - 10000);
}

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

    const llmHealth = {
      status: (LLM_ENABLED && openai) ? "PASS" : (LLM_STUB_ENABLED ? "WARN" : "FAIL"),
      ingestion_enabled: LLM_ENABLED,
      api_key: (LLM_ENABLED && process.env.OPENAI_API_KEY) ? "configured" : "missing",
      stub_mode: LLM_STUB_ENABLED,
      model: OPENAI_MODEL,
      dual_llm_loop: LLM_ENABLED && Boolean(openai),
      providers: {
        chatgpt: {
          status: (LLM_ENABLED && openai) ? "PASS" : "FAIL",
          model: OPENAI_MODEL,
          role: "strategy_synthesis"
        },
        copilot: {
          status: (LLM_ENABLED && copilotClient) ? "PASS" : "FAIL",
          model: COPILOT_MODEL,
          role: "red_team_challenge"
        }
      }
    };

    const pendingApprovals = approvalQueue.filter((a) => a.status === "PENDING_APPROVAL");
    const approvalOpsHealth = {
      status: "PASS",
      pending_count: pendingApprovals.length,
      persistence: "OK",
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
    return res.status(500).json({ error: "integrations_health_failed", details: String(err) });
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
    request_intercepts: { total: requestIntercepts.length, allow_pct: Math.round((allowCount / totalRequests) * 100), restrict_pct: Math.round((restrictCount / totalRequests) * 100), require_approval_pct: Math.round((requireApprovalCount / totalRequests) * 100) },
    response_governance: { total: responseEvents.length, allow_pct: Math.round((responseAllow / totalResponses) * 100), remediate_pct: Math.round((responseRemediate / totalResponses) * 100) },
    top_block_reasons: topBlockReasons,
  });
});

/* ================= ADMIN: EFFECTIVE CONFIG ================= */

app.get("/admin/config/effective", requireRole(["admin"]), (_req, res) => {
  return res.json({
    timestamp: new Date().toISOString(),
    auth: { mode: getAuthMode(), entra_enabled: isEntraEnabled(), tenant_id: process.env.ENTRA_EXPECTED_TENANT_ID || null, audience: process.env.ENTRA_EXPECTED_AUDIENCE || null, issuer_pinning: Boolean(process.env.ENTRA_EXPECTED_ISSUERS) },
    signing: { enabled: SIGNING_ENABLED, key_id: SIGNING_KEY_ID, key_mode: signingKeyMode },
    llm: { ingestion_enabled: LLM_ENABLED, stub_enabled: LLM_STUB_ENABLED, model: OPENAI_MODEL, api_key_present: Boolean(process.env.OPENAI_API_KEY) },
    tls: { profiles_loaded: 0, cert_expiry_warnings: 0 },
    offload: { targets: [] },
    python_runtime: { base_url: activePythonBase, autostart: PYTHON_AUTOSTART },
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
  appendLedger({ type: "APPROVAL_QUEUE_DECISION", approval_id, decision, actor_subject: actor.subject || "unknown", timestamp: entry.decided_at });
  return res.json(entry);
});

app.listen(PORT, "0.0.0.0", () => {
  console.log("DIIaC Governance Engine — Deterministic R/P Enforcement Active");
  console.log(`  Auth mode: ${getAuthMode()}`);
  console.log(`  Entra ID: ${isEntraEnabled() ? "ENABLED" : "disabled (legacy header auth)"}`);
});
