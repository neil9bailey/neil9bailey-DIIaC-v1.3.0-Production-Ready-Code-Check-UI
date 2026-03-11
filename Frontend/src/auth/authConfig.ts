// src/auth/authConfig.ts
// MSAL configuration for Entra ID OIDC (Authorization Code + PKCE)
// Uses @azure/msal-browser v5 — no storeAuthStateInCookie / navigateToLoginRequestUrl

import {
  PublicClientApplication,
  type Configuration,
  LogLevel,
} from "@azure/msal-browser";

// Read exclusively from environment variables — no hardcoded fallbacks.
// Set VITE_ENTRA_CLIENT_ID + VITE_ENTRA_TENANT_ID in Frontend/.env to enable MSAL.
// Leave them unset (or empty) to disable MSAL and use legacy x-role header auth.
const ENTRA_CLIENT_ID = import.meta.env.VITE_ENTRA_CLIENT_ID || "";

const ENTRA_TENANT_ID = import.meta.env.VITE_ENTRA_TENANT_ID || "";

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

