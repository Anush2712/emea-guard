/**
 * TypeScript mirror of backend/app/engine/access.py, used ONLY by the static live demo
 * (GitHub Pages has no Python backend). Parity with the Python engine is enforced by
 * parity.test.ts against 400 decisions exported from the real engine.
 */
import type { Asset, Decision, Employee, Requirement, Role, Rule, RuleResult, Severity, Trace, TransferMechanism } from "../types";

const CLASS_NAMES: Record<number, string> = { 1: "Public", 2: "Internal", 3: "Confidential", 4: "Restricted" };
const ACCESS_WEIGHT: Record<string, number> = { read: 0, write: 6, export: 10, admin: 14 };
const FAILED_POINTS: Record<Severity, number> = { Critical: 25, High: 15, Medium: 8, Low: 3 };
const RANK: Record<Severity, number> = { Low: 1, Medium: 2, High: 3, Critical: 4 };

export interface ApprovalIn { approval_type: string; status?: string; decided_at: string }
export interface RequestIn { access_type: string; purpose: string; ticket_ref?: string | null; justification?: string }
export interface EngineData {
  roles: Role[]; requirements: Requirement[]; jurisdictions: { code: string; is_eu: boolean }[];
  adequacy: Record<string, Record<string, boolean>>; mechanisms: TransferMechanism[]; rules: Rule[];
}
interface Ctx {
  employee: Employee; permissions: Role["permissions"]; asset: Asset; request: RequestIn; approvals: ApprovalIn[];
  adequate: boolean; mechanism: TransferMechanism | null; applicable: string[]; asOf: string;
}

export const days = (from: string, to: string) =>
  Math.round((Date.parse(to.slice(0, 10) + "T00:00:00Z") - Date.parse(from.slice(0, 10) + "T00:00:00Z")) / 86400000);

export function scoreToRating(s: number): Severity {
  return s >= 70 ? "Critical" : s >= 50 ? "High" : s >= 30 ? "Medium" : "Low";
}

const level = (a: Asset) => a.classification_level ?? 4;
const validApprovals = (c: Ctx, type: string, maxAge?: number) =>
  c.approvals.filter((a) => a.approval_type === type && (a.status ?? "Approved") === "Approved" && (maxAge === undefined || days(a.decided_at, c.asOf) <= maxAge));
const personalTransfer = (c: Ctx) => c.asset.contains_personal_data && c.employee.jurisdiction !== c.asset.jurisdiction;

