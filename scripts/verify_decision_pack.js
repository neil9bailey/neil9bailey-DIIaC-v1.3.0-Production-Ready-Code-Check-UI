#!/usr/bin/env node
"use strict";

const crypto = require("crypto");
const fs = require("fs");
const path = require("path");

function sha256Text(text) {
  return crypto.createHash("sha256").update(Buffer.from(text, "utf8")).digest("hex");
}

function canonicalJson(value) {
  if (value === null || typeof value !== "object") return JSON.stringify(value);
  if (Array.isArray(value)) return `[${value.map((item) => canonicalJson(item)).join(",")}]`;
  const keys = Object.keys(value).sort();
  return `{${keys.map((key) => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(",")}}`;
}

function escapeNonAscii(text) {
  return text.replace(/[\u007f-\uffff]/g, (char) => `\\u${char.charCodeAt(0).toString(16).padStart(4, "0")}`);
}

function canonicalJsonAscii(value) {
  return escapeNonAscii(canonicalJson(value));
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function readText(filePath) {
  return fs.readFileSync(filePath, "utf8");
}

function parseJsonAst(text) {
  let index = 0;

  function fail(message) {
    throw new Error(`json_parse_error:${message}@${index}`);
  }

  function skipWhitespace() {
    while (index < text.length && /\s/.test(text[index])) index += 1;
  }

  function parseStringToken() {
    if (text[index] !== "\"") fail("expected_quote");
    const start = index;
    index += 1;
    let escaping = false;
    while (index < text.length) {
      const ch = text[index];
      if (escaping) {
        escaping = false;
        index += 1;
        continue;
      }
      if (ch === "\\") {
        escaping = true;
        index += 1;
        continue;
      }
      if (ch === "\"") {
        index += 1;
        const raw = text.slice(start, index);
        return { raw, value: JSON.parse(raw) };
      }
      index += 1;
    }
    fail("unterminated_string");
    return null;
  }

  function parseNumberNode() {
    const match = text.slice(index).match(/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/);
    if (!match) fail("invalid_number");
    const raw = match[0];
    index += raw.length;
    return { type: "number", raw };
  }

  function parseLiteralNode(literal, type, value) {
    if (!text.startsWith(literal, index)) fail(`expected_${literal}`);
    index += literal.length;
    return { type, value };
  }

  function parseArrayNode() {
    index += 1; // [
    const items = [];
    skipWhitespace();
    if (text[index] === "]") {
      index += 1;
      return { type: "array", items };
    }
    while (index < text.length) {
      items.push(parseValueNode());
      skipWhitespace();
      if (text[index] === ",") {
        index += 1;
        skipWhitespace();
        continue;
      }
      if (text[index] === "]") {
        index += 1;
        return { type: "array", items };
      }
      fail("expected_comma_or_array_end");
    }
    fail("unterminated_array");
    return null;
  }

  function parseObjectNode() {
    index += 1; // {
    const entries = [];
    skipWhitespace();
    if (text[index] === "}") {
      index += 1;
      return { type: "object", entries };
    }
    while (index < text.length) {
      if (text[index] !== "\"") fail("expected_object_key");
      const keyToken = parseStringToken();
      skipWhitespace();
      if (text[index] !== ":") fail("expected_colon");
      index += 1;
      skipWhitespace();
      const value = parseValueNode();
      entries.push({ key: keyToken.value, value });
      skipWhitespace();
      if (text[index] === ",") {
        index += 1;
        skipWhitespace();
        continue;
      }
      if (text[index] === "}") {
        index += 1;
        return { type: "object", entries };
      }
      fail("expected_comma_or_object_end");
    }
    fail("unterminated_object");
    return null;
  }

  function parseValueNode() {
    skipWhitespace();
    if (index >= text.length) fail("unexpected_end");
    const ch = text[index];
    if (ch === "\"") {
      const token = parseStringToken();
      return { type: "string", value: token.value };
    }
    if (ch === "{") return parseObjectNode();
    if (ch === "[") return parseArrayNode();
    if (ch === "t") return parseLiteralNode("true", "boolean", true);
    if (ch === "f") return parseLiteralNode("false", "boolean", false);
    if (ch === "n") return parseLiteralNode("null", "null", null);
    if (ch === "-" || (ch >= "0" && ch <= "9")) return parseNumberNode();
    fail("unexpected_token");
    return null;
  }

  skipWhitespace();
  const root = parseValueNode();
  skipWhitespace();
  if (index !== text.length) fail("trailing_content");
  return root;
}

function canonicalizeAst(node) {
  switch (node.type) {
    case "string":
      return escapeNonAscii(JSON.stringify(node.value));
    case "number":
      return node.raw;
    case "boolean":
      return node.value ? "true" : "false";
    case "null":
      return "null";
    case "array":
      return `[${node.items.map((item) => canonicalizeAst(item)).join(",")}]`;
    case "object": {
      const sorted = node.entries
        .slice()
        .sort((a, b) => (a.key < b.key ? -1 : a.key > b.key ? 1 : 0));
      return `{${sorted
        .map((entry) => `${escapeNonAscii(JSON.stringify(entry.key))}:${canonicalizeAst(entry.value)}`)
        .join(",")}}`;
    }
    default:
      throw new Error(`unsupported_node_type:${node.type}`);
  }
}

function computeArtifactHash(filePath) {
  if (filePath.toLowerCase().endsWith(".json")) {
    const parsed = parseJsonAst(readText(filePath));
    return sha256Text(canonicalizeAst(parsed));
  }
  return sha256Text(readText(filePath));
}

function buildPublicKeyFromRawEd25519(rawPublicKey) {
  const spkiPrefix = Buffer.from("302a300506032b6570032100", "hex");
  const spki = Buffer.concat([spkiPrefix, rawPublicKey]);
  return crypto.createPublicKey({ key: spki, format: "der", type: "spki" });
}

function parseIsoDate(value) {
  if (typeof value !== "string" || !value.trim()) return null;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  return parsed;
}

function findTrustBundleKeyEntry(trustBundle, signingKeyId) {
  if (!trustBundle || typeof trustBundle !== "object") return null;
  const activeKey = trustBundle.active_key;
  if (activeKey && activeKey.key_id === signingKeyId && typeof activeKey.public_key_b64 === "string") {
    return { ...activeKey, source: "trust_bundle.active_key" };
  }
  const historical = Array.isArray(trustBundle.historical_keys) ? trustBundle.historical_keys : [];
  const historicalEntry = historical.find(
    (item) => item && item.key_id === signingKeyId && typeof item.public_key_b64 === "string",
  );
  return historicalEntry ? { ...historicalEntry, source: "trust_bundle.historical_keys" } : null;
}

function findRegistryKeyEntry(registry, signingKeyId) {
  if (!registry || !Array.isArray(registry.keys)) return null;
  const entry = registry.keys.find(
    (item) => item && item.key_id === signingKeyId && typeof item.public_key_b64 === "string",
  );
  return entry ? { ...entry, source: "registry.keys" } : null;
}

function resolveKeyMaterial(sigmeta, registry, trustBundle) {
  const signingKeyId = sigmeta.signing_key_id;
  const trustEntry = findTrustBundleKeyEntry(trustBundle, signingKeyId);
  const registryEntry = findRegistryKeyEntry(registry, signingKeyId);
  const sigmetaPublic = (typeof sigmeta.public_key_b64 === "string" && sigmeta.public_key_b64.trim())
    ? sigmeta.public_key_b64.trim()
    : null;
  const candidatePublicKeyB64 = sigmetaPublic
    || (trustEntry && typeof trustEntry.public_key_b64 === "string" ? trustEntry.public_key_b64.trim() : null)
    || (registryEntry && typeof registryEntry.public_key_b64 === "string" ? registryEntry.public_key_b64.trim() : null);
  return {
    public_key_b64: candidatePublicKeyB64,
    key_entry: trustEntry || registryEntry || null,
    key_entry_source: trustEntry ? trustEntry.source : (registryEntry ? registryEntry.source : null),
    public_key_source: sigmetaPublic
      ? "sigmeta.public_key_b64"
      : trustEntry
        ? trustEntry.source
        : registryEntry
          ? registryEntry.source
          : null,
  };
}

function validateKeyValidityWindow(signaturePayload, keyEntry) {
  const signedAt = signaturePayload && typeof signaturePayload === "object" ? signaturePayload.signed_at : null;
  if (!signedAt || typeof signedAt !== "string") {
    return { ok: false, error: "missing_signed_at" };
  }
  const signedAtDate = parseIsoDate(signedAt);
  if (!signedAtDate) {
    return { ok: false, error: "invalid_signed_at" };
  }
  if (!keyEntry || typeof keyEntry !== "object") {
    return { ok: false, error: "missing_key_entry" };
  }
  const validFromRaw = typeof keyEntry.valid_from === "string" ? keyEntry.valid_from.trim() : "";
  const validToRaw = typeof keyEntry.valid_to === "string" ? keyEntry.valid_to.trim() : "";
  if (!validFromRaw) {
    return { ok: false, error: "missing_key_valid_from" };
  }
  const validFrom = parseIsoDate(validFromRaw);
  if (!validFrom) {
    return { ok: false, error: "invalid_key_valid_from" };
  }
  if (validToRaw && !parseIsoDate(validToRaw)) {
    return { ok: false, error: "invalid_key_valid_to" };
  }
  const validTo = validToRaw ? parseIsoDate(validToRaw) : null;
  if (validTo && validTo < validFrom) {
    return { ok: false, error: "invalid_key_validity_window" };
  }
  if (validFrom && signedAtDate < validFrom) {
    return { ok: false, error: "key_not_yet_valid" };
  }
  if (validTo && signedAtDate > validTo) {
    return { ok: false, error: "key_expired" };
  }
  return { ok: true, error: null };
}

function usage() {
  console.error("Usage: node scripts/verify_decision_pack.js <pack_dir> [public_keys_json]");
}

function main() {
  const packDir = process.argv[2];
  const registryPath = process.argv[3] || null;
  if (!packDir) {
    usage();
    process.exit(1);
  }
  if (!fs.existsSync(packDir) || !fs.statSync(packDir).isDirectory()) {
    console.error(`Pack directory not found: ${packDir}`);
    process.exit(1);
  }

  const manifestPath = path.join(packDir, "governance_manifest.json");
  const sigmetaPath = path.join(packDir, "signed_export.sigmeta.json");
  const sigPath = path.join(packDir, "signed_export.sig");
  const trustBundlePath = path.join(packDir, "trust_bundle.json");
  const required = [manifestPath, sigmetaPath, sigPath];
  const missing = required.filter((item) => !fs.existsSync(item));
  if (missing.length > 0) {
    console.error(JSON.stringify({ overall: "FAIL", error: "missing_required_files", missing }, null, 2));
    process.exit(2);
  }

  const manifest = readJson(manifestPath);
  const sigmeta = readJson(sigmetaPath);
  const trustBundle = fs.existsSync(trustBundlePath) ? readJson(trustBundlePath) : null;
  const signatureB64 = (sigmeta.signature || "").trim() || readText(sigPath).trim();
  const signaturePayload = sigmeta.signature_payload;
  const leaves = (manifest.merkle && Array.isArray(manifest.merkle.leaves)) ? manifest.merkle.leaves : [];

  const artifactChecks = [];
  let artifactHashesOk = true;
  let leafHashesOk = true;
  for (const leaf of leaves) {
    const name = leaf.name;
    const expectedHash = leaf.hash;
    const expectedLeafHash = leaf.leaf_hash;
    const artifactPath = path.join(packDir, name);
    if (!fs.existsSync(artifactPath)) {
      artifactChecks.push({ name, exists: false, hash_ok: false, leaf_hash_ok: false });
      artifactHashesOk = false;
      leafHashesOk = false;
      continue;
    }
    let actualHash = null;
    let hashError = null;
    try {
      actualHash = computeArtifactHash(artifactPath);
    } catch (err) {
      hashError = `hash_compute_error:${err.message}`;
    }
    if (hashError) {
      artifactChecks.push({ name, exists: true, hash_ok: false, leaf_hash_ok: false, error: hashError });
      artifactHashesOk = false;
      leafHashesOk = false;
      continue;
    }
    const actualLeafHash = sha256Text(`${name}:${actualHash}`);
    const hashOk = actualHash === expectedHash;
    const leafHashOk = actualLeafHash === expectedLeafHash;
    artifactChecks.push({
      name,
      exists: true,
      hash_ok: hashOk,
      leaf_hash_ok: leafHashOk,
      expected_hash: expectedHash,
      actual_hash: actualHash,
    });
    artifactHashesOk = artifactHashesOk && hashOk;
    leafHashesOk = leafHashesOk && leafHashOk;
  }

  const sortedLeafHashes = leaves.map((leaf) => leaf.leaf_hash);
  function buildMerkleRoot(nodes) {
    if (!nodes.length) return sha256Text("");
    let current = nodes.slice();
    while (current.length > 1) {
      if (current.length % 2 === 1) current.push(current[current.length - 1]);
      const next = [];
      for (let i = 0; i < current.length; i += 2) {
        next.push(sha256Text(current[i] + current[i + 1]));
      }
      current = next;
    }
    return current[0];
  }

  const computedMerkleRoot = buildMerkleRoot(sortedLeafHashes);
  const merkleRootOk = computedMerkleRoot === (manifest.merkle && manifest.merkle.merkle_root);

  const sortedArtifactNames = leaves.map((leaf) => leaf.name).sort();
  const concatenatedHashes = sortedArtifactNames
    .map((name) => {
      const check = artifactChecks.find((item) => item.name === name);
      return check && check.actual_hash ? check.actual_hash : "";
    })
    .join("");
  const computedPackHash = sha256Text(concatenatedHashes);
  const packHashOk = computedPackHash === manifest.pack_hash;

  // Canonical manifest hash verification (excluding manifest_hash field).
  const manifestWithoutHash = JSON.parse(JSON.stringify(manifest));
  delete manifestWithoutHash.manifest_hash;
  const computedManifestHash = sha256Text(canonicalJsonAscii(manifestWithoutHash));
  const manifestHashMatches = computedManifestHash === manifest.manifest_hash;

  let registry = null;
  if (registryPath && fs.existsSync(registryPath)) {
    registry = readJson(registryPath);
  }
  const keyMaterial = resolveKeyMaterial(sigmeta, registry, trustBundle);
  const publicKeyB64 = keyMaterial.public_key_b64;
  let signatureOk = false;
  let signatureError = null;
  if (!publicKeyB64) {
    signatureError = "public_key_not_available";
  } else if (!signaturePayload || typeof signaturePayload !== "object") {
    signatureError = "signature_payload_missing";
  } else if (!signatureB64) {
    signatureError = "signature_missing";
  } else {
    const keyValidity = validateKeyValidityWindow(signaturePayload, keyMaterial.key_entry);
    if (!keyValidity.ok) {
      signatureError = keyValidity.error;
    }
  }
  if (!signatureError && publicKeyB64 && signaturePayload && typeof signaturePayload === "object" && signatureB64) {
    try {
      const publicKeyRaw = Buffer.from(publicKeyB64, "base64");
      const publicKey = buildPublicKeyFromRawEd25519(publicKeyRaw);
      const payloadBytes = Buffer.from(canonicalJsonAscii(signaturePayload), "utf8");
      const signatureBytes = Buffer.from(signatureB64, "base64");
      signatureOk = crypto.verify(null, payloadBytes, publicKey, signatureBytes);
      if (!signatureOk) signatureError = "invalid_signature";
    } catch (err) {
      signatureError = `signature_verify_exception:${err.message}`;
    }
  }

  const alignment = {
    execution_id: sigmeta.execution_id === manifest.execution_id,
    pack_hash: sigmeta.pack_hash === manifest.pack_hash,
    merkle_root: sigmeta.merkle_root === (manifest.merkle && manifest.merkle.merkle_root),
    manifest_hash: sigmeta.manifest_hash === manifest.manifest_hash,
  };

  const overall =
    artifactHashesOk &&
    leafHashesOk &&
    merkleRootOk &&
    packHashOk &&
    manifestHashMatches &&
    signatureOk &&
    Object.values(alignment).every(Boolean);

  const result = {
    overall: overall ? "PASS" : "FAIL",
    checks: {
      artifact_hashes_ok: artifactHashesOk,
      leaf_hashes_ok: leafHashesOk,
      merkle_root_ok: merkleRootOk,
      pack_hash_ok: packHashOk,
      manifest_hash_ok: manifestHashMatches,
      signature_ok: signatureOk,
      alignment,
    },
    signature: {
      signing_key_id: sigmeta.signing_key_id,
      payload_schema_version: sigmeta.signature_payload_schema_version || null,
      error: signatureError,
      public_key_source: keyMaterial.public_key_source,
      key_entry_source: keyMaterial.key_entry_source,
      valid_from: keyMaterial.key_entry && keyMaterial.key_entry.valid_from ? keyMaterial.key_entry.valid_from : null,
      valid_to: keyMaterial.key_entry && keyMaterial.key_entry.valid_to ? keyMaterial.key_entry.valid_to : null,
    },
    trust_bundle: {
      present: Boolean(trustBundle),
      source: trustBundle ? "pack" : "registry_or_sigmeta",
    },
    artifacts: artifactChecks,
  };

  console.log(JSON.stringify(result, null, 2));
  process.exit(overall ? 0 : 2);
}

main();
