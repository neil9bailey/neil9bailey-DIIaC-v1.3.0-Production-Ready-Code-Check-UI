#!/usr/bin/env node
// tools/verify-ledger.js — CLI chain verifier for the bridge ledger.jsonl
//
// Validates:
//   1. record_hash == sha256(JSON.stringify(record_without_hash))
//   2. previous_hash chain starting from GENESIS
//
// Usage:
//   node tools/verify-ledger.js [--ledger /path/to/ledger.jsonl]
//
// Exits 0 on success, 1 on verification failure, 2 on usage/IO error.

import fs from "fs";
import crypto from "crypto";

function sha256(input) {
  return crypto.createHash("sha256").update(input).digest("hex");
}

function usage() {
  console.error("Usage: node tools/verify-ledger.js [--ledger /path/to/ledger.jsonl]");
  process.exit(2);
}

function parseArgs(argv) {
  const out = { ledger: "/workspace/ledger/ledger.jsonl" };
  for (let i = 2; i < argv.length; i++) {
    if (argv[i] === "--ledger") {
      out.ledger = argv[++i] ?? usage();
    } else if (argv[i].startsWith("-")) {
      usage();
    }
  }
  return out;
}

function main() {
  const args = parseArgs(process.argv);

  if (!fs.existsSync(args.ledger)) {
    console.error(`[verify-ledger] File not found: ${args.ledger}`);
    process.exit(2);
  }

  const raw = fs.readFileSync(args.ledger, "utf8").trim();
  if (!raw) {
    console.log("[verify-ledger] Ledger is empty (GENESIS state). Nothing to verify.");
    process.exit(0);
  }

  const lines = raw.split("\n").filter(Boolean);
  console.log(`[verify-ledger] Verifying ${lines.length} record(s) in: ${args.ledger}`);

  let expectedPrevHash = "GENESIS";
  let failures = 0;

  for (let i = 0; i < lines.length; i++) {
    let record;
    try {
      record = JSON.parse(lines[i]);
    } catch (e) {
      console.error(`  [FAIL] Line ${i + 1}: JSON parse error — ${e.message}`);
      failures++;
      continue;
    }

    const { record_hash, ...rest } = record;

    /* 1. Verify record_hash = sha256(JSON.stringify(record_without_hash)) */
    const computed = sha256(JSON.stringify(rest));
    if (computed !== record_hash) {
      console.error(
        `  [FAIL] Record ${i + 1} (${record.type || "?"}): hash mismatch\n` +
        `         stored:   ${record_hash}\n` +
        `         computed: ${computed}`
      );
      failures++;
    }

    /* 2. Verify previous_hash chain */
    if (rest.previous_hash !== expectedPrevHash) {
      console.error(
        `  [FAIL] Record ${i + 1} (${record.type || "?"}): chain break\n` +
        `         expected previous_hash: ${expectedPrevHash}\n` +
        `         got:                   ${rest.previous_hash}`
      );
      failures++;
    }

    expectedPrevHash = record_hash;
    console.log(`  [OK]   Record ${i + 1}: type=${record.type || "?"} hash=${record_hash.slice(0, 16)}…`);
  }

  if (failures === 0) {
    console.log(`\n[verify-ledger] PASS — ${lines.length} record(s) verified. Ledger root: ${expectedPrevHash}`);
    process.exit(0);
  } else {
    console.error(`\n[verify-ledger] FAIL — ${failures} error(s) in ${lines.length} record(s).`);
    process.exit(1);
  }
}

main();