type Out = [applicable: boolean, passed: boolean, message: string];
const IMPL: Record<string, (c: Ctx, p: Record<string, any>) => Out> = {
  "ACC-001": (c) => {
    const lv = level(c.asset);
    const ok = c.permissions.find((p) => (p.domain === c.asset.domain || p.domain === "*") && p.max_classification >= lv && p.access_types.includes(c.request.access_type));
    return ok ? [true, true, `Role '${c.employee.role}' grants ${c.request.access_type} on ${c.asset.domain} up to ${CLASS_NAMES[ok.max_classification]}.`]
      : [true, false, `Role '${c.employee.role}' has no permission for ${c.request.access_type} access to ${CLASS_NAMES[lv]} ${c.asset.domain} data.`];
  },
  "ACC-002": (c, p) => {
    if (!(p.privileged_access_types ?? ["admin"]).includes(c.request.access_type)) return [false, true, "Not a privileged access type."];
    return c.employee.role_privileged ? [true, true, `Role '${c.employee.role}' is privileged.`]
      : [true, false, `'${c.request.access_type}' access requires a privileged role; '${c.employee.role}' is not privileged.`];
  },
  "ACC-003": (c, p) => (p.blocked_statuses ?? ["Terminated"]).includes(c.employee.status)
    ? [true, false, `Identity ${c.employee.employee_ref} has status '${c.employee.status}' but could still raise a request (leaver control failure).`]
    : [true, true, `Employee status is '${c.employee.status}'.`],
  "ACC-004": (c, p) => {
    if (level(c.asset) < (p.min_classification ?? 2)) return [false, true, "Public data: training not required."];
    const max = p.max_age_days ?? 365;
    if (!c.employee.last_training_date) return [true, false, "No data protection training on record."];
    const age = days(c.employee.last_training_date, c.asOf);
    return age > max ? [true, false, `Training completed ${age} days ago (limit ${max}).`] : [true, true, `Training completed ${age} days ago.`];
  },
  "ACC-005": (c, p) => {
    const conflicts: string[] = (p.conflicts ?? {})[c.employee.role] ?? [];
    if (!conflicts.length) return [false, true, "No SoD constraints for this role."];
    return conflicts.includes(c.asset.domain) ? [true, false, `Role '${c.employee.role}' may not access ${c.asset.domain} data (segregation of duties).`]
      : [true, true, `No conflict between '${c.employee.role}' and ${c.asset.domain}.`];
  },
  "ACC-006": (c, p) => {
    if (!(p.access_types ?? ["write", "export", "admin"]).includes(c.request.access_type)) return [false, true, "Read access: no ticket required."];
    const t = (c.request.ticket_ref ?? "").trim().toUpperCase();
    return t.startsWith("RITM") || t.startsWith("CHG") ? [true, true, `Ticket ${t} referenced.`]
      : [true, false, `${c.request.access_type} access requires an approved RITM/CHG ticket reference.`];
  },
  "APR-001": (c, p) => level(c.asset) < (p.min_classification ?? 2) ? [false, true, "Public data: no approval required."]
    : validApprovals(c, "LINE_MANAGER").length ? [true, true, "Line manager approval present."] : [true, false, "Line manager approval missing."],
  "APR-002": (c, p) => level(c.asset) < (p.min_classification ?? 3) ? [false, true, "Below Confidential: data owner approval not required."]
    : validApprovals(c, "DATA_OWNER").length ? [true, true, "Data owner approval present."] : [true, false, "Data owner approval required for Confidential/Restricted data."],
  "APR-003": (c) => {
    const needs = c.asset.contains_special_category || (personalTransfer(c) && !c.adequate);
    if (!needs) return [false, true, "No special category data or non-adequate transfer."];
    if (validApprovals(c, "DPO").length) return [true, true, "DPO approval present."];
    const why = c.asset.contains_special_category ? "special category data" : `exposure to non-adequate jurisdiction ${c.employee.jurisdiction}`;
    return [true, false, `DPO approval required (${why}).`];
  },
  "APR-004": (c, p) => {
    const max = p.max_age_days ?? 90;
    const approved = c.approvals.filter((a) => (a.status ?? "Approved") === "Approved");
    if (!approved.length) return [false, true, "No approvals to check."];
    const stale = approved.filter((a) => days(a.decided_at, c.asOf) > max);
    return stale.length ? [true, false, `${stale.length} approval(s) older than ${max} days: ${stale.map((a) => a.approval_type).join(", ")}.`]
      : [true, true, `All approvals within ${max} days.`];
  },
  "LOC-001": (c) => {
    if (!c.asset.residency_required) return [false, true, "Asset has no residency restriction."];
    return c.employee.jurisdiction === c.asset.jurisdiction ? [true, true, `Employee is located in ${c.asset.jurisdiction}, where the data must reside.`]
      : [true, false, `Asset must remain in ${c.asset.jurisdiction}; employee is located in ${c.employee.jurisdiction}.`];
  },
  "LOC-002": (c, p) => {
    if (!personalTransfer(c)) return [false, true, "No cross-border exposure of personal data."];
    if (c.adequate) return [true, true, `${c.employee.jurisdiction} is adequate for data from ${c.asset.jurisdiction}.`];
    const m = c.mechanism;
    if (!m) return [true, false, `No transfer mechanism for ${c.asset.jurisdiction} -> ${c.employee.jurisdiction} and no adequacy.`];
    if (m.valid_until < c.asOf) return [true, false, `${m.mechanism} (${m.reference}) expired on ${m.valid_until}.`];
    if ((p.require_tia ?? true) && !m.tia_completed) return [true, false, `${m.mechanism} (${m.reference}) has no completed transfer impact assessment.`];
    return [true, true, `Covered by ${m.mechanism} (${m.reference}) until ${m.valid_until}.`];
  },
  "LOC-003": (c, p) => {
    const strict: string[] = p.strict_jurisdictions ?? ["CH", "LU"];
    if (!(c.asset.contains_cid && strict.includes(c.asset.jurisdiction))) return [false, true, "No client identifying data under strict banking secrecy."];
    return c.employee.jurisdiction === c.asset.jurisdiction ? [true, true, "CID accessed from within the secrecy jurisdiction."]
      : [true, false, `Client identifying data in ${c.asset.jurisdiction} cannot be accessed from ${c.employee.jurisdiction}.`];
  },
  "LOC-004": (c) => {
    if (!(c.request.access_type === "export" && c.asset.contains_personal_data && level(c.asset) === 4)) return [false, true, "Not an export of Restricted personal data."];
    return c.employee.jurisdiction === c.asset.jurisdiction ? [true, true, "Export stays in-jurisdiction."]
      : [true, false, `Export of Restricted personal data from ${c.asset.jurisdiction} to ${c.employee.jurisdiction} is prohibited.`];
  },
  "PUR-001": (c) => c.asset.allowed_purposes.includes(c.request.purpose) ? [true, true, `Purpose '${c.request.purpose}' is registered for this asset.`]
    : [true, false, `Purpose '${c.request.purpose}' is not registered (allowed: ${c.asset.allowed_purposes.join(", ")}).`],
  "PUR-002": (c) => !c.asset.is_third_party_hosted ? [false, true, "Hosted in-house."]
    : c.asset.processor_agreement_ref ? [true, true, `Processor agreement ${c.asset.processor_agreement_ref} on the register.`]
      : [true, false, "Third-party hosted without a registered processor agreement."],
  "DAT-001": (c) => c.asset.classification_level ? [true, true, `Classified as ${CLASS_NAMES[c.asset.classification_level]}.`] : [true, false, "Asset is unclassified; treated as Restricted."],
  "DAT-002": (c) => c.asset.owner_id ? [true, true, "Accountable owner assigned."] : [true, false, "No accountable data owner assigned."],
  "DAT-003": (c, p) => level(c.asset) < (p.min_classification ?? 3) ? [false, true, "Encryption not mandated for this classification."]
    : c.asset.encrypted_at_rest ? [true, true, "Encrypted at rest."] : [true, false, "Confidential/Restricted asset is not encrypted at rest."],
  "DAT-004": (c) => {
    const age = days(c.asset.oldest_record_date, c.asOf);
    return age > c.asset.retention_days ? [true, false, `Oldest record is ${age} days old; retention is ${c.asset.retention_days} days.`]
      : [true, true, `Oldest record ${age} days old, within ${c.asset.retention_days}-day retention.`];
  },
};

