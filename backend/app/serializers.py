"""Model -> JSON-safe dict converters used by the routers (and the static demo export)."""
from __future__ import annotations

from datetime import date, datetime

from .engine.severity import CLASSIFICATION_NAMES
from .models import (
    AccessRequest,
    ComplianceGap,
    ControlAssessment,
    DataAsset,
    Employee,
    GovernanceControl,
    Jurisdiction,
    Policy,
    RemediationTask,
    Stakeholder,
)


def iso(v):
    return v.isoformat() if isinstance(v, (date, datetime)) else v


def jurisdiction(j: Jurisdiction) -> dict:
    return {
        "id": j.id, "code": j.code, "name": j.name, "region": j.region, "is_eu": j.is_eu, "is_eea": j.is_eea,
        "eu_adequacy": j.eu_adequacy, "data_protection_authority": j.data_protection_authority,
        "financial_regulator": j.financial_regulator, "primary_law": j.primary_law, "residency_regime": j.residency_regime,
        "banking_secrecy": j.banking_secrecy, "breach_notification_hours": j.breach_notification_hours,
        "inherent_risk": j.inherent_risk, "status": j.status, "onboarded_at": iso(j.onboarded_at),
    }


def stakeholder(s: Stakeholder | None) -> dict | None:
    if s is None:
        return None
    return {"id": s.id, "name": s.name, "title": s.title, "function": s.function, "email": s.email,
            "jurisdiction": s.jurisdiction.code if s.jurisdiction else None, "domain": s.domain}


def asset(a: DataAsset) -> dict:
    level = a.classification.level if a.classification else None
    return {
        "id": a.id, "asset_ref": a.asset_ref, "name": a.name, "domain": a.domain, "system": a.system,
        "hosting_provider": a.hosting_provider, "is_third_party_hosted": a.is_third_party_hosted,
        "processor_agreement_ref": a.processor_agreement_ref, "jurisdiction": a.jurisdiction.code,
        "classification_level": level, "classification": CLASSIFICATION_NAMES.get(level, "Unclassified"),
        "owner_id": a.owner_id, "owner": a.owner.name if a.owner else None,
        "contains_personal_data": a.contains_personal_data, "contains_special_category": a.contains_special_category,
        "contains_cid": a.contains_cid, "residency_required": a.residency_required, "encrypted_at_rest": a.encrypted_at_rest,
        "dpia_completed": a.dpia_completed, "ropa_registered": a.ropa_registered, "retention_days": a.retention_days,
        "oldest_record_date": iso(a.oldest_record_date), "record_count": a.record_count, "allowed_purposes": a.allowed_purposes,
        "created_at": iso(a.created_at), "last_reviewed_at": iso(a.last_reviewed_at),
        "locations": [{"id": loc.id, "jurisdiction": loc.location.code, "type": loc.location_type, "hosting_region": loc.hosting_region,
                       "compliant": loc.compliant, "issue": loc.issue} for loc in a.locations],
    }


def employee(e: Employee) -> dict:
    return {
        "id": e.id, "employee_ref": e.employee_ref, "full_name": e.full_name, "email": e.email,
        "jurisdiction": e.jurisdiction.code, "business_unit": e.business_unit, "role": e.role.name,
        "role_privileged": e.role.privileged, "status": e.status, "hire_date": iso(e.hire_date),
        "termination_date": iso(e.termination_date), "last_training_date": iso(e.last_training_date),
        "last_access_review": iso(e.last_access_review),
    }


def access_request(r: AccessRequest, include_trace: bool = False) -> dict:
    d = {
        "id": r.id, "request_ref": r.request_ref, "employee_id": r.employee_id, "employee_ref": r.employee.employee_ref,
        "employee_name": r.employee.full_name, "employee_jurisdiction": r.employee.jurisdiction.code,
        "asset_id": r.asset_id, "asset_ref": r.asset.asset_ref, "asset_name": r.asset.name,
        "asset_jurisdiction": r.asset.jurisdiction.code, "access_type": r.access_type, "purpose": r.purpose,
        "ticket_ref": r.ticket_ref, "requested_at": iso(r.requested_at), "decision": r.decision,
        "decision_reason": r.decision_reason, "risk_score": r.risk_score, "risk_rating": r.risk_rating,
        "cross_border": r.cross_border, "legacy": r.request_ref.startswith("LEG-"),
        "granted_until": iso(r.granted_until), "revoked_at": iso(r.revoked_at),
    }
    if include_trace:
        d["justification"] = r.justification
        d["trace"] = r.evaluation_trace
        d["approvals"] = [{"type": a.approval_type, "status": a.status, "decided_at": iso(a.decided_at),
                           "approver": a.approver.name if a.approver else None} for a in r.approvals]
    return d


