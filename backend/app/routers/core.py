"""Auth, dashboard, metrics, jurisdictions (incl. onboarding workflow), reference data."""
from __future__ import annotations

from collections import Counter
from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from .. import serializers as S
from ..auth import admin_only, create_access_token, get_current_user, verify_password
from ..database import get_db
from ..engine.severity import SEVERITIES
from ..engine.transfers import adequacy_matrix
from ..models import (
    DOMAIN_ENTITIES,
    AccessRequest,
    AuditLog,
    ComplianceGap,
    ControlAssessment,
    DataAsset,
    DataClassification,
    Employee,
    GovernanceControl,
    GovernanceRule,
    Jurisdiction,
    RegulatoryRequirement,
    RiskAssessment,
    Role,
    Stakeholder,
    User,
)
from ..schemas import JurisdictionIn, Token
from ..services.audit import AuditTrail
from ..services.lookups import Lookups

router = APIRouter()
Auth = Depends(get_current_user)


# ------------------------------------------------------------------ auth
@router.post("/auth/login", response_model=Token, tags=["auth"])
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.username == form.username)).scalar_one_or_none()
    if not user or not verify_password(form.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Incorrect username or password")
    AuditTrail(db).record(actor=user.username, action="USER_LOGIN", entity_type="User", entity_id=user.username)
    db.commit()
    return Token(access_token=create_access_token(user.username, user.app_role), role=user.app_role, full_name=user.full_name)


@router.get("/auth/me", tags=["auth"])
def me(user: User = Auth):
    return {"username": user.username, "full_name": user.full_name, "role": user.app_role}


# ------------------------------------------------------------------ metrics & dashboard
@router.get("/metrics", tags=["dashboard"], summary="Platform scale metrics (the numbers quoted in the README)")
def metrics(db: Session = Depends(get_db)):
    def count(m, *where):
        return db.execute(select(func.count()).select_from(m).where(*where)).scalar_one()
    return {
        "jurisdictions": count(Jurisdiction, Jurisdiction.status == "Active"),
        "regulatory_requirements": count(RegulatoryRequirement),
        "data_assets": count(DataAsset),
        "employees": count(Employee),
        "access_requests": count(AccessRequest),
        "governance_rules": count(GovernanceRule),
        "governance_rules_enabled": count(GovernanceRule, GovernanceRule.enabled.is_(True)),
        "governance_controls": count(GovernanceControl),
        "control_assessments": count(ControlAssessment),
        "compliance_gaps": count(ComplianceGap),
        "audit_log_entries": count(AuditLog),
        "database_entities": len(DOMAIN_ENTITIES),
        "severity_levels": len(SEVERITIES),
    }


@router.get("/dashboard/summary", tags=["dashboard"])
def dashboard(db: Session = Depends(get_db), _=Auth):
    today = date.today()
    jur = {j.id: j for j in db.execute(select(Jurisdiction)).scalars()}
    latest_date = db.execute(select(func.max(RiskAssessment.as_of))).scalar()
    risks = db.execute(select(RiskAssessment).where(RiskAssessment.as_of == latest_date)).scalars().all() if latest_date else []
    trend = db.execute(select(RiskAssessment).order_by(RiskAssessment.as_of)).scalars().all()
    gaps = db.execute(select(ComplianceGap).options(selectinload(ComplianceGap.owner), selectinload(ComplianceGap.jurisdiction),
                                                    selectinload(ComplianceGap.control), selectinload(ComplianceGap.tasks))).scalars().all()
    open_gaps = [g for g in gaps if g.status in ("Open", "In Remediation")]
    latest_cycle = db.execute(select(func.max(ControlAssessment.cycle))).scalar()
    latest_assess = db.execute(select(ControlAssessment).where(ControlAssessment.cycle == latest_cycle)).scalars().all() if latest_cycle else []
    # keep only the latest run per control/jurisdiction within the cycle
    dedup = {}
    for a in sorted(latest_assess, key=lambda a: a.id):
        dedup[(a.control_id, a.jurisdiction_id)] = a
    latest_assess = list(dedup.values())
    applicable = [a for a in latest_assess if a.result != "Not Applicable"]
    decisions = Counter(d for (d,) in db.execute(select(AccessRequest.decision).where(AccessRequest.request_ref.like("AR-%"))).all())
    recent = db.execute(select(AuditLog).order_by(AuditLog.id.desc()).limit(12)).scalars().all()
    sev_order = {s: i for i, s in enumerate(SEVERITIES)}
    top = sorted(open_gaps, key=lambda g: (sev_order[g.severity], g.due_date))[:8]
    by_j_open = Counter(g.jurisdiction_id for g in open_gaps)

    return {
        "as_of": latest_date.isoformat() if latest_date else None,
        "kpis": {
            "avg_residual_risk": round(sum(r.residual_score for r in risks) / len(risks), 1) if risks else 0,
            "control_effectiveness": round(100 * sum(1 for a in applicable if a.result == "Effective") / len(applicable), 1) if applicable else 100,
            "open_gaps": len(open_gaps),
            "critical_high_open": sum(1 for g in open_gaps if g.severity in ("Critical", "High")),
            "overdue_remediation": sum(1 for g in open_gaps if g.due_date < today),
            "access_requests": sum(decisions.values()),
            "denial_rate": round(decisions.get("DENIED", 0) / max(1, sum(decisions.values())) * 100, 1),
            "latest_cycle": latest_cycle,
        },
        "risk_by_jurisdiction": sorted([
            {"code": jur[r.jurisdiction_id].code, "name": jur[r.jurisdiction_id].name, "residual_score": r.residual_score,
             "rating": r.rating, "control_effectiveness": r.control_effectiveness, "open_gaps": by_j_open.get(r.jurisdiction_id, 0),
             "drivers": r.drivers} for r in risks], key=lambda x: -x["residual_score"]),
        "risk_trend": [{"code": jur[r.jurisdiction_id].code, "as_of": r.as_of.isoformat(), "cycle": r.cycle,
                        "residual_score": r.residual_score} for r in trend],
        "gaps_by_severity": {s: sum(1 for g in open_gaps if g.severity == s) for s in SEVERITIES},
        "gaps_by_status": dict(Counter(g.status for g in gaps)),
        "decisions": dict(decisions),
        "control_results": dict(Counter(a.result for a in latest_assess)),
        "top_gaps": [S.gap(g, today) for g in top],
        "recent_activity": [{"timestamp": S.iso(a.timestamp), "actor": a.actor, "action": a.action, "entity_type": a.entity_type,
                             "entity_id": a.entity_id, "jurisdiction": a.jurisdiction_code} for a in recent],
    }


# ------------------------------------------------------------------ jurisdictions & requirements
@router.get("/jurisdictions", tags=["jurisdictions"])
def list_jurisdictions(db: Session = Depends(get_db), _=Auth):
    reqs = Counter(r.jurisdiction_id for r in db.execute(select(RegulatoryRequirement)).scalars())
    assets = Counter(a for (a,) in db.execute(select(DataAsset.jurisdiction_id)).all())
    emps = Counter(e for (e,) in db.execute(select(Employee.jurisdiction_id)).all())
    out = []
    for j in db.execute(select(Jurisdiction).order_by(Jurisdiction.name)).scalars():
        d = S.jurisdiction(j)
        d.update(national_requirements=reqs.get(j.id, 0), data_assets=assets.get(j.id, 0), employees=emps.get(j.id, 0))
        out.append(d)
    return out


@router.get("/requirements", tags=["jurisdictions"])
def list_requirements(jurisdiction: str | None = None, db: Session = Depends(get_db), _=Auth):
    rows = db.execute(select(RegulatoryRequirement).options(selectinload(RegulatoryRequirement.jurisdiction))
                      .order_by(RegulatoryRequirement.code)).scalars().all()
    out = [{"id": r.id, "code": r.code, "scope": r.scope, "jurisdiction": r.jurisdiction.code if r.jurisdiction else None,
            "regime": r.regime, "reference": r.reference, "title": r.title, "description": r.description,
            "category": r.category, "min_classification": r.min_classification} for r in rows]
    if jurisdiction:
        j = db.execute(select(Jurisdiction).where(Jurisdiction.code == jurisdiction.upper())).scalar_one_or_none()
        if not j:
            raise HTTPException(404, "Unknown jurisdiction")
        out = [r for r in out if r["jurisdiction"] == j.code or r["scope"] == "GLOBAL" or (r["scope"] == "EU" and j.is_eu)]
    return out


@router.get("/transfers/adequacy-matrix", tags=["localisation"])
def adequacy(db: Session = Depends(get_db), _=Auth):
    lk = Lookups(db)
    return adequacy_matrix(list(lk.profiles.values()))


@router.post("/jurisdictions", tags=["jurisdictions"], status_code=201, summary="Start onboarding a new jurisdiction")
def onboard_jurisdiction(body: JurisdictionIn, db: Session = Depends(get_db), user=Depends(admin_only)):
    code = body.code.upper()
    if db.execute(select(Jurisdiction).where(Jurisdiction.code == code)).scalar_one_or_none():
        raise HTTPException(409, "Jurisdiction already exists")
    data = body.model_dump(exclude={"requirements", "dpo_name"})
    data["code"] = code
    j = Jurisdiction(**data, status="Onboarding")
    db.add(j)
    db.flush()
    for r in body.requirements:
        db.add(RegulatoryRequirement(scope="NATIONAL", jurisdiction_id=j.id, **r.model_dump()))
    if body.dpo_name:
        db.add(Stakeholder(name=body.dpo_name, title=f"Data Protection Officer, {j.name}", function="DPO", jurisdiction_id=j.id,
                           email=f"dpo.{code.lower()}@emeaguard-bank.example"))
    AuditTrail(db).record(actor=user.username, action="JURISDICTION_ONBOARDING_STARTED", entity_type="Jurisdiction", entity_id=code,
                          details={"requirements": len(body.requirements)}, jurisdiction_code=code)
    db.commit()
    return {**S.jurisdiction(j), "readiness": onboarding_readiness(db, j)}


def onboarding_readiness(db: Session, j: Jurisdiction) -> dict:
    checks = {
        "has_requirements": db.execute(select(func.count()).select_from(RegulatoryRequirement).where(RegulatoryRequirement.jurisdiction_id == j.id)).scalar_one() > 0,
        "has_dpo": db.execute(select(func.count()).select_from(Stakeholder).where(Stakeholder.jurisdiction_id == j.id, Stakeholder.function == "DPO")).scalar_one() > 0,
        "has_regulator": bool(j.financial_regulator and j.data_protection_authority),
        "residency_regime_set": j.residency_regime in ("Open", "Conditional", "Strict"),
    }
    return {"checks": checks, "ready": all(checks.values())}


@router.get("/jurisdictions/{code}", tags=["jurisdictions"])
def get_jurisdiction(code: str, db: Session = Depends(get_db), _=Auth):
    j = db.execute(select(Jurisdiction).where(Jurisdiction.code == code.upper())).scalar_one_or_none()
    if not j:
        raise HTTPException(404, "Unknown jurisdiction")
    return {**S.jurisdiction(j), "readiness": onboarding_readiness(db, j),
            "stakeholders": [S.stakeholder(s) for s in db.execute(select(Stakeholder).where(Stakeholder.jurisdiction_id == j.id)).scalars()]}


@router.post("/jurisdictions/{code}/activate", tags=["jurisdictions"], summary="Complete onboarding once readiness checks pass")
def activate_jurisdiction(code: str, db: Session = Depends(get_db), user=Depends(admin_only)):
    j = db.execute(select(Jurisdiction).where(Jurisdiction.code == code.upper())).scalar_one_or_none()
    if not j:
        raise HTTPException(404, "Unknown jurisdiction")
    readiness = onboarding_readiness(db, j)
    if not readiness["ready"]:
        raise HTTPException(422, {"message": "Onboarding checks failing", **readiness})
    j.status, j.onboarded_at = "Active", date.today()
    AuditTrail(db).record(actor=user.username, action="JURISDICTION_ACTIVATED", entity_type="Jurisdiction", entity_id=j.code, jurisdiction_code=j.code)
    db.commit()
    return S.jurisdiction(j)


# ------------------------------------------------------------------ reference data
@router.get("/classifications", tags=["reference"])
def classifications(db: Session = Depends(get_db), _=Auth):
    return [{"level": c.level, "name": c.name, "description": c.description, "handling_rules": c.handling_rules}
            for c in db.execute(select(DataClassification).order_by(DataClassification.level)).scalars()]


@router.get("/roles", tags=["reference"])
def roles(db: Session = Depends(get_db), _=Auth):
    return [{"id": r.id, "name": r.name, "description": r.description, "privileged": r.privileged,
             "permissions": [{"domain": p.domain, "max_classification": p.max_classification, "access_types": p.access_types} for p in r.permissions]}
            for r in db.execute(select(Role).options(selectinload(Role.permissions)).order_by(Role.name)).scalars()]


@router.get("/assets", tags=["reference"])
def assets(jurisdiction: str | None = None, db: Session = Depends(get_db), _=Auth):
    q = select(DataAsset).options(selectinload(DataAsset.jurisdiction), selectinload(DataAsset.classification),
                                  selectinload(DataAsset.owner), selectinload(DataAsset.locations)).order_by(DataAsset.asset_ref)
    out = [S.asset(a) for a in db.execute(q).scalars()]
    return [a for a in out if not jurisdiction or a["jurisdiction"] == jurisdiction.upper()]


@router.get("/employees", tags=["reference"])
def employees(jurisdiction: str | None = None, db: Session = Depends(get_db), _=Auth):
    q = select(Employee).options(selectinload(Employee.jurisdiction), selectinload(Employee.role)).order_by(Employee.employee_ref)
    out = [S.employee(e) for e in db.execute(q).scalars()]
    return [e for e in out if not jurisdiction or e["jurisdiction"] == jurisdiction.upper()]
