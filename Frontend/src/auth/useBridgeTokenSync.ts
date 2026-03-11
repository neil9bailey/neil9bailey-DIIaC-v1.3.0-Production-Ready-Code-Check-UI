// src/auth/useBridgeTokenSync.ts
// Keeps the Bearer token in the auth module in sync with the active MSAL
// session by silently acquiring a fresh ID token on a 4-minute interval.
// Emits a diagnostic console.warn when MSAL scopes are not configured —
// this typically means VITE_ENTRA_CLIENT_ID is absent from the environment.

import { useEffect } from "react";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { setAccessToken } from "../auth";
import { loginRequest } from "./authRequests";

const REFRESH_MS = 4 * 60 * 1000; // 4-minute token refresh interval

export function useBridgeTokenSync(): void {
  const { instance, accounts } = useMsal();
  const isAuthenticated = useIsAuthenticated();
  const account = accounts[0] ?? null;

  useEffect(() => {
    if (!isAuthenticated || !account) return;

    const apiRequest = { ...loginRequest, account };

    // Defensive guard: warn if scopes were not configured.
    // This fires when VITE_ENTRA_CLIENT_ID is absent and loginRequest
    // was not properly initialised before MSAL rendered.
    if (!apiRequest.scopes || apiRequest.scopes.length === 0) {
      console.warn(
        "useBridgeTokenSync: apiRequest.scopes empty (check VITE_ENTRA_CLIENT_ID)",
      );
      return;
    }

    function sync() {
      instance
        .acquireTokenSilent(apiRequest)
        .then((r) => { if (r.idToken) setAccessToken(r.idToken); })
        .catch(() => {}); // Silently fail; interactive flow handles re-auth
    }

    const id = setInterval(sync, REFRESH_MS);
    return () => clearInterval(id);
  }, [isAuthenticated, account, instance]);
}
