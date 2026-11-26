export type Severity = "Critical" | "High" | "Medium" | "Low";
export const SEVERITIES: Severity[] = ["Critical", "High", "Medium", "Low"];
export type Decision = "APPROVED" | "APPROVED_WITH_FINDINGS" | "PENDING_APPROVAL" | "DENIED";

export interface Jurisdiction {
  id: number; code: string; name: string; region: string; is_eu: boolean; is_eea: boolean; eu_adequacy: boolean;
  data_protection_authority: string; financial_regulator: string; primary_law: string; residency_regime: string;
  banking_secrecy: boolean; breach_notification_hours: number; inherent_risk: number; status: string;
  national_requirements?: number; data_assets?: number; employees?: number;
}
export interface Requirement {
  id: number; code: string; scope: "GLOBAL" | "EU" | "NATIONAL"; jurisdiction: string | null; regime: string;
  reference: string; title: string; description: string; category: string; min_classification: number;
}
export interface Permission { domain: string; max_classification: number; access_types: string[] }
export interface Role { id: number; name: string; description: string; privileged: boolean; permissions: Permission[] }
export interface Location { id: number; jurisdiction: string; type: string; hosting_region: string }
export interface Asset {
  id: number; asset_ref: string; name: string; domain: string; system: string; hosting_provider: string;
  is_third_party_hosted: boolean; processor_agreement_ref: string | null; jurisdiction: string;
  classification_level: number | null; classification: string; owner_id: number | null; owner: string | null;
  contains_personal_data: boolean; contains_special_category: boolean; contains_cid: boolean; residency_required: boolean;
  encrypted_at_rest: boolean; dpia_completed: boolean; ropa_registered: boolean; retention_days: number;
  oldest_record_date: string; record_count: number; allowed_purposes: string[]; locations: Location[];
}
export interface Employee {
  id: number; employee_ref: string; full_name: string; email: string; jurisdiction: string; business_unit: string;
  role: string; role_privileged: boolean; status: string; hire_date: string; termination_date: string | null;
  last_training_date: string | null; last_access_review: string | null;
}
export interface Rule {
  code: string; name: string; category: string; severity: Severity; effect: "deny" | "escalate" | "flag";
  raises_gap: boolean; enabled: boolean; params: Record<string, any>; requirement_codes: string[];
  remediation: string; owner_function: string; description: string;
}
export interface RuleResult {
  code: string; name: string; category: string; severity: Severity; effect: string; raises_gap: boolean;
  passed: boolean; applicable: boolean; message: string; requirement_codes: string[];
}
export interface Trace {
  decision: Decision; reason: string; risk_score: number; risk_rating: Severity; cross_border: boolean;
  effective_classification: number; steps: { step: number; name: string; detail: string }[]; rules: RuleResult[]; gaps?: string[];
}
export interface AccessRequestRow {
  id: number; request_ref: string; employee_id: number; employee_ref: string; employee_name: string; employee_jurisdiction: string;
  asset_id: number; asset_ref: string; asset_name: string; asset_jurisdiction: string; access_type: string; purpose: string;
  ticket_ref: string | null; requested_at: string; decision: Decision; decision_reason: string; risk_score: number;
  risk_rating: Severity; cross_border: boolean; legacy: boolean; granted_until: string | null; revoked_at: string | null;
  trace?: Trace; approvals?: { type: string; status: string; decided_at: string; approver: string | null }[]; justification?: string;
}
export interface TransferMechanism {
  id: number; source: string; destination: string; mechanism: string; reference: string; valid_from: string;
  valid_until: string; tia_completed: boolean; status: string;
}
export interface Task {
  id: number; task_ref: string; gap_id: number; gap_ref: string; title: string; action: string; owner: string | null;
  owner_id: number | null; priority: Severity; status: string; due_date: string; created_at: string; completed_at: string | null; jurisdiction: string;
}
export interface Gap {
  id: number; gap_ref: string; source: string; rule_code: string | null; control_code: string | null; assessment_id: number | null;
  access_request_id: number | null; jurisdiction: string; title: string; description: string; impact: number; likelihood: number;
  severity: Severity; status: string; owner: string | null; owner_id: number | null; owner_title: string | null; occurrences: number;
  identified_at: string; last_seen_at: string; due_date: string; resolved_at: string | null; resolution_note: string | null;
  overdue: boolean; tasks: Task[];
}
export interface Control {
  id: number; code: string; name: string; domain: string; description: string; test_type: string; control_type: string;
  criticality: number; threshold: number; frequency: string; scope: string; enabled: boolean; owner: string | null;
  requirements: string[]; remediation: string;
}
export interface Assessment {
  id: number; control_id: number; control_code: string; control_name: string; jurisdiction: string; cycle: string; as_of: string;
  population: number; exceptions: number; pass_rate: number; result: string; severity: Severity | null; assessed_at: string;
}
export interface RiskRow {
  jurisdiction: string; name: string; as_of: string; cycle: string; control_effectiveness: number; open_gap_score: number;
  overdue_ratio: number; access_denial_rate: number; inherent_risk: number; residual_score: number; rating: Severity;
  drivers: { factor: string; contribution: number; label: string }[];
}
export interface PolicyVersion {
  id: number; version: string; status: string; change_summary: string; content: string; author: string;
  approved_by: string | null; approved_at: string | null; effective_date: string | null; created_at: string;
}
export interface Policy {
  id: number; code: string; title: string; doc_type: string; owner: string | null; status: string; current_version: string;
  review_cycle_months: number; last_reviewed: string; next_review_date: string; review_overdue: boolean;
  requirements: string[]; version_count: number; versions: PolicyVersion[];
}
export interface Stakeholder {
  id: number; name: string; title: string; function: string; email: string; jurisdiction: string | null; domain: string | null;
  open_gaps: number; critical_high: number; overdue: number; open_tasks: number; assets_owned: number;
}
export interface Project {
  id: number; code: string; name: string; description: string; status: string; sponsor: string | null; start_date: string;
  target_date: string; progress: number; activities: { id: number; title: string; type: string; status: string; due_date: string }[];
}
export interface AuditEntry {
  id: number; timestamp: string; actor: string; action: string; entity_type: string; entity_id: string;
  jurisdiction: string | null; details: Record<string, any>; hash: string; prev_hash: string;
}
export interface LocalisationRecord {
  id: number; asset_id: number; asset_ref: string; asset_name: string; asset_jurisdiction: string; location_jurisdiction: string;
  location_type: string; hosting_region: string; personal_data: boolean; residency_required: boolean; verified_at: string;
  status: string; issue: string | null;
}
export interface Dashboard {
  as_of: string;
  kpis: { avg_residual_risk: number; control_effectiveness: number; open_gaps: number; critical_high_open: number;
    overdue_remediation: number; access_requests: number; denial_rate: number; latest_cycle: string };
  risk_by_jurisdiction: { code: string; name: string; residual_score: number; rating: Severity; control_effectiveness: number; open_gaps: number;
    drivers: { factor: string; contribution: number; label: string }[] }[];
  risk_trend: { code: string; as_of: string; cycle: string; residual_score: number }[];
  gaps_by_severity: Record<Severity, number>;
  gaps_by_status: Record<string, number>;
  decisions: Record<string, number>;
  control_results: Record<string, number>;
  top_gaps: Gap[];
  recent_activity: { timestamp: string; actor: string; action: string; entity_type: string; entity_id: string; jurisdiction: string | null }[];
}
