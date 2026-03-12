// backend-ui-bridge/auth/entra.js
// Entra ID (Azure AD) JWT validation middleware for DIIaC bridge
//
// Supports two modes:
//   AUTH_MODE=entra_jwt_rs256  — Production: validates RS256 JWTs via Entra OIDC/JWKS
//   AUTH_MODE=entra_jwt_hs256  — Integration test only: validates HS256 JWTs with shared secret
//
// When AUTH_MODE is unset or unsupported, production fails closed while
// development mode can opt into legacy x-role header auth.

import { createRemoteJWKSet, jwtVerify, errors as joseErrors } from "jose";
import crypto from "crypto";

// ────────────────────────────────────────────────────────────────
// Configuration (read once at startup, all from env)
// ────────────────────────────────────────────────────────────────

const AUTH_MODE = (process.env.AUTH_MODE || "").toLowerCase();

const ENTRA_EXPECTED_TENANT_ID = process.env.ENTRA_EXPECTED_TENANT_ID || "";
const ENTRA_EXPECTED_AUDIENCE = process.env.ENTRA_EXPECTED_AUDIENCE || "";

// Entra v1.0 tokens use "api://<client-id>" as audience, v2.0 tokens use the
// bare client-id.  Accept both so config works regardless of token version.
const ENTRA_ACCEPTED_AUDIENCES = (() => {
  if (!ENTRA_EXPECTED_AUDIENCE) return undefined;
  const auds = new Set([ENTRA_EXPECTED_AUDIENCE]);
  if (ENTRA_EXPECTED_AUDIENCE.startsWith("api://")) {
    auds.add(ENTRA_EXPECTED_AUDIENCE.slice(6)); // bare GUID
  } else {
    auds.add(`api://${ENTRA_EXPECTED_AUDIENCE}`); // api:// form
  }
  return [...auds];
})();
const ENTRA_EXPECTED_ISSUERS = (process.env.ENTRA_EXPECTED_ISSUERS || "")
  .split(",")
  .map((s) => s.trim())
  .filter(Boolean);
const ENTRA_ROLE_CLAIM = process.env.ENTRA_ROLE_CLAIM || "roles";

// Group-to-role mapping — supports two formats:
//   Legacy flat:   {"<oid>": "admin"}
//   Structured:    {"<oid>": {"role":"admin"}, "<oid>": {"role":"standard"}, "<oid>": {"subrole":"cto"}}
const ENTRA_GROUP_TO_ROLE_JSON = parseJsonEnv("ENTRA_GROUP_TO_ROLE_JSON");

// Principal-to-role mapping for client_credentials (app-only) tokens
const ENTRA_PRINCIPAL_TO_ROLE_JSON = parseJsonEnv("ENTRA_PRINCIPAL_TO_ROLE_JSON");

// HS256 shared secret (integration-test mode only)
const ENTRA_JWT_HS256_SECRET = process.env.ENTRA_JWT_HS256_SECRET || "";

// OIDC discovery URL (defaults to standard Entra v2.0 endpoint)
const ENTRA_OIDC_DISCOVERY_URL =
  process.env.ENTRA_OIDC_DISCOVERY_URL ||
  (ENTRA_EXPECTED_TENANT_ID
    ? `https://login.microsoftonline.com/${ENTRA_EXPECTED_TENANT_ID}/v2.0/.well-known/openid-configuration`
    : "");

// ────────────────────────────────────────────────────────────────
// JWKS key set (lazy-initialised on first RS256 request)
// ────────────────────────────────────────────────────────────────

// Construct JWKS URI directly from tenant ID (preferred) or from discovery URL
const ENTRA_JWKS_URI =
  process.env.ENTRA_JWKS_URI ||
  (ENTRA_EXPECTED_TENANT_ID
    ? `https://login.microsoftonline.com/${ENTRA_EXPECTED_TENANT_ID}/discovery/v2.0/keys`
    : "");

let _jwks = null;

function getJWKS() {
  if (!_jwks) {
    if (!ENTRA_JWKS_URI) {
      throw new Error(
        "ENTRA_EXPECTED_TENANT_ID (or ENTRA_JWKS_URI) must be set for RS256 mode"
      );
    }
    // jose's createRemoteJWKSet handles caching, rotation, and rate limiting
    _jwks = createRemoteJWKSet(new URL(ENTRA_JWKS_URI));
  }
  return _jwks;
}

// ────────────────────────────────────────────────────────────────
// Helpers
// ────────────────────────────────────────────────────────────────

