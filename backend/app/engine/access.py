"""Access decision engine.

Pure functions over plain dataclasses: no database, no I/O. The service layer
(app/services/access_service.py) builds an AccessContext from PostgreSQL, calls
`evaluate`, then persists the decision, gaps, remediation tasks and audit entries.

Keeping the engine pure makes it fully unit-testable and lets the same logic be
mirrored (and parity-tested) in the static live demo.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date
from typing import Callable

from .severity import CLASSIFICATION_NAMES, SEVERITY_RANK, score_to_rating

ACCESS_TYPE_WEIGHT = {"read": 0, "write": 6, "export": 10, "admin": 14}
FAILED_RULE_POINTS = {"Critical": 25, "High": 15, "Medium": 8, "Low": 3}


@dataclass
class EmployeeCtx:
    id: int
    ref: str
    name: str
    jurisdiction: str
    role: str
    role_privileged: bool
    business_unit: str
    status: str
    last_training_date: date | None


@dataclass
class PermissionCtx:
    domain: str
    max_classification: int
    access_types: list[str]


@dataclass
class AssetCtx:
    id: int
    ref: str
    name: str
    jurisdiction: str
    domain: str
    classification_level: int | None
    owner_id: int | None
    contains_personal_data: bool
    contains_special_category: bool
    contains_cid: bool
    residency_required: bool
    encrypted_at_rest: bool
    retention_days: int
    oldest_record_date: date
    allowed_purposes: list[str]
    is_third_party_hosted: bool
    processor_agreement_ref: str | None


@dataclass
class ApprovalCtx:
    approval_type: str  # LINE_MANAGER | DATA_OWNER | DPO
    status: str
    decided_at: date


@dataclass
class TransferCtx:
    mechanism: str
    reference: str
    valid_until: date
    tia_completed: bool


@dataclass
class RequestCtx:
    access_type: str
    purpose: str
    justification: str = ""
    ticket_ref: str | None = None


@dataclass
class AccessContext:
    employee: EmployeeCtx
    permissions: list[PermissionCtx]
    asset: AssetCtx
    request: RequestCtx
    approvals: list[ApprovalCtx]
    adequate: bool
    transfer_mechanism: TransferCtx | None
    applicable_requirements: list[str]
    as_of: date


@dataclass
class RuleResult:
    code: str
    name: str
    category: str
    severity: str
    effect: str
    raises_gap: bool
    passed: bool
    applicable: bool
    message: str
    requirement_codes: list[str]


@dataclass
class Decision:
    decision: str
    reason: str
    risk_score: float
    risk_rating: str
    cross_border: bool
    effective_classification: int
    steps: list[dict]
    rules: list[RuleResult] = field(default_factory=list)

    @property
    def failed(self) -> list[RuleResult]:
        return [r for r in self.rules if not r.passed]

    def to_trace(self) -> dict:
        return {
            "decision": self.decision,
            "reason": self.reason,
            "risk_score": self.risk_score,
            "risk_rating": self.risk_rating,
            "cross_border": self.cross_border,
            "effective_classification": self.effective_classification,
            "steps": self.steps,
            "rules": [asdict(r) for r in self.rules],
        }


# ------------------------------------------------------------------ helpers
def effective_classification(asset: AssetCtx) -> int:
    """Unclassified assets are handled as Restricted (fail-safe)."""
    return asset.classification_level or 4


def _valid_approvals(ctx: AccessContext, approval_type: str, max_age_days: int | None = None) -> list[ApprovalCtx]:
    out = []
    for a in ctx.approvals:
        if a.approval_type != approval_type or a.status != "Approved":
            continue
        if max_age_days is not None and (ctx.as_of - a.decided_at).days > max_age_days:
            continue
        out.append(a)
    return out


def _is_personal_transfer(ctx: AccessContext) -> bool:
    return ctx.asset.contains_personal_data and ctx.employee.jurisdiction != ctx.asset.jurisdiction


# ------------------------------------------------------------------ rule implementations
# Each returns (applicable, passed, message).
RuleFn = Callable[[AccessContext, dict], tuple[bool, bool, str]]


def rule_acc_001(ctx: AccessContext, p: dict):
    level = effective_classification(ctx.asset)
    for perm in ctx.permissions:
        if perm.domain in (ctx.asset.domain, "*") and perm.max_classification >= level and ctx.request.access_type in perm.access_types:
            return True, True, f"Role '{ctx.employee.role}' grants {ctx.request.access_type} on {ctx.asset.domain} up to {CLASSIFICATION_NAMES[perm.max_classification]}."
    return True, False, (
        f"Role '{ctx.employee.role}' has no permission for {ctx.request.access_type} access to "
        f"{CLASSIFICATION_NAMES[level]} {ctx.asset.domain} data."
    )


def rule_acc_002(ctx, p):
    types = p.get("privileged_access_types", ["admin"])
    if ctx.request.access_type not in types:
        return False, True, "Not a privileged access type."
    if ctx.employee.role_privileged:
        return True, True, f"Role '{ctx.employee.role}' is privileged."
    return True, False, f"'{ctx.request.access_type}' access requires a privileged role; '{ctx.employee.role}' is not privileged."


def rule_acc_003(ctx, p):
    blocked = p.get("blocked_statuses", ["Terminated"])
    if ctx.employee.status in blocked:
        return True, False, f"Identity {ctx.employee.ref} has status '{ctx.employee.status}' but could still raise a request (leaver control failure)."
    return True, True, f"Employee status is '{ctx.employee.status}'."


def rule_acc_004(ctx, p):
    if effective_classification(ctx.asset) < p.get("min_classification", 2):
        return False, True, "Public data: training not required."
    max_age = p.get("max_age_days", 365)
    t = ctx.employee.last_training_date
    if t is None:
        return True, False, "No data protection training on record."
    age = (ctx.as_of - t).days
    if age > max_age:
        return True, False, f"Training completed {age} days ago (limit {max_age})."
    return True, True, f"Training completed {age} days ago."


def rule_acc_005(ctx, p):
    conflicts = p.get("conflicts", {}).get(ctx.employee.role, [])
    if not conflicts:
        return False, True, "No SoD constraints for this role."
    if ctx.asset.domain in conflicts:
        return True, False, f"Role '{ctx.employee.role}' may not access {ctx.asset.domain} data (segregation of duties)."
    return True, True, f"No conflict between '{ctx.employee.role}' and {ctx.asset.domain}."


def rule_acc_006(ctx, p):
    if ctx.request.access_type not in p.get("access_types", ["write", "export", "admin"]):
        return False, True, "Read access: no ticket required."
    ticket = (ctx.request.ticket_ref or "").strip().upper()
    if ticket.startswith(("RITM", "CHG")):
        return True, True, f"Ticket {ticket} referenced."
    return True, False, f"{ctx.request.access_type} access requires an approved RITM/CHG ticket reference."


def rule_apr_001(ctx, p):
    if effective_classification(ctx.asset) < p.get("min_classification", 2):
        return False, True, "Public data: no approval required."
    if _valid_approvals(ctx, "LINE_MANAGER"):
        return True, True, "Line manager approval present."
    return True, False, "Line manager approval missing."


def rule_apr_002(ctx, p):
    if effective_classification(ctx.asset) < p.get("min_classification", 3):
        return False, True, "Below Confidential: data owner approval not required."
    if _valid_approvals(ctx, "DATA_OWNER"):
        return True, True, "Data owner approval present."
    return True, False, "Data owner approval required for Confidential/Restricted data."


def rule_apr_003(ctx, p):
    needs = ctx.asset.contains_special_category or (_is_personal_transfer(ctx) and not ctx.adequate)
    if not needs:
        return False, True, "No special category data or non-adequate transfer."
    if _valid_approvals(ctx, "DPO"):
        return True, True, "DPO approval present."
    why = "special category data" if ctx.asset.contains_special_category else f"exposure to non-adequate jurisdiction {ctx.employee.jurisdiction}"
    return True, False, f"DPO approval required ({why})."


def rule_apr_004(ctx, p):
    max_age = p.get("max_age_days", 90)
    approved = [a for a in ctx.approvals if a.status == "Approved"]
    if not approved:
        return False, True, "No approvals to check."
    stale = [a for a in approved if (ctx.as_of - a.decided_at).days > max_age]
    if stale:
        return True, False, f"{len(stale)} approval(s) older than {max_age} days: {', '.join(a.approval_type for a in stale)}."
    return True, True, f"All approvals within {max_age} days."


def rule_loc_001(ctx, p):
    if not ctx.asset.residency_required:
        return False, True, "Asset has no residency restriction."
    if ctx.employee.jurisdiction == ctx.asset.jurisdiction:
        return True, True, f"Employee is located in {ctx.asset.jurisdiction}, where the data must reside."
    return True, False, f"Asset must remain in {ctx.asset.jurisdiction}; employee is located in {ctx.employee.jurisdiction}."


def rule_loc_002(ctx, p):
    if not _is_personal_transfer(ctx):
        return False, True, "No cross-border exposure of personal data."
    if ctx.adequate:
        return True, True, f"{ctx.employee.jurisdiction} is adequate for data from {ctx.asset.jurisdiction}."
    m = ctx.transfer_mechanism
    if m is None:
        return True, False, f"No transfer mechanism for {ctx.asset.jurisdiction} -> {ctx.employee.jurisdiction} and no adequacy."
    if m.valid_until < ctx.as_of:
        return True, False, f"{m.mechanism} ({m.reference}) expired on {m.valid_until.isoformat()}."
    if p.get("require_tia", True) and not m.tia_completed:
        return True, False, f"{m.mechanism} ({m.reference}) has no completed transfer impact assessment."
    return True, True, f"Covered by {m.mechanism} ({m.reference}) until {m.valid_until.isoformat()}."


def rule_loc_003(ctx, p):
    strict = p.get("strict_jurisdictions", ["CH", "LU"])
    if not (ctx.asset.contains_cid and ctx.asset.jurisdiction in strict):
        return False, True, "No client identifying data under strict banking secrecy."
    if ctx.employee.jurisdiction == ctx.asset.jurisdiction:
        return True, True, "CID accessed from within the secrecy jurisdiction."
    return True, False, f"Client identifying data in {ctx.asset.jurisdiction} cannot be accessed from {ctx.employee.jurisdiction}."


def rule_loc_004(ctx, p):
    if not (ctx.request.access_type == "export" and ctx.asset.contains_personal_data and effective_classification(ctx.asset) == 4):
        return False, True, "Not an export of Restricted personal data."
    if ctx.employee.jurisdiction == ctx.asset.jurisdiction:
        return True, True, "Export stays in-jurisdiction."
    return True, False, f"Export of Restricted personal data from {ctx.asset.jurisdiction} to {ctx.employee.jurisdiction} is prohibited."


def rule_pur_001(ctx, p):
    if ctx.request.purpose in ctx.asset.allowed_purposes:
        return True, True, f"Purpose '{ctx.request.purpose}' is registered for this asset."
    return True, False, f"Purpose '{ctx.request.purpose}' is not registered (allowed: {', '.join(ctx.asset.allowed_purposes)})."


def rule_dat_001(ctx, p):
    if ctx.asset.classification_level:
        return True, True, f"Classified as {CLASSIFICATION_NAMES[ctx.asset.classification_level]}."
    return True, False, "Asset is unclassified; treated as Restricted."


def rule_dat_002(ctx, p):
    if ctx.asset.owner_id:
        return True, True, "Accountable owner assigned."
    return True, False, "No accountable data owner assigned."


def rule_dat_003(ctx, p):
    if effective_classification(ctx.asset) < p.get("min_classification", 3):
        return False, True, "Encryption not mandated for this classification."
    if ctx.asset.encrypted_at_rest:
        return True, True, "Encrypted at rest."
    return True, False, "Confidential/Restricted asset is not encrypted at rest."


def rule_dat_004(ctx, p):
    age = (ctx.as_of - ctx.asset.oldest_record_date).days
    if age > ctx.asset.retention_days:
        return True, False, f"Oldest record is {age} days old; retention is {ctx.asset.retention_days} days."
    return True, True, f"Oldest record {age} days old, within {ctx.asset.retention_days}-day retention."


def rule_pur_002(ctx, p):
    if not ctx.asset.is_third_party_hosted:
        return False, True, "Hosted in-house."
    if ctx.asset.processor_agreement_ref:
        return True, True, f"Processor agreement {ctx.asset.processor_agreement_ref} on the register."
    return True, False, "Third-party hosted without a registered processor agreement."


RULE_IMPLEMENTATIONS: dict[str, RuleFn] = {
    "ACC-001": rule_acc_001, "ACC-002": rule_acc_002, "ACC-003": rule_acc_003,
    "ACC-004": rule_acc_004, "ACC-005": rule_acc_005, "ACC-006": rule_acc_006,
    "APR-001": rule_apr_001, "APR-002": rule_apr_002, "APR-003": rule_apr_003, "APR-004": rule_apr_004,
    "LOC-001": rule_loc_001, "LOC-002": rule_loc_002, "LOC-003": rule_loc_003, "LOC-004": rule_loc_004,
    "PUR-001": rule_pur_001, "PUR-002": rule_pur_002,
    "DAT-001": rule_dat_001, "DAT-002": rule_dat_002, "DAT-003": rule_dat_003, "DAT-004": rule_dat_004,
}


# ------------------------------------------------------------------ evaluation
def evaluate(ctx: AccessContext, rules: list[dict]) -> Decision:
    """Run the 10-step access pipeline over the configured rules."""
    level = effective_classification(ctx.asset)
    cross_border = ctx.employee.jurisdiction != ctx.asset.jurisdiction

    results: list[RuleResult] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        fn = RULE_IMPLEMENTATIONS.get(rule["code"])
        if fn is None:
            continue
        applicable, passed, message = fn(ctx, rule.get("params") or {})
        results.append(
            RuleResult(
                code=rule["code"], name=rule["name"], category=rule["category"], severity=rule["severity"],
                effect=rule["effect"], raises_gap=rule.get("raises_gap", False), passed=passed,
                applicable=applicable, message=message, requirement_codes=list(rule.get("requirement_codes", [])),
            )
        )

    failed = [r for r in results if not r.passed]
    deny = [r for r in failed if r.effect == "deny"]
    escalate = [r for r in failed if r.effect == "escalate"]
    flag = [r for r in failed if r.effect == "flag"]

    if deny:
        decision = "DENIED"
        worst = max(deny, key=lambda r: SEVERITY_RANK[r.severity])
        reason = f"Denied by {worst.code}: {worst.message}"
    elif escalate:
        decision = "PENDING_APPROVAL"
        reason = "Awaiting: " + "; ".join(f"{r.code} {r.message}" for r in escalate)
    elif flag:
        decision = "APPROVED_WITH_FINDINGS"
        reason = "Approved; findings raised: " + ", ".join(r.code for r in flag)
    else:
        decision = "APPROVED"
        reason = "All applicable controls passed."

    # Request risk score (0-100): inherent exposure + failed-control penalty.
    score = level * 12 + ACCESS_TYPE_WEIGHT.get(ctx.request.access_type, 0)
    score += 12 if cross_border and ctx.asset.contains_personal_data else 0
    score += 8 if ctx.asset.contains_special_category else 0
    score += 6 if ctx.asset.contains_cid else 0
    score += sum(FAILED_RULE_POINTS[r.severity] for r in failed)
    score = float(min(100, score))

    gap_rules = [r.code for r in failed if r.raises_gap]
    steps = [
        {"step": 1, "name": "Identify employee jurisdiction",
         "detail": f"{ctx.employee.name} ({ctx.employee.ref}) is located in {ctx.employee.jurisdiction}; role '{ctx.employee.role}'."},
        {"step": 2, "name": "Identify data location and classification",
         "detail": f"{ctx.asset.name} ({ctx.asset.ref}) resides in {ctx.asset.jurisdiction}; classified "
                   f"{CLASSIFICATION_NAMES[ctx.asset.classification_level] if ctx.asset.classification_level else 'UNCLASSIFIED (treated as Restricted)'}."},
        {"step": 3, "name": "Resolve applicable jurisdiction requirements",
         "detail": f"{len(ctx.applicable_requirements)} requirements apply: {', '.join(ctx.applicable_requirements[:8])}"
                   + ("..." if len(ctx.applicable_requirements) > 8 else "")},
        {"step": 4, "name": "Validate role-based permissions",
         "detail": next((r.message for r in results if r.code == "ACC-001"), "RBAC rule disabled.")},
        {"step": 5, "name": "Check required approvals",
         "detail": " ".join(r.message for r in results if r.category == "Approvals" and r.applicable) or "No approvals required."},
        {"step": 6, "name": "Evaluate governance rules",
         "detail": f"{len(results)} rules evaluated, {len(failed)} failed ({len(deny)} deny, {len(escalate)} escalate, {len(flag)} flag)."},
        {"step": 7, "name": "Create compliance gaps for failed controls",
         "detail": f"Gap-raising failures: {', '.join(gap_rules)}" if gap_rules else "No control failures requiring a gap."},
        {"step": 8, "name": "Assign responsible stakeholder", "detail": "Assigned per rule owner function (see gaps)." if gap_rules else "Not required."},
        {"step": 9, "name": "Generate remediation deadline", "detail": "SLA by severity: Critical 7d, High 30d, Medium 60d, Low 90d." if gap_rules else "Not required."},
        {"step": 10, "name": "Record audit log and update regional risk",
         "detail": f"Decision {decision}; request risk {score:.0f}/100 ({score_to_rating(score)})."},
    ]
    return Decision(
        decision=decision, reason=reason, risk_score=score, risk_rating=score_to_rating(score),
        cross_border=cross_border, effective_classification=level, steps=steps, rules=results,
    )
