import { useState, useEffect, useCallback, useMemo } from "react";
import { setRole as setAuthRole, setAccessToken, hasAccessToken } from "./auth";
import type { Role } from "./auth";
import { fetchAuthStatus, type AuthStatusResponse } from "./api";

// @azure/msal-react hooks (functional inside MsalProvider; safe no-ops outside)
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { resolveRole } from "./auth/roleMapping";
import { loginRequest } from "./auth/authRequests";
import { ENTRA_CLIENT_ID } from "./auth/authConfig";
import SignInButton from "./auth/SignInButton";

import HumanInputPanel from "./HumanInputPanel";
import GovernedCtoStrategy from "./GovernedCtoStrategy";
import GovernedReportViewer from "./GovernedReportViewer";
import ImpactViewer from "./ImpactViewer";
import TrustDashboard from "./TrustDashboard";
import MultiRoleGovernedCompilePanel from "./MultiRoleGovernedCompilePanel";
import AdminConsolePanel from "./AdminConsolePanel";
import GovernanceNotice from "./components/GovernanceNotice";
import OperationalDashboard from "./OperationalDashboard";

export type LlmProvider = "ChatGPT" | "Copilot";

// Whether MSAL is wired up — uses the same value (with hardcoded default)
// as authConfig.ts so it stays true even when .env isn't loaded.
const msalEnabled = !!ENTRA_CLIENT_ID;

