import { useState, useEffect, useCallback, useMemo } from "react";
import { Routes, Route, NavLink, useLocation } from "react-router-dom";
import { setRole as setAuthRole, setAccessToken, hasAccessToken } from "./auth";
import type { Role } from "./auth";
import { fetchAuthStatus, type AuthStatusResponse } from "./api";
import { useBridgeTokenSync } from "./auth/useBridgeTokenSync";
import { useMsal, useIsAuthenticated } from "@azure/msal-react";
import { InteractionStatus } from "@azure/msal-browser";
import { resolveRole } from "./auth/roleMapping";
import { loginRequest } from "./auth/authRequests";
import { ENTRA_CLIENT_ID } from "./auth/authConfig";
import SignInButton from "./auth/SignInButton";
import { AppContext } from "./AppContext";

import HomePage from "./pages/HomePage";
import WorkflowPage from "./pages/WorkflowPage";
import CompilePage from "./pages/CompilePage";
import AdminPage from "./pages/AdminPage";
import DashboardPage from "./pages/DashboardPage";

export type LlmProvider = "ChatGPT" | "Copilot";

const msalEnabled = !!ENTRA_CLIENT_ID;

// ── SVG Nav Icons ──────────────────────────────────────────────
function IconHome() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" />
      <polyline points="9,22 9,12 15,12 15,22" />
    </svg>
  );
}
function IconWorkflow() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M9 11l3 3L22 4" />
      <path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
    </svg>
  );
}
function IconCompile() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="16,18 22,12 16,6" />
      <polyline points="8,6 2,12 8,18" />
    </svg>
  );
}
function IconAdmin() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  );
}
function IconDashboard() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <rect x="3" y="3" width="7" height="7" />
      <rect x="14" y="3" width="7" height="7" />
      <rect x="14" y="14" width="7" height="7" />
      <rect x="3" y="14" width="7" height="7" />
    </svg>
  );
}

function pageMeta(path: string): { title: string; subtitle: string } {
  if (path === "/" || path === "") return { title: "Overview", subtitle: "Platform status, recent activity, and quick actions" };
  if (path.startsWith("/workflow")) return { title: "Governance Workflow", subtitle: "Submit human intent, run exploratory decision draft, and export artifacts" };
  if (path.startsWith("/compile")) return { title: "Decision Evidence Workspace", subtitle: "Production multi-role governed compile with full evidence chain" };
  if (path.startsWith("/admin")) return { title: "Admin Console", subtitle: "Service health, audit exports, execution logs, and database operations" };
  if (path.startsWith("/dashboard")) return { title: "Operational Dashboard", subtitle: "Real-time integration health, governance operations, and approval queue" };
  return { title: "DIIaC", subtitle: "" };
}

