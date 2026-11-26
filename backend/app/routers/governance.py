"""Access control, localisation, control engine, gaps, remediation, risk, policies, stakeholders, audit."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import serializers as S
from ..auth import admin_only, can_write, get_current_user
from ..database import get_db
from ..models import (
    AccessRequest,
    AuditLog,
    ComplianceGap,
    ControlAssessment,
    DataAsset,
    DataLocalisationRecord,
    Employee,
    GovernanceControl,
    GovernanceRule,
    Policy,
    PolicyVersion,
    Project,
    RemediationTask,
    RiskAssessment,
    Stakeholder,
    TransferMechanism,
)
from ..schemas import AccessRequestIn, AssessmentRunIn, GapUpdate, PolicyVersionIn, RuleUpdate, TaskUpdate
from ..services.access_service import submit_access_request
from ..services.assessments import run_cycle
from ..services.audit import AuditTrail, verify_chain
from ..services.gaps import apply_remediation, close_gap
from ..services.lookups import Lookups
from ..services.risk import compute_risk

router = APIRouter()
Auth = Depends(get_current_user)


def _gap_query():
    return select(ComplianceGap).options(selectinload(ComplianceGap.owner), selectinload(ComplianceGap.jurisdiction),
                                         selectinload(ComplianceGap.control), selectinload(ComplianceGap.tasks).selectinload(RemediationTask.owner))


# ------------------------------------------------------------------ access control
@router.post("/access-requests/evaluate", tags=["access control"], status_code=201,
             summary="Submit an access request and run the 10-step control pipeline")
def evaluate_access(body: AccessRequestIn, db: Session = Depends(get_db), user=Depends(can_write)):
    emp = db.get(Employee, body.employee_id)
    asset = db.get(DataAsset, body.asset_id)
    if not emp or not asset:
        raise HTTPException(404, "Unknown employee or asset")
    now = datetime.utcnow().replace(microsecond=0)
    lk, audit = Lookups(db), AuditTrail(db)
    approvals = [{"approval_type": a.approval_type, "status": a.status, "decided_at": a.decided_at or now,
                  "approver_id": lk.owner_for({"DATA_OWNER": "Data Owner", "DPO": "DPO"}.get(a.approval_type, "Executive"),
                                              asset.jurisdiction.code, asset.domain, asset.owner_id) if a.approval_type != "LINE_MANAGER" else None}
                 for a in body.approvals]
    ar = submit_access_request(db, lk, audit, employee=emp, asset=asset, access_type=body.access_type, purpose=body.purpose,
                               justification=body.justification, ticket_ref=body.ticket_ref, approvals=approvals,
                               actor=user.username, now=now)
    db.flush()
    compute_risk(db, lk, audit, as_of=now.date())  # step 10: refresh the regional risk dashboard
    db.commit()
    db.refresh(ar)
    return S.access_request(ar, include_trace=True)


@router.get("/access-requests", tags=["access control"])
def list_access_requests(db: Session = Depends(get_db), _=Auth):
    q = select(AccessRequest).options(selectinload(AccessRequest.employee).selectinload(Employee.jurisdiction),
                                      selectinload(AccessRequest.asset).selectinload(DataAsset.jurisdiction)).order_by(AccessRequest.requested_at.desc())
    return [S.access_request(r) for r in db.execute(q).scalars()]


@router.get("/access-requests/{request_id}", tags=["access control"])
def get_access_request(request_id: int, db: Session = Depends(get_db), _=Auth):
    r = db.get(AccessRequest, request_id)
    if not r:
        raise HTTPException(404, "Not found")
    return S.access_request(r, include_trace=True)


# ------------------------------------------------------------------ localisation
@router.get("/localisation/records", tags=["localisation"])
def localisation_records(db: Session = Depends(get_db), _=Auth):
    lk = Lookups(db)
    today = date.today()
    out = []
    q = select(DataLocalisationRecord).options(selectinload(DataLocalisationRecord.asset).selectinload(DataAsset.jurisdiction),
                                               selectinload(DataLocalisationRecord.location))
    for r in db.execute(q).scalars():
        a = r.asset
        src, dst = a.jurisdiction.code, r.location.code
        status, issue = "Compliant", None
        if src != dst:
            if a.residency_required:
                status, issue = "Residency breach", f"Residency-restricted asset has a {r.location_type} copy in {dst}"
            elif a.contains_personal_data and not lk.adequate(src, dst):
                m = lk.mechanism(src, dst, today)
                if not m:
                    status, issue = "No transfer mechanism", f"No mechanism for {src} -> {dst}"
                elif m.valid_until < today:
                    status, issue = "Mechanism expired", f"{m.reference} expired {m.valid_until}"
                elif not m.tia_completed:
                    status, issue = "TIA missing", f"{m.reference} has no transfer impact assessment"
                else:
                    status = "Covered by mechanism"
            elif a.contains_personal_data:
                status = "Adequate destination"
        out.append({"id": r.id, "asset_id": a.id, "asset_ref": a.asset_ref, "asset_name": a.name, "asset_jurisdiction": src,
                    "location_jurisdiction": dst, "location_type": r.location_type, "hosting_region": r.hosting_region,
                    "personal_data": a.contains_personal_data, "residency_required": a.residency_required,
                    "verified_at": S.iso(r.verified_at), "status": status, "issue": issue})
    return out


@router.get("/localisation/transfer-mechanisms", tags=["localisation"])
def transfer_mechanisms(db: Session = Depends(get_db), _=Auth):
    today = date.today()
    q = select(TransferMechanism).options(selectinload(TransferMechanism.source), selectinload(TransferMechanism.destination))
    return [{"id": m.id, "source": m.source.code, "destination": m.destination.code, "mechanism": m.mechanism, "reference": m.reference,
             "valid_from": S.iso(m.valid_from), "valid_until": S.iso(m.valid_until), "tia_completed": m.tia_completed,
             "status": "Expired" if m.valid_until < today else ("TIA missing" if not m.tia_completed else
                                                                ("Expiring" if (m.valid_until - today).days < 90 else "Valid"))}
            for m in db.execute(q).scalars()]


# ------------------------------------------------------------------ rules & controls
@router.get("/rules", tags=["control engine"])
def list_rules(db: Session = Depends(get_db), _=Auth):
    return [Lookups.rule_dict(r) | {"description": r.description} for r in db.execute(select(GovernanceRule).order_by(GovernanceRule.code)).scalars()]


@router.patch("/rules/{code}", tags=["control engine"], summary="Reconfigure a governance rule at runtime")
def update_rule(code: str, body: RuleUpdate, db: Session = Depends(get_db), user=Depends(admin_only)):
    r = db.execute(select(GovernanceRule).where(GovernanceRule.code == code.upper())).scalar_one_or_none()
    if not r:
        raise HTTPException(404, "Unknown rule")
    changes = body.model_dump(exclude_none=True)
    before = {k: getattr(r, k) for k in changes}
    for k, v in changes.items():
        setattr(r, k, v)
    AuditTrail(db).record(actor=user.username, action="RULE_RECONFIGURED", entity_type="GovernanceRule", entity_id=r.code,
                          details={"before": before, "after": changes})
    db.commit()
    return Lookups.rule_dict(r) | {"description": r.description}


@router.get("/controls", tags=["control engine"])
def list_controls(db: Session = Depends(get_db), _=Auth):
    q = select(GovernanceControl).options(selectinload(GovernanceControl.owner), selectinload(GovernanceControl.requirements)).order_by(GovernanceControl.code)
    return [S.control(c) for c in db.execute(q).scalars()]


@router.get("/assessments", tags=["control engine"])
def list_assessments(cycle: str | None = None, db: Session = Depends(get_db), _=Auth):
    q = select(ControlAssessment).options(selectinload(ControlAssessment.control), selectinload(ControlAssessment.jurisdiction)).order_by(ControlAssessment.id)
    if cycle:
        q = q.where(ControlAssessment.cycle == cycle)
    return [S.assessment(a) for a in db.execute(q).scalars()]


@router.get("/assessments/{assessment_id}", tags=["control engine"])
def get_assessment(assessment_id: int, db: Session = Depends(get_db), _=Auth):
    a = db.get(ControlAssessment, assessment_id)
    if not a:
        raise HTTPException(404, "Not found")
    return S.assessment(a, include_evidence=True)


@router.post("/assessments/run", tags=["control engine"], summary="Run automated control tests now (all or selected controls)")
def run_assessments(body: AssessmentRunIn, db: Session = Depends(get_db), user=Depends(can_write)):
    lk, audit = Lookups(db), AuditTrail(db)
    as_of = body.as_of or date.today()
    results = run_cycle(db, lk, audit, as_of=as_of, now=datetime.utcnow(), actor=user.username, control_codes=body.control_codes)
    db.flush()
    compute_risk(db, lk, audit, as_of=as_of)
    db.commit()
    summary = {}
    for a in results:
        summary[a.result] = summary.get(a.result, 0) + 1
    return {"as_of": as_of.isoformat(), "assessments": len(results), "results": summary}


# ------------------------------------------------------------------ gaps & remediation
@router.get("/gaps", tags=["gaps & remediation"])
def list_gaps(status: str | None = None, severity: str | None = None, jurisdiction: str | None = None,
              db: Session = Depends(get_db), _=Auth):
    today = date.today()
    out = [S.gap(g, today) for g in db.execute(_gap_query().order_by(ComplianceGap.identified_at.desc())).scalars()]
    return [g for g in out if (not status or g["status"] == status) and (not severity or g["severity"] == severity)
            and (not jurisdiction or g["jurisdiction"] == jurisdiction.upper())]


@router.patch("/gaps/{gap_id}", tags=["gaps & remediation"])
def update_gap(gap_id: int, body: GapUpdate, db: Session = Depends(get_db), user=Depends(can_write)):
    g = db.get(ComplianceGap, gap_id)
    if not g:
        raise HTTPException(404, "Not found")
    audit = AuditTrail(db)
    jcode = g.jurisdiction.code if g.jurisdiction else None
    if body.owner_id is not None:
        if not db.get(Stakeholder, body.owner_id):
            raise HTTPException(422, "Unknown stakeholder")
        audit.record(actor=user.username, action="GAP_REASSIGNED", entity_type="ComplianceGap", entity_id=g.gap_ref,
                     details={"from": g.owner_id, "to": body.owner_id}, jurisdiction_code=jcode)
        g.owner_id = body.owner_id
        for t in g.tasks:
            t.owner_id = body.owner_id
    if body.status and body.status != g.status:
        if body.status in ("Resolved", "Risk Accepted"):
            close_gap(db, audit, g, status=body.status, note=body.note or f"{body.status} by {user.username}",
                      when=datetime.utcnow(), actor=user.username, jurisdiction_code=jcode)
        else:
            audit.record(actor=user.username, action="GAP_STATUS_CHANGED", entity_type="ComplianceGap", entity_id=g.gap_ref,
                         details={"from": g.status, "to": body.status}, jurisdiction_code=jcode)
            g.status = body.status
            g.resolved_at = None
    db.commit()
    db.refresh(g)
    return S.gap(g)


@router.post("/gaps/{gap_id}/remediate", tags=["gaps & remediation"],
             summary="Simulate the corrective action on the synthetic data and close the gap")
def remediate_gap(gap_id: int, db: Session = Depends(get_db), user=Depends(can_write)):
    g = db.get(ComplianceGap, gap_id)
    if not g or g.status not in ("Open", "In Remediation"):
        raise HTTPException(404, "No open gap with that id")
    now = datetime.utcnow()
    note = apply_remediation(db, g, now)
    db.flush()
    lk, audit = Lookups(db), AuditTrail(db)
    close_gap(db, audit, g, status="Resolved", note=f"{note} (remediated by {user.username}; retest on next cycle)",
              when=now, actor=user.username, jurisdiction_code=g.jurisdiction.code if g.jurisdiction else None)
    db.flush()
    compute_risk(db, lk, audit, as_of=now.date())
    db.commit()
    db.refresh(g)
    return S.gap(g)


@router.get("/remediation-tasks", tags=["gaps & remediation"])
def list_tasks(db: Session = Depends(get_db), _=Auth):
    q = select(RemediationTask).options(selectinload(RemediationTask.owner), selectinload(RemediationTask.gap).selectinload(ComplianceGap.jurisdiction))
    return [S.task(t) for t in db.execute(q.order_by(RemediationTask.due_date)).scalars()]


@router.patch("/remediation-tasks/{task_id}", tags=["gaps & remediation"])
def update_task(task_id: int, body: TaskUpdate, db: Session = Depends(get_db), user=Depends(can_write)):
    t = db.get(RemediationTask, task_id)
    if not t:
        raise HTTPException(404, "Not found")
    changes = body.model_dump(exclude_none=True)
    for k, v in changes.items():
        setattr(t, k, v)
    if body.status == "Completed":
        t.completed_at = datetime.utcnow()
    elif body.status == "In Progress" and t.gap.status == "Open":
        t.gap.status = "In Remediation"
    AuditTrail(db).record(actor=user.username, action="TASK_UPDATED", entity_type="RemediationTask", entity_id=t.task_ref,
                          details={k: S.iso(v) for k, v in changes.items()}, jurisdiction_code=t.gap.jurisdiction.code if t.gap.jurisdiction else None)
    db.commit()
    return S.task(t)


# ------------------------------------------------------------------ risk
@router.get("/risk/jurisdictions", tags=["risk"])
def risk_latest(db: Session = Depends(get_db), _=Auth):
    rows = db.execute(select(RiskAssessment).options(selectinload(RiskAssessment.jurisdiction)).order_by(RiskAssessment.as_of)).scalars().all()
    latest = {}
    for r in rows:
        latest[r.jurisdiction_id] = r
    return sorted([_risk(r) for r in latest.values()], key=lambda x: -x["residual_score"])


@router.get("/risk/history", tags=["risk"])
def risk_history(db: Session = Depends(get_db), _=Auth):
    q = select(RiskAssessment).options(selectinload(RiskAssessment.jurisdiction)).order_by(RiskAssessment.as_of)
    return [_risk(r) for r in db.execute(q).scalars()]


@router.post("/risk/recalculate", tags=["risk"])
def risk_recalculate(db: Session = Depends(get_db), user=Depends(can_write)):
    lk = Lookups(db)
    res = compute_risk(db, lk, AuditTrail(db), as_of=date.today())
    db.commit()
    return [_risk(r) for r in res]


def _risk(r: RiskAssessment) -> dict:
    return {"jurisdiction": r.jurisdiction.code, "name": r.jurisdiction.name, "as_of": S.iso(r.as_of), "cycle": r.cycle,
            "control_effectiveness": r.control_effectiveness, "open_gap_score": r.open_gap_score, "overdue_ratio": r.overdue_ratio,
            "access_denial_rate": r.access_denial_rate, "inherent_risk": r.jurisdiction.inherent_risk,
            "residual_score": r.residual_score, "rating": r.rating, "drivers": r.drivers}


# ------------------------------------------------------------------ policies
@router.get("/policies", tags=["policies"])
def list_policies(db: Session = Depends(get_db), _=Auth):
    q = select(Policy).options(selectinload(Policy.owner), selectinload(Policy.requirements), selectinload(Policy.versions)).order_by(Policy.code)
    return [S.policy(p, include_versions=True) for p in db.execute(q).scalars()]


@router.post("/policies/{policy_id}/versions", tags=["policies"], status_code=201, summary="Draft a new policy version")
def draft_version(policy_id: int, body: PolicyVersionIn, db: Session = Depends(get_db), user=Depends(can_write)):
    p = db.get(Policy, policy_id)
    if not p:
        raise HTTPException(404, "Not found")
    if any(v.status in ("Draft", "In Review") for v in p.versions):
        raise HTTPException(409, "A draft is already in progress for this policy")
    major, minor = (int(x) for x in p.current_version.split("."))
    new = f"{major + 1}.0" if body.major else f"{major}.{minor + 1}"
    v = PolicyVersion(policy_id=p.id, version=new, status="In Review", change_summary=body.change_summary, content=body.content,
                      author=user.full_name, created_at=datetime.utcnow())
    db.add(v)
    AuditTrail(db).record(actor=user.username, action="POLICY_VERSION_DRAFTED", entity_type="Policy", entity_id=f"{p.code} v{new}",
                          details={"change_summary": body.change_summary})
    db.commit()
    db.refresh(p)
    return S.policy(p, include_versions=True)


@router.post("/policies/{policy_id}/versions/{version_id}/approve", tags=["policies"],
             summary="Approve and publish a version (maker-checker: approver must differ from author)")
def approve_version(policy_id: int, version_id: int, db: Session = Depends(get_db), user=Depends(admin_only)):
    p = db.get(Policy, policy_id)
    v = db.get(PolicyVersion, version_id)
    if not p or not v or v.policy_id != p.id:
        raise HTTPException(404, "Not found")
    if v.status != "In Review":
        raise HTTPException(409, "Only versions in review can be approved")
    if v.author == user.full_name:
        raise HTTPException(403, "Maker-checker: the author cannot approve their own version")
    now = datetime.utcnow()
    for old in p.versions:
        if old.status == "Published":
            old.status = "Superseded"
    v.status, v.approved_by, v.approved_at, v.effective_date = "Published", user.full_name, now, now.date()
    p.current_version, p.last_reviewed = v.version, now.date()
    p.next_review_date = now.date() + timedelta(days=30 * p.review_cycle_months)
    AuditTrail(db).record(actor=user.username, action="POLICY_VERSION_PUBLISHED", entity_type="Policy", entity_id=f"{p.code} v{v.version}")
    db.commit()
    db.refresh(p)
    return S.policy(p, include_versions=True)


# ------------------------------------------------------------------ stakeholders & projects
@router.get("/stakeholders", tags=["stakeholders"])
def list_stakeholders(db: Session = Depends(get_db), _=Auth):
    today = date.today()
    gaps = db.execute(select(ComplianceGap).where(ComplianceGap.status.in_(("Open", "In Remediation")))).scalars().all()
    tasks = db.execute(select(RemediationTask).where(RemediationTask.status != "Completed")).scalars().all()
    assets = db.execute(select(DataAsset.owner_id)).all()
    out = []
    for s in db.execute(select(Stakeholder).options(selectinload(Stakeholder.jurisdiction)).order_by(Stakeholder.function, Stakeholder.name)).scalars():
        mine = [g for g in gaps if g.owner_id == s.id]
        out.append(S.stakeholder(s) | {
            "open_gaps": len(mine), "critical_high": sum(1 for g in mine if g.severity in ("Critical", "High")),
            "overdue": sum(1 for g in mine if g.due_date < today), "open_tasks": sum(1 for t in tasks if t.owner_id == s.id),
            "assets_owned": sum(1 for (o,) in assets if o == s.id)})
    return out


@router.get("/projects", tags=["stakeholders"])
def list_projects(db: Session = Depends(get_db), _=Auth):
    q = select(Project).options(selectinload(Project.sponsor), selectinload(Project.activities)).order_by(Project.code)
    return [{"id": p.id, "code": p.code, "name": p.name, "description": p.description, "status": p.status,
             "sponsor": p.sponsor.name if p.sponsor else None, "start_date": S.iso(p.start_date), "target_date": S.iso(p.target_date),
             "progress": round(100 * sum(1 for a in p.activities if a.status == "Done") / max(1, len(p.activities))),
             "activities": [{"id": a.id, "title": a.title, "type": a.activity_type, "status": a.status, "due_date": S.iso(a.due_date)}
                            for a in sorted(p.activities, key=lambda a: a.due_date)]}
            for p in db.execute(q).scalars()]


# ------------------------------------------------------------------ audit
@router.get("/audit", tags=["audit"])
def audit_log(limit: int = 1000, action: str | None = None, db: Session = Depends(get_db), _=Auth):
    q = select(AuditLog).order_by(AuditLog.id.desc()).limit(min(limit, 5000))
    if action:
        q = q.where(AuditLog.action == action)
    return [{"id": a.id, "timestamp": S.iso(a.timestamp), "actor": a.actor, "action": a.action, "entity_type": a.entity_type,
             "entity_id": a.entity_id, "jurisdiction": a.jurisdiction_code, "details": a.details, "hash": a.hash, "prev_hash": a.prev_hash}
            for a in db.execute(q).scalars()]


@router.get("/audit/verify", tags=["audit"], summary="Verify the integrity of the hash-chained audit trail")
def audit_verify(db: Session = Depends(get_db), _=Auth):
    return verify_chain(db)
