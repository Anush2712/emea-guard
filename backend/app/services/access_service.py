"""Access request orchestration: DB -> pure engine -> persisted decision, gaps, audit, risk."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from ..engine.access import (
    AccessContext,
    ApprovalCtx,
    AssetCtx,
    EmployeeCtx,
    PermissionCtx,
    RequestCtx,
    TransferCtx,
    evaluate,
)
from ..engine.severity import SEVERITY_RANK, matrix_severity
from ..models import AccessRequest, Approval, DataAsset, Employee
from .audit import AuditTrail
from .gaps import next_ref, raise_gap
from .lookups import Lookups


def build_context(lk: Lookups, employee: Employee, asset: DataAsset, request: RequestCtx,
                  approvals: list[ApprovalCtx], as_of: date) -> AccessContext:
    ej, aj = employee.jurisdiction.code, asset.jurisdiction.code
    level = asset.classification.level if asset.classification else None
    mech = lk.mechanism(aj, ej, as_of) if ej != aj else None
    return AccessContext(
        employee=EmployeeCtx(
            id=employee.id, ref=employee.employee_ref, name=employee.full_name, jurisdiction=ej, role=employee.role.name,
            role_privileged=employee.role.privileged, business_unit=employee.business_unit, status=employee.status,
            last_training_date=employee.last_training_date,
        ),
        permissions=[PermissionCtx(p.domain, p.max_classification, list(p.access_types)) for p in employee.role.permissions],
        asset=AssetCtx(
            id=asset.id, ref=asset.asset_ref, name=asset.name, jurisdiction=aj, domain=asset.domain, classification_level=level,
            owner_id=asset.owner_id, contains_personal_data=asset.contains_personal_data,
            contains_special_category=asset.contains_special_category, contains_cid=asset.contains_cid,
            residency_required=asset.residency_required, encrypted_at_rest=asset.encrypted_at_rest,
            retention_days=asset.retention_days, oldest_record_date=asset.oldest_record_date,
            allowed_purposes=list(asset.allowed_purposes or []), is_third_party_hosted=asset.is_third_party_hosted,
            processor_agreement_ref=asset.processor_agreement_ref,
        ),
        request=request,
        approvals=approvals,
        adequate=lk.adequate(aj, ej),
        transfer_mechanism=TransferCtx(mech.mechanism, mech.reference, mech.valid_until, mech.tia_completed) if mech else None,
        applicable_requirements=lk.applicable_requirements(aj, ej, level or 4),
        as_of=as_of,
    )


def gap_dedup_key(rule_code: str, ctx: AccessContext) -> str:
    """Gaps de-duplicate on the underlying weakness, not on each request."""
    if rule_code in ("ACC-003", "ACC-004"):
        return f"{rule_code}:EMP:{ctx.employee.id}"
    if rule_code == "LOC-002":
        return f"{rule_code}:FLOW:{ctx.asset.jurisdiction}->{ctx.employee.jurisdiction}"
    return f"{rule_code}:ASSET:{ctx.asset.id}"


def submit_access_request(
    db: Session, lk: Lookups, audit: AuditTrail, *, employee: Employee, asset: DataAsset, access_type: str,
    purpose: str, justification: str = "", ticket_ref: str | None = None, approvals: list[dict] | None = None,
    actor: str = "access-portal", now: datetime | None = None,
) -> AccessRequest:
    now = (now or datetime.utcnow()).replace(microsecond=0)
    as_of = now.date()
    approvals = approvals or []
    approval_ctx = [ApprovalCtx(a["approval_type"], a.get("status", "Approved"), a["decided_at"].date() if isinstance(a["decided_at"], datetime) else a["decided_at"]) for a in approvals]
    req = RequestCtx(access_type=access_type, purpose=purpose, justification=justification, ticket_ref=ticket_ref)
    ctx = build_context(lk, employee, asset, req, approval_ctx, as_of)
    decision = evaluate(ctx, lk.rules)

    ar = AccessRequest(
        request_ref=next_ref(db, AccessRequest, f"AR-{now.year}"), employee_id=employee.id, asset_id=asset.id,
        access_type=access_type, purpose=purpose, justification=justification, ticket_ref=ticket_ref, requested_at=now,
        decision=decision.decision, decision_reason=decision.reason, risk_score=decision.risk_score,
        risk_rating=decision.risk_rating, cross_border=decision.cross_border, evaluation_trace=decision.to_trace(),
    )
    if decision.decision in ("APPROVED", "APPROVED_WITH_FINDINGS"):
        ar.granted_until = as_of + timedelta(days=365)
        ar.last_used_at = as_of
        ar.last_recertified_at = as_of
    db.add(ar)
    db.flush()
    for a in approvals:
        decided = a["decided_at"] if isinstance(a["decided_at"], datetime) else datetime.combine(a["decided_at"], datetime.min.time())
        db.add(Approval(access_request_id=ar.id, approval_type=a["approval_type"], approver_id=a.get("approver_id"),
                        status=a.get("status", "Approved"), decided_at=decided))

    jcode = asset.jurisdiction.code
    audit.record(actor=actor, action="ACCESS_REQUEST_EVALUATED", entity_type="AccessRequest", entity_id=ar.request_ref,
                 details={"employee": employee.employee_ref, "employee_jurisdiction": employee.jurisdiction.code,
                          "asset": asset.asset_ref, "asset_jurisdiction": jcode, "access_type": access_type,
                          "decision": decision.decision, "risk_score": decision.risk_score,
                          "failed_rules": [r.code for r in decision.failed]},
                 jurisdiction_code=jcode, timestamp=now)

    # Steps 7-9: gaps for failed detective controls, routed to an owner with an SLA deadline.
    rule_meta = {r["code"]: r for r in lk.rules}
    gap_refs = []
    for r in decision.failed:
        if not r.raises_gap:
            continue
        meta = rule_meta[r.code]
        impact = decision.effective_classification
        likelihood = SEVERITY_RANK[r.severity]
        severity = matrix_severity(impact, likelihood)
        gap_j = jcode if r.code != "ACC-003" and r.code != "ACC-004" else employee.jurisdiction.code
        owner = lk.owner_for(meta["owner_function"], gap_j, asset.domain, asset.owner_id)
        gap, _ = raise_gap(
            db, audit, dedup_key=gap_dedup_key(r.code, ctx), source="access_check",
            title=f"{r.code} {r.name}", description=r.message, impact=impact, likelihood=likelihood, severity=severity,
            jurisdiction_id=lk.jurisdictions[gap_j].id, owner_id=owner, remediation_action=meta["remediation"], now=now,
            jurisdiction_code=gap_j, rule_code=r.code, access_request_id=ar.id, asset_id=asset.id, employee_id=employee.id,
        )
        gap_refs.append(gap.gap_ref)
    if gap_refs:
        ar.evaluation_trace = {**ar.evaluation_trace, "gaps": gap_refs}
    return ar
