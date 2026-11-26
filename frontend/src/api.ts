import { demoRequest } from "./demo/demoApi";
import { localChangePassword, localLogin, localRegister, localRole, localUpdateUser, localUsers } from "./demo/localAuth";

const API_BASE: string = import.meta.env.VITE_API_URL ?? "";
/** Static build with no API: data comes from the bundled snapshot and accounts live in this browser. */
export const DEMO = import.meta.env.VITE_DEMO === "true" && !API_BASE;
const TOKEN_KEY = "emea-guard-session";

export interface Session { token: string; role: string; full_name: string; username: string }
export interface Account { id: number; username: string; email: string; full_name: string; role: string; is_active: boolean; created_at: string | null; last_login_at: string | null }

function readSession(): Session | null {
  try {
    const raw = localStorage.getItem(TOKEN_KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}
let session: Session | null = readSession();
if (session && DEMO) {
  // keep the role in sync with what an admin set for this local account
  const r = localRole(session.username);
  if (!r) session = null;
  else session.role = r;
}
const listeners = new Set<(s: Session | null) => void>();
export const onSession = (fn: (s: Session | null) => void) => { listeners.add(fn); return () => listeners.delete(fn); };

export const getSession = () => session;
function setSession(s: Session | null) {
  session = s;
  try { s ? localStorage.setItem(TOKEN_KEY, JSON.stringify(s)) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage unavailable */ }
  listeners.forEach((l) => l(s));
}
export const logout = () => setSession(null);

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function raw<T>(method: string, path: string, body?: unknown, form = false): Promise<T> {
  const headers: Record<string, string> = session ? { Authorization: `Bearer ${session.token}` } : {};
  if (!form) headers["Content-Type"] = "application/json";
  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method, headers,
      body: body === undefined ? undefined : form ? new URLSearchParams(body as Record<string, string>) : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection and try again.");
  }
  if (res.status === 401 && session && !path.startsWith("/api/auth/")) {
    setSession(null);
    window.location.hash = "#/login";
  }
  if (!res.ok) {
    const j = await res.json().catch(() => ({}));
    const d = j.detail;
    const msg = typeof d === "string" ? d : Array.isArray(d) ? d.map((x: any) => x.msg).join("; ") : d?.message ?? res.statusText;
    throw new ApiError(res.status, msg || "Request failed");
  }
  return res.json() as Promise<T>;
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  if (DEMO) return demoRequest<T>(method, path, body, session);
  return raw<T>(method, path, body);
}

export const api = {
  get: <T,>(path: string) => request<T>("GET", path),
  post: <T,>(path: string, body: unknown = {}) => request<T>("POST", path, body),
  patch: <T,>(path: string, body: unknown) => request<T>("PATCH", path, body),
};

const fromToken = (j: any, username: string): Session => ({ token: j.access_token, role: j.role, full_name: j.full_name, username: j.username ?? username });

// ------------------------------------------------------------------ accounts
export const auth = {
  async login(identifier: string, password: string) {
    if (DEMO) {
      const u = await localLogin(identifier, password);
      return setSession({ token: "local", role: u.role, full_name: u.full_name, username: u.username });
    }
    setSession(fromToken(await raw("POST", "/api/auth/login", { username: identifier, password }, true), identifier));
  },
  async register(username: string, email: string, password: string, full_name?: string) {
    if (DEMO) {
      const u = await localRegister(username, email, password, full_name);
      return setSession({ token: "local", role: u.role, full_name: u.full_name, username: u.username });
    }
    setSession(fromToken(await raw("POST", "/api/auth/register", { username, email, password, full_name: full_name || null }), username));
  },
  async changePassword(current_password: string, new_password: string) {
    if (DEMO) return localChangePassword(session!.username, current_password, new_password);
    const j = await raw<any>("POST", "/api/auth/change-password", { current_password, new_password });
    if (j.access_token) setSession(fromToken(j, session!.username));
  },
  async forgot(email: string): Promise<{ message: string }> {
    if (DEMO) throw new ApiError(503, "Password reset by email needs the hosted API. Accounts on this static site are stored only in this browser.");
    return raw("POST", "/api/auth/forgot-password", { email });
  },
  async reset(token: string, new_password: string): Promise<{ message: string }> {
    if (DEMO) throw new ApiError(503, "Password reset needs the hosted API.");
    return raw("POST", "/api/auth/reset-password", { token, new_password });
  },
  async me(): Promise<Account> {
    if (DEMO) return localUsers().find((u) => u.username === session?.username) as Account;
    return raw("GET", "/api/auth/me");
  },
  async users(): Promise<Account[]> {
    if (DEMO) return localUsers() as Account[];
    return raw("GET", "/api/users");
  },
  async updateUser(id: number, patch: { app_role?: string; is_active?: boolean }): Promise<Account> {
    if (DEMO) return localUpdateUser(id, patch) as Account;
    return raw("PATCH", `/api/users/${id}`, patch);
  },
};

const REPORT_FILES: Record<string, string> = {
  "risk-report.xlsx": "emea-guard-risk-report.xlsx", "gaps.csv": "emea-guard-gaps.csv", "executive.html": "emea-guard-executive-report.html",
};

/** Download a generated report (authenticated fetch against the API; bundled file in the static build). */
export async function downloadReport(name: string) {
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
