import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import { MsalProvider } from "@azure/msal-react";
import { msalInstance } from "./auth/authConfig";
import App from "./App";
import AuthCallback from "./auth/AuthCallback";

// BrowserRouter is always present so react-router hooks work in all modes.
// MsalProvider wraps only when an Entra app registration is configured.

function Root() {
  const routes = (
    <BrowserRouter>
      <Routes>
        <Route path="/auth/callback" element={<AuthCallback />} />
        <Route path="/*" element={<App />} />
      </Routes>
    </BrowserRouter>
  );

  if (msalInstance) {
    return <MsalProvider instance={msalInstance}>{routes}</MsalProvider>;
  }

  return routes;
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);
