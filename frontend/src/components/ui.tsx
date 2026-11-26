import { useCallback, useEffect, useMemo, useState, type ReactNode } from "react";
import { api } from "../api";

// ------------------------------------------------------------------ data hook
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(!!path);
  const load = useCallback(() => {
    if (!path) return;
    setLoading(true);
    api.get<T>(path).then((d) => { setData(d); setError(null); }).catch((e) => setError(e.message)).finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, ...deps]);
  useEffect(load, [load]);
  return { data, error, loading, reload: load, setData };
}

// ------------------------------------------------------------------ toast
let pushToast: (msg: string, err?: boolean) => void = () => {};
export const toast = (msg: string, err = false) => pushToast(msg, err);
export function ToastHost() {
  const [t, setT] = useState<{ msg: string; err: boolean } | null>(null);
  useEffect(() => {
    pushToast = (msg, err = false) => { setT({ msg, err }); setTimeout(() => setT(null), 4200); };
  }, []);
  return t ? <div className={`toast ${t.err ? "err" : ""}`} role="status">{t.msg}</div> : null;
}

// ------------------------------------------------------------------ layout bits
export function PageHead({ title, desc, actions }: { title: string; desc?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="page-head">
      <div><h1>{title}</h1>{desc && <p>{desc}</p>}</div>
      {actions && <div className="actions">{actions}</div>}
    </div>
  );
}

export function Card({ title, sub, right, children, className = "" }: { title?: ReactNode; sub?: ReactNode; right?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || right) && <div className="card-head"><h2>{title}</h2>{sub && <span className="sub">{sub}</span>}<div className="right">{right}</div></div>}
      {children}
    </section>
  );
}

export function Kpi({ label, value, unit, hint }: { label: string; value: ReactNode; unit?: string; hint?: ReactNode }) {
  return (
    <div className="card kpi">
      <div className="label">{label}</div>
      <div className="value">{value}{unit && <small>{unit}</small>}</div>
      {hint && <div className="hint">{hint}</div>}
    </div>
  );
}

export const Loading = ({ what = "data" }: { what?: string }) => <div className="loading">Loading {what}…</div>;
export const ErrorBox = ({ error }: { error: string }) => <div className="card" style={{ color: "#8c1415" }}>Could not load: {error}</div>;

// ------------------------------------------------------------------ badges (status colour always paired with an icon + label)
const SEV_ICON: Record<string, string> = { Critical: "▲", High: "◆", Medium: "●", Low: "▼" };
export function Sev({ s }: { s: string | null | undefined }) {
  if (!s) return <span className="faint">—</span>;
  return <span className={`badge sev-${s}`}><span aria-hidden>{SEV_ICON[s]}</span>{s}</span>;
}
const DEC: Record<string, [string, string]> = {
  APPROVED: ["b-good", "✓ Approved"], APPROVED_WITH_FINDINGS: ["b-blue", "✓ Approved · findings"],
  PENDING_APPROVAL: ["b-warn", "⧗ Pending approval"], DENIED: ["b-bad", "✕ Denied"],
};
export const DecisionBadge = ({ d }: { d: string }) => <span className={`badge ${DEC[d]?.[0] ?? "b-neutral"}`}>{DEC[d]?.[1] ?? d}</span>;
const STATUS: Record<string, string> = {
  Open: "b-bad", "In Remediation": "b-warn", Resolved: "b-good", "Risk Accepted": "b-neutral", Completed: "b-good", "In Progress": "b-warn",
  "Not Started": "b-neutral", Effective: "b-good", "Partially Effective": "b-warn", Ineffective: "b-bad", "Not Applicable": "b-neutral",
  Published: "b-good", Superseded: "b-neutral", "In Review": "b-warn", Draft: "b-neutral", Active: "b-good", Onboarding: "b-warn",
  Valid: "b-good", Expired: "b-bad", "TIA missing": "b-warn", Expiring: "b-warn", Compliant: "b-good", "Adequate destination": "b-good",
  "Covered by mechanism": "b-blue", "Residency breach": "b-bad", "No transfer mechanism": "b-bad", "Mechanism expired": "b-bad",
  Done: "b-good", Blocked: "b-bad", "At Risk": "b-bad", Planned: "b-neutral", Terminated: "b-bad", Leave: "b-warn",
};
export const Status = ({ s }: { s: string }) => <span className={`badge ${STATUS[s] ?? "b-neutral"}`}>{s}</span>;
export const Flag = ({ on, yes = "Yes", no = "No", invert = false }: { on: boolean; yes?: string; no?: string; invert?: boolean }) =>
  <span className={`badge ${on !== invert ? "b-good" : "b-bad"}`}>{on ? yes : no}</span>;

