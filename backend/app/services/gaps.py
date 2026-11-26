"""Compliance gap lifecycle: raise (with de-duplication), assign, remediate, auto-resolve on retest."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..engine.severity import REMEDIATION_SLA_DAYS, SEVERITY_RANK
from ..models import (
    AccessRequest,
    ComplianceGap,
    DataAsset,
    DataLocalisationRecord,
    Employee,
    Policy,
    RemediationTask,
    TransferMechanism,
)
from .audit import AuditTrail

OPEN_STATUSES = ("Open", "In Remediation")


def next_ref(db: Session, model, prefix: str, width: int = 5) -> str:
    n = db.execute(select(func.count()).select_from(model)).scalar_one() + 1
    return f"{prefix}-{n:0{width}d}"


def raise_gap(
    db: Session, audit: AuditTrail, *, dedup_key: str, source: str, title: str, description: str,
    impact: int, likelihood: int, severity: str, jurisdiction_id: int | None, owner_id: int | None,
    remediation_action: str, now: datetime, actor: str = "control-engine", jurisdiction_code: str | None = None,
    rule_code: str | None = None, control_id: int | None = None, assessment_id: int | None = None,
    access_request_id: int | None = None, asset_id: int | None = None, employee_id: int | None = None,
) -> tuple[ComplianceGap, bool]:
    """Create a gap, or bump the existing open gap with the same dedup key. Returns (gap, created)."""
    existing = db.execute(
        select(ComplianceGap).where(ComplianceGap.dedup_key == dedup_key, ComplianceGap.status.in_(OPEN_STATUSES))
    ).scalar_one_or_none()
    if existing:
        existing.occurrences += 1
        existing.last_seen_at = now
        existing.description = description
        if assessment_id:
            existing.assessment_id = assessment_id
        if SEVERITY_RANK[severity] > SEVERITY_RANK[existing.severity]:
            audit.record(actor=actor, action="GAP_ESCALATED", entity_type="ComplianceGap", entity_id=existing.gap_ref,
                         details={"from": existing.severity, "to": severity}, jurisdiction_code=jurisdiction_code, timestamp=now)
            existing.severity, existing.impact, existing.likelihood = severity, impact, likelihood
        return existing, False

    due = (now + timedelta(days=REMEDIATION_SLA_DAYS[severity])).date()
    gap = ComplianceGap(
        gap_ref=next_ref(db, ComplianceGap, "GAP"), dedup_key=dedup_key, source=source, rule_code=rule_code,
        control_id=control_id, assessment_id=assessment_id, access_request_id=access_request_id, asset_id=asset_id,
        employee_id=employee_id, jurisdiction_id=jurisdiction_id, title=title, description=description, impact=impact,
        likelihood=likelihood, severity=severity, status="Open", owner_id=owner_id, occurrences=1,
        identified_at=now, last_seen_at=now, due_date=due,
    )
    db.add(gap)
    db.flush()
    task = RemediationTask(
        task_ref=next_ref(db, RemediationTask, "RT"), gap_id=gap.id, title=f"Remediate: {title}"[:200],
        action=remediation_action, owner_id=owner_id, priority=severity, status="Not Started", due_date=due, created_at=now,
    )
    db.add(task)
    db.flush()
    audit.record(actor=actor, action="GAP_CREATED", entity_type="ComplianceGap", entity_id=gap.gap_ref,
                 details={"severity": severity, "source": source, "rule": rule_code, "owner_id": owner_id, "due": due.isoformat(), "task": task.task_ref},
                 jurisdiction_code=jurisdiction_code, timestamp=now)
    return gap, True


def close_gap(db: Session, audit: AuditTrail, gap: ComplianceGap, *, status: str, note: str, when: datetime,
              actor: str, jurisdiction_code: str | None = None) -> None:
    gap.status = status
    gap.resolved_at = when
    gap.resolution_note = note
    for t in gap.tasks:
        if t.status != "Completed":
            t.status = "Completed"
            t.completed_at = when
    audit.record(actor=actor, action="GAP_" + status.upper().replace(" ", "_"), entity_type="ComplianceGap",
                 entity_id=gap.gap_ref, details={"note": note}, jurisdiction_code=jurisdiction_code, timestamp=when)


# ------------------------------------------------------------------ simulated remediation
def apply_remediation(db: Session, gap: ComplianceGap, when: datetime) -> str:
    """Apply the corrective action to the synthetic data so a retest passes.

    Used by the seed (to simulate a remediation history) and by POST /api/gaps/{id}/remediate in the demo.
    """
    d: date = when.date()
    key = gap.rule_code or (gap.control.test_type if gap.control else "")
    ids = _evidence_ids(db, gap)

    def assets():
        return [db.get(DataAsset, i) for i in ids.get("asset", [])] or ([db.get(DataAsset, gap.asset_id)] if gap.asset_id else [])

    def employees():
        return [db.get(Employee, i) for i in ids.get("employee", [])] or ([db.get(Employee, gap.employee_id)] if gap.employee_id else [])

    def grants():
        return [db.get(AccessRequest, i) for i in ids.get("grant", [])]

    if key in ("ACC-004", "training"):
        for e in employees():
            e.last_training_date = d
        return "Training completed for affected employees."
    if key in ("DAT-002", "asset_ownership"):
        from ..models import Stakeholder
        for a in assets():
            a.owner_id = a.owner_id or db.execute(select(Stakeholder.id).where(Stakeholder.function == "Data Owner", Stakeholder.domain == a.domain)).scalar()
        return "Accountable owners assigned."
    if key in ("DAT-001", "asset_classification"):
        for a in assets():
            a.classification_id = a.classification_id or 3
        return "Assets classified (provisionally Confidential)."
    if key in ("DAT-003", "encryption_at_rest"):
        for a in assets():
            a.encrypted_at_rest = True
        return "Encryption at rest enabled."
    if key in ("DAT-004", "retention"):
        for a in assets():
            a.oldest_record_date = d - timedelta(days=max(30, a.retention_days - 30))
        return "Retention purge executed."
    if key in ("PUR-002", "processor_agreements"):
        for a in assets():
            a.processor_agreement_ref = a.processor_agreement_ref or f"DPA-{a.id:04d}"
        return "Processor agreements executed and registered."
    if key == "dpia":
        for a in assets():
            a.dpia_completed = True
        return "DPIAs completed."
    if key == "ropa":
        for a in assets():
            a.ropa_registered = True
        return "Processing activities registered in the RoPA."
    if key == "residency":
        for lid in ids.get("location", []):
            loc = db.get(DataLocalisationRecord, lid)
            loc.location_jurisdiction_id = loc.asset.jurisdiction_id
            loc.hosting_region = f"{loc.hosting_region} -> relocated in-jurisdiction"
            loc.verified_at = d
        return "Non-compliant copies relocated in-jurisdiction."
    if key in ("LOC-002", "transfer_mechanisms"):
        for mid in ids.get("mechanism", []):
            m = db.get(TransferMechanism, mid)
            m.valid_until = max(m.valid_until, d) + timedelta(days=730)
            m.tia_completed = True
        for pair in ids.get("pair", []):
            src, dst = pair
            db.add(TransferMechanism(source_jurisdiction_id=src, destination_jurisdiction_id=dst, mechanism="EU SCCs (2021/914) Module 1",
                                     reference=f"SCC-{src}-{dst}-{d.year}", valid_from=d, valid_until=d + timedelta(days=1095), tia_completed=True))
        return "Transfer mechanisms executed/renewed with TIA."
    if key in ("leaver_access", "dormant_access", "cid_access"):
        for g in grants():
            g.revoked_at = d
        return "Entitlements revoked."
    if key == "recertification":
        for g in grants():
            g.last_recertified_at = d
        return "Entitlements recertified."
    if key == "privileged_review":
        for e in employees():
            e.last_access_review = d
        return "Privileged access review completed."
    if key == "policy_review":
        for pid in ids.get("policy", []):
            p = db.get(Policy, pid)
            p.last_reviewed = d
            p.next_review_date = d + timedelta(days=30 * p.review_cycle_months)
        return "Policies reviewed."
    return "Corrective action completed."


def _evidence_ids(db: Session, gap: ComplianceGap) -> dict[str, list]:
    if not gap.assessment_id:
        out: dict[str, list] = {}
        if gap.rule_code == "LOC-002" and gap.access_request_id:
            ar = db.get(AccessRequest, gap.access_request_id)
            src, dst = ar.asset.jurisdiction_id, ar.employee.jurisdiction_id
            mech = db.execute(select(TransferMechanism).where(TransferMechanism.source_jurisdiction_id == src,
                                                             TransferMechanism.destination_jurisdiction_id == dst).order_by(TransferMechanism.id)).scalars().all()
            if mech:
                out["mechanism"] = [m.id for m in mech]
            else:
                out["pair"] = [(src, dst)]
        return out
    from ..models import ControlAssessment
    a = db.get(ControlAssessment, gap.assessment_id)
    out = {}
    for ev in a.evidence or []:
        if ev["entity"] == "pair":
            out.setdefault("pair", []).append(tuple(ev["id"]))
        else:
            out.setdefault(ev["entity"], []).append(ev["id"])
    return out
