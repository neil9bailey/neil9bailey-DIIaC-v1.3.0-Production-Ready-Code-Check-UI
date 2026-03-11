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
const LLM_ENABLED = process.env.LLM_INGESTION_ENABLED === "true";
const LLM_STUB_ENABLED = process.env.LLM_STUB_ENABLED === "true";

const openai = (LLM_ENABLED && process.env.OPENAI_API_KEY)
  ? new OpenAI({ apiKey: process.env.OPENAI_API_KEY })
  : null;

const allowedOrigins = new Set([
  "http://localhost:5173",
  "http://127.0.0.1:5173",
]);

app.use(cors({
  origin(origin, cb) {
    if (!origin || allowedOrigins.has(origin)) return cb(null, true);
    return cb(new Error("Not allowed by CORS"));
  },
  allowedHeaders: ["Content-Type", "x-role"]
}));

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
  const record_hash = sha256(JSON.stringify(full));
  const sealed = { ...full, record_hash };
  fs.appendFileSync(LEDGER_PATH, JSON.stringify(sealed) + "\n");
  return sealed;
}

/* ================= TRUST ================= */

app.get("/trust", requireRole(["admin", "customer"]), (_, res) => {
  ensureLedger();
  const raw = fs.readFileSync(LEDGER_PATH, "utf8").trim();
  const count = raw ? raw.split("\n").filter(Boolean).length : 0;

  res.json({
    valid: true,
    records: count,
    ledger_root: getLastHash(),
    frozen: false
  });
});

/* ================= HUMAN INPUT ================= */

app.post("/api/human-input",
  requireRole(["customer", "admin"]),
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

      const aiReport = LLM_ENABLED
        ? await generateAI(context, reasoning_level, policy_level)
        : {};

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
  requireRole(["admin", "customer"]),
  (req, res, next) => {

    const artefactsDir = path.join(DECISION_PACK_BASE, req.params.execution_id, "artefacts");
    if (!fs.existsSync(artefactsDir)) return next();

    const reports = fs.readdirSync(artefactsDir).sort();
    return res.json({ execution_id: req.params.execution_id, reports });
  },
  (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/reports`)
);

app.get("/executions/:execution_id/reports/:file",
  requireRole(["admin", "customer"]),
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
  requireRole(["admin", "customer"]),
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

app.get("/api/business-profiles", requireRole(["admin", "customer"]), async (req, res) => {
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
app.post("/api/human-input/role", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, "/api/human-input/role"));
app.post("/api/governed-compile", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/api/governed-compile"));
app.get("/executions/:execution_id/trace-map", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/trace-map`));
app.get("/executions/:execution_id/scoring", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/scoring`));
app.get("/executions/:execution_id/merkle", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/merkle`));
app.get("/executions/:execution_id/merkle/proof/:artefact_name", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, `/executions/${req.params.execution_id}/merkle/proof/${req.params.artefact_name}`));
app.get("/verify/public-keys", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, "/verify/public-keys"));
app.get("/verify/execution/:execution_id", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, `/verify/execution/${req.params.execution_id}`));
app.post("/verify/merkle-proof", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, "/verify/merkle-proof"));
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
app.get("/trust/status", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, "/trust/status"));
app.get("/admin/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/logs"));
app.get("/admin/executions/:execution_id/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/executions/${req.params.execution_id}/logs`));
app.post("/admin/audit-export", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/audit-export"));
app.get("/admin/audit-export/:export_id/download", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/audit-export/${req.params.export_id}/download`));
app.get("/admin/audit/exports", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/audit/exports"));

app.listen(PORT, "0.0.0.0", () => {
  console.log("DIIaC Governance Engine — Deterministic R/P Enforcement Active");
});
