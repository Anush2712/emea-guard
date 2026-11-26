"""Configurable control assessment engine.

Each GovernanceControl names a `test_type`; the registry below maps test types to automated
tests that compute a population and its exceptions for one jurisdiction at a point in time.
Results drive effectiveness ratings, compliance gaps (raised or auto-resolved on retest) and risk.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..engine.severity import likelihood_from_exception_rate, matrix_severity
from ..models import (
    AccessRequest,
    ComplianceGap,
    ControlAssessment,
    DataAsset,
    Employee,
    GovernanceControl,
    Policy,
)
from .audit import AuditTrail
from .gaps import OPEN_STATUSES, close_gap, raise_gap
from .lookups import Lookups

APPROVED = ("APPROVED", "APPROVED_WITH_FINDINGS")


def cycle_label(d: date) -> str:
    return f"{d.year}-Q{(d.month - 1) // 3 + 1}"


@dataclass
class Snapshot:
    """All data a cycle needs, loaded once."""
    as_of: date
    assets: list[DataAsset]
    employees: list[Employee]
    grants: list[AccessRequest]
    policies: list[Policy]


@dataclass
class TestResult:
    population: int = 0
    exceptions: list[dict] = field(default_factory=list)


def _active_employee(e: Employee, as_of: date) -> bool:
    return e.hire_date <= as_of and not (e.termination_date and e.termination_date <= as_of)


def _active_grant(g: AccessRequest, as_of: date) -> bool:
    return (g.decision in APPROVED and g.requested_at.date() <= as_of and (g.granted_until or as_of) >= as_of
            and not (g.revoked_at and g.revoked_at <= as_of))


def _ex(entity: str, id_, label: str, reason: str) -> dict:
    return {"entity": entity, "id": id_, "label": label, "reason": reason}


# ------------------------------------------------------------------ control tests
def t_asset_ownership(s, j, lk):
    pop = [a for a in s.assets if a.jurisdiction_id == j.id]
    return TestResult(len(pop), [_ex("asset", a.id, a.asset_ref, "No accountable owner") for a in pop if not a.owner_id])


def t_asset_classification(s, j, lk):
    pop = [a for a in s.assets if a.jurisdiction_id == j.id]
    return TestResult(len(pop), [_ex("asset", a.id, a.asset_ref, "Unclassified") for a in pop if not a.classification_id])


def t_encryption(s, j, lk):
    pop = [a for a in s.assets if a.jurisdiction_id == j.id and (not a.classification or a.classification.level >= 3)]
    return TestResult(len(pop), [_ex("asset", a.id, a.asset_ref, "Not encrypted at rest") for a in pop if not a.encrypted_at_rest])


def t_retention(s, j, lk):
    pop = [a for a in s.assets if a.jurisdiction_id == j.id]
    exc = []
    for a in pop:
        age = (s.as_of - a.oldest_record_date).days
        if age > a.retention_days:
            exc.append(_ex("asset", a.id, a.asset_ref, f"Oldest record {age}d > retention {a.retention_days}d"))
    return TestResult(len(pop), exc)


def t_residency(s, j, lk):
    pop, exc = 0, []
    for a in s.assets:
        if a.jurisdiction_id != j.id or not a.residency_required:
            continue
        for loc in a.locations:
            pop += 1
            if loc.location_jurisdiction_id != a.jurisdiction_id:
                exc.append(_ex("location", loc.id, f"{a.asset_ref} {loc.location_type}",
                               f"{loc.location_type} copy held in {lk.jur_by_id[loc.location_jurisdiction_id].code}"))
    return TestResult(pop, exc)


def t_transfers(s, j, lk):
    """Copies of personal data held abroad need adequacy or a valid mechanism with a completed TIA.

    Returns (result, exposed_copies): the pass rate counts every exposed copy, while evidence is
    de-duplicated per mechanism / jurisdiction pair (the unit that remediation fixes).
    """
    pop, exposed, exc, seen = 0, 0, [], set()
    for a in s.assets:
        if a.jurisdiction_id != j.id or not a.contains_personal_data:
            continue
        for loc in a.locations:
            if loc.location_jurisdiction_id == a.jurisdiction_id:
                continue
            pop += 1
            dest = lk.jur_by_id[loc.location_jurisdiction_id].code
            if lk.adequate(j.code, dest):
                continue
            m = lk.mechanism(j.code, dest, s.as_of)
            if m and m.valid_until >= s.as_of and m.tia_completed:
                continue
            exposed += 1
            if m:
                key, ev_id = ("mechanism", m.id), m.id
                reason = f"{m.mechanism} {m.reference} expired {m.valid_until}" if m.valid_until < s.as_of else f"{m.mechanism} {m.reference} lacks TIA"
            else:
                key, ev_id = ("pair", (j.id, loc.location_jurisdiction_id)), [j.id, loc.location_jurisdiction_id]
                reason = f"No transfer mechanism {j.code}->{dest}"
            if key not in seen:
                seen.add(key)
                exc.append(_ex(key[0], ev_id, f"{a.asset_ref} {loc.location_type} -> {dest}", reason))
    return TestResult(pop, exc), exposed


def t_training(s, j, lk):
    pop = [e for e in s.employees if e.jurisdiction_id == j.id and _active_employee(e, s.as_of)]
    exc = []
    for e in pop:
        if e.last_training_date is None:
            exc.append(_ex("employee", e.id, e.employee_ref, "No training record"))
        elif (s.as_of - e.last_training_date).days > 365:
            exc.append(_ex("employee", e.id, e.employee_ref, f"Training {(s.as_of - e.last_training_date).days}d old"))
    return TestResult(len(pop), exc)


def _grants_in(s, j):
    return [g for g in s.grants if g.employee.jurisdiction_id == j.id and _active_grant(g, s.as_of)]


def t_leaver(s, j, lk):
    pop = _grants_in(s, j)
    exc = [_ex("grant", g.id, g.request_ref, f"{g.employee.employee_ref} left on {g.employee.termination_date}")
           for g in pop if g.employee.termination_date and g.employee.termination_date <= s.as_of]
    return TestResult(len(pop), exc)


def t_privileged(s, j, lk):
    pop = [e for e in s.employees if e.jurisdiction_id == j.id and e.role.privileged and _active_employee(e, s.as_of)]
    exc = [_ex("employee", e.id, e.employee_ref, "No review in 90 days") for e in pop
           if not e.last_access_review or (s.as_of - e.last_access_review).days > 90]
    return TestResult(len(pop), exc)


def t_recert(s, j, lk):
    pop = _grants_in(s, j)
    exc = [_ex("grant", g.id, g.request_ref, "Not recertified in 180 days") for g in pop
           if not g.last_recertified_at or (s.as_of - g.last_recertified_at).days > 180]
    return TestResult(len(pop), exc)


def t_dormant(s, j, lk):
    pop = _grants_in(s, j)
    exc = [_ex("grant", g.id, g.request_ref, f"Unused since {g.last_used_at}") for g in pop
           if g.last_used_at and (s.as_of - g.last_used_at).days > 90]
    return TestResult(len(pop), exc)


def t_processor(s, j, lk):
    pop = [a for a in s.assets if a.jurisdiction_id == j.id and a.is_third_party_hosted]
    return TestResult(len(pop), [_ex("asset", a.id, a.asset_ref, f"{a.hosting_provider} without processor agreement") for a in pop if not a.processor_agreement_ref])


def t_dpia(s, j, lk):
    pop = [a for a in s.assets if a.jurisdiction_id == j.id and a.contains_special_category]
    return TestResult(len(pop), [_ex("asset", a.id, a.asset_ref, "DPIA not completed") for a in pop if not a.dpia_completed])


def t_ropa(s, j, lk):
    pop = [a for a in s.assets if a.jurisdiction_id == j.id and a.contains_personal_data]
    return TestResult(len(pop), [_ex("asset", a.id, a.asset_ref, "Not in RoPA") for a in pop if not a.ropa_registered])


def t_cid(s, j, lk):
    if j.code not in ("CH", "LU"):
        return TestResult(0, [])
    pop = [g for g in s.grants if g.asset.jurisdiction_id == j.id and g.asset.contains_cid and _active_grant(g, s.as_of)]
    exc = [_ex("grant", g.id, g.request_ref, f"CID entitled to {g.employee.employee_ref} in {lk.jur_by_id[g.employee.jurisdiction_id].code}")
           for g in pop if g.employee.jurisdiction_id != j.id]
    return TestResult(len(pop), exc)


def t_policy(s, j, lk):
    pop = s.policies
    return TestResult(len(pop), [_ex("policy", p.id, p.code, f"Review overdue since {p.next_review_date}") for p in pop if p.next_review_date < s.as_of])


TESTS: dict[str, Callable] = {
    "asset_ownership": t_asset_ownership, "asset_classification": t_asset_classification, "encryption_at_rest": t_encryption,
    "retention": t_retention, "residency": t_residency, "transfer_mechanisms": t_transfers, "training": t_training,
    "leaver_access": t_leaver, "privileged_review": t_privileged, "recertification": t_recert, "dormant_access": t_dormant,
    "processor_agreements": t_processor, "dpia": t_dpia, "ropa": t_ropa, "cid_access": t_cid, "policy_review": t_policy,
}


def rate_result(population: int, exceptions: int, threshold: float) -> tuple[float, str]:
    if population == 0:
        return 100.0, "Not Applicable"
    pass_rate = round((population - exceptions) / population * 100, 1)
    if pass_rate >= threshold:
        return pass_rate, "Effective"
    if pass_rate >= threshold - 15:
        return pass_rate, "Partially Effective"
    return pass_rate, "Ineffective"


def load_snapshot(db: Session, as_of: date) -> Snapshot:
    assets = [a for a in db.execute(select(DataAsset).order_by(DataAsset.id).options(selectinload(DataAsset.locations), selectinload(DataAsset.classification))).scalars() if a.created_at <= as_of]
    employees = [e for e in db.execute(select(Employee).order_by(Employee.id).options(selectinload(Employee.role))).scalars() if e.hire_date <= as_of]
    grants = list(db.execute(select(AccessRequest).where(AccessRequest.decision.in_(APPROVED)).order_by(AccessRequest.id)
                             .options(selectinload(AccessRequest.employee), selectinload(AccessRequest.asset))).scalars())
    policies = list(db.execute(select(Policy).order_by(Policy.id)).scalars())
    return Snapshot(as_of, assets, employees, grants, policies)


def run_cycle(db: Session, lk: Lookups, audit: AuditTrail, *, as_of: date, now: datetime | None = None,
              actor: str = "control-engine", control_codes: list[str] | None = None) -> list[ControlAssessment]:
    now = (now or datetime.combine(as_of, datetime.min.time().replace(hour=18))).replace(microsecond=0)
    cycle = cycle_label(as_of)
    snap = load_snapshot(db, as_of)
    q = select(GovernanceControl).where(GovernanceControl.enabled.is_(True)).options(selectinload(GovernanceControl.owner))
    controls = [c for c in db.execute(q.order_by(GovernanceControl.code)).scalars() if not control_codes or c.code in control_codes]
    jurisdictions = [j for j in lk.jurisdictions.values() if j.status == "Active"]
    out: list[ControlAssessment] = []
    created = resolved = 0

    for c in controls:
        scopes = [None] if c.scope == "EMEA" else jurisdictions
        for j in scopes:
            res = TESTS[c.test_type](snap, j, lk)
            if isinstance(res, tuple):  # transfer test returns (result, exposed copies count)
                res, exposed = res
                n_exc = exposed
            else:
                n_exc = len(res.exceptions)
            pass_rate, result = rate_result(res.population, n_exc, c.threshold)
            severity = None
            if result in ("Partially Effective", "Ineffective"):
                rate = n_exc / res.population
                severity = matrix_severity(c.criticality, likelihood_from_exception_rate(rate))
            a = ControlAssessment(
                control_id=c.id, jurisdiction_id=j.id if j else None, cycle=cycle, as_of=as_of, population=res.population,
                exceptions=n_exc, pass_rate=pass_rate, result=result, severity=severity, evidence=res.exceptions[:500],
                assessed_at=now, assessed_by=actor,
            )
            db.add(a)
            db.flush()
            out.append(a)

            jcode = j.code if j else None
            dedup = f"CTRL:{c.code}:{jcode or 'EMEA'}"
            if severity:
                owner_fn = c.owner.function if c.owner else "Executive"
                owner = lk.owner_for(owner_fn, jcode) if jcode else c.owner_id
                _, was_new = raise_gap(
                    db, audit, dedup_key=dedup, source="control_assessment",
                    title=f"{c.code} {c.name} {result.lower()} in {j.name if j else 'EMEA'}",
                    description=f"{n_exc} of {res.population} items failed ({pass_rate}% pass vs {c.threshold}% threshold). "
                                + "; ".join(f"{e['label']}: {e['reason']}" for e in res.exceptions[:3]),
                    impact=c.criticality, likelihood=likelihood_from_exception_rate(n_exc / res.population), severity=severity,
                    jurisdiction_id=j.id if j else None, owner_id=owner, remediation_action=c.remediation, now=now, actor=actor,
                    jurisdiction_code=jcode, control_id=c.id, assessment_id=a.id,
                )
                created += int(was_new)
            elif result == "Effective":
                open_gap = db.execute(select(ComplianceGap).where(ComplianceGap.dedup_key == dedup, ComplianceGap.status.in_(OPEN_STATUSES))).scalar_one_or_none()
                if open_gap:
                    close_gap(db, audit, open_gap, status="Resolved", note=f"Auto-resolved: control retest passed in {cycle} ({pass_rate}%).",
                              when=now, actor=actor, jurisdiction_code=jcode)
                    resolved += 1

    audit.record(actor=actor, action="CONTROL_CYCLE_COMPLETED", entity_type="AssessmentCycle", entity_id=cycle,
                 details={"as_of": as_of.isoformat(), "assessments": len(out), "gaps_created": created, "gaps_auto_resolved": resolved,
                          "ineffective": sum(1 for a in out if a.result == "Ineffective"),
                          "partially_effective": sum(1 for a in out if a.result == "Partially Effective")},
                 timestamp=now)
    return out
