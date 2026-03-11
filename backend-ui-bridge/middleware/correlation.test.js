// Tests for middleware/correlation.js — Node built-in test runner
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { correlationId } from "./correlation.js";

describe("correlationId middleware", () => {
  it("generates a UUID when no header is present", () => {
    const mw = correlationId();
    const req = { headers: {} };
    const headers = {};
    const res = { setHeader(k, v) { headers[k] = v; } };
    let nextCalled = false;
    mw(req, res, () => { nextCalled = true; });

    assert.equal(nextCalled, true);
    assert.ok(req.correlationId);
    assert.match(req.correlationId, /^[0-9a-f-]{36}$/);
    assert.equal(headers["X-Correlation-ID"], req.correlationId);
  });

  it("uses existing X-Correlation-ID header if present", () => {
    const mw = correlationId();
    const req = { headers: { "x-correlation-id": "custom-id-123" } };
    const headers = {};
    const res = { setHeader(k, v) { headers[k] = v; } };
    mw(req, res, () => {});

    assert.equal(req.correlationId, "custom-id-123");
    assert.equal(headers["X-Correlation-ID"], "custom-id-123");
  });
});
