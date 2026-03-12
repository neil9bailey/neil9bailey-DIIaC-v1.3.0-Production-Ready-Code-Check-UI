// Frontend/src/auth.ts
// Auth state module — bridges MSAL tokens and legacy header auth
// into a unified interface consumed by api.ts

export type Role = "admin" | "standard" | "customer" | "viewer";

// ─── Token + role state ───────────────────────────────────────
let _accessToken: string | null = null;
let _currentRole: Role = "standard";
const LEGACY_ROLE_HEADER_ENABLED =
  import.meta.env.DEV || String(import.meta.env.VITE_LEGACY_ROLE_HEADER_ENABLED || "").toLowerCase() === "true";

export function setAccessToken(token: string | null): void {
  _accessToken = token;
}

export function hasAccessToken(): boolean {
  return _accessToken !== null;
}

export function getAccessToken(): string | null {
  return _accessToken;
}

export function setRole(role: Role): void {
  _currentRole = role;
}

export function getRole(): Role {
  return _currentRole;
}

export function isAdmin(): boolean {
  return _currentRole === "admin";
}

export function isStandard(): boolean {
  return _currentRole === "standard";
}

/**
 * Returns headers for authenticated API calls.
 *
 * When an MSAL access token is set, sends Bearer auth.
 * Legacy x-role header fallback is opt-in for local/dev only.
 */
export function authHeaders(): Record<string, string> {
  if (_accessToken) {
    return { Authorization: `Bearer ${_accessToken}` };
  }
  if (LEGACY_ROLE_HEADER_ENABLED) {
    return { "x-role": _currentRole };
  }
  return {};
}
