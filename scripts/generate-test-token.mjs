#!/usr/bin/env node
// scripts/generate-test-token.mjs
// Generates HS256 JWTs for local Entra auth testing.
//
// Usage:
//   node scripts/generate-test-token.mjs                  # admin token (1 h)
//   node scripts/generate-test-token.mjs customer          # customer token
//   node scripts/generate-test-token.mjs admin 5m          # admin, 5-minute expiry
//   node scripts/generate-test-token.mjs --expired         # already-expired token (for negative tests)

import { SignJWT } from "jose";

// ── Defaults (must match your .env / docker-compose env) ─────────
const SECRET = process.env.ENTRA_JWT_HS256_SECRET || "diiac-local-test-secret-change-me-in-prod!!";
const TENANT = process.env.ENTRA_EXPECTED_TENANT_ID || "local-test-tenant";
const AUDIENCE = process.env.ENTRA_EXPECTED_AUDIENCE || "diiac-bridge-local";
const ISSUER = process.env.ENTRA_EXPECTED_ISSUERS?.split(",")[0]?.trim() || "https://diiac-local-test-issuer";

// ── Parse CLI args ───────────────────────────────────────────────
const args = process.argv.slice(2);
const expired = args.includes("--expired");
const role = args.find((a) => a === "admin" || a === "customer") || "admin";
const expiry = expired ? "-1h" : (args.find((a) => /^\d+[smhd]$/.test(a)) || "1h");

const secret = new TextEncoder().encode(SECRET);

const token = await new SignJWT({
  sub: `test-${role}-001`,
  name: `Test ${role.charAt(0).toUpperCase() + role.slice(1)}`,
  email: `${role}@vendorlogic.local`,
  tid: TENANT,
  roles: [role],
})
  .setProtectedHeader({ alg: "HS256", typ: "JWT" })
  .setAudience(AUDIENCE)
  .setIssuer(ISSUER)
  .setIssuedAt()
  .setExpirationTime(expiry)
  .sign(secret);

console.log("\n--- Token Details ---");
console.log(`  Role:     ${role}`);
console.log(`  Expiry:   ${expiry}${expired ? " (ALREADY EXPIRED)" : ""}`);
console.log(`  Tenant:   ${TENANT}`);
console.log(`  Audience: ${AUDIENCE}`);
console.log(`  Issuer:   ${ISSUER}`);
console.log("\n--- JWT ---");
console.log(token);
console.log("\n--- curl example ---");
console.log(`curl -s -H "Authorization: Bearer ${token}" http://localhost:3001/auth/status | jq .`);
console.log(`curl -s -H "Authorization: Bearer ${token}" -X POST -H "Content-Type: application/json" -d '{"prompt":"test"}' http://localhost:3001/api/intercept/request | jq .`);
console.log();