export default function App() {
  // ── MSAL auth via @azure/msal-react ─────────────────────
  const { instance, accounts, inProgress } = useMsal();
  const msalAuthenticated = useIsAuthenticated();
  const msalLoading = inProgress !== InteractionStatus.None;

  // Resolve role from ID token claims
  const account = accounts[0] ?? null;
  const { role: msalRole, subroles, groups } = useMemo(() => {
    if (!account) return { role: "viewer" as const, subroles: [] as string[], groups: [] as string[] };
    return resolveRole((account.idTokenClaims as Record<string, unknown>) ?? {});
  }, [account]);

  // ── Legacy auth state (dev mode / non-Entra) ──────────────
  const [legacyRole, setLegacyRole] = useState<string>(
    localStorage.getItem("role") || "standard"
  );
  const [llmProvider, setLlmProvider] = useState<LlmProvider>(
    (localStorage.getItem("llmProvider") as LlmProvider) || "ChatGPT"
  );
  const [latestExecutionId, setLatestExecutionId] = useState<string | null>(null);
  const [showDashboard, setShowDashboard] = useState(false);
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(null);
  const [groupOverageWarning, setGroupOverageWarning] = useState(false);

  // Legacy token-paste state (kept as fallback)
  const [showTokenDialog, setShowTokenDialog] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [legacyTokenSet, setLegacyTokenSet] = useState(hasAccessToken());

  // ── Fetch backend auth status ─────────────────────────────
  useEffect(() => {
    fetchAuthStatus()
      .then(setAuthStatus)
      .catch(() => setAuthStatus(null));
  }, []);

  const entraRequired = authStatus?.entra_enabled === true;

  // ── Restore legacy token from sessionStorage ──────────────
  useEffect(() => {
    if (!entraRequired) return;
    const saved = sessionStorage.getItem("entra_token");
    if (saved) {
      setAccessToken(saved);
      setLegacyTokenSet(true);
    }
  }, [entraRequired]);

  // ── Sync MSAL auth into the auth module ────────────────────
  useEffect(() => {
    if (!msalAuthenticated || !account) return;

    // Persist role to localStorage so x-role header logic works
    localStorage.setItem("role", msalRole);
    setAuthRole(msalRole as Role);

    // Check for group overage (no groups in token)
    if (groups.length === 0) {
      setGroupOverageWarning(true);
    }

    // Get an ID token for Bearer auth
    instance
      .acquireTokenSilent({ scopes: ["openid", "profile"], account })
      .then((response) => {
        if (response.idToken) {
          setAccessToken(response.idToken);
        }
      })
      .catch(() => {
        // Token will be acquired on demand
      });
  }, [msalAuthenticated, account, msalRole, groups.length, instance]);

  // ── Keep access token fresh via MSAL ──────────────────────
  useEffect(() => {
    if (!msalAuthenticated || !account) return;
    const interval = setInterval(() => {
      instance
        .acquireTokenSilent({ scopes: ["openid", "profile"], account })
        .then((response) => {
          if (response.idToken) {
            setAccessToken(response.idToken);
          }
        })
        .catch(() => {});
    }, 4 * 60 * 1000);
    return () => clearInterval(interval);
  }, [msalAuthenticated, account, instance]);

  // ── Legacy role sync ──────────────────────────────────────
  useEffect(() => {
    localStorage.setItem("role", legacyRole);
    if (!msalAuthenticated) {
      setAuthRole(legacyRole as Role);
    }
  }, [legacyRole, msalAuthenticated]);

  useEffect(() => {
    localStorage.setItem("llmProvider", llmProvider);
  }, [llmProvider]);

  // ── Resolve effective role ────────────────────────────────
  const role: string = msalAuthenticated ? msalRole : legacyRole;
  const authenticated = msalAuthenticated || legacyTokenSet || !entraRequired;

  // ── Legacy token handlers ─────────────────────────────────
  const handleSetToken = useCallback(() => {
    const trimmed = tokenInput.trim();
    if (!trimmed) return;
    setAccessToken(trimmed);
    sessionStorage.setItem("entra_token", trimmed);
    setLegacyTokenSet(true);
    setTokenInput("");
    setShowTokenDialog(false);
    window.location.reload();
  }, [tokenInput]);

  const handleClearToken = useCallback(() => {
    setAccessToken(null);
    sessionStorage.removeItem("entra_token");
    setLegacyTokenSet(false);
  }, []);

  // ── Sign-out handler ──────────────────────────────────────
  const handleSignOut = useCallback(async () => {
    if (msalAuthenticated) {
      await instance.logoutRedirect({
        postLogoutRedirectUri: window.location.origin,
      });
    } else {
      handleClearToken();
    }
  }, [msalAuthenticated, instance, handleClearToken]);

  // ── Role display helpers ──────────────────────────────────
  function roleBadgeLabel(r: string): string {
    switch (r) {
      case "admin": return "Admin";
      case "standard": return "Standard User";
      case "viewer": return "Viewer";
      default: return r;
    }
  }

  // ── Loading state (MSAL processing redirect) ──────────────
  if (msalEnabled && msalLoading) {
    return (
      <div className="app-container">
        <header className="enterprise-header">
          <div className="brand-left">
            <h1 className="brand-title">DIIaC</h1>
            <span className="brand-product">
              Decision Intelligence Infrastructure as Code
            </span>
          </div>
        </header>
        <main className="main-content">
          <div className="panel" style={{ maxWidth: 400, margin: "80px auto", textAlign: "center" }}>
            <h2>Authenticating...</h2>
            <p className="muted-text">Connecting to Entra ID...</p>
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="app-container">

      {/* ── Enterprise Header ────────────────────────────── */}
      <header className="enterprise-header">
        <div className="brand-left">
          <h1 className="brand-title">DIIaC</h1>
          <span className="brand-product">
            Decision Intelligence Infrastructure as Code
          </span>
        </div>

        <div className="brand-right">
          <div className="header-controls">
            {/* Auth badge */}
            {msalAuthenticated && account ? (
              <span className="header-badge auth-active" title={`Signed in as ${account.name} (${account.username})`}>
                {account.name || account.username || "Entra ID"}
              </span>
            ) : entraRequired ? (
              <span
                className="header-badge auth-legacy"
                style={{ cursor: "pointer" }}
                onClick={() => {
                  if (!legacyTokenSet && msalEnabled) {
                    instance.loginRedirect(loginRequest).catch(console.error);
                  } else {
                    setShowTokenDialog(true);
                  }
                }}
                title={legacyTokenSet ? "Entra ID authenticated (legacy token)" : "Click to sign in with Entra ID"}
              >
                {legacyTokenSet ? "Entra ID" : "Sign In"}
              </span>
            ) : (
              <span className="header-badge auth-legacy" title="Legacy header auth (dev mode)">
                Legacy Auth
              </span>
            )}

            {/* Role badge (shown when authenticated) */}
            {authenticated && (
              <span
                className="header-badge"
                style={{ background: role === "admin" ? "#2563eb" : "#6b7280", color: "#fff", fontSize: 11, padding: "2px 8px", borderRadius: 4 }}
                title={`Role: ${role}${subroles.length ? ` | Sub-roles: ${subroles.join(", ")}` : ""}`}
              >
                {roleBadgeLabel(role)}
              </span>
            )}

            {/* Sign Out button */}
            {(msalAuthenticated || legacyTokenSet) && (
              <button
                className="admin-dashboard-btn"
                onClick={handleSignOut}
                title="Sign out"
                style={{ fontSize: 12, width: "auto", padding: "0 8px" }}
              >
                Sign Out
              </button>
            )}

            {/* Role selector (only in legacy/dev mode) */}
            {!entraRequired && (
              <select
                className="header-select"
                value={legacyRole}
                onChange={(e) => setLegacyRole(e.target.value)}
                title="Switch role (dev mode)"
              >
                <option value="admin">Admin</option>
                <option value="standard">Standard User</option>
              </select>
            )}

            {/* LLM Provider selector */}
            <div className="llm-selector">
              <span className="llm-label">LLM</span>
              <select
                className="header-select"
                value={llmProvider}
                onChange={(e) => setLlmProvider(e.target.value as LlmProvider)}
                title="Select LLM provider"
              >
                <option value="ChatGPT">ChatGPT</option>
                <option value="Copilot">Copilot</option>
              </select>
            </div>

            {/* Admin dashboard button (admin only) */}
            {role === "admin" && authenticated && (
              <button
                className="admin-dashboard-btn"
                onClick={() => setShowDashboard(true)}
                title="Open Operational Dashboard"
              >
                &#9881;
              </button>
            )}
          </div>
        </div>
      </header>

      {/* ── Auth Gate ─────────────────────────────────────── */}
      {entraRequired && !authenticated ? (
        <main className="main-content">
          <div className="panel" style={{ maxWidth: 520, margin: "60px auto", textAlign: "center" }}>
            <h2>Welcome to DIIaC</h2>
            <p style={{ margin: "12px 0", color: "#334155" }}>
              Sign in with your <strong>vendorlogic.io</strong> account to continue.
            </p>
            <p className="muted-text" style={{ margin: "8px 0 20px" }}>
              Authentication is handled securely via Microsoft Entra ID.
            </p>
            {msalEnabled ? (
              <SignInButton />
            ) : (
              <p className="muted-text">MSAL not configured. Set VITE_ENTRA_CLIENT_ID.</p>
            )}
            {authStatus?.tenant_id && (
              <p className="muted-text" style={{ marginTop: 16, fontSize: 11 }}>
                Tenant: {authStatus.tenant_id}
              </p>
            )}

            {/* Fallback: manual token paste */}
            <details style={{ marginTop: 24, textAlign: "left" }}>
              <summary className="muted-text" style={{ cursor: "pointer", fontSize: 12 }}>
                Advanced: Paste a Bearer token manually
              </summary>
              <div style={{ marginTop: 8 }}>
                <textarea
                  rows={3}
                  value={tokenInput}
                  onChange={(e) => setTokenInput(e.target.value)}
                  placeholder="Paste your Entra Bearer token here..."
                  style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 11 }}
                />
                <div className="button-row" style={{ justifyContent: "center", marginTop: 8 }}>
                  <button className="btn-secondary" onClick={handleSetToken} disabled={!tokenInput.trim()}>
                    Authenticate
                  </button>
                </div>
              </div>
            </details>
          </div>
        </main>
      ) : (

        /* ── Main Content ─────────────────────────────────── */
        <main className="main-content">
          <GovernanceNotice />

          {/* Group overage warning */}
          {groupOverageWarning && msalAuthenticated && (
            <div className="panel" style={{ background: "#fef3c7", border: "1px solid #f59e0b", margin: "8px 0" }}>
              <p style={{ margin: 0, fontSize: 12, color: "#92400e" }}>
                Group claim not present in ID token; role fallback applied.
                Contact your admin if you expect specific group-based access.
              </p>
            </div>
          )}

          {/* Standard users and viewers see the HumanInputPanel */}
          {role !== "admin" && <HumanInputPanel />}

          <GovernedCtoStrategy
            role={role}
            llmProvider={llmProvider}
            onExecutionComplete={(executionId: string) =>
              setLatestExecutionId(executionId)
            }
          />

          <GovernedReportViewer
            executionId={latestExecutionId}
          />

          {/* ── Admin-only Governance Controls ────────────── */}
          {role === "admin" && (
            <>
              <div className="section-divider">
                <div className="line" />
                <span className="label">Admin Governance Controls</span>
                <div className="line" />
              </div>

              <ImpactViewer role={role} />
              <TrustDashboard role={role} />
              <MultiRoleGovernedCompilePanel
                role={role}
                llmProvider={llmProvider}
                onExecutionComplete={setLatestExecutionId}
              />
              <AdminConsolePanel role={role} executionId={latestExecutionId} />
            </>
          )}
        </main>
      )}

      {/* ── Footer ───────────────────────────────────────── */}
      <footer className="enterprise-footer">
        &copy; 2026 DIIaC &mdash; Decision Intelligence Infrastructure as Code Platform
      </footer>

      {/* ── Token Dialog (legacy fallback) ────────────────── */}
      {showTokenDialog && (
        <div className="dashboard-overlay" onClick={(e) => { if (e.target === e.currentTarget) setShowTokenDialog(false); }}>
          <div className="dashboard-container" style={{ maxWidth: 520, marginTop: "10vh" }}>
            <div className="dashboard-header">
              <h2>Entra ID Authentication</h2>
              <button className="dashboard-close" onClick={() => setShowTokenDialog(false)}>x</button>
            </div>
            <div className="dashboard-body">
              <p style={{ fontSize: 13, color: "#334155", marginBottom: 12 }}>
                {legacyTokenSet
                  ? "You are currently authenticated. You can replace the token or sign out."
                  : "Paste a valid Entra Bearer token to authenticate."}
              </p>
              <textarea
                rows={4}
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Paste Bearer token..."
                style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 11 }}
              />
              <div className="button-row" style={{ marginTop: 12 }}>
                <button className="btn-primary" onClick={handleSetToken} disabled={!tokenInput.trim()}>
                  Set Token
                </button>
                {legacyTokenSet && (
                  <button className="btn-danger" onClick={() => { handleClearToken(); setShowTokenDialog(false); }}>
                    Sign Out
                  </button>
                )}
                <button className="btn-secondary" onClick={() => setShowTokenDialog(false)}>
                  Cancel
                </button>
              </div>
              {authStatus && (
                <div style={{ marginTop: 12, fontSize: 11, color: "#64748b" }}>
                  Mode: {authStatus.auth_mode} &mdash;
                  Tenant: {authStatus.tenant_id || "n/a"} &mdash;
                  Audience: {authStatus.audience || "n/a"}
                </div>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Operational Dashboard Overlay (admin only) ───── */}
      {showDashboard && (
        <OperationalDashboard onClose={() => setShowDashboard(false)} />
      )}
    </div>
  );
}
