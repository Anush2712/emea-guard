import { useEffect, useRef, useState, type ReactNode } from "react";
import { HashRouter, Link, Navigate, NavLink, Route, Routes, useLocation } from "react-router-dom";
import { getSession, logout, onSession, type Session } from "./api";
import { Mark } from "./components/Mark";
import { ToastHost } from "./components/ui";
import Account from "./pages/Account";
import AccessControl from "./pages/AccessControl";
import Audit from "./pages/Audit";
import { ForgotPassword, ResetPassword, SignIn, SignUp } from "./pages/Auth";
import Controls from "./pages/Controls";
import Dashboard from "./pages/Dashboard";
import Gaps from "./pages/Gaps";
import Inventory from "./pages/Inventory";
import Jurisdictions from "./pages/Jurisdictions";
import Localisation from "./pages/Localisation";
import Policies from "./pages/Policies";
import Risk from "./pages/Risk";
import Stakeholders from "./pages/Stakeholders";

const I = (d: string) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden><path d={d} /></svg>;
export const NAV: { group: string; items: [string, string, ReactNode][] }[] = [
  { group: "Overview", items: [["/", "Governance dashboard", I("M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z")]] },
  { group: "Controls", items: [
    ["/access", "Access control", I("M12 11V7a4 4 0 0 1 8 0M5 11h14v10H5z")],
    ["/localisation", "Data localisation", I("M12 21s-7-6.2-7-11a7 7 0 0 1 14 0c0 4.8-7 11-7 11zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z")],
    ["/controls", "Control assessments", I("M9 11l3 3 8-8M20 12v7a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h9")],
    ["/gaps", "Gaps and remediation", I("M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z")],
  ] },
  { group: "Governance", items: [
    ["/jurisdictions", "Jurisdictions", I("M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zM2 12h20M12 2a15 15 0 0 1 0 20M12 2a15 15 0 0 0 0 20")],
    ["/inventory", "Data and people", I("M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3zM4 6v12c0 1.7 3.6 3 8 3s8-1.3 8-3V6M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3")],
    ["/policies", "Policies", I("M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zM14 2v6h6M8 13h8M8 17h5")],
    ["/stakeholders", "Stakeholders and projects", I("M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.9M16 3.1a4 4 0 0 1 0 7.8")],
  ] },
  { group: "Assurance", items: [
    ["/risk", "Risk and reports", I("M3 3v18h18M7 15l4-4 3 3 6-7")],
    ["/audit", "Audit trail", I("M12 8v4l3 3M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5")],
  ] },
];
const TITLES: Record<string, string> = Object.fromEntries(NAV.flatMap((g) => g.items.map(([to, label]) => [to, label])).concat([["/account", "Account"]]));


function Shell({ session, children }: { session: Session; children: ReactNode }) {
  const [menu, setMenu] = useState(false);
  const [acct, setAcct] = useState(false);
  const loc = useLocation();
  const burgerRef = useRef<HTMLButtonElement>(null);
  const sheetRef = useRef<HTMLElement>(null);
  useEffect(() => { setMenu(false); setAcct(false); window.scrollTo(0, 0); }, [loc.pathname]);
  useEffect(() => {
    if (!menu && !acct) return;
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") { setMenu(false); setAcct(false); burgerRef.current?.focus(); } };
    window.addEventListener("keydown", h);
    if (menu) (sheetRef.current?.querySelector<HTMLElement>(".nav-group a.active") ?? sheetRef.current?.querySelector<HTMLElement>(".nav-group a"))?.focus();
    return () => window.removeEventListener("keydown", h);
  }, [menu, acct]);
  const initials = (session.full_name || session.username).split(/\s+/).map((w) => w[0]).join("").slice(0, 2).toUpperCase();

  return (
    <div className="app">
      <header className="topbar">
        <button ref={burgerRef} className="burger" aria-label="Open menu" aria-expanded={menu} aria-controls="nav-sheet" onClick={() => setMenu(!menu)}><span /></button>
        <Mark />
        <div className="crumb">{TITLES[loc.pathname] ?? ""}</div>
        <div className="spacer" />
        <button className="avatar" aria-label="Account menu" aria-expanded={acct} onClick={() => setAcct(!acct)}>{initials}</button>
        {acct && (
          <div className="popover" role="menu">
            <div className="who"><b>{session.full_name}</b><span className="faint">@{session.username} · {session.role}</span></div>
            <Link to="/account" role="menuitem">Account and password</Link>
            {session.role === "admin" && <Link to="/account#users" role="menuitem">Manage users</Link>}
            <button role="menuitem" onClick={logout}>Sign out</button>
          </div>
        )}
      </header>
      {menu && (
        <>
          <div className="scrim" onClick={() => setMenu(false)} />
          <nav id="nav-sheet" className="sheet nav" ref={sheetRef} aria-label="Main">
            <div className="sheet-head"><Mark /><button className="burger" aria-label="Close menu" aria-expanded="true" onClick={() => setMenu(false)}><span /></button></div>
            {NAV.map((g) => (
              <div key={g.group} className="nav-group">
                <div>{g.group}</div>
                {g.items.map(([to, label, icon]) => <NavLink key={to} to={to} end={to === "/"}>{icon}{label}</NavLink>)}
              </div>
            ))}
            <div className="sheet-foot">All records in EMEA Guard are synthetic, generated for demonstration.</div>
          </nav>
        </>
      )}
      <main className="content">{children}</main>
    </div>
  );
}

function Protected({ session }: { session: Session | null }) {
  const loc = useLocation();
  if (!session) return <Navigate to="/login" state={{ from: loc.pathname }} replace />;
  return (
    <Shell session={session}>
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
        <Route path="/account" element={<Account />} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </Shell>
  );
}

export default function App() {
  const [session, setSession] = useState<Session | null>(getSession());
  useEffect(() => { onSession(setSession); }, []);
  return (
    <HashRouter>
      <Routes>
        <Route path="/login" element={session ? <Navigate to="/" replace /> : <SignIn />} />
        <Route path="/signup" element={session ? <Navigate to="/" replace /> : <SignUp />} />
        <Route path="/forgot-password" element={<ForgotPassword />} />
        <Route path="/reset-password" element={<ResetPassword />} />
        <Route path="*" element={<Protected session={session} />} />
      </Routes>
      <ToastHost />
    </HashRouter>
  );
}
