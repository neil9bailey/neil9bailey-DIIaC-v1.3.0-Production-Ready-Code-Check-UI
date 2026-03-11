// Tests for auth/entra.js — Node built-in test runner (node --test)
//
// These tests cover the exported functions in isolation.
// RS256/HS256 validation requires real JWTs so we test the middleware
// behaviour: pass-through when AUTH_MODE is unset, and the helper exports.

import { describe, it } from "node:test";
import assert from "node:assert/strict";

// AUTH_MODE is read at import time, so we test the default (unset) behaviour.
const { entraAuth, isEntraEnabled, getAuthMode } = await import("./entra.js");

describe("entra.js exports (AUTH_MODE unset)", () => {
  it("isEntraEnabled() returns false when AUTH_MODE is unset", () => {
    assert.equal(isEntraEnabled(), false);
  });

  it("getAuthMode() returns 'legacy_header' when AUTH_MODE is unset", () => {
    assert.equal(getAuthMode(), "legacy_header");
  });

  it("entraAuth() returns a no-op middleware that calls next()", () => {
    const mw = entraAuth();
    assert.equal(typeof mw, "function");

    let nextCalled = false;
    mw({}, {}, () => { nextCalled = true; });
    assert.equal(nextCalled, true);
  });

  it("no-op middleware does not set any auth properties on request", () => {
    const mw = entraAuth();
    const req = { headers: {} };
    mw(req, {}, () => {});
    assert.equal(req.entraAuth, undefined);
  });
});
