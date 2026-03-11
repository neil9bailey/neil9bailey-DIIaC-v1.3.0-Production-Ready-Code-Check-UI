// src/auth/useUserGroups.ts
// Extracts group OIDs from the active account's ID token claims.
// Merges both `groups` and `roles` arrays to handle the Entra
// "emit_as_roles" configuration.

import { useMsal } from "@azure/msal-react";

export function useUserGroups(): string[] {
  const { accounts } = useMsal();
  const account = accounts[0];
  if (!account) return [];

  const claims = account.idTokenClaims as
    | Record<string, unknown>
    | undefined;
  const groups: string[] = Array.isArray(claims?.groups)
    ? (claims.groups as string[])
    : [];
  const roles: string[] = Array.isArray(claims?.roles)
    ? (claims.roles as string[])
    : [];

  return [...new Set([...groups, ...roles])];
}
