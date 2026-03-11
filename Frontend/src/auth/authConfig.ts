// src/auth/authConfig.ts
// MSAL configuration for Entra ID OIDC (Authorization Code + PKCE)
// Uses @azure/msal-browser v5 — no storeAuthStateInCookie / navigateToLoginRequestUrl

import {
  PublicClientApplication,
  type Configuration,
  LogLevel,
} from "@azure/msal-browser";

// Defaults are the vendorlogic.io app registration (public identifiers, not secrets).
// Override via VITE_ENTRA_* env vars for other tenants / environments.
const ENTRA_CLIENT_ID =
  import.meta.env.VITE_ENTRA_CLIENT_ID || "b726558d-f1c6-48f7-8a3d-72d5db818d0f";

const ENTRA_TENANT_ID =
  import.meta.env.VITE_ENTRA_TENANT_ID || "1384b1c5-2bae-45a1-a4b4-e94e3315eb41";

export const msalConfig: Configuration = {
  auth: {
    clientId: ENTRA_CLIENT_ID,
    authority: `https://login.microsoftonline.com/${ENTRA_TENANT_ID}`,
    redirectUri:
      import.meta.env.VITE_ENTRA_REDIRECT_URI ||
      "http://localhost:5173/auth/callback",
    postLogoutRedirectUri: window.location.origin,
  },
  cache: {
    cacheLocation: "sessionStorage",
  },
  system: {
    loggerOptions: {
      logLevel: LogLevel.Warning,
      piiLoggingEnabled: false,
    },
  },
};

// Only create the PCA when a valid client ID is configured.
// When VITE_ENTRA_CLIENT_ID is empty, msalInstance is null and
// MsalProvider won't be rendered (see main.tsx).
export const msalInstance: PublicClientApplication | null = ENTRA_CLIENT_ID
  ? new PublicClientApplication(msalConfig)
  : null;

export { ENTRA_CLIENT_ID, ENTRA_TENANT_ID };
