/**
 * Static live-demo backend. Reads the API snapshot exported by backend/app/scripts/export_demo.py
 * and handles write actions in memory (per browser tab). Access decisions use the TypeScript
 * mirror of the Python engine, parity-tested against the real engine.
 */
import type { AccessRequestRow, Asset, AuditEntry, Employee, Gap, Policy, Rule, Severity, Stakeholder, Task } from "../types";
import { buildContext, evaluate, type ApprovalIn } from "./engine";

const BASE = `${import.meta.env.BASE_URL}demo/api/`;
const cache = new Map<string, Promise<any>>();
const state: Record<string, any> = {};

function file<T = any>(name: string): Promise<T> {
  if (state[name]) return Promise.resolve(state[name]);
  if (!cache.has(name)) {
    cache.set(name, fetch(`${BASE}${name}.json`).then((r) => {
      if (!r.ok) throw new Error(`Demo data missing: ${name}`);
      return r.json();
    }).then((d) => (state[name] = d)));
  }
  return cache.get(name)!;
}

const ROUTES: [RegExp, string][] = [
  [/^\/api\/metrics$/, "metrics"], [/^\/api\/dashboard\/summary$/, "dashboard"], [/^\/api\/jurisdictions$/, "jurisdictions"],
  [/^\/api\/requirements$/, "requirements"], [/^\/api\/transfers\/adequacy-matrix$/, "adequacy"], [/^\/api\/classifications$/, "classifications"],
  [/^\/api\/roles$/, "roles"], [/^\/api\/assets$/, "assets"], [/^\/api\/employees$/, "employees"], [/^\/api\/access-requests$/, "access-requests"],
  [/^\/api\/localisation\/records$/, "localisation-records"], [/^\/api\/localisation\/transfer-mechanisms$/, "transfer-mechanisms"],
  [/^\/api\/rules$/, "rules"], [/^\/api\/controls$/, "controls"], [/^\/api\/assessments$/, "assessments"], [/^\/api\/gaps$/, "gaps"],
  [/^\/api\/remediation-tasks$/, "remediation-tasks"], [/^\/api\/risk\/jurisdictions$/, "risk-latest"], [/^\/api\/risk\/history$/, "risk-history"],
  [/^\/api\/policies$/, "policies"], [/^\/api\/stakeholders$/, "stakeholders"], [/^\/api\/projects$/, "projects"],
  [/^\/api\/audit$/, "audit"], [/^\/api\/audit\/verify$/, "audit-verify"],
];

class DemoError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

const SLA: Record<Severity, number> = { Critical: 7, High: 30, Medium: 60, Low: 90 };
const today = () => new Date().toISOString().slice(0, 10);
const nowIso = () => new Date().toISOString().slice(0, 19);
const addDays = (d: string, n: number) => new Date(Date.parse(d + "T00:00:00Z") + n * 86400000).toISOString().slice(0, 10);
const matrix = (impact: number, likelihood: number): Severity => {
  const s = impact * likelihood;
  return s >= 12 ? "Critical" : s >= 8 ? "High" : s >= 4 ? "Medium" : "Low";
};
const RANK: Record<string, number> = { Low: 1, Medium: 2, High: 3, Critical: 4 };

async function audit(actor: string, action: string, entity_type: string, entity_id: string, details: Record<string, any>, jurisdiction: string | null) {
  const log: AuditEntry[] = await file("audit");
  const id = (log[0]?.id ?? 0) + 1;
  log.unshift({ id, timestamp: nowIso(), actor, action, entity_type, entity_id, jurisdiction, details,
    hash: "demo-session (not persisted)", prev_hash: log[0]?.hash ?? "" });
}

function ownerFor(fn: string, j: string, asset: Asset | null, people: Stakeholder[]): Stakeholder | undefined {
  if (fn === "DPO") return people.find((s) => s.function === "DPO" && s.jurisdiction === j);
  if (fn === "Data Steward") return people.find((s) => s.function === "Data Steward" && s.jurisdiction === j);
  if (fn === "Data Owner") return people.find((s) => s.id === asset?.owner_id) ?? people.find((s) => s.function === "Data Owner" && s.domain === asset?.domain);
  if (fn === "IAM") return people.find((s) => s.function === "IAM");
  if (fn === "Control Owner") return people.find((s) => s.title.startsWith("Chief Information Security"));
  return people.find((s) => s.title.startsWith("Chief Data"));
}

