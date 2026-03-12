#!/usr/bin/env node
"use strict";

const fs = require("fs");
const path = require("path");
const crypto = require("crypto");

function sha256(text) {
  return crypto.createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
}

function listJsonFiles(dirPath, suffix) {
  if (!fs.existsSync(dirPath)) return [];
  return fs.readdirSync(dirPath)
    .filter((name) => name.endsWith(suffix))
    .sort();
}

function main() {
  const repoRoot = path.resolve(__dirname, "..");
  const profilesDir = path.join(repoRoot, "contracts", "business-profiles");
  const policyPacksDir = path.join(repoRoot, "contracts", "policy-packs");
  const testsPath = path.join(repoRoot, "tests", "test_admin_console.py");

  const profiles = listJsonFiles(profilesDir, "_profile_v1.json");
  const policyPacks = listJsonFiles(policyPacksDir, "_v1.json");
  const profilesHash = sha256(JSON.stringify(profiles));
  const policyPacksHash = sha256(JSON.stringify(policyPacks));

  const issues = [];
  const warnings = [];

  if (!profiles.length) issues.push("No business profiles found under contracts/business-profiles.");
  if (!policyPacks.length) issues.push("No policy packs found under contracts/policy-packs.");

  if (fs.existsSync(testsPath)) {
    const testsText = fs.readFileSync(testsPath, "utf8");
    const hardcodedProfileCount = testsText.match(/profiles_count'\]\s*==\s*\d+/g) || [];
    if (hardcodedProfileCount.length > 0) {
      issues.push("Hard-coded profile count assertions detected in tests; use dynamic contract count.");
    }
  } else {
    warnings.push("tests/test_admin_console.py not found; unable to check profile-count assertion drift.");
  }

  const result = {
    status: issues.length ? "FAIL" : "PASS",
    generated_at: new Date().toISOString(),
    contract: {
      profiles_count: profiles.length,
      policy_packs_count: policyPacks.length,
      profiles_hash: profilesHash,
      policy_packs_hash: policyPacksHash,
    },
    warnings,
    issues,
  };

  console.log(JSON.stringify(result, null, 2));
  process.exit(issues.length ? 2 : 0);
}

main();
