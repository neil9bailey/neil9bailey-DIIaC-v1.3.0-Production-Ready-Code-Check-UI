#!/usr/bin/env node
// tools/verify-replay-batch.js — CLI release-gate tool for deterministic replay verification
//
// Usage:
//   node tools/verify-replay-batch.js --base http://localhost:3001 <id1> <id2> ...
//   node tools/verify-replay-batch.js --base http://localhost:3001 --file tools/replay-gate.executions.txt
//
// Exits 0 when all executions verify; exits 1 on any failure.

import fs from "fs";

function usage() {
  console.error(
    "Usage: node tools/verify-replay-batch.js --base <url> (--file <ids.txt> | <id1> <id2> ...)",
  );
  process.exit(2);
}

function parseArgs(argv) {
  const out = { base: "http://localhost:3001", file: "", ids: [] };
  for (let i = 2; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--base") {
      out.base = argv[++i] ?? out.base;
    } else if (a === "--file") {
      out.file = argv[++i] ?? "";
    } else if (a.startsWith("-")) {
      usage();
    } else {
      out.ids.push(a);
    }
  }
  return out;
}

async function main() {
  const args = parseArgs(process.argv);
  let ids = args.ids;

  if (args.file) {
    if (!fs.existsSync(args.file)) {
      console.error("Execution list file not found:", args.file);
      process.exit(2);
    }
    const raw = fs.readFileSync(args.file, "utf8");
    ids = raw
      .split("\n")
      .map((x) => x.trim())
      .filter(Boolean);
  }

  if (!ids.length) usage();

  console.log(`Running batch replay gate for ${ids.length} execution(s) against ${args.base}`);

  const res = await fetch(`${args.base}/verify/replay/batch`, {
    method: "POST",
    headers: { "content-type": "application/json", "x-role": "admin" },
    body: JSON.stringify({ execution_ids: ids }),
  });

  const data = await res.json().catch(() => ({}));
  const status = String(data.status ?? "").toUpperCase();
  const failed = Number(data.failed ?? 0);

  console.log(
    JSON.stringify(
      {
        status,
        total: data.total,
        passed: data.passed,
        failed,
        results: data.results,
      },
      null,
      2,
    ),
  );

  if (!res.ok || status !== "VERIFIED" || failed > 0) {
    console.error(`\nREPLAY GATE FAILED — ${failed} execution(s) did not verify. Deployment blocked.`);
    process.exit(1);
  }

  console.log("\nREPLAY GATE PASSED — all executions verified.");
}

main().catch((err) => {
  console.error("Replay batch gate error:", err);
  process.exit(1);
});
