// backend-ui-bridge/lib/crypto.js
// Deterministic hashing and stable JSON serialisation for governance integrity.

import crypto from "crypto";

export function sha256(input) {
  return crypto.createHash("sha256").update(input).digest("hex");
}

export function stableJson(value) {
  if (Array.isArray(value)) {
    return `[${value.map((v) => stableJson(v)).join(",")}]`;
  }
  if (value && typeof value === "object") {
    const keys = Object.keys(value).sort();
    return `{${keys.map((k) => `${JSON.stringify(k)}:${stableJson(value[k])}`).join(",")}}`;
  }
  return JSON.stringify(value);
}
