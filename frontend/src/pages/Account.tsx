import { useEffect, useState, type FormEvent } from "react";
import { useLocation } from "react-router-dom";
import { auth, DEMO, getSession, type Account as Acct } from "../api";
import { Card, DataTable, fmtDate, fmtDateTime, PageHead, Status, toast } from "../components/ui";
import { PasswordInput, PasswordRules } from "./Auth";

export default function Account() {
  const s = getSession()!;
  const loc = useLocation();
  const [me, setMe] = useState<Acct | null>(null);
  const [users, setUsers] = useState<Acct[] | null>(null);
  const [f, setF] = useState({ current: "", next: "", confirm: "" });
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const isAdmin = s.role === "admin";

  useEffect(() => { auth.me().then(setMe).catch(() => {}); if (isAdmin) auth.users().then(setUsers).catch((e) => toast(e.message, true)); }, [isAdmin]);
  useEffect(() => { if (loc.hash === "#users" || loc.pathname.endsWith("users")) document.getElementById("users")?.scrollIntoView(); }, [loc, users]);

  const change = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    if (f.next !== f.confirm) return setErr("The new passwords don't match.");
    setBusy(true);
    try { await auth.changePassword(f.current, f.next); setF({ current: "", next: "", confirm: "" }); toast("Password changed. Other signed-in sessions have been signed out."); }
    catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  const update = async (u: Acct, patch: { app_role?: string; is_active?: boolean }) => {
    try { const n = await auth.updateUser(u.id, patch); setUsers((xs) => xs!.map((x) => (x.id === u.id ? n : x))); toast(`${u.username} updated`); }
    catch (x: any) { toast(x.message, true); }
  };

  return (
    <>
      <PageHead title="Account" desc="Your profile and password. Passwords are stored only as salted hashes; a reset link from the sign-in page goes to your email." />
      <div className="grid g2">
        <Card title="Profile">
          <dl className="kv">
            <dt>Username</dt><dd>@{s.username}</dd>
            <dt>Name</dt><dd>{s.full_name}</dd>
            <dt>Email</dt><dd>{me?.email ?? "—"}</dd>
            <dt>Role</dt><dd><Status s={s.role} /> <span className="faint">{{ admin: "Full access, including users, rules and policy approval", analyst: "Run checks, manage gaps, draft policies", auditor: "Read-only" }[s.role]}</span></dd>
            <dt>Member since</dt><dd>{fmtDate(me?.created_at ?? null)}</dd>
            <dt>Last sign-in</dt><dd>{fmtDateTime(me?.last_login_at ?? null)}</dd>
          </dl>
          {DEMO && <p className="notice" style={{ marginTop: 14 }}>This account is stored in this browser only. Connect the hosted API to keep accounts in the database and enable email resets.</p>}
        </Card>
        <Card title="Change password">
          <form className="grid" style={{ gap: 12 }} onSubmit={change}>
            <PasswordInput id="cur" label="Current password" value={f.current} onChange={(v) => setF({ ...f, current: v })} autoComplete="current-password" />
            <PasswordInput id="new" label="New password" value={f.next} onChange={(v) => setF({ ...f, next: v })} autoComplete="new-password" />
            <PasswordRules pw={f.next} username={s.username} />
            <PasswordInput id="new2" label="Confirm new password" value={f.confirm} onChange={(v) => setF({ ...f, confirm: v })} autoComplete="new-password" />
            {err && <div className="notice err" role="alert">{err}</div>}
            <button className="primary" disabled={busy}>{busy ? "Saving…" : "Change password"}</button>
          </form>
        </Card>
      </div>
      {isAdmin && (
        <div id="users" className="mt">
          <Card title="Users" sub={users ? `${users.length} accounts` : undefined}>
            <DataTable rows={users ?? []} empty="Loading accounts…" cols={[
              { key: "username", label: "Username", render: (u) => <><b>@{u.username}</b><div className="faint">{u.full_name}</div></> },
              { key: "email", label: "Email" },
              { key: "role", label: "Role", render: (u) => <select aria-label={`Role for ${u.username}`} value={u.role} onChange={(e) => update(u, { app_role: e.target.value })}>{["admin", "analyst", "auditor"].map((r) => <option key={r}>{r}</option>)}</select> },
              { key: "is_active", label: "Status", render: (u) => <label className="check"><input type="checkbox" checked={u.is_active} onChange={(e) => update(u, { is_active: e.target.checked })} />{u.is_active ? "Active" : "Disabled"}</label> },
              { key: "created_at", label: "Joined", render: (u) => fmtDate(u.created_at) },
              { key: "last_login_at", label: "Last sign-in", render: (u) => fmtDateTime(u.last_login_at) },
            ]} />
          </Card>
        </div>
      )}
    </>
  );
}
