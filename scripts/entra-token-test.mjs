#!/usr/bin/env node
// scripts/entra-token-test.mjs
//
// Acquires an Entra ID token via client_credentials flow and tests
// the DIIaC bridge endpoints end-to-end.
//
// Usage:
//   node scripts/entra-token-test.mjs
//
// Required env vars (set in .env or export):
//   ENTRA_EXPECTED_TENANT_ID   — Entra tenant ID
//   ENTRA_EXPECTED_AUDIENCE    — App registration client ID (also used as resource)
//   ENTRA_CLIENT_SECRET        — App registration client secret
//
// Optional:
//   BRIDGE_URL                 — Bridge base URL (default: http://localhost:3001)

const TENANT_ID = process.env.ENTRA_EXPECTED_TENANT_ID || "1384b1c5-2bae-45a1-a4b4-e94e3315eb41";
const CLIENT_ID = process.env.ENTRA_EXPECTED_AUDIENCE || "b726558d-f1c6-48f7-8a3d-72d5db818d0f";
const CLIENT_SECRET = process.env.ENTRA_CLIENT_SECRET || "";
const BRIDGE_URL = process.env.BRIDGE_URL || "http://localhost:3001";

if (!CLIENT_ID || !CLIENT_SECRET) {
  console.error("ERROR: ENTRA_EXPECTED_AUDIENCE and ENTRA_CLIENT_SECRET must be set.");
  console.error("");
  console.error("  export ENTRA_EXPECTED_AUDIENCE=<app-client-id>");
  console.error("  export ENTRA_CLIENT_SECRET=<app-client-secret>");
  console.error("  node scripts/entra-token-test.mjs");
  process.exit(1);
}

// ── Helpers ─────────────────────────────────────────────────────

function log(label, value) {
  console.log(`  ${label.padEnd(28)} ${value}`);
}

function section(title) {
  console.log("");
  console.log(`── ${title} ${"─".repeat(Math.max(0, 55 - title.length))}`);
}

async function post(url, body, headers = {}) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify(body),
  });
  const data = await res.json().catch(() => null);
  return { status: res.status, data };
}

async function get(url, headers = {}) {
  const res = await fetch(url, { headers });
  const data = await res.json().catch(() => null);
  return { status: res.status, data };
}

// ── Step 1: Acquire Token ───────────────────────────────────────

section("1. Acquiring Entra ID token (client_credentials)");

const tokenUrl = `https://login.microsoftonline.com/${TENANT_ID}/oauth2/v2.0/token`;
const tokenBody = new URLSearchParams({
  grant_type: "client_credentials",
  client_id: CLIENT_ID,
  client_secret: CLIENT_SECRET,
  scope: `${CLIENT_ID}/.default`,
});

let accessToken;
try {
  const tokenRes = await fetch(tokenUrl, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: tokenBody.toString(),
  });
  const tokenData = await tokenRes.json();

  if (!tokenRes.ok || !tokenData.access_token) {
    console.error("  FAILED to acquire token:", tokenData.error_description || tokenData.error || "unknown error");
    process.exit(1);
  }

  accessToken = tokenData.access_token;

  // Decode payload (no verification — just for display)
  const payload = JSON.parse(Buffer.from(accessToken.split(".")[1], "base64url").toString());
  log("Token acquired:", "YES");
  log("Subject (sub):", payload.sub || "n/a");
  log("App ID (appid):", payload.appid || payload.azp || "n/a");
  log("Tenant (tid):", payload.tid || "n/a");
  log("Audience (aud):", payload.aud || "n/a");
  log("Roles:", JSON.stringify(payload.roles || []));
  log("Expires:", new Date((payload.exp || 0) * 1000).toISOString());
} catch (err) {
  console.error("  FAILED to connect to Entra:", err.message);
  process.exit(1);
}

const authHeaders = { Authorization: `Bearer ${accessToken}` };

// ── Step 2: Auth Status ─────────────────────────────────────────

section("2. Checking bridge auth status");
try {
  const { status, data } = await get(`${BRIDGE_URL}/auth/status`);
  log("HTTP status:", status);
  log("Auth mode:", data?.auth_mode || "unknown");
  log("Entra enabled:", String(data?.entra_enabled));
} catch (err) {
  console.error("  FAILED — is the bridge running?", err.message);
  process.exit(1);
}

// ── Step 3: Test with valid token ───────────────────────────────

