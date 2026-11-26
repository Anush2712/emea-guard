import { useState, type ReactNode } from "react";
import { HashRouter, Navigate, NavLink, Route, Routes, useNavigate } from "react-router-dom";
import { DEMO, getSession, login, logout, type Session } from "./api";
import { ToastHost } from "./components/ui";
import AccessControl from "./pages/AccessControl";
import Audit from "./pages/Audit";
import Controls from "./pages/Controls";
import Dashboard from "./pages/Dashboard";
import Gaps from "./pages/Gaps";
import Inventory from "./pages/Inventory";
import Jurisdictions from "./pages/Jurisdictions";
import Localisation from "./pages/Localisation";
import Policies from "./pages/Policies";
import Risk from "./pages/Risk";
import Stakeholders from "./pages/Stakeholders";

const I = (d: string) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>;
const NAV: { section: string; items: [string, string, ReactNode][] }[] = [
  { section: "Overview", items: [["/", "Governance dashboard", I("M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z")]] },
  { section: "Controls", items: [
    ["/access", "Access control", I("M12 11V7a4 4 0 0 1 8 0M5 11h14v10H5z")],
    ["/localisation", "Data localisation", I("M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z")],
    ["/controls", "Control assessments", I("M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9")],
    ["/gaps", "Gaps & remediation", I("M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z")],
  ] },
  { section: "Governance", items: [
    ["/jurisdictions", "Jurisdictions", I("M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20")],
    ["/inventory", "Data & people", I("M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3")],
    ["/policies", "Policies", I("M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5")],
    ["/stakeholders", "Stakeholders & projects", I("M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8")],
  ] },
  { section: "Assurance", items: [
    ["/risk", "Risk & reports", I("M3 3v18h18M7 15l4-4 3 3 6-7")],
    ["/audit", "Audit trail", I("M12 8v4l3 3M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5")],
  ] },
];

function Layout({ session, onLogout, children }: { session: Session; onLogout: () => void; children: ReactNode }) {
  return (
    <div className="shell">
      <aside className="sidebar">
        <div className="brand"><img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" /><div><b>EMEA Guard</b><span>Data Governance & Controls</span></div></div>
        <nav className="nav">
          {NAV.map((s) => (
            <div key={s.section}>
              <div className="nav-section">{s.section}</div>
              {s.items.map(([to, label, icon]) => <NavLink key={to} to={to} end={to === "/"}>{icon}{label}</NavLink>)}
            </div>
          ))}
        </nav>
        <div className="sidebar-foot">
          Signed in as <b style={{ color: "#fff" }}>{session.full_name}</b><br />Role: {session.role}
          <div><button onClick={onLogout}>Sign out</button></div>
        </div>
      </aside>
      <div className="main">
        {DEMO && (
          <div className="demo-banner">
            <b>Live demo</b> on a static snapshot of the API (synthetic data). Access checks run the parity-tested control engine in your browser;
            other write actions are kept for this tab only. Run the full stack (FastAPI + PostgreSQL) with <code>docker compose up</code>.
          </div>
        )}
        <div className="content">{children}</div>
      </div>
      <ToastHost />
    </div>
  );
}

function Login({ onLogin }: { onLogin: (s: Session) => void }) {
  const [u, setU] = useState("analyst");
  const [p, setP] = useState("analyst123");
  const [err, setErr] = useState<string | null>(null);
  const nav = useNavigate();
  const submit = async (user = u, pass = p) => {
    try { onLogin(await login(user, pass)); nav("/"); } catch (e: any) { setErr(e.message); }
  };
  return (
    <div className="login">
      <div className="login-card">
        <div className="brand"><img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" style={{ width: 36 }} /><div><b>EMEA Guard</b><span>Enterprise Data Governance & Control Management</span></div></div>
        <form onSubmit={(e) => { e.preventDefault(); submit(); }} className="grid" style={{ gap: 12 }}>
          <label className="field">Username<input value={u} onChange={(e) => setU(e.target.value)} autoComplete="username" /></label>
          <label className="field">Password<input type="password" value={p} onChange={(e) => setP(e.target.value)} autoComplete="current-password" /></label>
          {err && <div style={{ color: "#a3191a", fontSize: 13 }}>{err}</div>}
          <button className="primary" type="submit" style={{ justifyContent: "center" }}>Sign in</button>
        </form>
        <div className="creds">
          <div className="faint">Demo accounts (synthetic environment):</div>
          {[["admin", "admin123", "Configure rules, approve policies"], ["analyst", "analyst123", "Run checks, manage gaps"], ["auditor", "auditor123", "Read-only"]].map(([a, b, c]) => (
            <button key={a} type="button" onClick={() => submit(a, b)}><span><b>{a}</b> / {b}</span><span className="faint">{c}</span></button>
          ))}
        </div>
      </div>
    </div>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(getSession());
  const out = () => { logout(); setSession(null); };
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={<Login onLogin={setSession} />} />
        <Route path="*" element={session ? (
          <Layout session={session} onLogout={out}>
            <Routes>
              <Route path="/" element={<Dashboard />} />
              <Route path="/access" element={<AccessControl />} />
              <Route path="/localisation" element={<Localisation />} />
              <Route path="/controls" element={<Controls />} />
              <Route path="/gaps" element={<Gaps />} />
              <Route path="/jurisdictions" element={<Jurisdictions />} />
              <Route path="/inventory" element={<Inventory />} />
              <Route path="/policies" element={<Policies />} />
              <Route path="/stakeholders" element={<Stakeholders />} />
              <Route path="/risk" element={<Risk />} />
              <Route path="/audit" element={<Audit />} />
              <Route path="*" element={<Navigate to="/" />} />
            </Routes>
          </Layout>
        ) : <Navigate to="/login" />} />
      </Routes>
    </HashRouter>
  );
}
