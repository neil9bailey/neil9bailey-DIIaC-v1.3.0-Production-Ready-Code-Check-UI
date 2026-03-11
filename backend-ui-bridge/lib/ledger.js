// backend-ui-bridge/lib/ledger.js
// Append-only hash-chained ledger for governance audit trail.

import fs from "fs";
import { sha256, stableJson } from "./crypto.js";

export function createLedger(ledgerPath) {
  function ensureLedger() {
    if (!fs.existsSync(ledgerPath)) fs.writeFileSync(ledgerPath, "");
  }

  function getLastHash() {
    ensureLedger();
    const raw = fs.readFileSync(ledgerPath, "utf8").trim();
    if (!raw) return "GENESIS";
    const lines = raw.split("\n").filter(Boolean);
    return JSON.parse(lines[lines.length - 1]).record_hash;
  }

  function append(record) {
    const full = { ...record, previous_hash: getLastHash() };
    const record_hash = sha256(stableJson(full));
    const sealed = { ...full, record_hash };

    // Atomic append: write to temp file, then append to ledger.
    const tmpPath = `${ledgerPath}.${process.pid}.tmp`;
    fs.writeFileSync(tmpPath, JSON.stringify(sealed) + "\n");
    fs.appendFileSync(ledgerPath, fs.readFileSync(tmpPath));
    fs.unlinkSync(tmpPath);

    return sealed;
  }

  return { ensureLedger, getLastHash, append };
}