export function buildContext(d: EngineData, employee: Employee, asset: Asset, request: RequestIn, approvals: ApprovalIn[], asOf: string): Ctx {
  const ej = employee.jurisdiction, aj = asset.jurisdiction;
  let mechanism: TransferMechanism | null = null;
  if (ej !== aj) {
    const rows = d.mechanisms.filter((m) => m.source === aj && m.destination === ej);
    const valid = rows.filter((m) => m.valid_from <= asOf && asOf <= m.valid_until);
    const pool = valid.length ? valid : rows;
    mechanism = pool.reduce<TransferMechanism | null>((best, m) => (!best || m.valid_until > best.valid_until ? m : best), null);
  }
  const lv = asset.classification_level ?? 4;
  const eu = [aj, ej].some((c) => d.jurisdictions.find((j) => j.code === c)?.is_eu);
  const applicable = d.requirements.filter((r) => r.min_classification <= lv &&
    (r.scope === "GLOBAL" || (r.scope === "EU" && eu) || (r.scope === "NATIONAL" && r.jurisdiction !== null && [aj, ej].includes(r.jurisdiction)))).map((r) => r.code);
  return {
    employee, asset, request, approvals, asOf, applicable, mechanism,
    permissions: d.roles.find((r) => r.name === employee.role)?.permissions ?? [],
    adequate: d.adequacy[aj]?.[ej] ?? false,
  };
}