// ------------------------------------------------------------------ table
export interface Col<T> { key: string; label: string; render?: (r: T) => ReactNode; sort?: (r: T) => string | number; num?: boolean; width?: number }

export function DataTable<T extends { id?: number | string }>({ rows, cols, onRow, selectedId, maxRows = 500, empty = "No rows" }: {
  rows: T[]; cols: Col<T>[]; onRow?: (r: T) => void; selectedId?: number | string | null; maxRows?: number; empty?: string;
}) {
  const [sortKey, setSortKey] = useState<string | null>(null);
  const [asc, setAsc] = useState(true);
  const sorted = useMemo(() => {
    const c = cols.find((x) => x.key === sortKey);
    if (!c) return rows;
    const f = c.sort ?? ((r: any) => r[c.key]);
    return [...rows].sort((a, b) => { const x = f(a), y = f(b); return (x > y ? 1 : x < y ? -1 : 0) * (asc ? 1 : -1); });
  }, [rows, cols, sortKey, asc]);
  const shown = sorted.slice(0, maxRows);
  return (
    <>
      <div className="table-wrap">
        <table>
          <thead><tr>{cols.map((c) => (
            <th key={c.key} className={`sortable ${c.num ? "num" : ""}`} style={c.width ? { width: c.width } : undefined}
              onClick={() => { if (sortKey === c.key) setAsc(!asc); else { setSortKey(c.key); setAsc(true); } }}>
              {c.label}{sortKey === c.key ? (asc ? " ↑" : " ↓") : ""}
            </th>))}</tr></thead>
          <tbody>
            {shown.map((r, i) => (
              <tr key={(r.id as any) ?? i} className={`${onRow ? "clickable" : ""} ${selectedId !== undefined && r.id === selectedId ? "sel" : ""}`} onClick={() => onRow?.(r)}>
                {cols.map((c) => <td key={c.key} className={c.num ? "num" : ""}>{c.render ? c.render(r) : String((r as any)[c.key] ?? "")}</td>)}
              </tr>))}
            {!rows.length && <tr><td colSpan={cols.length} className="empty">{empty}</td></tr>}
          </tbody>
        </table>
      </div>
      <div className="table-foot">{rows.length > maxRows ? `Showing ${maxRows} of ${rows.length}` : `${rows.length} rows`}</div>
    </>
  );
}

// ------------------------------------------------------------------ drawer
export function Drawer({ title, sub, onClose, children }: { title: ReactNode; sub?: ReactNode; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);
  return (
    <>
      <div className="drawer-backdrop" onClick={onClose} />
      <aside className="drawer" role="dialog" aria-modal="true">
        <div className="drawer-head"><div style={{ flex: 1 }}><h2>{title}</h2>{sub && <div className="faint">{sub}</div>}</div>
          <button onClick={onClose} aria-label="Close">✕</button></div>
        <div className="drawer-body">{children}</div>
      </aside>
    </>
  );
}

export function Tabs({ tabs, value, onChange }: { tabs: string[]; value: string; onChange: (t: string) => void }) {
  return <div className="tabs" role="tablist">{tabs.map((t) => <button key={t} role="tab" aria-selected={t === value} className={t === value ? "on" : ""} onClick={() => onChange(t)}>{t}</button>)}</div>;
}

export function Bar({ pct, color }: { pct: number; color?: string }) {
  return <div className="bar-track"><div className="bar-fill" style={{ width: `${Math.max(0, Math.min(100, pct))}%`, background: color }} /></div>;
}

export const fmtDate = (s: string | null | undefined) => (s ? new Date(s.length <= 10 ? s + "T00:00:00Z" : s + (s.endsWith("Z") ? "" : "Z")).toLocaleDateString("en-IE", { day: "2-digit", month: "short", year: "numeric", timeZone: "UTC" }) : "—");
export const fmtDateTime = (s: string | null | undefined) => (s ? new Date(s + (s.endsWith("Z") ? "" : "Z")).toLocaleString("en-IE", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) : "—");

export function uniq<T>(xs: T[]): T[] { return Array.from(new Set(xs)).sort() as T[]; }
