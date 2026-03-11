import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { MsalProvider } from "@azure/msal-react";
import { msalInstance } from "./auth/authConfig";
import App from "./App";
import AuthCallback from "./auth/AuthCallback";
import "./index.css";

// MSAL is enabled when a valid PCA instance was created (requires VITE_ENTRA_CLIENT_ID).
// When null, MsalProvider is NOT rendered and the app falls through to legacy auth.
// The useMsal() / useIsAuthenticated() hooks in App.tsx use @azure/msal-react's
// default context (accounts: [], inProgress: None) when outside MsalProvider.

function Root() {
  if (!msalInstance) {
    // No MSAL configured — render without MsalProvider or routing.
    // App.tsx detects this via its own msalEnabled check and shows
    // the role selector (dev mode) or "MSAL not configured" message.
    return <App />;
  }

  return (
    <MsalProvider instance={msalInstance}>
      <BrowserRouter>
        <Routes>
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/*" element={<App />} />
        </Routes>
      </BrowserRouter>
    </MsalProvider>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