def control(c: GovernanceControl) -> dict:
    return {
        "id": c.id, "code": c.code, "name": c.name, "domain": c.domain, "description": c.description,
        "test_type": c.test_type, "control_type": c.control_type, "criticality": c.criticality, "threshold": c.threshold,
        "frequency": c.frequency, "scope": c.scope, "enabled": c.enabled, "owner": c.owner.name if c.owner else None,
        "requirements": [r.code for r in c.requirements], "remediation": c.remediation,
    }


def assessment(a: ControlAssessment, include_evidence: bool = False) -> dict:
    d = {
        "id": a.id, "control_id": a.control_id, "control_code": a.control.code, "control_name": a.control.name,
        "jurisdiction": a.jurisdiction.code if a.jurisdiction else "EMEA", "cycle": a.cycle, "as_of": iso(a.as_of),
        "population": a.population, "exceptions": a.exceptions, "pass_rate": a.pass_rate, "result": a.result,
        "severity": a.severity, "assessed_at": iso(a.assessed_at),
    }
    if include_evidence:
        d["evidence"] = a.evidence
    return d


def task(t: RemediationTask) -> dict:
    return {"id": t.id, "task_ref": t.task_ref, "gap_id": t.gap_id, "gap_ref": t.gap.gap_ref, "title": t.title, "action": t.action,
            "owner": t.owner.name if t.owner else None, "owner_id": t.owner_id, "priority": t.priority, "status": t.status,
            "due_date": iso(t.due_date), "created_at": iso(t.created_at), "completed_at": iso(t.completed_at),
            "jurisdiction": t.gap.jurisdiction.code if t.gap.jurisdiction else "EMEA"}


def gap(g: ComplianceGap, today: date | None = None) -> dict:
    today = today or date.today()
    open_ = g.status in ("Open", "In Remediation")
    return {
        "id": g.id, "gap_ref": g.gap_ref, "source": g.source, "rule_code": g.rule_code,
        "control_code": g.control.code if g.control else None, "assessment_id": g.assessment_id,
        "access_request_id": g.access_request_id, "asset_id": g.asset_id, "employee_id": g.employee_id,
        "jurisdiction": g.jurisdiction.code if g.jurisdiction else "EMEA", "title": g.title, "description": g.description,
        "impact": g.impact, "likelihood": g.likelihood, "severity": g.severity, "status": g.status,
        "owner": g.owner.name if g.owner else None, "owner_id": g.owner_id, "owner_title": g.owner.title if g.owner else None,
        "occurrences": g.occurrences, "identified_at": iso(g.identified_at), "last_seen_at": iso(g.last_seen_at),
        "due_date": iso(g.due_date), "resolved_at": iso(g.resolved_at), "resolution_note": g.resolution_note,
        "overdue": open_ and g.due_date < today, "tasks": [task(t) for t in g.tasks],
    }


def policy(p: Policy, include_versions: bool = False) -> dict:
    d = {"id": p.id, "code": p.code, "title": p.title, "doc_type": p.doc_type, "owner": p.owner.name if p.owner else None,
         "status": p.status, "current_version": p.current_version, "review_cycle_months": p.review_cycle_months,
         "last_reviewed": iso(p.last_reviewed), "next_review_date": iso(p.next_review_date),
         "review_overdue": p.next_review_date < date.today(), "requirements": [r.code for r in p.requirements],
         "version_count": len(p.versions)}
    if include_versions:
        d["versions"] = [{"id": v.id, "version": v.version, "status": v.status, "change_summary": v.change_summary,
                          "content": v.content, "author": v.author, "approved_by": v.approved_by, "approved_at": iso(v.approved_at),
                          "effective_date": iso(v.effective_date), "created_at": iso(v.created_at)} for v in p.versions]
    return d
