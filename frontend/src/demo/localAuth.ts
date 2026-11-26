/**
 * Browser-only accounts for the static build (no API configured). Passwords are hashed with
 * PBKDF2-SHA256 (210k iterations, random salt) via WebCrypto and kept in localStorage on this device.
 * With VITE_API_URL set, none of this is used: accounts live in PostgreSQL behind the FastAPI auth API.
 */
const KEY = "emea-guard-local-accounts";

export interface LocalUser {
  id: number; username: string; email: string; full_name: string; role: string; is_active: boolean;
  salt: string; hash: string; created_at: string; last_login_at: string | null;
}

const enc = new TextEncoder();
const b64 = (buf: ArrayBuffer | Uint8Array) => btoa(String.fromCharCode(...new Uint8Array(buf)));
const unb64 = (s: string) => Uint8Array.from(atob(s), (c) => c.charCodeAt(0));

async function derive(password: string, salt: Uint8Array): Promise<string> {
  const key = await crypto.subtle.importKey("raw", enc.encode(password), "PBKDF2", false, ["deriveBits"]);
  const bits = await crypto.subtle.deriveBits({ name: "PBKDF2", hash: "SHA-256", salt, iterations: 210000 }, key, 256);
  return b64(bits);
}

function load(): LocalUser[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? "[]"); } catch { return []; }
}
function save(users: LocalUser[]) {
  try { localStorage.setItem(KEY, JSON.stringify(users)); } catch { throw new Error("This browser blocks local storage, so accounts can't be saved here."); }
}

export class AuthError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

export const USERNAME_RE = /^[a-zA-Z0-9][a-zA-Z0-9_.-]{2,29}$/;
export const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export function passwordChecks(pw: string, username = "") {
  return [
    { label: "At least 10 characters", ok: pw.length >= 10 },
    { label: "A letter and a number", ok: /[A-Za-z]/.test(pw) && /\d/.test(pw) },
    { label: "Doesn't contain your username", ok: !username || !pw.toLowerCase().includes(username.toLowerCase()) },
  ];
}

const publicUser = ({ salt: _s, hash: _h, ...u }: LocalUser) => u;

export async function localRegister(username: string, email: string, password: string, full_name?: string) {
  const users = load();
  if (!USERNAME_RE.test(username)) throw new AuthError(422, "Username must be 3-30 characters: letters, numbers, dot, dash or underscore.");
  const mail = email.trim().toLowerCase();
  if (!EMAIL_RE.test(mail)) throw new AuthError(422, "Enter a valid email address.");
  if (passwordChecks(password, username).some((c) => !c.ok)) throw new AuthError(422, "Password doesn't meet the requirements yet.");
  if (users.some((u) => u.username.toLowerCase() === username.toLowerCase())) throw new AuthError(409, "That username is taken. Choose another.");
  if (users.some((u) => u.email === mail)) throw new AuthError(409, "An account with that email already exists. Sign in instead.");
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const now = new Date().toISOString();
  const user: LocalUser = { id: (users.at(-1)?.id ?? 0) + 1, username, email: mail, full_name: full_name?.trim() || username,
    role: users.length === 0 ? "admin" : "analyst", is_active: true, salt: b64(salt), hash: await derive(password, salt), created_at: now, last_login_at: now };
  save([...users, user]);
  return publicUser(user);
}

export async function localLogin(identifier: string, password: string) {
  const users = load();
  const id = identifier.trim().toLowerCase();
  const u = users.find((x) => x.username.toLowerCase() === id || x.email === id);
  if (!u || (await derive(password, unb64(u.salt))) !== u.hash) throw new AuthError(401, "Incorrect username or password.");
  if (!u.is_active) throw new AuthError(403, "This account is disabled.");
  u.last_login_at = new Date().toISOString();
  save(users);
  return publicUser(u);
}

export async function localChangePassword(username: string, current: string, next: string) {
  const users = load();
  const u = users.find((x) => x.username === username);
  if (!u || (await derive(current, unb64(u.salt))) !== u.hash) throw new AuthError(400, "Your current password is incorrect.");
  if (passwordChecks(next, username).some((c) => !c.ok)) throw new AuthError(422, "New password doesn't meet the requirements.");
  const salt = crypto.getRandomValues(new Uint8Array(16));
  u.salt = b64(salt);
  u.hash = await derive(next, salt);
  save(users);
}

export const localUsers = () => load().map(publicUser);

export function localUpdateUser(id: number, patch: { app_role?: string; is_active?: boolean }) {
  const users = load();
  const u = users.find((x) => x.id === id);
  if (!u) throw new AuthError(404, "Not found");
  const demoting = (patch.app_role && patch.app_role !== "admin") || patch.is_active === false;
  if (u.role === "admin" && demoting && users.filter((x) => x.role === "admin" && x.is_active).length <= 1)
    throw new AuthError(409, "There must always be at least one active admin.");
  if (patch.app_role) u.role = patch.app_role;
  if (patch.is_active !== undefined) u.is_active = patch.is_active;
  save(users);
  return publicUser(u);
}

export const localRole = (username: string) => load().find((u) => u.username === username)?.role;
