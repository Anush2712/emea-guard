import { demoRequest } from "./demo/demoApi";

export const DEMO = import.meta.env.VITE_DEMO === "true";
const API_BASE: string = import.meta.env.VITE_API_URL ?? "";
const TOKEN_KEY = "emea-guard-token";

export interface Session { token: string; role: string; full_name: string; username: string }

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}
let session: Session | null = readSession();

export const getSession = () => session;

export function logout() {
  session = null;
  try { localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export async function login(username: string, password: string): Promise<Session> {
  let s: Session;
  if (DEMO) {
    const users: Record<string, [string, string, string]> = {
      admin: ["admin123", "admin", "Governance Administrator"], analyst: ["analyst123", "analyst", "Governance Analyst"],
      auditor: ["auditor123", "auditor", "Internal Auditor (read-only)"],
    };
    const u = users[username];
    if (!u || u[0] !== password) throw new ApiError(401, "Incorrect username or password");
    s = { token: "demo", role: u[1], full_name: u[2], username };
  } else {
    const res = await fetch(`${API_BASE}/api/auth/login`, {
      method: "POST", headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password }),
    });
    if (!res.ok) throw new ApiError(res.status, (await res.json().catch(() => ({}))).detail ?? "Login failed");
    const j = await res.json();
    s = { token: j.access_token, role: j.role, full_name: j.full_name, username };
  }
  session = s;
  try { localStorage.setItem(TOKEN_KEY, JSON.stringify(s)); } catch { /* storage unavailable */ }
  return s;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  if (DEMO) return demoRequest<T>(method, path, body, session);
  const res = await fetch(`${API_BASE}${path}`, {
    method,
    headers: { "Content-Type": "application/json", ...(session ? { Authorization: `Bearer ${session.token}` } : {}) },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (res.status === 401) {
    logout();
    window.location.hash = "#/login";
  }
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    const detail = typeof j.detail === "string" ? j.detail : j.detail?.message ?? JSON.stringify(j.detail ?? j);
    throw new ApiError(res.status, detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body: unknown = {}) => request<T>("POST", path, body),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, body),
};

const REPORT_FILES: Record<string, string> = {
  "risk-report.xlsx": "emea-guard-risk-report.xlsx", "gaps.csv": "emea-guard-gaps.csv", "executive.html": "emea-guard-executive-report.html",
};

/** Download a generated report (authenticated fetch in full-stack mode; static file in the demo). */
export async function downloadReport(name: keyof typeof REPORT_FILES | string) {
  const file = REPORT_FILES[name];
  if (DEMO) {
    const a = document.createElement("a");
    a.href = `${import.meta.env.BASE_URL}demo/reports/${file}`;
    a.download = file;
    a.click();
    return;
  }
  const res = await fetch(`${API_BASE}/api/reports/${name}`, { headers: { Authorization: `Bearer ${session?.token}` } });
  if (!res.ok) throw new ApiError(res.status, "Report generation failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = file;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}