section("3. Testing authenticated request (GET /trust/status)");
{
  const { status, data } = await get(`${BRIDGE_URL}/trust/status`, authHeaders);
  log("HTTP status:", status);
  if (status === 200) {
    log("Result:", "PASS — authenticated access granted");
  } else {
    log("Result:", `FAIL — ${data?.error || "unexpected status"}`);
    log("Message:", data?.message || "");
  }
}

// ── Step 4: Copilot intercept ───────────────────────────────────

section("4. Testing Copilot intercept (POST /api/intercept/request)");
let interceptId;
{
  const { status, data } = await post(
    `${BRIDGE_URL}/api/intercept/request`,
    {
      prompt: "What SD-WAN vendor should we select for the UK rail network?",
      source: "copilot",
      context: { workspace: "entra-integration-test" },
    },
    authHeaders
  );
  log("HTTP status:", status);
  if (status === 200 && data?.intercept_id) {
    interceptId = data.intercept_id;
    log("Intercept ID:", interceptId);
    log("Actor subject:", data.actor?.subject || "n/a");
    log("Actor role:", data.actor?.role || "n/a");
    log("Token type:", data.actor?.token_type || "n/a");
    log("Prompt hash:", data.prompt_hash || "n/a");
    log("Ledger hash:", data.ledger_hash || "n/a");
    log("Result:", "PASS");
  } else {
    log("Result:", `FAIL — ${data?.error || "unexpected"}`);
    log("Message:", data?.message || "");
  }
}

// ── Step 5: Copilot response ────────────────────────────────────

if (interceptId) {
  section("5. Testing Copilot response (POST /api/intercept/response)");
  const { status, data } = await post(
    `${BRIDGE_URL}/api/intercept/response`,
    {
      intercept_id: interceptId,
      response_text: "Based on governance analysis, Vendor A scores highest on resilience and compliance.",
      model: "gpt-4o",
      confidence: 0.87,
    },
    authHeaders
  );
  log("HTTP status:", status);
  if (status === 200) {
    log("Response hash:", data.response_hash || "n/a");
    log("Ledger hash:", data.ledger_hash || "n/a");
    log("Result:", "PASS");
  } else {
    log("Result:", `FAIL — ${data?.error || "unexpected"}`);
  }
}

// ── Step 6: Copilot approval ────────────────────────────────────

if (interceptId) {
  section("6. Testing Copilot approval (POST /api/intercept/approval)");
  const { status, data } = await post(
    `${BRIDGE_URL}/api/intercept/approval`,
    {
      intercept_id: interceptId,
      decision: "approve",
      justification: "Entra integration test — governance criteria met",
    },
    authHeaders
  );
  log("HTTP status:", status);
  if (status === 200) {
    log("Decision:", data.decision || "n/a");
    log("Ledger hash:", data.ledger_hash || "n/a");
    log("Result:", "PASS");
  } else {
    log("Result:", `FAIL — ${data?.error || "unexpected"}`);
  }
}

// ── Step 7: Rejection test (no token) ───────────────────────────

section("7. Testing rejection (no token)");
{
  const { status, data } = await get(`${BRIDGE_URL}/trust/status`);
  log("HTTP status:", status);
  if (status === 401) {
    log("Error:", data?.error || "n/a");
    log("Result:", "PASS — correctly rejected");
  } else {
    log("Result:", status === 200 ? "WARN — request allowed without token (check AUTH_MODE)" : `UNEXPECTED — ${status}`);
  }
}

// ── Step 8: Rejection test (bad token) ──────────────────────────

section("8. Testing rejection (invalid token)");
{
  const { status, data } = await get(`${BRIDGE_URL}/trust/status`, {
    Authorization: "Bearer invalid.token.here",
  });
  log("HTTP status:", status);
  if (status === 401) {
    log("Error:", data?.error || "n/a");
    log("Result:", "PASS — correctly rejected");
  } else {
    log("Result:", `UNEXPECTED — ${status}`);
  }
}

// ── Summary ─────────────────────────────────────────────────────

section("Summary");
console.log("  Token acquisition, authenticated access, Copilot governance");
console.log("  intercept flow, and rejection tests complete.");
console.log("");
console.log("  Next steps:");
console.log("  - Run COPILOT_ENTRA_PRODUCTION_CHECKLIST.md for full validation");
console.log("  - Test with delegated (user) tokens via interactive MSAL flow");
console.log("  - Verify group-to-role mapping if using Entra group membership");
console.log("");