function parseJsonEnv(name) {
  const raw = process.env[name];
  if (!raw) return {};
  try {
    return JSON.parse(raw);
  } catch (e) {
    console.error(`[entra] WARNING: failed to parse ${name}: ${e.message}`);
    return {};
  }
}

function inferTokenType(claims) {
  const idtyp = typeof claims.idtyp === "string" ? claims.idtyp.toLowerCase().trim() : "";
  if (idtyp === "app") return "app_only";

  // Delegated tokens commonly carry scopes and user identifiers.
  if (typeof claims.scp === "string" && claims.scp.trim()) return "delegated";
  if (typeof claims.oid === "string" && claims.oid.trim()) return "delegated";
  if (typeof claims.upn === "string" && claims.upn.trim()) return "delegated";
  if (typeof claims.preferred_username === "string" && claims.preferred_username.trim()) return "delegated";
  if (typeof claims.email === "string" && claims.email.trim()) return "delegated";

  if (claims.appid || claims.azp) return "app_only";
  return "delegated";
}

/**
 * Normalise a role string to its canonical DIIaC name.
 * Handles common Entra group-name variations like "Admins", "Standard Users".
 */
function normaliseRoleName(raw) {
  if (!raw || typeof raw !== "string") return raw;
  const lower = raw.toLowerCase().trim();
  if (lower === "admin" || lower === "admins") return "admin";
  if (lower === "standard" || lower === "standard users" || lower === "standarduser" || lower === "standard_user") return "standard";
  if (lower === "customer" || lower === "customers") return "customer";
  if (lower === "viewer" || lower === "viewers") return "viewer";
  return raw; // pass through unknown values
}

/**
 * Normalise a group mapping entry.
 * Supports legacy flat strings ("admin") and structured objects ({"role":"admin","subrole":"cto"}).
 */
function normaliseGroupMapping(entry) {
  if (typeof entry === "string") return { role: normaliseRoleName(entry) };
  if (entry && typeof entry === "object") {
    return { ...entry, role: entry.role ? normaliseRoleName(entry.role) : undefined };
  }
  return {};
}

/**
 * Resolve DIIaC role from JWT claims.
 *
 * Priority:
 *   1. Explicit `roles` claim — checked as both app role names AND group OIDs
 *      (Entra emits group OIDs into `roles` when optionalClaims uses "emit_as_roles")
 *   2. `groups` claim mapped via ENTRA_GROUP_TO_ROLE_JSON
 *   3. `appid` / `azp` mapped via ENTRA_PRINCIPAL_TO_ROLE_JSON (client_credentials)
 *
 * Returns { role, subroles[] } or null if no role can be resolved.
 * The `role` is the highest-privilege match: admin > standard > customer > viewer.
 */
function resolveRole(claims) {
  const ROLE_PRIORITY = { admin: 4, standard: 3, customer: 2, viewer: 1 };

  let resolvedRole = null;
  let resolvedPriority = 0;
  const subroles = [];

  // 1. Roles claim — handles both app role names AND group OIDs
  //    (when "emit_as_roles" is set, Entra puts group OIDs into the roles array)
  const roleClaim = claims[ENTRA_ROLE_CLAIM];
  if (Array.isArray(roleClaim)) {
    for (const r of roleClaim) {
      // First: check if this is a group OID in the mapping
      const groupMapping = ENTRA_GROUP_TO_ROLE_JSON[r];
      if (groupMapping) {
        const mapping = normaliseGroupMapping(groupMapping);
        if (mapping.role && (ROLE_PRIORITY[mapping.role] || 0) > resolvedPriority) {
          resolvedRole = mapping.role;
          resolvedPriority = ROLE_PRIORITY[mapping.role];
        }
        if (mapping.subrole) {
          subroles.push(mapping.subrole);
        }
        continue;
      }

      // Second: check if this is a named app role (e.g. "admin", "StandardUser")
      const normalised = r.toLowerCase();
      const mapped = normalised === "standarduser" ? "standard"
        : normalised === "admin" ? "admin"
        : normalised === "standard" ? "standard"
        : normalised === "customer" ? "customer"
        : normalised === "viewer" ? "viewer"
        : null;
      if (mapped && (ROLE_PRIORITY[mapped] || 0) > resolvedPriority) {
        resolvedRole = mapped;
        resolvedPriority = ROLE_PRIORITY[mapped];
      }
    }
  }

  // 2. Group membership mapping (standard groups claim without emit_as_roles)
  const groups = claims.groups;
  if (Array.isArray(groups)) {
    for (const gid of groups) {
      const raw = ENTRA_GROUP_TO_ROLE_JSON[gid];
      if (!raw) continue;
      const mapping = normaliseGroupMapping(raw);

      if (mapping.role && (ROLE_PRIORITY[mapping.role] || 0) > resolvedPriority) {
        resolvedRole = mapping.role;
        resolvedPriority = ROLE_PRIORITY[mapping.role];
      }
      if (mapping.subrole) {
        subroles.push(mapping.subrole);
      }
    }
  }

  // 3. Principal (appid/azp) mapping for client_credentials tokens
  if (!resolvedRole) {
    const principalId = claims.appid || claims.azp;
    if (principalId && ENTRA_PRINCIPAL_TO_ROLE_JSON[principalId]) {
      const principalRole = ENTRA_PRINCIPAL_TO_ROLE_JSON[principalId];
      resolvedRole = typeof principalRole === "string" ? principalRole : principalRole.role || null;
    }
  }

  if (!resolvedRole) return null;
  return { role: resolvedRole, subroles };
}

