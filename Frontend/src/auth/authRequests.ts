// src/auth/authRequests.ts
// Login scopes — openid + profile only.
// Groups come from the ID token via Entra's groupMembershipClaims config,
// so no Graph scopes are needed.

export const loginRequest = {
  scopes: ["openid", "profile"],
};
