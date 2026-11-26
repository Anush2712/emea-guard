import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { auth, DEMO } from "../api";
import { Mark } from "../components/Mark";
import { EMAIL_RE, passwordChecks, USERNAME_RE } from "../demo/localAuth";

const REGIONS = ["Ireland", "United Kingdom", "Germany", "France", "Netherlands", "Luxembourg", "Switzerland", "Poland", "UAE", "South Africa"];

function Frame({ children }: { children: ReactNode }) {
  return (
    <div className="auth">
      <section className="auth-intro">
        <Mark />
        <h1>Data governance for ten EMEA jurisdictions, in one place.</h1>
        <p>Check every access request against residency, transfer, banking-secrecy and approval rules, test controls each quarter, and track every gap to an owner and a deadline.</p>
        <div className="regions" aria-label="Jurisdictions covered">{REGIONS.map((r) => <span key={r}>{r}</span>)}</div>
      </section>
      <section className="auth-card">{children}</section>
    </div>
  );
}

export function PasswordInput({ value, onChange, label, autoComplete, id }: { value: string; onChange: (v: string) => void; label: string; autoComplete: string; id: string }) {
  const [show, setShow] = useState(false);
  return (
    <label className="field" htmlFor={id}>{label}
      <span className="pw">
        <input id={id} type={show ? "text" : "password"} value={value} onChange={(e) => onChange(e.target.value)} autoComplete={autoComplete} required />
        <button type="button" onClick={() => setShow(!show)} aria-label={show ? "Hide password" : "Show password"}>{show ? "Hide" : "Show"}</button>
      </span>
    </label>
  );
}

export function PasswordRules({ pw, username }: { pw: string; username?: string }) {
  return <ul className="rules">{passwordChecks(pw, username).map((c) => <li key={c.label} className={c.ok ? "ok" : ""}>{c.label}</li>)}</ul>;
}

const Err = ({ msg }: { msg: string | null }) => (msg ? <div className="notice err" role="alert">{msg}</div> : null);

export function SignIn() {
  const [id, setId] = useState(""); const [pw, setPw] = useState("");
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const nav = useNavigate(); const loc = useLocation() as { state?: { from?: string } };
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { await auth.login(id, pw); nav(loc.state?.from ?? "/", { replace: true }); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <Frame>
      <h2>Sign in</h2>
      <form onSubmit={submit}>
        <label className="field">Username or email<input value={id} onChange={(e) => setId(e.target.value)} autoComplete="username" autoCapitalize="none" required /></label>
        <PasswordInput id="pw" label="Password" value={pw} onChange={setPw} autoComplete="current-password" />
        <div style={{ textAlign: "right", marginTop: -6 }}><Link to="/forgot-password">Forgot password?</Link></div>
        <Err msg={err} />
        <button className="primary" disabled={busy}>{busy ? "Signing in…" : "Sign in"}</button>
      </form>
      <div className="alt">New to EMEA Guard? <Link to="/signup">Create an account</Link></div>
    </Frame>
  );
}

