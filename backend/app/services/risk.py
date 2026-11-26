"""Jurisdiction-level residual risk scoring.

residual = inherent_multiplier x (
      0.45 x control ineffectiveness          (100 - weighted control effectiveness)
    + 0.30 x open gap pressure                (severity-weighted open gaps, normalised 0-100)
    + 0.15 x overdue remediation ratio x 100
    + 0.10 x access denial rate x 100         (last 180 days)
)  capped at 100, rated on the 4-level scale.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine.severity import SEVERITY_WEIGHT, score_to_rating
from ..models import AccessRequest, ComplianceGap, ControlAssessment, DataAsset, GovernanceControl, RiskAssessment
from .assessments import cycle_label
from .audit import AuditTrail
from .lookups import Lookups

RESULT_SCORE = {"Effective": 100.0, "Partially Effective": 50.0, "Ineffective": 0.0}
GAP_PRESSURE_NORMALISER = 60.0
WEIGHTS = {"controls": 0.45, "gaps": 0.30, "overdue": 0.15, "denials": 0.10}


def _open_at(g: ComplianceGap, as_of: datetime) -> bool:
    return g.identified_at <= as_of and (g.resolved_at is None or g.resolved_at > as_of) and g.status != "Risk Accepted"


def compute_risk(db: Session, lk: Lookups, audit: AuditTrail | None, *, as_of: date, persist: bool = True) -> list[RiskAssessment]:
    cutoff = datetime.combine(as_of, datetime.max.time())
    cycle = cycle_label(as_of)
    controls = {c.id: c for c in db.execute(select(GovernanceControl)).scalars()}
    # latest assessment per (control, jurisdiction) on or before as_of
    latest: dict[tuple[int, int | None], ControlAssessment] = {}
    for a in db.execute(select(ControlAssessment).where(ControlAssessment.as_of <= as_of).order_by(ControlAssessment.as_of, ControlAssessment.id)).scalars():
        latest[(a.control_id, a.jurisdiction_id)] = a
    gaps = list(db.execute(select(ComplianceGap)).scalars())
    since = cutoff - timedelta(days=180)
    requests = list(db.execute(
        select(AccessRequest.decision, DataAsset.jurisdiction_id).join(DataAsset, AccessRequest.asset_id == DataAsset.id)
        .where(AccessRequest.requested_at <= cutoff, AccessRequest.requested_at >= since, AccessRequest.evaluation_trace.isnot(None))
    ).all())

    results = []
    for j in lk.jurisdictions.values():
        if j.status != "Active":
            continue
        rel = [a for (cid, jid), a in latest.items() if jid == j.id and a.result in RESULT_SCORE]
        if rel:
            wsum = sum(controls[a.control_id].criticality for a in rel)
            effectiveness = sum(RESULT_SCORE[a.result] * controls[a.control_id].criticality for a in rel) / wsum
        else:
            effectiveness = 100.0
        jg = [g for g in gaps if g.jurisdiction_id == j.id and _open_at(g, cutoff)]
        pressure = min(100.0, sum(SEVERITY_WEIGHT[g.severity] for g in jg) / GAP_PRESSURE_NORMALISER * 100)
        overdue = [g for g in jg if g.due_date < as_of]
        overdue_ratio = len(overdue) / len(jg) if jg else 0.0
        jr = [d for d, jid in requests if jid == j.id]
        denial = sum(1 for d in jr if d == "DENIED") / len(jr) if jr else 0.0

        parts = {
            "controls": WEIGHTS["controls"] * (100 - effectiveness),
            "gaps": WEIGHTS["gaps"] * pressure,
            "overdue": WEIGHTS["overdue"] * overdue_ratio * 100,
            "denials": WEIGHTS["denials"] * denial * 100,
        }
        residual = round(min(100.0, j.inherent_risk * sum(parts.values())), 1)
        labels = {
            "controls": f"Control effectiveness {effectiveness:.0f}%",
            "gaps": f"{len(jg)} open gaps ({sum(1 for g in jg if g.severity in ('Critical', 'High'))} Critical/High)",
            "overdue": f"{len(overdue)} overdue remediation items",
            "denials": f"{denial:.0%} access denial rate (180d)",
        }
        drivers = [{"factor": k, "contribution": round(v * j.inherent_risk, 1), "label": labels[k]}
                   for k, v in sorted(parts.items(), key=lambda kv: -kv[1])]
        ra = RiskAssessment(
            jurisdiction_id=j.id, as_of=as_of, cycle=cycle, control_effectiveness=round(effectiveness, 1),
            open_gap_score=round(pressure, 1), overdue_ratio=round(overdue_ratio, 3), access_denial_rate=round(denial, 3),
            residual_score=residual, rating=score_to_rating(residual), drivers=drivers, created_at=cutoff.replace(microsecond=0),
        )
        results.append(ra)

    if persist:
        # one snapshot per jurisdiction per day: replace any existing for this date
        for old in db.execute(select(RiskAssessment).where(RiskAssessment.as_of == as_of)).scalars():
            db.delete(old)
        db.flush()
        db.add_all(results)
        if audit:
            audit.record(actor="risk-engine", action="RISK_RECALCULATED", entity_type="RiskAssessment", entity_id=as_of.isoformat(),
                         details={r_.jurisdiction_id and lk.jur_by_id[r_.jurisdiction_id].code: r_.residual_score for r_ in results},
                         timestamp=datetime.combine(as_of, datetime.min.time().replace(hour=19)))
    return results