// ────────────────────────────────────────────────────────────────
// RS256 validation (production)
// ────────────────────────────────────────────────────────────────

async function validateRS256(token) {
  const { payload } = await jwtVerify(token, getJWKS(), {
    audience: ENTRA_ACCEPTED_AUDIENCES,
    issuer: ENTRA_EXPECTED_ISSUERS.length ? ENTRA_EXPECTED_ISSUERS : undefined,
  });

  // Validate tenant ID
  if (ENTRA_EXPECTED_TENANT_ID && payload.tid !== ENTRA_EXPECTED_TENANT_ID) {
    throw new Error(
      `Tenant ID mismatch: expected ${ENTRA_EXPECTED_TENANT_ID}, got ${payload.tid}`
    );
  }

  return payload;
}

// ────────────────────────────────────────────────────────────────
// HS256 validation (integration-test fallback)
// ────────────────────────────────────────────────────────────────

async function validateHS256(token) {
  if (!ENTRA_JWT_HS256_SECRET) {
    throw new Error("ENTRA_JWT_HS256_SECRET is required for hs256 mode");
  }

  const secret = new TextEncoder().encode(ENTRA_JWT_HS256_SECRET);
  const { payload } = await jwtVerify(token, secret, {
    audience: ENTRA_ACCEPTED_AUDIENCES,
    issuer: ENTRA_EXPECTED_ISSUERS.length ? ENTRA_EXPECTED_ISSUERS : undefined,
    algorithms: ["HS256"],
  });

  // Validate tenant ID if present
  if (ENTRA_EXPECTED_TENANT_ID && payload.tid && payload.tid !== ENTRA_EXPECTED_TENANT_ID) {
    throw new Error(
      `Tenant ID mismatch: expected ${ENTRA_EXPECTED_TENANT_ID}, got ${payload.tid}`
    );
  }

  return payload;
}

// ────────────────────────────────────────────────────────────────
// Express middleware
// ────────────────────────────────────────────────────────────────

/**
 * Entra ID authentication middleware.
 *
 * When AUTH_MODE is entra_jwt_rs256 or entra_jwt_hs256:
 *   - Extracts Bearer token from Authorization header
 *   - Validates JWT signature, audience, issuer, tenant
 *   - Resolves DIIaC role from claims
 *   - Populates req.entraAuth with identity context
 *   - Sets req.headers["x-role"] so downstream requireRole() works unchanged
 *
 * When AUTH_MODE is unset/unsupported:
 *   - Development: passes through for local legacy-role testing
 *   - Production: fails closed for all non-public routes
 */