export default function App() {
  const { instance, accounts, inProgress } = useMsal();
  const msalAuthenticated = useIsAuthenticated();
  const msalLoading = inProgress !== InteractionStatus.None;
  const location = useLocation();

  const account = accounts[0] ?? null;
  const { role: msalRole, subroles, groups } = useMemo(() => {
    if (!account) return { role: "viewer" as const, subroles: [] as string[], groups: [] as string[] };
    return resolveRole((account.idTokenClaims as Record<string, unknown>) ?? {});
  }, [account]);

  const [legacyRole, setLegacyRole] = useState<string>(localStorage.getItem("role") || "standard");
  const [llmProvider, setLlmProvider] = useState<LlmProvider>((localStorage.getItem("llmProvider") as LlmProvider) || "ChatGPT");
  const [latestExecutionId, setLatestExecutionId] = useState<string | null>(null);
  const [authStatus, setAuthStatus] = useState<AuthStatusResponse | null>(null);
  const [authStatusLoading, setAuthStatusLoading] = useState(true);
  const [groupOverageWarning, setGroupOverageWarning] = useState(false);
  const [tokenInput, setTokenInput] = useState("");
  const [legacyTokenSet, setLegacyTokenSet] = useState(hasAccessToken());

  useEffect(() => {
    fetchAuthStatus()
      .then(setAuthStatus)
      .catch(() => setAuthStatus(null))
      .finally(() => setAuthStatusLoading(false));
  }, []);

  const entraRequired = authStatus?.entra_enabled === true;

  useEffect(() => {
    if (!entraRequired) return;
    const saved = sessionStorage.getItem("entra_token");
    if (saved) { setAccessToken(saved); setLegacyTokenSet(true); }
  }, [entraRequired]);

  useEffect(() => {
    if (!msalAuthenticated || !account) return;
    localStorage.setItem("role", msalRole);
    setAuthRole(msalRole as Role);
    if (groups.length === 0) setGroupOverageWarning(true);
    instance
      .acquireTokenSilent({ scopes: ["openid", "profile"], account })
      .then((r) => { if (r.idToken) setAccessToken(r.idToken); })
      .catch(() => {});
  }, [msalAuthenticated, account, msalRole, groups.length, instance]);

  useBridgeTokenSync();

  useEffect(() => {
    localStorage.setItem("role", legacyRole);
    if (!msalAuthenticated) setAuthRole(legacyRole as Role);
  }, [legacyRole, msalAuthenticated]);

  useEffect(() => { localStorage.setItem("llmProvider", llmProvider); }, [llmProvider]);

  const role: string = msalAuthenticated ? msalRole : legacyRole;
  const authenticated = msalAuthenticated || legacyTokenSet || !entraRequired;
  const isAdmin = role === "admin";

  const handleSetToken = useCallback(() => {
    const t = tokenInput.trim();
    if (!t) return;
    setAccessToken(t);
    sessionStorage.setItem("entra_token", t);
    setLegacyTokenSet(true);
    setTokenInput("");
    window.location.reload();
  }, [tokenInput]);

  const handleClearToken = useCallback(() => {
    setAccessToken(null);
    sessionStorage.removeItem("entra_token");
    setLegacyTokenSet(false);
  }, []);

  const handleSignOut = useCallback(async () => {
    if (msalAuthenticated) {
      await instance.logoutRedirect({ postLogoutRedirectUri: window.location.origin });
    } else {
      handleClearToken();
    }
  }, [msalAuthenticated, instance, handleClearToken]);

  // ── Loading state ─────────────────────────────────────────
  if ((msalEnabled && msalLoading) || authStatusLoading) {
    return (
      <div className="app-shell" style={{ alignItems: "center", justifyContent: "center" }}>
        <div className="panel" style={{ maxWidth: 360, textAlign: "center", padding: "40px 32px", margin: "auto" }}>
          <img src="/diiac-logo.png" alt="DIIaC" style={{ maxWidth: 200, width: "100%", height: "auto", marginBottom: 8 }} />
          <div className="loading-dots">
            <span /><span /><span />
          </div>
          <p className="muted-text" style={{ marginTop: 16 }}>
            {msalEnabled && msalLoading ? "Connecting to Entra ID…" : "Checking authentication status…"}
          </p>
        </div>
      </div>
    );
  }

  // ── Auth gate ─────────────────────────────────────────────
  if (entraRequired && !authenticated) {
    return (
      <div className="app-shell auth-gate-bg">
        <div className="auth-gate-card">
          <div className="auth-gate-logo">
            <img src="/diiac-logo.png" alt="DIIaC" className="auth-gate-logo-img" />
            <span className="auth-gate-version">v1.2.0</span>
          </div>
          <h2 className="auth-gate-title">Secure Sign-In Required</h2>
          <p className="auth-gate-sub">
            This platform requires authentication via <strong>Microsoft Entra ID</strong>.
            Sign in with your <strong>vendorlogic.io</strong> account to continue.
          </p>
          <div className="auth-gate-actions">
            {msalEnabled ? <SignInButton /> : <p className="muted-text">MSAL not configured. Set VITE_ENTRA_CLIENT_ID.</p>}
          </div>
          {authStatus?.tenant_id && (
            <p className="auth-gate-meta">Tenant: {authStatus.tenant_id}</p>
          )}
          <details className="auth-gate-advanced">
            <summary>Advanced: paste Bearer token manually</summary>
            <div style={{ marginTop: 10 }}>
              <textarea
                rows={3}
                value={tokenInput}
                onChange={(e) => setTokenInput(e.target.value)}
                placeholder="Paste your Entra Bearer token here…"
                style={{ width: "100%", fontFamily: "var(--font-mono)", fontSize: 11 }}
              />
              <button className="btn-secondary" onClick={handleSetToken} disabled={!tokenInput.trim()} style={{ marginTop: 6, width: "100%" }}>
                Authenticate with Token
              </button>
            </div>
          </details>
        </div>
      </div>
    );
  }

  // ── Compute display info ───────────────────────────────────
  const { title, subtitle } = pageMeta(location.pathname);
  const userInitial = msalAuthenticated && account?.name
    ? account.name[0].toUpperCase()
    : role[0].toUpperCase();
  const userName = msalAuthenticated && account?.name
    ? account.name
    : (role === "admin" ? "Admin User" : "Standard User");
  const userEmail = msalAuthenticated && account?.username ? account.username : "";

  return (
    <AppContext.Provider value={{ role, llmProvider, setLlmProvider, latestExecutionId, setLatestExecutionId }}>
      <div className="app-shell">

        {/* ── Sidebar ──────────────────────────────────────── */}
        <nav className="sidebar">
          {/* Brand */}
          <div className="sidebar-brand">
            <img src="/diiac-logo.png" alt="DIIaC" className="sidebar-brand-logo" />
            <div style={{ display: "flex", alignItems: "center", gap: 6, marginTop: 8 }}>
              <span className="sidebar-version-chip">v1.2</span>
              <div className="sidebar-brand-sub" style={{ margin: 0 }}>Decision Intelligence Platform</div>
            </div>
          </div>

          {/* Nav links */}
          <div className="sidebar-nav">
            <p className="nav-section-label">Navigation</p>
            <NavLink to="/" end className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
              <IconHome /> Overview
            </NavLink>
            <NavLink to="/workflow" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
              <IconWorkflow /> Governance Workflow
            </NavLink>
            {isAdmin && (
              <>
                <p className="nav-section-label" style={{ marginTop: 16 }}>Admin</p>
                <NavLink to="/compile" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
                  <IconCompile /> Decision Evidence
                </NavLink>
                <NavLink to="/admin" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
                  <IconAdmin /> Admin Console
                </NavLink>
                <NavLink to="/dashboard" className={({ isActive }) => `nav-item${isActive ? " active" : ""}`}>
                  <IconDashboard /> Operations
                </NavLink>
              </>
            )}

            {/* Dev mode role override */}
            {!entraRequired && (
              <>
                <p className="nav-section-label" style={{ marginTop: 16 }}>Dev Mode</p>
                <div style={{ padding: "4px 20px 8px" }}>
                  <label style={{ display: "block", fontSize: 10, color: "var(--slate-500)", marginBottom: 4, textTransform: "uppercase", letterSpacing: "0.05em" }}>Role Override</label>
                  <select
                    className="sidebar-select"
                    value={legacyRole}
                    onChange={(e) => setLegacyRole(e.target.value)}
                  >
                    <option value="admin">Admin</option>
                    <option value="standard">Standard User</option>
                    <option value="viewer">Viewer</option>
                  </select>
                </div>
              </>
            )}
          </div>

          {/* Sidebar footer – user info & controls */}
          <div className="sidebar-footer">
            {groupOverageWarning && msalAuthenticated && (
              <div className="sidebar-warning">⚠ Group claim missing — role fallback applied</div>
            )}
            <div className="sidebar-user">
              <div className="sidebar-avatar">{userInitial}</div>
              <div className="sidebar-user-info">
                <div className="sidebar-user-name">{userName}</div>
                <div className="sidebar-user-email" title={userEmail}>{userEmail || role}</div>
              </div>
            </div>
            <div className="sidebar-controls">
              <div className="sidebar-llm-row">
                <span className="sidebar-llm-label">LLM</span>
                <select className="sidebar-select" value={llmProvider} onChange={(e) => setLlmProvider(e.target.value as LlmProvider)}>
                  <option value="ChatGPT">ChatGPT</option>
                  <option value="Copilot">Copilot</option>
                </select>
              </div>
              {(msalAuthenticated || legacyTokenSet) && (
                <button className="sidebar-signout-btn" onClick={() => void handleSignOut()}>
                  Sign Out
                </button>
              )}
            </div>
          </div>
        </nav>

        {/* ── Page shell ───────────────────────────────────── */}
        <div className="page-shell">
          {/* Topbar */}
          <div className="page-topbar">
            <div className="page-topbar-left">
              <span className="breadcrumb-root">DIIaC</span>
              <span className="breadcrumb-sep">›</span>
              <span className="breadcrumb-current">{title}</span>
            </div>
            <div className="page-topbar-right">
              {msalAuthenticated && account && (
                <span className="topbar-badge topbar-badge-green">
                  <span className="topbar-dot" /> Entra ID
                </span>
              )}
              {!msalAuthenticated && legacyTokenSet && (
                <span className="topbar-badge topbar-badge-blue">Token Auth</span>
              )}
              {!entraRequired && (
                <span className="topbar-badge topbar-badge-amber">Dev Mode</span>
              )}
              <span className="topbar-role-badge" style={{ background: isAdmin ? "var(--blue-600)" : "var(--slate-500)" }}>
                {isAdmin ? "Admin" : role === "standard" ? "Standard" : "Viewer"}
              </span>
            </div>
          </div>

          {/* Main page content */}
          <main className="page-content">
            <div className="page-header">
              <h1 className="page-title">{title}</h1>
              {subtitle && <p className="page-subtitle">{subtitle}</p>}
            </div>

            <Routes>
              <Route path="/" element={<HomePage />} />
              <Route path="/workflow" element={<WorkflowPage />} />
              {isAdmin && <Route path="/compile" element={<CompilePage />} />}
              {isAdmin && <Route path="/admin" element={<AdminPage />} />}
              {isAdmin && <Route path="/dashboard" element={<DashboardPage />} />}
              <Route path="*" element={<HomePage />} />
            </Routes>
          </main>

          <footer className="enterprise-footer">
            © 2026 DIIaC — Decision Intelligence Infrastructure as Code Platform — v1.2.0
          </footer>
        </div>
      </div>
    </AppContext.Provider>
  );
}
