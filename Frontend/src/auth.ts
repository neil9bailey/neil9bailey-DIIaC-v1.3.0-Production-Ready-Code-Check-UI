// Frontend/src/auth.ts
// Auth state module — bridges MSAL tokens and legacy header auth
// into a unified interface consumed by api.ts

export type Role = "admin" | "standard" | "customer" | "viewer";

// ─── Token + role state ───────────────────────────────────────
let _accessToken: string | null = null;
let _currentRole: Role = "standard";

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
 * Otherwise falls back to legacy x-role header (dev mode).
 */
export function authHeaders(): Record<string, string> {
  if (_accessToken) {
    return { Authorization: `Bearer ${_accessToken}` };
  }
  return { "x-role": _currentRole };
}