export function evaluate(c: Ctx, rules: Rule[]): Trace {
  const lv = level(c.asset);
  const crossBorder = c.employee.jurisdiction !== c.asset.jurisdiction;
  const results: RuleResult[] = [];
  for (const r of rules) {
    if (!r.enabled || !IMPL[r.code]) continue;
    const [applicable, passed, message] = IMPL[r.code](c, r.params ?? {});
    results.push({ code: r.code, name: r.name, category: r.category, severity: r.severity, effect: r.effect, raises_gap: r.raises_gap,
      passed, applicable, message, requirement_codes: r.requirement_codes });
  }
  const failed = results.filter((r) => !r.passed);
  const deny = failed.filter((r) => r.effect === "deny"), esc = failed.filter((r) => r.effect === "escalate"), flag = failed.filter((r) => r.effect === "flag");
  let decision: Decision, reason: string;
  if (deny.length) {
    const worst = deny.reduce((a, b) => (RANK[b.severity] > RANK[a.severity] ? b : a));
    decision = "DENIED"; reason = `Denied by ${worst.code}: ${worst.message}`;
  } else if (esc.length) {
    decision = "PENDING_APPROVAL"; reason = "Awaiting: " + esc.map((r) => `${r.code} ${r.message}`).join("; ");
  } else if (flag.length) {
    decision = "APPROVED_WITH_FINDINGS"; reason = "Approved; findings raised: " + flag.map((r) => r.code).join(", ");
  } else {
    decision = "APPROVED"; reason = "All applicable controls passed.";
  }
  let score = lv * 12 + (ACCESS_WEIGHT[c.request.access_type] ?? 0);
  score += crossBorder && c.asset.contains_personal_data ? 12 : 0;
  score += c.asset.contains_special_category ? 8 : 0;
  score += c.asset.contains_cid ? 6 : 0;
  score += failed.reduce((s, r) => s + FAILED_POINTS[r.severity], 0);
  score = Math.min(100, score);
  const gapRules = failed.filter((r) => r.raises_gap).map((r) => r.code);
  const reqs = c.applicable;
  const steps = [
    { step: 1, name: "Identify employee jurisdiction", detail: `${c.employee.full_name} (${c.employee.employee_ref}) is located in ${c.employee.jurisdiction}; role '${c.employee.role}'.` },
    { step: 2, name: "Identify data location and classification", detail: `${c.asset.name} (${c.asset.asset_ref}) resides in ${c.asset.jurisdiction}; classified ${c.asset.classification_level ? CLASS_NAMES[c.asset.classification_level] : "UNCLASSIFIED (treated as Restricted)"}.` },
    { step: 3, name: "Resolve applicable jurisdiction requirements", detail: `${reqs.length} requirements apply: ${reqs.slice(0, 8).join(", ")}${reqs.length > 8 ? "..." : ""}` },
    { step: 4, name: "Validate role-based permissions", detail: results.find((r) => r.code === "ACC-001")?.message ?? "RBAC rule disabled." },
    { step: 5, name: "Check required approvals", detail: results.filter((r) => r.category === "Approvals" && r.applicable).map((r) => r.message).join(" ") || "No approvals required." },
    { step: 6, name: "Evaluate governance rules", detail: `${results.length} rules evaluated, ${failed.length} failed (${deny.length} deny, ${esc.length} escalate, ${flag.length} flag).` },
    { step: 7, name: "Create compliance gaps for failed controls", detail: gapRules.length ? `Gap-raising failures: ${gapRules.join(", ")}` : "No control failures requiring a gap." },
    { step: 8, name: "Assign responsible stakeholder", detail: gapRules.length ? "Assigned per rule owner function (see gaps)." : "Not required." },
    { step: 9, name: "Generate remediation deadline", detail: gapRules.length ? "SLA by severity: Critical 7d, High 30d, Medium 60d, Low 90d." : "Not required." },
    { step: 10, name: "Record audit log and update regional risk", detail: `Decision ${decision}; request risk ${score.toFixed(0)}/100 (${scoreToRating(score)}).` },
  ];
  return { decision, reason, risk_score: score, risk_rating: scoreToRating(score), cross_border: crossBorder, effective_classification: lv, steps, rules: results };
}
