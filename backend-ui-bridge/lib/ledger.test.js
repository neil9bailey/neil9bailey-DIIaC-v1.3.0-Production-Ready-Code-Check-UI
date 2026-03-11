// Tests for lib/ledger.js — Node built-in test runner
import { describe, it, beforeEach, afterEach } from "node:test";
import assert from "node:assert/strict";
import fs from "fs";
import os from "os";
import path from "path";
import { createLedger } from "./ledger.js";

let tmpDir;
let ledgerPath;

beforeEach(() => {
  tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), "ledger-test-"));
  ledgerPath = path.join(tmpDir, "ledger.jsonl");
});

afterEach(() => {
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

describe("createLedger", () => {
  it("creates ledger file if it does not exist", () => {
    const ledger = createLedger(ledgerPath);
    ledger.ensureLedger();
    assert.equal(fs.existsSync(ledgerPath), true);
  });

  it("getLastHash returns GENESIS for empty ledger", () => {
    const ledger = createLedger(ledgerPath);
    assert.equal(ledger.getLastHash(), "GENESIS");
  });

  it("append writes a record and chains hashes", () => {
    const ledger = createLedger(ledgerPath);
    const record1 = ledger.append({ type: "TEST", data: "first" });
    assert.equal(record1.previous_hash, "GENESIS");
    assert.ok(record1.record_hash);

    const record2 = ledger.append({ type: "TEST", data: "second" });
    assert.equal(record2.previous_hash, record1.record_hash);
    assert.notEqual(record2.record_hash, record1.record_hash);
  });

  it("getLastHash returns hash of most recent record", () => {
    const ledger = createLedger(ledgerPath);
    const record = ledger.append({ type: "TEST" });
    assert.equal(ledger.getLastHash(), record.record_hash);
  });

  it("ledger file contains one JSON line per record", () => {
    const ledger = createLedger(ledgerPath);
    ledger.append({ type: "A" });
    ledger.append({ type: "B" });
    ledger.append({ type: "C" });
    const lines = fs.readFileSync(ledgerPath, "utf8").trim().split("\n");
    assert.equal(lines.length, 3);
    assert.equal(JSON.parse(lines[0]).type, "A");
    assert.equal(JSON.parse(lines[2]).type, "C");
  });

  it("no temp files remain after append", () => {
    const ledger = createLedger(ledgerPath);
    ledger.append({ type: "CLEAN" });
    const files = fs.readdirSync(tmpDir);
    assert.equal(files.length, 1); // only ledger.jsonl
    assert.equal(files[0], "ledger.jsonl");
  });
});