export function SignUp() {
  const [f, setF] = useState({ username: "", email: "", full_name: "", pw: "", pw2: "" });
  const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const nav = useNavigate();
  const set = (k: keyof typeof f) => (v: string) => setF({ ...f, [k]: v });
  const userOk = USERNAME_RE.test(f.username), mailOk = EMAIL_RE.test(f.email.trim());
  const pwOk = passwordChecks(f.pw, f.username).every((c) => c.ok), match = f.pw === f.pw2 && f.pw2.length > 0;
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    if (!userOk) return setErr("Username must be 3-30 characters: letters, numbers, dot, dash or underscore.");
    if (!mailOk) return setErr("Enter a valid email address. It's used to reset your password.");
    if (!pwOk) return setErr("Your password doesn't meet the requirements yet.");
    if (!match) return setErr("The two passwords don't match.");
    setBusy(true);
    try { await auth.register(f.username.trim(), f.email.trim(), f.pw, f.full_name); nav("/", { replace: true }); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <Frame>
      <h2>Create your account</h2>
      <p className="faint" style={{ margin: "6px 0 0" }}>The first account on a new installation becomes the administrator. Everyone after that joins as an analyst, and an administrator can change roles.</p>
      <form onSubmit={submit} noValidate>
        <label className="field">Username<input value={f.username} onChange={(e) => set("username")(e.target.value)} autoComplete="username" autoCapitalize="none" placeholder="e.g. anush.c" required /></label>
        <label className="field">Full name (optional)<input value={f.full_name} onChange={(e) => set("full_name")(e.target.value)} autoComplete="name" /></label>
        <label className="field">Email<input type="email" value={f.email} onChange={(e) => set("email")(e.target.value)} autoComplete="email" inputMode="email" required /></label>
        <PasswordInput id="pw1" label="Password" value={f.pw} onChange={set("pw")} autoComplete="new-password" />
        <PasswordRules pw={f.pw} username={f.username} />
        <PasswordInput id="pw2" label="Confirm password" value={f.pw2} onChange={set("pw2")} autoComplete="new-password" />
        {DEMO && <div className="notice">This site isn't connected to the hosted API yet, so your account is stored only in this browser, with the password hashed (PBKDF2).</div>}
        <Err msg={err} />
        <button className="primary" disabled={busy}>{busy ? "Creating account…" : "Create account"}</button>
      </form>
      <div className="alt">Already have an account? <Link to="/login">Sign in</Link></div>
    </Frame>
  );
}

export function ForgotPassword() {
  const [email, setEmail] = useState(""); const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ message: string } | null>(null); const [err, setErr] = useState<string | null>(null);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setBusy(true); setErr(null);
    try { setDone(await auth.forgot(email)); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <Frame>
      <h2>Reset your password</h2>
      <p className="faint" style={{ margin: "6px 0 0" }}>Enter the email on your account. We'll send a link that works once and expires in 30 minutes.</p>
      {done ? (
        <div className="grid" style={{ marginTop: 18 }}>
          <div className="notice ok">{done.message}</div>
        </div>
      ) : (
        <form onSubmit={submit}>
          <label className="field">Email<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" inputMode="email" required /></label>
          <Err msg={err} />
          <button className="primary" disabled={busy}>{busy ? "Sending…" : "Send reset link"}</button>
        </form>
      )}
      <div className="alt"><Link to="/login">Back to sign in</Link></div>
    </Frame>
  );
}

export function ResetPassword() {
  const [params] = useSearchParams();
  const token = params.get("token") ?? "";
  const [pw, setPw] = useState(""); const [pw2, setPw2] = useState("");
  const [err, setErr] = useState<string | null>(null); const [ok, setOk] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const submit = async (e: FormEvent) => {
    e.preventDefault(); setErr(null);
    if (passwordChecks(pw).some((c) => !c.ok)) return setErr("Your new password doesn't meet the requirements yet.");
    if (pw !== pw2) return setErr("The two passwords don't match.");
    setBusy(true);
    try { setOk((await auth.reset(token, pw)).message); } catch (x: any) { setErr(x.message); } finally { setBusy(false); }
  };
  return (
    <Frame>
      <h2>Choose a new password</h2>
      {!token ? <div className="notice err" style={{ marginTop: 16 }}>This page needs the link from your reset email. <Link to="/forgot-password">Request a new link</Link>.</div>
        : ok ? <div className="grid" style={{ marginTop: 16 }}><div className="notice ok">{ok}</div><Link to="/login"><button className="primary" style={{ width: "100%" }}>Sign in</button></Link></div>
        : (
          <form onSubmit={submit}>
            <PasswordInput id="np1" label="New password" value={pw} onChange={setPw} autoComplete="new-password" />
            <PasswordRules pw={pw} />
            <PasswordInput id="np2" label="Confirm new password" value={pw2} onChange={setPw2} autoComplete="new-password" />
            <Err msg={err} />
            <button className="primary" disabled={busy}>{busy ? "Saving…" : "Save new password"}</button>
          </form>
        )}
      <div className="alt"><Link to="/login">Back to sign in</Link></div>
    </Frame>
  );
}