async function evaluateRequest(body: any, user: string): Promise<AccessRequestRow> {
  const [employees, assets, roles, requirements, jurisdictions, adequacy, mechanisms, rules, people, requests] = await Promise.all([
    file<Employee[]>("employees"), file<Asset[]>("assets"), file("roles"), file("requirements"), file("jurisdictions"), file("adequacy"),
    file("transfer-mechanisms"), file<Rule[]>("rules"), file<Stakeholder[]>("stakeholders"), file<AccessRequestRow[]>("access-requests"),
  ]);
  const emp = employees.find((e) => e.id === Number(body.employee_id));
  const asset = assets.find((a) => a.id === Number(body.asset_id));
  if (!emp || !asset) throw new DemoError(404, "Unknown employee or asset");
  const asOf = today();
  const approvals: ApprovalIn[] = (body.approvals ?? []).map((a: any) => ({ approval_type: a.approval_type, status: a.status ?? "Approved", decided_at: a.decided_at ?? asOf }));
  const ctx = buildContext({ roles, requirements, jurisdictions, adequacy, mechanisms, rules }, emp, asset,
    { access_type: body.access_type, purpose: body.purpose, ticket_ref: body.ticket_ref }, approvals, asOf);
  const trace = evaluate(ctx, rules);
  const id = Math.max(...requests.map((r) => r.id)) + 1;
  const ref = `AR-${asOf.slice(0, 4)}-D${String(id).padStart(4, "0")}`;

  // steps 7-9: gaps for failed detective controls, routed and given an SLA
  const gaps: Gap[] = await file("gaps");
  const ruleMeta = new Map(rules.map((r) => [r.code, r]));
  const created: string[] = [];
  for (const r of trace.rules.filter((x) => !x.passed && x.raises_gap)) {
    const meta = ruleMeta.get(r.code)!;
    const severity = matrix(trace.effective_classification, RANK[r.severity]);
    const gapJ = r.code === "ACC-003" || r.code === "ACC-004" ? emp.jurisdiction : asset.jurisdiction;
    const owner = ownerFor(meta.owner_function, gapJ, asset, people);
    const gid = Math.max(...gaps.map((g) => g.id)) + 1;
    const gref = `GAP-D${String(gid).padStart(4, "0")}`;
    const due = addDays(asOf, SLA[severity]);
    const task: Task = { id: gid * 10, task_ref: `RT-D${gid}`, gap_id: gid, gap_ref: gref, title: `Remediate: ${r.code} ${r.name}`,
      action: meta.remediation, owner: owner?.name ?? null, owner_id: owner?.id ?? null, priority: severity, status: "Not Started",
      due_date: due, created_at: nowIso(), completed_at: null, jurisdiction: gapJ };
    gaps.unshift({ id: gid, gap_ref: gref, source: "access_check", rule_code: r.code, control_code: null, assessment_id: null,
      access_request_id: id, jurisdiction: gapJ, title: `${r.code} ${r.name}`, description: r.message, impact: trace.effective_classification,
      likelihood: RANK[r.severity], severity, status: "Open", owner: owner?.name ?? null, owner_id: owner?.id ?? null,
      owner_title: owner?.title ?? null, occurrences: 1, identified_at: nowIso(), last_seen_at: nowIso(), due_date: due,
      resolved_at: null, resolution_note: null, overdue: false, tasks: [task] });
    (await file<Task[]>("remediation-tasks")).unshift(task);
    created.push(gref);
    await audit("control-engine", "GAP_CREATED", "ComplianceGap", gref, { severity, rule: r.code, owner: owner?.name, due }, gapJ);
  }
  if (created.length) trace.gaps = created;
  const row: AccessRequestRow = {
    id, request_ref: ref, employee_id: emp.id, employee_ref: emp.employee_ref, employee_name: emp.full_name, employee_jurisdiction: emp.jurisdiction,
    asset_id: asset.id, asset_ref: asset.asset_ref, asset_name: asset.name, asset_jurisdiction: asset.jurisdiction, access_type: body.access_type,
    purpose: body.purpose, ticket_ref: body.ticket_ref ?? null, requested_at: nowIso(), decision: trace.decision, decision_reason: trace.reason,
    risk_score: trace.risk_score, risk_rating: trace.risk_rating, cross_border: trace.cross_border, legacy: false,
    granted_until: null, revoked_at: null,
  };
  requests.unshift(row);
  const details = await file("access-request-details");
  const full = { ...row, trace, justification: body.justification ?? "", approvals: approvals.map((a) => ({ type: a.approval_type, status: a.status ?? "Approved", decided_at: a.decided_at, approver: null })) };
  details[id] = full;
  await audit(user, "ACCESS_REQUEST_EVALUATED", "AccessRequest", ref, { employee: emp.employee_ref, asset: asset.asset_ref, decision: trace.decision,
    failed_rules: trace.rules.filter((r) => !r.passed).map((r) => r.code) }, asset.jurisdiction);
  return full;
}

function requireWriter(role?: string) {
  if (role === "auditor") throw new DemoError(403, "Requires role: admin, analyst");
}