export function entraAuth() {
  const isEntraRS256 = AUTH_MODE === "entra_jwt_rs256";
  const isEntraHS256 = AUTH_MODE === "entra_jwt_hs256";
  const entraEnabled = isEntraRS256 || isEntraHS256;
  const isDev = process.env.APP_ENV === "development" || process.env.APP_ENV === "dev";

  // Paths that must be accessible without a Bearer token
  const publicPaths = new Set([
    "/health",
    "/readiness",
    "/auth/status",
    "/auth/callback",
  ]);

  if (!entraEnabled) {
    if (isDev) {
      console.warn("[entra] AUTH_MODE not set to entra_jwt_*; legacy header auth is enabled for development only.");
      return (_req, _res, next) => next();
    }
    return (req, res, next) => {
      if (publicPaths.has(req.path)) {
        return next();
      }
      return res.status(503).json({
        error: "auth_mode_misconfigured",
        message: "Entra ID authentication must be enabled in production.",
        auth_mode: AUTH_MODE || "unset",
      });
    };
  }

  // Log configuration summary at startup (values redacted in production)
  console.log(`[entra] AUTH_MODE=${AUTH_MODE}`);
  console.log(`[entra] tenant=${isDev ? ENTRA_EXPECTED_TENANT_ID : (ENTRA_EXPECTED_TENANT_ID ? "***configured***" : "(not set)")}`);
  console.log(`[entra] audience=${isDev ? (ENTRA_ACCEPTED_AUDIENCES ? ENTRA_ACCEPTED_AUDIENCES.join(", ") : "(any)") : (ENTRA_ACCEPTED_AUDIENCES ? "***configured***" : "(any)")}`);
  console.log(
    `[entra] issuers=${ENTRA_EXPECTED_ISSUERS.length ? (isDev ? ENTRA_EXPECTED_ISSUERS.join(", ") : `***${ENTRA_EXPECTED_ISSUERS.length} configured***`) : "(any)"}`
  );
  console.log(
    `[entra] group_map_entries=${Object.keys(ENTRA_GROUP_TO_ROLE_JSON).length}`
  );
  console.log(
    `[entra] principal_map_entries=${Object.keys(ENTRA_PRINCIPAL_TO_ROLE_JSON).length}`
  );
  if (isEntraRS256) {
    console.log(`[entra] oidc_discovery=${isDev ? (ENTRA_OIDC_DISCOVERY_URL || "(derived from tenant)") : "***configured***"}`);
    console.log(`[entra] jwks_uri=${ENTRA_JWKS_URI ? (isDev ? ENTRA_JWKS_URI : "***configured***") : "(not configured)"}`);
  }

  return async function entraAuthMiddleware(req, res, next) {
    if (publicPaths.has(req.path)) {
      return next();
    }

    const authHeader = req.headers.authorization || "";
    if (!authHeader.startsWith("Bearer ")) {
      return res.status(401).json({
        error: "authentication_required",
        message: "Bearer token required. Provide Authorization: Bearer <token>",
        auth_mode: AUTH_MODE,
      });
    }

    const token = authHeader.slice(7);

    try {
      const claims = isEntraRS256
        ? await validateRS256(token)
        : await validateHS256(token);

      const resolved = resolveRole(claims);
      if (!resolved) {
        return res.status(403).json({
          error: "no_diiac_role",
          message:
            "Token is valid but no DIIaC role could be resolved. " +
            "Ensure the user/principal has app roles, group membership, or principal mapping configured.",
          subject: claims.sub,
          auth_mode: AUTH_MODE,
        });
      }

      const { role, subroles } = resolved;

      // Populate identity context for downstream consumption
      req.entraAuth = {
        subject: claims.sub,
        name: claims.name || claims.preferred_username || claims.sub,
        email: claims.email || claims.preferred_username || null,
        tenant_id: claims.tid || ENTRA_EXPECTED_TENANT_ID,
        role,
        subroles,
        roles_claim: claims[ENTRA_ROLE_CLAIM] || [],
        groups: claims.groups || [],
        principal_id: claims.appid || claims.azp || null,
        token_type: inferTokenType(claims),
        issued_at: claims.iat
          ? new Date(claims.iat * 1000).toISOString()
          : null,
        expires_at: claims.exp
          ? new Date(claims.exp * 1000).toISOString()
          : null,
      };

      // Bridge the Entra role into the x-role header so requireRole() works unchanged
      req.headers["x-role"] = role;

      next();
    } catch (err) {
      const isExpired = err instanceof joseErrors.JWTExpired;
      const isClaimValidation = err instanceof joseErrors.JWTClaimValidationFailed;

      return res.status(401).json({
        error: isExpired
          ? "token_expired"
          : isClaimValidation
            ? "claim_validation_failed"
            : "token_invalid",
        message: err.message,
        auth_mode: AUTH_MODE,
      });
    }
  };
}

/**
 * Returns true if Entra auth is active (any entra_jwt_* mode).
 */
export function isEntraEnabled() {
  return AUTH_MODE === "entra_jwt_rs256" || AUTH_MODE === "entra_jwt_hs256";
}

/**
 * Returns the current auth mode string for diagnostics.
 */
export function getAuthMode() {
  return AUTH_MODE || "unset";
}
