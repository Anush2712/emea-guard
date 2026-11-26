"""In-memory lookups for reference data used on every evaluation."""
from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..engine.transfers import JurisdictionProfile, is_adequate
from ..models import GovernanceRule, Jurisdiction, RegulatoryRequirement, Stakeholder, TransferMechanism


class Lookups:
    def __init__(self, db: Session):
        self.db = db
        self.reload()

    def reload(self) -> None:
        db = self.db
        self.jurisdictions = {j.code: j for j in db.execute(select(Jurisdiction).order_by(Jurisdiction.id)).scalars()}
        self.jur_by_id = {j.id: j for j in self.jurisdictions.values()}
        self.profiles = {c: JurisdictionProfile(c, j.is_eea, j.eu_adequacy) for c, j in self.jurisdictions.items()}
        self.requirements = list(db.execute(select(RegulatoryRequirement).order_by(RegulatoryRequirement.id)).scalars())
        self.stakeholders = list(db.execute(select(Stakeholder).order_by(Stakeholder.id)).scalars())
        self.rules = [self.rule_dict(r) for r in db.execute(select(GovernanceRule).order_by(GovernanceRule.code)).scalars()]

    @staticmethod
    def rule_dict(r: GovernanceRule) -> dict:
        return {
            "code": r.code, "name": r.name, "category": r.category, "severity": r.severity, "effect": r.effect,
            "raises_gap": r.raises_gap, "enabled": r.enabled, "params": r.params or {},
            "requirement_codes": r.requirement_codes or [], "remediation": r.remediation, "owner_function": r.owner_function,
        }

    def adequate(self, source_code: str, dest_code: str) -> bool:
        return is_adequate(self.profiles[source_code], self.profiles[dest_code])

    def applicable_requirements(self, asset_j: str, employee_j: str, level: int) -> list[str]:
        involved = {asset_j, employee_j}
        eu = any(self.jurisdictions[c].is_eu for c in involved)
        out = []
        for r in self.requirements:
            if r.min_classification > level:
                continue
            if r.scope == "GLOBAL" or (r.scope == "EU" and eu) or (
                r.scope == "NATIONAL" and r.jurisdiction_id and self.jur_by_id[r.jurisdiction_id].code in involved
            ):
                out.append(r.code)
        return out

    def mechanism(self, source_code: str, dest_code: str, as_of: date) -> TransferMechanism | None:
        """Best mechanism for a flow: a currently valid one if any, else the most recent (expired) one."""
        src, dst = self.jurisdictions[source_code].id, self.jurisdictions[dest_code].id
        rows = list(self.db.execute(
            select(TransferMechanism).where(
                TransferMechanism.source_jurisdiction_id == src, TransferMechanism.destination_jurisdiction_id == dst
            )
        ).scalars())
        if not rows:
            return None
        valid = [m for m in rows if m.valid_from <= as_of <= m.valid_until]
        pool = valid or rows
        return max(pool, key=lambda m: m.valid_until)

    # ---- stakeholder routing
    def owner_for(self, function: str, jurisdiction_code: str | None, domain: str | None = None, asset_owner_id: int | None = None) -> int | None:
        def find(pred):
            return next((s.id for s in self.stakeholders if pred(s)), None)

        jid = self.jurisdictions[jurisdiction_code].id if jurisdiction_code else None
        if function == "DPO" and jid:
            return find(lambda s: s.function == "DPO" and s.jurisdiction_id == jid)
        if function == "Data Steward" and jid:
            return find(lambda s: s.function == "Data Steward" and s.jurisdiction_id == jid)
        if function == "Data Owner":
            return asset_owner_id or find(lambda s: s.function == "Data Owner" and s.domain == domain) or find(lambda s: s.title.startswith("Chief Data"))
        if function == "IAM":
            return find(lambda s: s.function == "IAM")
        if function == "Control Owner":
            return find(lambda s: s.title.startswith("Chief Information Security"))
        if function == "Executive":
            return find(lambda s: s.title.startswith("Chief Data"))
        return find(lambda s: s.title.startswith("Chief Data"))
