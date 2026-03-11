// Tests for lib/crypto.js — Node built-in test runner
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { sha256, stableJson } from "./crypto.js";

describe("sha256", () => {
  it("produces a 64-char hex digest", () => {
    const hash = sha256("hello");
    assert.equal(hash.length, 64);
    assert.match(hash, /^[0-9a-f]{64}$/);
  });

  it("is deterministic", () => {
    assert.equal(sha256("test"), sha256("test"));
  });

  it("produces different hashes for different inputs", () => {
    assert.notEqual(sha256("a"), sha256("b"));
  });
});

describe("stableJson", () => {
  it("sorts object keys deterministically", () => {
    const a = stableJson({ z: 1, a: 2 });
    const b = stableJson({ a: 2, z: 1 });
    assert.equal(a, b);
    assert.equal(a, '{"a":2,"z":1}');
  });

  it("handles nested objects", () => {
    const result = stableJson({ b: { d: 1, c: 2 }, a: 3 });
    assert.equal(result, '{"a":3,"b":{"c":2,"d":1}}');
  });

  it("handles arrays preserving order", () => {
    assert.equal(stableJson([3, 1, 2]), "[3,1,2]");
  });

  it("handles primitives", () => {
    assert.equal(stableJson("hello"), '"hello"');
    assert.equal(stableJson(42), "42");
    assert.equal(stableJson(null), "null");
    assert.equal(stableJson(true), "true");
  });
});
