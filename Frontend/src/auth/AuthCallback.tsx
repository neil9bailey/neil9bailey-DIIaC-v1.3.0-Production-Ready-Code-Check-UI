// src/auth/AuthCallback.tsx
// Handles the /auth/callback redirect from Microsoft Entra ID.
// MsalProvider calls handleRedirectPromise() automatically —
// this component just waits for MSAL to finish processing and
// then navigates back to "/".

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useMsal } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";

export default function AuthCallback() {
  const { instance, inProgress, accounts } = useMsal();
  const navigate = useNavigate();

  useEffect(() => {
    if (inProgress !== InteractionStatus.None) return; // still processing

    const account = accounts[0] ?? null;
    if (account) {
      instance.setActiveAccount(account);

      // Debug: log group OIDs once
      const claims = account.idTokenClaims as
        | Record<string, unknown>
        | undefined;
      const groups = claims?.groups ?? [];
      const roles = claims?.roles ?? [];
      console.log("[AuthCallback] Groups claim:", groups);
      console.log("[AuthCallback] Roles claim:", roles);
    }

    navigate("/", { replace: true });
  }, [inProgress, accounts, instance, navigate]);

  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100vh",
        fontFamily: "system-ui, sans-serif",
      }}
    >
      <div style={{ textAlign: "center" }}>
        <h2>Signing you in&hellip;</h2>
        <p style={{ color: "#64748b" }}>
          Processing Entra ID authentication
        </p>
      </div>
    </div>
  );
}
