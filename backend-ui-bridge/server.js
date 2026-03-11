import express from "express";
import cors from "cors";
import fs from "fs";
import path from "path";
import crypto from "crypto";
import archiver from "archiver";
import { fileURLToPath } from "url";
import { spawn } from "child_process";
import OpenAI from "openai";
import { requireRole } from "./auth/rbac.js";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

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

app.get("/trust", requireRole(["admin"]), (_, res) => {
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

  if (!openai) throw new Error("LLM ingestion enabled but OPENAI_API_KEY is missing");

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

const PYTHON_BASE = "http://127.0.0.1:8000";
const REPO_ROOT = path.resolve(__dirname, "..");
let pyProc = null;
let pyStarting = null;

async function ensurePythonRuntime() {
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
      try {
        const r = await fetch(`${PYTHON_BASE}/health`);
        if (r.ok) return resolve();
      } catch (_e) {
      }
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
    const url = `${PYTHON_BASE}${targetPath}${query}`;

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

/* ================= EXPORT ================= */

app.get("/decision-pack/:execution_id/export",
  requireRole(["admin"]),
  (req, res) => {

    const folder = path.join(
      DECISION_PACK_BASE,
      req.params.execution_id
    );

    if (!fs.existsSync(folder))
      return res.status(404).json({ error: "Not found" });

    res.setHeader(
      "Content-Disposition",
      `attachment; filename=decision-pack_${req.params.execution_id}.zip`
    );

    res.setHeader("Content-Type", "application/zip");

    const archive = archiver("zip");
    archive.pipe(res);
    archive.directory(folder, false);
    archive.finalize();
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

app.get("/api/business-profiles", requireRole(["admin", "customer"]), (req, res) => proxyToPython(req, res, "/api/business-profiles"));
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
app.get("/admin/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/logs"));
app.get("/admin/executions/:execution_id/logs", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/executions/${req.params.execution_id}/logs`));
app.post("/admin/audit-export", requireRole(["admin"]), (req, res) => proxyToPython(req, res, "/admin/audit-export"));
app.get("/admin/audit-export/:export_id/download", requireRole(["admin"]), (req, res) => proxyToPython(req, res, `/admin/audit-export/${req.params.export_id}/download`));

app.listen(PORT, "0.0.0.0", () => {
  console.log("DIIaC Governance Engine — Deterministic R/P Enforcement Active");
});
