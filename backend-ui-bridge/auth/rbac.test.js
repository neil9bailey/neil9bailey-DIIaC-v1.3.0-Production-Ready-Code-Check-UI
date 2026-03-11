// Tests for auth/rbac.js — Node built-in test runner (node --test)
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { requireRole } from "./rbac.js";

function fakeReq(role, entraAuth) {
  return {
    headers: role ? { "x-role": role } : {},
    entraAuth: entraAuth || undefined,
  };
}

function fakeRes() {
  let _status = 200;
  let _body = null;
  return {
    status(code) { _status = code; return this; },
    json(data) { _body = data; return this; },
    get _status() { return _status; },
    get _body() { return _body; },
  };
}

describe("requireRole middleware", () => {
  it("returns 403 when no role header is present", () => {
    const mw = requireRole(["admin"]);
    const res = fakeRes();
    let nextCalled = false;
    mw(fakeReq(null), res, () => { nextCalled = true; });
    assert.equal(res._status, 403);
    assert.equal(res._body.reason, "No role provided");
    assert.equal(nextCalled, false);
  });

  it("returns 403 when role is not in allowed list", () => {
    const mw = requireRole(["admin"]);
    const res = fakeRes();
    let nextCalled = false;
    mw(fakeReq("customer"), res, () => { nextCalled = true; });
    assert.equal(res._status, 403);
    assert.equal(res._body.reason, "Insufficient role permissions");
    assert.equal(nextCalled, false);
  });

  it("calls next() for allowed role", () => {
    const mw = requireRole(["admin", "standard"]);
    const res = fakeRes();
    let nextCalled = false;
    const req = fakeReq("admin");
    mw(req, res, () => { nextCalled = true; });
    assert.equal(nextCalled, true);
  });

  it("populates req.actor from entraAuth when present", () => {
    const mw = requireRole(["admin"]);
    const req = fakeReq("admin", {
      subject: "user-123",
      name: "Test User",
      email: "test@example.com",
      role: "admin",
      subroles: ["cto"],
      tenant_id: "tenant-abc",
      token_type: "delegated",
      principal_id: null,
    });
    mw(req, fakeRes(), () => {});
    assert.equal(req.actor.subject, "user-123");
    assert.equal(req.actor.name, "Test User");
    assert.deepEqual(req.actor.subroles, ["cto"]);
  });

  it("populates req.actor as anonymous for legacy header auth", () => {
    const mw = requireRole(["standard"]);
    const req = fakeReq("standard");
    mw(req, fakeRes(), () => {});
    assert.equal(req.actor.subject, "anonymous");
    assert.equal(req.actor.token_type, "legacy_header");
  });
});
