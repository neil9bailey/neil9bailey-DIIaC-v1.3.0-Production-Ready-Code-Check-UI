// src/auth/roleMapping.ts
// Maps Entra ID group OIDs (from ID token claims) to DIIaC RBAC roles.
// Pure functions — no React dependency.

export type DiiacRole = "admin" | "standard" | "viewer";

export interface RoleResolution {
  role: DiiacRole;
  subroles: string[];
  groups: string[];
}

// ── Group mapping from env ──────────────────────────────────

interface GroupMapping {
  role?: string;
  subrole?: string;
}

// Default group mapping for vendorlogic.io (public OIDs, not secrets).
// Override via VITE_ENTRA_GROUP_MAP env var for other tenants.
const DEFAULT_GROUP_MAP: Record<string, GroupMapping> = {
  "81786818-de16-4115-b061-92fce74b00bd": { role: "admin" },
  "9c7dd0d4-5b44-4811-b167-e52df21092d8": { role: "standard" },
};

function loadGroupMap(): Record<string, GroupMapping> {
  const raw = import.meta.env.VITE_ENTRA_GROUP_MAP;
  if (!raw) return DEFAULT_GROUP_MAP;
  try {
    return JSON.parse(raw) as Record<string, GroupMapping>;
  } catch {
    console.warn("[roleMapping] Failed to parse VITE_ENTRA_GROUP_MAP");
    return DEFAULT_GROUP_MAP;
  }
}

const GROUP_MAP = loadGroupMap();

// ── Normalisation ───────────────────────────────────────────

function normaliseRole(raw: string | undefined): DiiacRole | null {
  if (!raw) return null;
  const lower = raw.toLowerCase().trim();
  if (lower === "admin" || lower === "admins") return "admin";
  if (
    lower === "standard" ||
    lower === "standard users" ||
    lower === "standarduser" ||
    lower === "standard_user"
  )
    return "standard";
  if (lower === "viewer") return "viewer";
  return null;
}

// ── Group OID resolution ────────────────────────────────────

function resolveRoleFromGroups(groups: string[]): {
  role: DiiacRole;
  subroles: string[];
} {
  let role: DiiacRole = "viewer";
  const subroles: string[] = [];

  for (const gid of groups) {
    const mapping = GROUP_MAP[gid];
    if (!mapping) continue;
    const mapped = normaliseRole(mapping.role);
    if (mapped === "admin") role = "admin";
    else if (mapped === "standard" && role !== "admin") role = "standard";
    if (mapping.subrole) subroles.push(mapping.subrole);
  }

  return { role, subroles };
}

// ── Named app-role resolution ───────────────────────────────

function resolveRoleFromAppRoles(roles: string[]): DiiacRole | null {
  for (const r of roles) {
    const normalised = normaliseRole(r);
    if (normalised) return normalised;
  }
  return null;
}

// ── Main entry point ────────────────────────────────────────

export function resolveRole(
  idTokenClaims: Record<string, unknown>
): RoleResolution {
  const groupsClaim: string[] = Array.isArray(idTokenClaims.groups)
    ? (idTokenClaims.groups as string[])
    : [];
  const rolesClaim: string[] = Array.isArray(idTokenClaims.roles)
    ? (idTokenClaims.roles as string[])
    : [];

  // With "emit_as_roles" configured in Entra, group OIDs appear in
  // the `roles` claim instead of (or alongside) the `groups` claim.
  // We check BOTH arrays against the group mapping.
  const allGroupCandidates = [...new Set([...groupsClaim, ...rolesClaim])];

  const groupResolution = resolveRoleFromGroups(allGroupCandidates);

  // Also check for named app roles (e.g. "admin", "StandardUser")
  const appRole = resolveRoleFromAppRoles(rolesClaim);

  // App roles take priority over group-based resolution
  const role = appRole ?? groupResolution.role;

  return {
    role,
    subroles: groupResolution.subroles,
    groups: allGroupCandidates,
  };
}