export async function demoRequest<T>(method: string, rawPath: string, body: any, session: { role: string; username: string } | null): Promise<T> {
  const path = rawPath.split("?")[0];
  const user = session?.username ?? "demo";
  if (method === "GET") {
    const hit = ROUTES.find(([re]) => re.test(path));
    if (hit) return file(hit[1]);
    let m = path.match(/^\/api\/access-requests\/(\d+)$/);
    if (m) return (await file("access-request-details"))[m[1]];
    m = path.match(/^\/api\/assessments\/(\d+)$/);
    if (m) {
      const a = (await file("assessments")).find((x: any) => x.id === Number(m![1]));
      return { ...a, evidence: (await file("assessment-evidence"))[m[1]] ?? [] } as T;
    }
    m = path.match(/^\/api\/jurisdictions\/([A-Z]{2})$/i);
    if (m) return (await file("jurisdictions")).find((j: any) => j.code === m![1].toUpperCase());
    throw new DemoError(404, `Not available in demo: ${path}`);
  }

  requireWriter(session?.role);
  if (method === "POST" && path === "/api/access-requests/evaluate") return (await evaluateRequest(body, user)) as T;

  let m = path.match(/^\/api\/rules\/([A-Z0-9-]+)$/);
  if (method === "PATCH" && m) {
    if (session?.role !== "admin") throw new DemoError(403, "Requires role: admin");
    const rule = (await file<Rule[]>("rules")).find((r) => r.code === m![1]);
    if (!rule) throw new DemoError(404, "Unknown rule");
    Object.assign(rule, body);
    await audit(user, "RULE_RECONFIGURED", "GovernanceRule", rule.code, { after: body }, null);
    return rule as T;
  }
  m = path.match(/^\/api\/gaps\/(\d+)(\/remediate)?$/);
  if (m) {
    const gaps: Gap[] = await file("gaps");
    const g = gaps.find((x) => x.id === Number(m![1]));
    if (!g) throw new DemoError(404, "Not found");
    const close = (status: string, note: string) => {
      g.status = status; g.resolved_at = nowIso(); g.resolution_note = note; g.overdue = false;
      g.tasks.forEach((t) => { t.status = "Completed"; t.completed_at = nowIso(); });
    };
    if (m[2]) close("Resolved", `Corrective action completed by ${user} (demo session; retest on next cycle).`);
    else if (body.status === "Resolved" || body.status === "Risk Accepted") close(body.status, body.note ?? `${body.status} by ${user}`);
    else if (body.status) g.status = body.status;
    await audit(user, m[2] ? "GAP_RESOLVED" : "GAP_STATUS_CHANGED", "ComplianceGap", g.gap_ref, { status: g.status }, g.jurisdiction);
    return g as T;
  }
  m = path.match(/^\/api\/remediation-tasks\/(\d+)$/);
  if (method === "PATCH" && m) {
    const t = (await file<Task[]>("remediation-tasks")).find((x) => x.id === Number(m![1]));
    if (!t) throw new DemoError(404, "Not found");
    Object.assign(t, body);
    if (body.status === "Completed") t.completed_at = nowIso();
    await audit(user, "TASK_UPDATED", "RemediationTask", t.task_ref, body, t.jurisdiction);
    return t as T;
  }
  if (method === "POST" && path === "/api/assessments/run") {
    const latest = (await file("assessments")).filter((a: any) => a.cycle === "2026-Q4");
    const results: Record<string, number> = {};
    latest.forEach((a: any) => (results[a.result] = (results[a.result] ?? 0) + 1));
    return { as_of: "2026-11-26", assessments: latest.length, results, demo: true } as T;
  }
  m = path.match(/^\/api\/policies\/(\d+)\/versions(?:\/(\d+)\/approve)?$/);
  if (method === "POST" && m) {
    const p = (await file<Policy[]>("policies")).find((x) => x.id === Number(m![1]));
    if (!p) throw new DemoError(404, "Not found");
    if (!m[2]) {
      if (p.versions.some((v) => v.status === "In Review")) throw new DemoError(409, "A draft is already in progress for this policy");
      const [maj, min] = p.current_version.split(".").map(Number);
      const version = body.major ? `${maj + 1}.0` : `${maj}.${min + 1}`;
      p.versions.push({ id: Date.now(), version, status: "In Review", change_summary: body.change_summary, content: body.content,
        author: session?.username === "admin" ? "Governance Administrator" : "Governance Analyst", approved_by: null, approved_at: null, effective_date: null, created_at: nowIso() });
      await audit(user, "POLICY_VERSION_DRAFTED", "Policy", `${p.code} v${version}`, { change_summary: body.change_summary }, null);
    } else {
      if (session?.role !== "admin") throw new DemoError(403, "Requires role: admin");
      const v = p.versions.find((x) => x.id === Number(m![2]));
      if (!v || v.status !== "In Review") throw new DemoError(409, "Only versions in review can be approved");
      if (v.author === "Governance Administrator") throw new DemoError(403, "Maker-checker: the author cannot approve their own version");
      p.versions.forEach((x) => { if (x.status === "Published") x.status = "Superseded"; });
      Object.assign(v, { status: "Published", approved_by: "Governance Administrator", approved_at: nowIso(), effective_date: today() });
      p.current_version = v.version; p.last_reviewed = today(); p.next_review_date = addDays(today(), 30 * p.review_cycle_months); p.review_overdue = false;
      await audit(user, "POLICY_VERSION_PUBLISHED", "Policy", `${p.code} v${v.version}`, {}, null);
    }
    p.version_count = p.versions.length;
    return p as T;
  }
  throw new DemoError(501, "This action needs the full-stack deployment (Docker). The live demo runs on a static snapshot.");
}
