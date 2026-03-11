// Tests for lib/logger.js — Node built-in test runner
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { log } from "./logger.js";

describe("log", () => {
  it("exposes debug, info, warn, error methods", () => {
    assert.equal(typeof log.debug, "function");
    assert.equal(typeof log.info, "function");
    assert.equal(typeof log.warn, "function");
    assert.equal(typeof log.error, "function");
  });

  it("does not throw when called", () => {
    assert.doesNotThrow(() => log.info("test message", { key: "value" }));
    assert.doesNotThrow(() => log.error("test error"));
  });
});
