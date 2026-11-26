import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { api, getSession } from "../api";
import { Card, DataTable, DecisionBadge, Drawer, ErrorBox, fmtDateTime, Loading, PageHead, Sev, Tabs, toast, uniq, useApi } from "../components/ui";
import type { AccessRequestRow, Asset, Employee, Role, Trace } from "../types";

const APPROVALS = [["LINE_MANAGER", "Line manager"], ["DATA_OWNER", "Data owner"], ["DPO", "Data Protection Officer"]] as const;
const PURPOSES = ["Analytics", "Client Servicing", "Financial Reporting", "Fraud Prevention", "HR Administration", "KYC/AML", "Marketing",
  "Model Development", "Payment Processing", "Payroll", "Regulatory Reporting", "Risk Management", "Surveillance", "Trading", "Product Testing", "Ad-hoc Investigation"];

interface Form { empJ: string; employee_id: number | ""; assetJ: string; asset_id: number | ""; access_type: string; purpose: string; ticket_ref: string; justification: string; approvals: string[] }

export function TraceView({ trace }: { trace: Trace }) {
  const failedSteps = new Set<number>();
  if (trace.rules.some((r) => !r.passed && r.code === "ACC-001")) failedSteps.add(4);
  if (trace.rules.some((r) => !r.passed && r.category === "Approvals")) failedSteps.add(5);
  if (trace.rules.some((r) => !r.passed)) failedSteps.add(6);
  if (trace.rules.some((r) => !r.passed && r.raises_gap)) failedSteps.add(7);
  return (
    <div className="grid" style={{ gap: 14 }}>
      <div className={`decision d-${trace.decision}`}>
        <div><div className="big">{trace.decision.replace(/_/g, " ")}</div><div style={{ fontSize: 12.5 }}>{trace.reason}</div></div>
        <div style={{ marginLeft: "auto", textAlign: "right" }}>
          <div style={{ fontSize: 22, fontWeight: 700 }}>{trace.risk_score.toFixed(0)}<small style={{ fontSize: 12 }}>/100</small></div>
          <Sev s={trace.risk_rating} />
        </div>
      </div>
      {trace.gaps?.length ? <div className="faint">Compliance gaps raised: <b className="mono">{trace.gaps.join(", ")}</b> (routed to an owner with an SLA deadline; see Gaps & remediation)</div> : null}
      <div>
        <h3 style={{ marginBottom: 8 }}>Control pipeline</h3>
        <ol className="pipeline">
          {trace.steps.map((s) => (
            <li key={s.step}><div className={`step-num ${failedSteps.has(s.step) ? "bad" : ""}`}>{s.step}</div>
              <div><div className="step-name">{s.name}</div><div className="step-detail">{s.detail}</div></div></li>
          ))}
        </ol>
      </div>
      <div>
        <h3 style={{ marginBottom: 8 }}>Rule evaluation ({trace.rules.length} rules)</h3>
        <div className="table-wrap" style={{ maxHeight: 420 }}>
          <table>
            <thead><tr><th>Rule</th><th>Result</th><th>Severity</th><th>Effect</th><th>Detail</th></tr></thead>
            <tbody>
              {[...trace.rules].sort((a, b) => Number(a.passed) - Number(b.passed) || Number(b.applicable) - Number(a.applicable)).map((r) => (
                <tr key={r.code}>
                  <td><span className="mono">{r.code}</span><div className="faint">{r.name}</div></td>
                  <td>{!r.applicable ? <span className="badge b-neutral">N/A</span> : r.passed ? <span className="badge b-good">✓ Pass</span> : <span className="badge b-bad">✕ Fail</span>}</td>
                  <td><Sev s={r.severity} /></td>
                  <td className="faint">{r.effect}{r.raises_gap ? " · gap" : ""}</td>
                  <td style={{ fontSize: 12.5 }}>{r.message}<div className="faint">{r.requirement_codes.join(", ")}</div></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function Simulator({ employees, assets, roles, onDone }: { employees: Employee[]; assets: Asset[]; roles: Role[]; onDone: () => void }) {
  const [params] = useSearchParams();
  const [f, setF] = useState<Form>({ empJ: "DE", employee_id: "", assetJ: "IE", asset_id: "", access_type: "read", purpose: "Analytics", ticket_ref: "", justification: "", approvals: ["LINE_MANAGER", "DATA_OWNER"] });
  const [result, setResult] = useState<AccessRequestRow | null>(null);
  const [busy, setBusy] = useState(false);
  const canWrite = getSession()?.role !== "auditor";
  const jurs = uniq(employees.map((e) => e.jurisdiction));
  const emp = employees.find((e) => e.id === f.employee_id);
  const asset = assets.find((a) => a.id === f.asset_id);
  const role = roles.find((r) => r.name === emp?.role);
  const set = (p: Partial<Form>) => setF((x) => ({ ...x, ...p }));

  const presets = useMemo(() => {
    const recent = (e: Employee) => e.status === "Active" && !!e.last_training_date && e.last_training_date > "2026-01-01";
    const can = (e: Employee, a: Asset, t = "read") => roles.find((r) => r.name === e.role)?.permissions.some((p) =>
      (p.domain === a.domain || p.domain === "*") && p.max_classification >= (a.classification_level ?? 4) && p.access_types.includes(t));
    // find the first (employee, asset) pair matching a scenario's conditions
    const pair = (ej: string, ep: (e: Employee) => boolean, ap: (a: Asset) => boolean) => {
      for (const a of assets.filter(ap)) {
        const e = employees.find((x) => x.jurisdiction === ej && ep(x) && can(x, a));
        if (e) return { e, a };
      }
      return null;
    };
    const clean = (a: Asset) => !!a.owner_id && a.encrypted_at_rest && !!a.classification_level && (!a.is_third_party_hosted || !!a.processor_agreement_ref);
    const out: { label: string; form: Partial<Form> }[] = [];
    const add = (label: string, p: { e: Employee; a: Asset } | null, approvals: string[]) => p && out.push({ label, form: {
      empJ: p.e.jurisdiction, employee_id: p.e.id, assetJ: p.a.jurisdiction, asset_id: p.a.id, purpose: p.a.allowed_purposes[0], access_type: "read", approvals } });
    const ieData = (strict: boolean) => (a: Asset) => a.jurisdiction === "IE" && a.contains_personal_data && !a.residency_required &&
      (strict ? a.domain === "Customer" && clean(a) : ["Customer", "Payments", "Marketing"].includes(a.domain));
    add("JD scenario: Germany employee → Irish customer data", pair("DE", recent, ieData(true)) ?? pair("DE", recent, ieData(false)), ["LINE_MANAGER", "DATA_OWNER"]);
    add("UK employee → Swiss client identifying data", pair("GB", recent, (a) => a.jurisdiction === "CH" && a.contains_cid), ["LINE_MANAGER", "DATA_OWNER", "DPO"]);
    add("South Africa hub → German personal data (non-adequate transfer)", pair("ZA", recent, (a) => a.jurisdiction === "DE" && a.contains_personal_data && !a.residency_required && clean(a)), ["LINE_MANAGER", "DATA_OWNER", "DPO"]);
    add("UAE staff → Irish customer data (no adequacy)", pair("AE", recent, (a) => a.jurisdiction === "IE" && a.contains_personal_data && clean(a)), ["LINE_MANAGER", "DATA_OWNER"]);
    const term = employees.find((e) => e.status === "Terminated");
    const termAsset = term && assets.find((a) => a.jurisdiction === term.jurisdiction && can(term, a));
    if (term && termAsset) add("Leaver still able to request access", { e: term, a: termAsset }, ["LINE_MANAGER"]);
    return out;
  }, [employees, assets, roles]);

  useEffect(() => {
    const jd = presets.find((p) => p.label.startsWith("JD"));
    if (params.get("scenario") === "jd" && jd) set(jd.form);
  }, [params, presets]);

  const submit = async () => {
    if (!f.employee_id || !f.asset_id) return toast("Choose an employee and a data asset", true);
    setBusy(true);
    try {
      const r = await api.post<AccessRequestRow>("/api/access-requests/evaluate", {
        employee_id: f.employee_id, asset_id: f.asset_id, access_type: f.access_type, purpose: f.purpose, ticket_ref: f.ticket_ref || null,
        justification: f.justification, approvals: f.approvals.map((a) => ({ approval_type: a })),
      });
      setResult(r);
      onDone();
      toast(`${r.request_ref}: ${r.decision.replace(/_/g, " ").toLowerCase()}`);
    } catch (e: any) { toast(e.message, true); } finally { setBusy(false); }
  };

  return (
    <div className="grid" style={{ gridTemplateColumns: "minmax(320px, 420px) 1fr", alignItems: "start" }}>
      <Card title="New access request">
        <div className="grid" style={{ gap: 10 }}>
          <div className="faint">Scenarios</div>
          <div className="grid" style={{ gap: 6 }}>{presets.map((p) => <button key={p.label} onClick={() => { set(p.form); setResult(null); }} style={{ justifyContent: "flex-start", textAlign: "left" }}>▸ {p.label}</button>)}</div>
          <div className="row">
            <label className="field" style={{ width: 90 }}>Located in<select value={f.empJ} onChange={(e) => set({ empJ: e.target.value, employee_id: "" })}>{jurs.map((j) => <option key={j}>{j}</option>)}</select></label>
            <label className="field" style={{ flex: 1 }}>Employee<select value={f.employee_id} onChange={(e) => set({ employee_id: Number(e.target.value) })}>
              <option value="">Select…</option>
              {employees.filter((e) => e.jurisdiction === f.empJ).map((e) => <option key={e.id} value={e.id}>{e.full_name} · {e.role}{e.status !== "Active" ? ` · ${e.status}` : ""}</option>)}
            </select></label>
          </div>
          {emp && <div className="faint">{emp.employee_ref} · {emp.business_unit} · training {emp.last_training_date ?? "none"} · {role?.privileged ? "privileged role" : "standard role"}</div>}
          <div className="row">
            <label className="field" style={{ width: 90 }}>Data in<select value={f.assetJ} onChange={(e) => set({ assetJ: e.target.value, asset_id: "" })}>{jurs.map((j) => <option key={j}>{j}</option>)}</select></label>
            <label className="field" style={{ flex: 1 }}>Data asset<select value={f.asset_id} onChange={(e) => { const a = assets.find((x) => x.id === Number(e.target.value)); set({ asset_id: Number(e.target.value), purpose: a?.allowed_purposes[0] ?? f.purpose }); }}>
              <option value="">Select…</option>
              {assets.filter((a) => a.jurisdiction === f.assetJ).map((a) => <option key={a.id} value={a.id}>{a.asset_ref} · {a.name} · {a.classification}</option>)}
            </select></label>
          </div>
          {asset && <div className="faint">{asset.domain} · {asset.classification}{asset.contains_personal_data ? " · personal data" : ""}{asset.contains_special_category ? " · special category" : ""}{asset.contains_cid ? " · CID" : ""}{asset.residency_required ? " · residency-restricted" : ""} · purposes: {asset.allowed_purposes.join(", ")}</div>}
          <div className="row">
            <label className="field" style={{ flex: 1 }}>Access type<select value={f.access_type} onChange={(e) => set({ access_type: e.target.value })}>{["read", "write", "export", "admin"].map((t) => <option key={t}>{t}</option>)}</select></label>
            <label className="field" style={{ flex: 2 }}>Purpose<select value={f.purpose} onChange={(e) => set({ purpose: e.target.value })}>{uniq([...(asset?.allowed_purposes ?? []), ...PURPOSES]).map((p) => <option key={p}>{p}</option>)}</select></label>
          </div>
          <label className="field">Ticket reference (needed for write / export / admin)<input value={f.ticket_ref} placeholder="RITM1234567" onChange={(e) => set({ ticket_ref: e.target.value })} /></label>
          <label className="field">Business justification<input value={f.justification} placeholder="e.g. Quarterly churn analysis" onChange={(e) => set({ justification: e.target.value })} /></label>
          <div className="field" style={{ fontSize: 12, color: "var(--ink-2)", fontWeight: 550 }}>Approvals already obtained</div>
          {APPROVALS.map(([k, l]) => (
            <label key={k} className="check"><input type="checkbox" checked={f.approvals.includes(k)} onChange={(e) => set({ approvals: e.target.checked ? [...f.approvals, k] : f.approvals.filter((x) => x !== k) })} />{l}</label>
          ))}
          <button className="primary" onClick={submit} disabled={busy || !canWrite} style={{ justifyContent: "center" }}>{busy ? "Evaluating…" : "Evaluate request"}</button>
          {!canWrite && <div className="faint">Auditor role is read-only. Sign in as analyst to submit.</div>}
        </div>
      </Card>
      <Card title={result ? `Decision · ${result.request_ref}` : "Decision"} sub={result ? `${result.employee_name} (${result.employee_jurisdiction}) → ${result.asset_ref} (${result.asset_jurisdiction})` : undefined}>
        {result?.trace ? <TraceView trace={result.trace} /> : (
          <div className="empty" style={{ textAlign: "left" }}>
            <p><b>How it works.</b> Every request runs the same 10-step pipeline: identify the employee's jurisdiction, locate and classify the data,
              resolve the applicable regulatory requirements, validate RBAC permissions, check approvals, evaluate all configurable governance rules,
              raise compliance gaps for failed detective controls, route them to the accountable stakeholder with an SLA deadline, write a hash-chained
              audit entry, and refresh regional risk.</p>
            <p>Pick a scenario on the left or build your own request.</p>
          </div>
        )}
      </Card>
    </div>
  );
}

function RequestLog({ rows }: { rows: AccessRequestRow[] }) {
  const [q, setQ] = useState(""); const [dec, setDec] = useState(""); const [j, setJ] = useState(""); const [legacy, setLegacy] = useState(false);
  const [open, setOpen] = useState<AccessRequestRow | null>(null);
  const [detail, setDetail] = useState<AccessRequestRow | null>(null);
  useEffect(() => { if (open) { setDetail(null); api.get<AccessRequestRow>(`/api/access-requests/${open.id}`).then(setDetail).catch((e) => toast(e.message, true)); } }, [open]);
  const filtered = rows.filter((r) => (legacy || !r.legacy) && (!dec || r.decision === dec) && (!j || r.employee_jurisdiction === j || r.asset_jurisdiction === j) &&
    (!q || `${r.request_ref} ${r.employee_name} ${r.asset_name} ${r.purpose}`.toLowerCase().includes(q.toLowerCase())));
  return (
    <Card title="Access request log" sub="every decision is reproducible from its stored trace">
      <div className="filters">
        <input type="search" placeholder="Search requests…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select value={dec} onChange={(e) => setDec(e.target.value)}><option value="">All decisions</option>{["APPROVED", "APPROVED_WITH_FINDINGS", "PENDING_APPROVAL", "DENIED"].map((d) => <option key={d} value={d}>{d.replace(/_/g, " ").toLowerCase()}</option>)}</select>
        <select value={j} onChange={(e) => setJ(e.target.value)}><option value="">All jurisdictions</option>{uniq(rows.map((r) => r.asset_jurisdiction)).map((x) => <option key={x}>{x}</option>)}</select>
        <label className="check"><input type="checkbox" checked={legacy} onChange={(e) => setLegacy(e.target.checked)} />Include legacy migrated entitlements</label>
      </div>
      <DataTable rows={filtered} onRow={(r) => !r.legacy && setOpen(r)} cols={[
        { key: "request_ref", label: "Request", render: (r) => <span className="mono">{r.request_ref}</span> },
        { key: "requested_at", label: "Requested", render: (r) => fmtDateTime(r.requested_at) },
        { key: "employee_name", label: "Employee", render: (r) => <>{r.employee_name} <span className="faint">{r.employee_jurisdiction}</span></> },
        { key: "asset_name", label: "Data asset", render: (r) => <>{r.asset_name} <span className="faint">{r.asset_jurisdiction}</span></> },
        { key: "access_type", label: "Type" },
        { key: "cross_border", label: "Cross-border", render: (r) => (r.cross_border ? "Yes" : "No") },
        { key: "risk_score", label: "Risk", num: true, render: (r) => r.risk_score.toFixed(0) },
        { key: "decision", label: "Decision", render: (r) => (r.legacy ? <span className="badge b-neutral">Legacy (not evaluated)</span> : <DecisionBadge d={r.decision} />) },
      ]} />
      {open && (
        <Drawer title={`${open.request_ref} · ${open.employee_name} → ${open.asset_name}`} sub={`${open.employee_jurisdiction} → ${open.asset_jurisdiction} · ${open.access_type} · ${open.purpose} · ${fmtDateTime(open.requested_at)}`} onClose={() => setOpen(null)}>
          {detail?.trace ? <>
            <TraceView trace={detail.trace} />
            {detail.approvals?.length ? <div className="mt"><h3>Approvals on file</h3><ul>{detail.approvals.map((a, i) => <li key={i}>{a.type} · {a.status} · {fmtDateTime(a.decided_at)}{a.approver ? ` · ${a.approver}` : ""}</li>)}</ul></div> : null}
          </> : <Loading what="decision trace" />}
        </Drawer>
      )}
    </Card>
  );
}

export default function AccessControl() {
  const [tab, setTab] = useState("Request simulator");
  const emps = useApi<Employee[]>("/api/employees");
  const assets = useApi<Asset[]>("/api/assets");
  const roles = useApi<Role[]>("/api/roles");
  const reqs = useApi<AccessRequestRow[]>("/api/access-requests");
  const err = emps.error || assets.error || roles.error || reqs.error;
  return (
    <>
      <PageHead title="Access control" desc="RBAC and permission validation combined with jurisdiction, localisation, approval and data-hygiene rules. Submit a request to watch the control engine decide." />
      <Tabs tabs={["Request simulator", "Request log"]} value={tab} onChange={setTab} />
      {err ? <ErrorBox error={err} /> : !emps.data || !assets.data || !roles.data || !reqs.data ? <Loading /> :
        tab === "Request simulator" ? <Simulator employees={emps.data} assets={assets.data} roles={roles.data} onDone={reqs.reload} /> : <RequestLog rows={reqs.data} />}
    </>
  );
}
