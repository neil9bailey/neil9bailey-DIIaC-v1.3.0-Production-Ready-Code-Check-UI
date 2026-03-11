// src/auth/SignInButton.tsx
// "Sign in with Entra ID" button.
// Uses useMsal() — instance is guaranteed initialised by MsalProvider.

import { useMsal } from "@azure/msal-react";
import { loginRequest } from "./authRequests";

export default function SignInButton() {
  const { instance } = useMsal();

  const handleLogin = () => {
    instance.loginRedirect(loginRequest).catch((err) => {
      console.error("[SignInButton] loginRedirect failed:", err);
    });
  };

  return (
    <button
      className="btn-primary"
      onClick={handleLogin}
      style={{ fontSize: 14, padding: "10px 32px" }}
    >
      Sign in with Entra ID
    </button>
  );
}
