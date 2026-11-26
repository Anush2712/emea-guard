"""Deterministic synthetic data generator.

Builds the reference data, then REPLAYS 2026 chronologically through the real engines:
access requests are evaluated by the access engine as they arrive, control assessment
cycles run at each quarter end (plus "today"), remediation happens between cycles,
and risk is recalculated after each cycle. Nothing in the gap / assessment / risk tables
is hand-written: it is all produced by the platform's own logic over synthetic inputs.
"""
from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..database import Base
from ..models import (
    AccessRequest,
    ComplianceGap,
    DataAsset,
    DataClassification,
    DataLocalisationRecord,
    Employee,
    GovernanceControl,
    GovernanceRule,
    Jurisdiction,
    Permission,
    Policy,
    PolicyVersion,
    Project,
    ProjectActivity,
    RegulatoryRequirement,
    Role,
    Stakeholder,
    TransferMechanism,
    User,
)
from ..services.access_service import submit_access_request
from ..services.assessments import run_cycle
from ..services.audit import AuditTrail
from ..services.gaps import apply_remediation, close_gap
from ..services.lookups import Lookups
from ..services.risk import compute_risk
from . import reference as R

RULES_FILE = Path(__file__).resolve().parent.parent / "engine" / "rules.yaml"
SEED_TODAY = date(2026, 11, 26)
CYCLE_DATES = [date(2026, 3, 31), date(2026, 6, 30), date(2026, 9, 30), SEED_TODAY]

ASSETS_PER_JURISDICTION = {"IE": 18, "GB": 16, "DE": 14, "FR": 12, "NL": 10, "LU": 12, "CH": 12, "PL": 10, "AE": 9, "ZA": 7}
EMPLOYEES_PER_JURISDICTION = {"IE": 45, "GB": 40, "DE": 30, "FR": 25, "NL": 20, "LU": 20, "CH": 20, "PL": 20, "AE": 10, "ZA": 10}

HOSTING = {
    "IE": "AWS eu-west-1 (Dublin)", "GB": "Azure UK South (London)", "DE": "AWS eu-central-1 (Frankfurt)",
    "FR": "Azure France Central (Paris)", "NL": "Azure West Europe (Amsterdam)", "LU": "On-premises DC (Luxembourg)",
    "CH": "Azure Switzerland North (Zurich)", "PL": "GCP europe-central2 (Warsaw)", "AE": "Azure UAE North (Dubai)",
    "ZA": "AWS af-south-1 (Cape Town)",
}
DR_PAIR = {"IE": "NL", "GB": "GB", "DE": "NL", "FR": "DE", "NL": "IE", "LU": "LU", "CH": "CH", "PL": "DE", "AE": "AE", "ZA": "ZA"}
PROVIDERS = {"AWS": True, "Azure": True, "GCP": True, "On-premises": False}

DOMAIN_ASSETS = {
    "Customer": ["Retail Customer Master", "KYC Document Store", "Client Onboarding Records", "Wealth Client Profiles", "Customer Complaints Register", "CRM Contact Data"],
    "Payments": ["SEPA Payments Ledger", "Card Transactions Warehouse", "SWIFT Message Archive", "Payment Fraud Alerts", "Direct Debit Mandates"],
    "Markets": ["Trade Capture Store", "FX Pricing History", "Order Book Archive", "Counterparty Exposure Data"],
    "Risk": ["Credit Risk Data Mart", "Market Risk VaR Results", "Liquidity Risk Reporting", "Model Inventory"],
    "HR": ["Employee Master Records", "Payroll Data", "Occupational Health Records", "Recruitment Pipeline"],
    "Finance": ["General Ledger", "Regulatory Reporting Mart", "Accounts Payable"],
    "Compliance": ["AML Transaction Monitoring", "Trade Surveillance Alerts", "Sanctions Screening Results", "Regulatory Correspondence"],
    "Marketing": ["Campaign Analytics", "Customer Segmentation Model", "Website Analytics"],
}
DOMAIN_PURPOSES = {
    "Customer": ["Client Servicing", "KYC/AML", "Analytics", "Regulatory Reporting"],
    "Payments": ["Payment Processing", "Fraud Prevention", "Analytics", "Regulatory Reporting"],
    "Markets": ["Trading", "Risk Management", "Regulatory Reporting"],
    "Risk": ["Risk Management", "Regulatory Reporting", "Model Development"],
    "HR": ["HR Administration", "Payroll"],
    "Finance": ["Financial Reporting", "Regulatory Reporting"],
    "Compliance": ["KYC/AML", "Surveillance", "Regulatory Reporting"],
    "Marketing": ["Marketing", "Analytics"],
}
ALL_PURPOSES = sorted({p for v in DOMAIN_PURPOSES.values() for p in v} | {"Product Testing", "Ad-hoc Investigation"})

FIRST = {
    "IE": ["Aoife", "Cian", "Niamh", "Darragh", "Saoirse", "Eoin", "Orla", "Conor", "Ciara", "Seán"],
    "GB": ["Oliver", "Amelia", "Harry", "Isla", "George", "Emily", "Jack", "Sophie", "Charlie", "Grace"],
    "DE": ["Lukas", "Anna", "Felix", "Lena", "Jonas", "Marie", "Paul", "Hannah", "Leon", "Sophie"],
    "FR": ["Louis", "Chloé", "Hugo", "Léa", "Arthur", "Manon", "Jules", "Camille", "Nathan", "Inès"],
    "NL": ["Daan", "Emma", "Sem", "Julia", "Lucas", "Tess", "Finn", "Sanne", "Bram", "Lotte"],
    "LU": ["Luca", "Mia", "Noah", "Emma", "Ben", "Lara", "Tom", "Sarah", "Max", "Laura"],
    "CH": ["Noah", "Mia", "Liam", "Lea", "Luca", "Lina", "Elias", "Elena", "Nico", "Sara"],
    "PL": ["Jakub", "Zuzanna", "Kacper", "Julia", "Szymon", "Maja", "Filip", "Hanna", "Jan", "Oliwia"],
    "AE": ["Ahmed", "Fatima", "Omar", "Mariam", "Khalid", "Aisha", "Yousef", "Noor", "Saeed", "Layla"],
    "ZA": ["Sipho", "Thandi", "Pieter", "Naledi", "Johan", "Lerato", "Thabo", "Anika", "Kagiso", "Zanele"],
}
LAST = {
    "IE": ["Murphy", "Kelly", "O'Sullivan", "Walsh", "Byrne", "Ryan", "O'Brien", "Doyle", "McCarthy", "Gallagher"],
    "GB": ["Smith", "Jones", "Taylor", "Brown", "Williams", "Wilson", "Evans", "Thomas", "Roberts", "Walker"],
    "DE": ["Müller", "Schmidt", "Schneider", "Fischer", "Weber", "Meyer", "Wagner", "Becker", "Hoffmann", "Koch"],
    "FR": ["Martin", "Bernard", "Dubois", "Thomas", "Robert", "Richard", "Petit", "Durand", "Leroy", "Moreau"],
    "NL": ["de Jong", "Jansen", "de Vries", "van den Berg", "Bakker", "Visser", "Smit", "Meijer", "Mulder", "Bos"],
    "LU": ["Schmit", "Muller", "Weber", "Wagner", "Hoffmann", "Thill", "Kremer", "Schroeder", "Klein", "Reuter"],
    "CH": ["Müller", "Meier", "Schmid", "Keller", "Weber", "Huber", "Steiner", "Fischer", "Baumann", "Frei"],
    "PL": ["Nowak", "Kowalski", "Wiśniewski", "Wójcik", "Kamiński", "Lewandowski", "Zieliński", "Szymański", "Woźniak", "Dąbrowski"],
    "AE": ["Al Mansoori", "Al Hashimi", "Al Nuaimi", "Al Shamsi", "Al Ketbi", "Al Mazrouei", "Al Dhaheri", "Al Suwaidi", "Haddad", "Rahman"],
    "ZA": ["Nkosi", "Dlamini", "van der Merwe", "Botha", "Mokoena", "Naidoo", "Pillay", "Khumalo", "Pretorius", "Mahlangu"],
}
ROLE_WEIGHTS = {
    "Data Analyst": 14, "Relationship Manager": 16, "Operations Analyst": 16, "Software Engineer": 18, "Risk Analyst": 10,
    "Trader": 8, "Compliance Officer": 8, "HR Specialist": 5, "Finance Controller": 6, "Data Steward": 4,
    "Platform Administrator": 4, "Internal Auditor": 3, "Marketing Specialist": 5,
}
# Shared-service hubs: staff in these locations regularly work on data held elsewhere.
HUB_TARGETS = {"PL": ["DE", "IE", "LU", "GB"], "ZA": ["GB", "IE", "NL"], "AE": ["GB", "IE"], "IE": ["GB", "NL", "DE", "LU"], "GB": ["IE", "CH", "AE"]}


def _d(s: str) -> date:
    return date.fromisoformat(s)


def _dt(d: date, rng: random.Random) -> datetime:
    return datetime.combine(d, datetime.min.time()) + timedelta(hours=rng.randint(8, 18), minutes=rng.randint(0, 59))


def reset_schema(engine) -> None:
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)


def seed(db: Session, random_seed: int = 2712) -> dict:
    rng = random.Random(random_seed)

    # ---------------------------------------------------------------- reference
    jur = {}
    for code, name, region, is_eu, is_eea, adequacy, dpa, reg, law, residency, secrecy, hrs, inherent in R.JURISDICTIONS:
        j = Jurisdiction(code=code, name=name, region=region, is_eu=is_eu, is_eea=is_eea, eu_adequacy=adequacy,
                         data_protection_authority=dpa, financial_regulator=reg, primary_law=law, residency_regime=residency,
                         banking_secrecy=secrecy, breach_notification_hours=hrs, inherent_risk=inherent, status="Active",
                         onboarded_at=date(2025, 10, 1))
        db.add(j)
        jur[code] = j
    db.flush()

    req = {}
    for code, scope, jcode, regime, ref, title, desc, cat, minc in R.REQUIREMENTS:
        r = RegulatoryRequirement(code=code, scope=scope, jurisdiction_id=jur[jcode].id if jcode else None, regime=regime,
                                  reference=ref, title=title, description=desc, category=cat, min_classification=minc)
        db.add(r)
        req[code] = r

    cls = {}
    for level, name, desc, rules, owner_appr, enc in R.CLASSIFICATIONS:
        c = DataClassification(id=level, level=level, name=name, description=desc, handling_rules=rules,
                               requires_owner_approval=owner_appr, requires_encryption=enc)
        db.add(c)
        cls[level] = c

    stake = {}
    for name, title, fn, domain in R.EMEA_STAKEHOLDERS:
        s = Stakeholder(name=name, title=title, function=fn, domain=domain, email=_email(name))
        db.add(s)
        stake[title] = s
    for code, (dpo, steward) in R.JURISDICTION_STAKEHOLDERS.items():
        db.add(Stakeholder(name=dpo, title=f"Data Protection Officer, {jur[code].name}", function="DPO", jurisdiction_id=jur[code].id, email=_email(dpo)))
        db.add(Stakeholder(name=steward, title=f"Data Steward, {jur[code].name}", function="Data Steward", jurisdiction_id=jur[code].id, email=_email(steward)))
    db.flush()
    owners_by_domain = {s.domain: s for s in stake.values() if s.function == "Data Owner"}
    by_function = {}
    for s in stake.values():
        by_function.setdefault(s.function, s)

    roles = {}
    for name, desc, priv, perms in R.ROLES:
        role = Role(name=name, description=desc, privileged=priv)
        role.permissions = [Permission(domain=d, max_classification=m, access_types=t) for d, m, t in perms]
        db.add(role)
        roles[name] = role

    rules_cfg = yaml.safe_load(RULES_FILE.read_text())["rules"]
    for r in rules_cfg:
        db.add(GovernanceRule(code=r["code"], name=r["name"], category=r["category"], description=r["description"],
                              severity=r["severity"], effect=r["effect"], raises_gap=r["raises_gap"], enabled=True,
                              params=r.get("params") or {}, requirement_codes=r["requirement_codes"],
                              remediation=r["remediation"], owner_function=r["owner_function"]))

    dpo_any = db.execute(select(Stakeholder).where(Stakeholder.function == "DPO").order_by(Stakeholder.id)).scalars().first()
    steward_any = db.execute(select(Stakeholder).where(Stakeholder.function == "Data Steward", Stakeholder.jurisdiction_id.isnot(None)).order_by(Stakeholder.id)).scalars().first()
    fn_owner = {"Data Steward": stake["Head of Records Management"], "Control Owner": stake["Chief Information Security Officer, EMEA"],
                "IAM": stake["Head of Identity & Access Management, EMEA"], "Executive": stake["Chief Data Officer, EMEA"],
                "DPO": stake["Senior Counsel, Data Protection"]}
    # Control owners: DPO- and steward-owned controls carry a DPO/steward-function owner so that gaps
    # route to the DPO / steward of the jurisdiction being assessed.
    control_owner = {**fn_owner, "DPO": dpo_any, "Data Steward": steward_any}
    for code, name, domain, desc, test, ctype, crit, thr, freq, scope, ofn, rcodes, rem in R.CONTROLS:
        c = GovernanceControl(code=code, name=name, domain=domain, description=desc, test_type=test, control_type=ctype,
                              criticality=crit, threshold=thr, frequency=freq, scope=scope, owner_id=control_owner[ofn].id, remediation=rem)
        c.requirements = [req[x] for x in rcodes]
        db.add(c)
    db.flush()

    for username, full, role, pw in [("admin", "Governance Administrator", "admin", "admin123"),
                                     ("analyst", "Governance Analyst", "analyst", "analyst123"),
                                     ("auditor", "Internal Auditor (read-only)", "auditor", "auditor123")]:
        db.add(User(username=username, full_name=full, app_role=role, hashed_password=hash_password(pw)))

    # ---------------------------------------------------------------- data assets (120)
    asset_n = 0
    assets: list[DataAsset] = []
    for jcode, n in ASSETS_PER_JURISDICTION.items():
        j = jur[jcode]
        domains = rng.sample(R.DOMAINS, len(R.DOMAINS))
        for i in range(n):
            asset_n += 1
            domain = domains[i % len(domains)]
            base = rng.choice(DOMAIN_ASSETS[domain])
            personal = domain in ("Customer", "HR", "Payments", "Compliance", "Marketing") or rng.random() < 0.2
            special = domain == "HR" and ("Health" in base or rng.random() < 0.35)
            level = 4 if (special or base in ("KYC Document Store", "Wealth Client Profiles", "AML Transaction Monitoring", "Payroll Data", "SWIFT Message Archive")) \
                else rng.choices([2, 3, 4, 1], weights=[25, 45, 20, 10])[0]
            if domain == "Marketing" and level == 4:
                level = 3
            cid = domain in ("Customer", "Payments") and jcode in ("CH", "LU", "FR", "PL") and level >= 3
            residency = (cid and jcode in ("CH", "LU")) or (jcode == "AE" and domain in ("Customer", "Payments")) or rng.random() < 0.05
            provider = HOSTING[jcode].split()[0]
            third_party = PROVIDERS.get(provider, False) or rng.random() < 0.1
            retention = rng.choice([1825, 2190, 2555, 3650]) if domain != "Marketing" else rng.choice([365, 730, 1095])
            created = date(2025, 6, 1) + timedelta(days=rng.randint(0, 420))
            retention_breach = rng.random() < 0.09
            oldest = created - timedelta(days=(retention + rng.randint(30, 400)) if retention_breach else rng.randint(30, max(60, retention - 400)))
            a = DataAsset(
                asset_ref=f"DA-{asset_n:04d}", name=f"{j.name} {base}", domain=domain,
                system=rng.choice(["Snowflake", "Oracle Exadata", "PostgreSQL", "SQL Server", "S3 Data Lake", "Databricks", "Teradata"]),
                hosting_provider=HOSTING[jcode], is_third_party_hosted=third_party,
                processor_agreement_ref=None if (third_party and rng.random() < 0.16) else (f"DPA-{asset_n:04d}" if third_party else None),
                jurisdiction_id=j.id, classification_id=None if rng.random() < 0.04 else level,
                owner_id=None if rng.random() < 0.06 else owners_by_domain[domain].id,
                contains_personal_data=personal, contains_special_category=special, contains_cid=cid, residency_required=residency,
                encrypted_at_rest=not (level >= 3 and rng.random() < 0.07), dpia_completed=(not special) or rng.random() < 0.7,
                ropa_registered=(not personal) or rng.random() < 0.9, retention_days=retention, oldest_record_date=oldest,
                record_count=rng.randint(5_000, 40_000_000), allowed_purposes=rng.sample(DOMAIN_PURPOSES[domain], k=min(len(DOMAIN_PURPOSES[domain]), rng.randint(2, 3))),
                created_at=created, last_reviewed_at=created + timedelta(days=rng.randint(30, 300)),
            )
            db.add(a)
            assets.append(a)
    db.flush()

    # ---------------------------------------------------------------- localisation (primary + replicas/backups)
    for a in assets:
        jcode = next(c for c, j in jur.items() if j.id == a.jurisdiction_id)
        db.add(DataLocalisationRecord(asset_id=a.id, location_jurisdiction_id=a.jurisdiction_id, location_type="Primary",
                                      hosting_region=HOSTING[jcode], verified_at=SEED_TODAY - timedelta(days=rng.randint(5, 80))))
        if rng.random() < 0.65:
            dr = DR_PAIR[jcode]
            # deliberate localisation defects
            if a.residency_required and rng.random() < 0.3:
                dr = {"CH": "DE", "LU": "DE", "AE": "IE"}.get(jcode, "IE")
            if jcode in ("AE",) and not a.residency_required and rng.random() < 0.5:
                dr = "GB"
            db.add(DataLocalisationRecord(asset_id=a.id, location_jurisdiction_id=jur[dr].id, location_type=rng.choice(["DR", "Backup"]),
                                          hosting_region=HOSTING[dr], verified_at=SEED_TODAY - timedelta(days=rng.randint(5, 120))))
        if a.contains_personal_data and rng.random() < 0.18 and jcode not in ("CH", "LU"):
            dest = rng.choice(["ZA", "AE", "GB"]) if jcode != "ZA" else "GB"
            db.add(DataLocalisationRecord(asset_id=a.id, location_jurisdiction_id=jur[dest].id, location_type="Replica",
                                          hosting_region=f"{HOSTING[dest]} (analytics hub)", verified_at=SEED_TODAY - timedelta(days=rng.randint(5, 90))))

    # ---------------------------------------------------------------- transfer mechanisms (time-varying validity)
    mechanisms = [
        ("IE", "ZA", "EU SCCs (2021/914) Module 1", "SCC-IE-ZA-2023", "2023-01-15", "2027-06-30", True),
        ("IE", "AE", "EU SCCs (2021/914) Module 1", "SCC-IE-AE-2024", "2024-03-01", "2027-02-28", True),
        ("DE", "ZA", "EU SCCs (2021/914) Module 1", "SCC-DE-ZA-2022", "2022-09-01", "2026-08-31", True),
        ("NL", "ZA", "EU SCCs (2021/914) Module 1", "SCC-NL-ZA-2025", "2025-02-01", "2028-01-31", False),
        ("GB", "ZA", "UK IDTA", "IDTA-GB-ZA-2024", "2024-05-01", "2027-04-30", True),
        ("GB", "AE", "UK IDTA", "IDTA-GB-AE-2023", "2023-04-01", "2026-05-31", True),
        ("CH", "ZA", "Swiss-adapted SCCs", "SCC-CH-ZA-2024", "2024-01-01", "2027-12-31", True),
        ("AE", "GB", "Intra-group data transfer agreement", "IGA-AE-GB-2024", "2024-01-10", "2026-10-31", True),
        ("AE", "IE", "Intra-group data transfer agreement", "IGA-AE-IE-2025", "2025-06-01", "2027-05-31", True),
        ("FR", "ZA", "EU SCCs (2021/914) Module 1", "SCC-FR-ZA-2023", "2023-07-01", "2026-12-31", True),
        ("PL", "AE", "EU SCCs (2021/914) Module 1", "SCC-PL-AE-2025", "2025-09-01", "2028-08-31", True),
    ]
    for s, d_, mech, ref, vf, vu, tia in mechanisms:
        db.add(TransferMechanism(source_jurisdiction_id=jur[s].id, destination_jurisdiction_id=jur[d_].id, mechanism=mech,
                                 reference=ref, valid_from=_d(vf), valid_until=_d(vu), tia_completed=tia))

    # ---------------------------------------------------------------- employees (240)
    employees: list[Employee] = []
    emp_n = 0
    role_names = list(ROLE_WEIGHTS)
    for jcode, n in EMPLOYEES_PER_JURISDICTION.items():
        for _ in range(n):
            emp_n += 1
            role_name = rng.choices(role_names, weights=[ROLE_WEIGHTS[r] for r in role_names])[0]
            first, last = rng.choice(FIRST[jcode]), rng.choice(LAST[jcode])
            hire = date(2015, 1, 1) + timedelta(days=rng.randint(0, 4000))
            hire = min(hire, date(2026, 6, 30))
            status, term = "Active", None
            roll = rng.random()
            if roll < 0.04:
                status, term = "Terminated", date(2026, 2, 1) + timedelta(days=rng.randint(0, 270))
            elif roll < 0.08:
                status = "Leave"
            tr = rng.random()
            training = None if tr < 0.03 else (date(2025, 1, 10) + timedelta(days=rng.randint(0, 200)) if tr < 0.16 else date(2025, 9, 1) + timedelta(days=rng.randint(0, 440)))
            if training and training > SEED_TODAY:
                training = SEED_TODAY - timedelta(days=rng.randint(1, 60))
            review = None
            if roles[role_name].privileged:
                review = SEED_TODAY - timedelta(days=rng.choice([20, 45, 70, 130, 200]))
            e = Employee(employee_ref=f"EMP-{emp_n:04d}", full_name=f"{first} {last}",
                         email=f"{_slug(first)}.{_slug(last)}{emp_n}@emeaguard-bank.example", jurisdiction_id=jur[jcode].id,
                         business_unit=R.ROLE_BUSINESS_UNIT[role_name], role=roles[role_name], status=status, hire_date=hire,
                         termination_date=term, last_training_date=training, last_access_review=review)
            db.add(e)
            employees.append(e)
    db.flush()

    # ---------------------------------------------------------------- policies & versions
    for code, title, doc_type, ofn, months, rcodes in R.POLICIES:
        owner = fn_owner[ofn]
        last = SEED_TODAY - timedelta(days=rng.randint(60, 420))
        p = Policy(code=code, title=title, doc_type=doc_type, owner_id=owner.id, status="Published", review_cycle_months=months,
                   last_reviewed=last, next_review_date=last + timedelta(days=30 * months))
        p.requirements = [req[x] for x in rcodes]
        n_versions = rng.randint(1, 3)
        versions = []
        for v in range(n_versions):
            vnum = f"{1 + v // 2}.{v % 2}" if v else "1.0"
            created = last - timedelta(days=200 * (n_versions - 1 - v))
            versions.append(PolicyVersion(
                version=vnum, status="Published" if v == n_versions - 1 else "Superseded",
                change_summary="Initial issue" if v == 0 else rng.choice([
                    "Aligned to DORA Art. 9 access requirements", "Added UAE PDPL transfer conditions",
                    "Clarified data owner approval thresholds", "Updated retention schedule for AML records",
                    "Added Swiss revFADP references", "Introduced quarterly privileged access reviews"]),
                content=_policy_content(title, doc_type, rcodes), author=owner.name, approved_by="Aoife Brennan",
                approved_at=datetime.combine(created, datetime.min.time()) + timedelta(days=7), effective_date=created + timedelta(days=14),
                created_at=datetime.combine(created, datetime.min.time())))
        p.versions = versions
        p.current_version = versions[-1].version
        db.add(p)

    # ---------------------------------------------------------------- projects
    for code, name, desc, ofn, status, start, target, acts in R.PROJECTS:
        p = Project(code=code, name=name, description=desc, sponsor_id=fn_owner[ofn].id, status=status, start_date=_d(start), target_date=_d(target))
        p.activities = [ProjectActivity(title=t, activity_type=ty, owner_id=fn_owner[ofn].id, status=st, due_date=_d(due)) for t, ty, st, due in acts]
        db.add(p)
    db.commit()

    # ---------------------------------------------------------------- replay 2026
    lk = Lookups(db)
    audit = AuditTrail(db)
    audit.record(actor="system", action="PLATFORM_INITIALISED", entity_type="System", entity_id="emea-guard",
                 details={"jurisdictions": len(jur), "requirements": len(req), "assets": len(assets), "employees": len(employees),
                          "rules": len(rules_cfg), "controls": len(R.CONTROLS)}, timestamp=datetime(2025, 12, 31, 9, 0))
    _legacy_entitlements(db, rng, employees, assets, jur, audit)

    events = _request_plan(rng, employees, assets, jur, n=330)
    cycle_iter = iter(CYCLE_DATES)
    next_cycle = next(cycle_iter)
    for when, payload in events:
        while next_cycle and when.date() > next_cycle:
            _close_cycle(db, lk, audit, rng, next_cycle)
            next_cycle = next(cycle_iter, None)
        submit_access_request(db, lk, audit, now=when, actor=f"portal:{payload['employee'].employee_ref}", **payload)
    while next_cycle:
        _close_cycle(db, lk, audit, rng, next_cycle)
        next_cycle = next(cycle_iter, None)

    _simulate_task_progress(db, rng)
    db.commit()
    return {"jurisdictions": len(jur), "requirements": len(req), "assets": len(assets), "employees": len(employees)}


# ---------------------------------------------------------------- helpers
def _close_cycle(db: Session, lk: Lookups, audit: AuditTrail, rng: random.Random, as_of: date) -> None:
    """Between cycles: owners remediate some open gaps, then controls are retested and risk recalculated."""
    open_gaps = db.execute(select(ComplianceGap).where(ComplianceGap.status.in_(("Open", "In Remediation"))).order_by(ComplianceGap.id)).scalars().all()
    for g in open_gaps:
        age = (as_of - g.identified_at.date()).days
        if age < 25:
            continue
        p = 0.55 if g.severity in ("Critical", "High") else 0.4
        if rng.random() < p:
            when = g.identified_at + timedelta(days=rng.randint(5, max(6, age - 2)))
            note = apply_remediation(db, g, when)
            db.flush()
            jcode = lk.jur_by_id[g.jurisdiction_id].code if g.jurisdiction_id else None
            close_gap(db, audit, g, status="Resolved", note=note, when=when, actor=f"owner:{g.owner_id}", jurisdiction_code=jcode)
        elif g.status == "Open" and rng.random() < 0.6:
            g.status = "In Remediation"
    db.flush()
    lk.reload()
    run_cycle(db, lk, audit, as_of=as_of)
    db.flush()
    compute_risk(db, lk, audit, as_of=as_of)
    db.commit()


def _simulate_task_progress(db: Session, rng: random.Random) -> None:
    from ..models import RemediationTask
    for t in db.execute(select(RemediationTask).where(RemediationTask.status != "Completed").order_by(RemediationTask.id)).scalars():
        if t.gap.status == "In Remediation" or rng.random() < 0.35:
            t.status = "In Progress"
        if t.gap.status == "Open" and t.status == "In Progress":
            t.gap.status = "In Remediation"
    # a couple of documented risk acceptances
    for g in db.execute(select(ComplianceGap).where(ComplianceGap.status == "Open", ComplianceGap.severity == "Low").order_by(ComplianceGap.id)).scalars().all()[:3]:
        g.status = "Risk Accepted"
        g.resolution_note = "Risk accepted by CDO EMEA until next annual review (synthetic)."


def _request_plan(rng: random.Random, employees, assets, jur, n: int):
    id2code = {j.id: c for c, j in jur.items()}
    assets_by_j = {}
    for a in assets:
        assets_by_j.setdefault(id2code[a.jurisdiction_id], []).append(a)
    events = []
    start = datetime(2026, 1, 5)
    span = (datetime(2026, 11, 25) - start).days
    for _ in range(n):
        e = rng.choice(employees)
        when = start + timedelta(days=rng.randint(0, span), hours=rng.randint(8, 18), minutes=rng.randint(0, 59))
        if e.termination_date and when.date() > e.termination_date and rng.random() < 0.85:
            when = datetime.combine(e.termination_date, datetime.min.time()) - timedelta(days=rng.randint(10, 60), hours=-10)
            if when < start:
                when = start + timedelta(days=rng.randint(1, 20), hours=10)
        ej = id2code[e.jurisdiction_id]
        perms = {p.domain: p for p in e.role.permissions}
        if rng.random() < 0.6:
            pool = assets_by_j[ej]
        else:
            targets = HUB_TARGETS.get(ej) or list(assets_by_j)
            pool = assets_by_j[rng.choice(targets)]

        def fits(a):
            p = perms.get(a.domain) or perms.get("*")
            return p is not None and (a.classification_id or 4) <= p.max_classification
        fitting = [a for a in pool if fits(a)]
        well_formed = bool(fitting) and rng.random() < 0.88  # most requests are sensible; some are not
        asset = rng.choice(fitting if well_formed else pool)
        if asset.created_at > when.date():
            when = datetime.combine(asset.created_at, datetime.min.time()) + timedelta(days=rng.randint(1, 30), hours=11)
        perm = perms.get(asset.domain) or perms.get("*")
        if well_formed and perm:
            types = perm.access_types
            access_type = rng.choices(types, weights=[6 if t == "read" else 2 for t in types])[0]
        else:
            access_type = rng.choices(["read", "write", "export", "admin"], weights=[55, 18, 20, 7])[0]
        purpose = rng.choice(asset.allowed_purposes) if rng.random() < 0.86 else rng.choice(ALL_PURPOSES)
        ticket = f"RITM{rng.randint(1000000, 9999999)}" if access_type != "read" and rng.random() < 0.8 else None
        level = asset.classification_id or 4
        approvals = []
        stale = rng.random() < 0.06

        def appr(t):
            back = rng.randint(100, 160) if stale else rng.randint(0, 4)
            approvals.append({"approval_type": t, "decided_at": when - timedelta(days=back, hours=2)})
        if level >= 2 and rng.random() < 0.88:
            appr("LINE_MANAGER")
        if level >= 3 and rng.random() < 0.8:
            appr("DATA_OWNER")
        if (asset.contains_special_category or (id2code[asset.jurisdiction_id] != ej and asset.contains_personal_data)) and rng.random() < 0.7:
            appr("DPO")
        events.append((when, {"employee": e, "asset": asset, "access_type": access_type, "purpose": purpose,
                              "justification": f"{purpose} activity for {e.business_unit}", "ticket_ref": ticket, "approvals": approvals}))
    events.sort(key=lambda x: x[0])
    return events


def _legacy_entitlements(db, rng, employees, assets, jur, audit):
    """Entitlements migrated from the legacy IAM system before go-live (never evaluated by the engine).

    The detective controls (leaver access, recertification, dormant access, CID access) find the
    problems the preventive engine never had the chance to stop.
    """
    id2code = {j.id: c for c, j in jur.items()}
    cid_assets = [a for a in assets if a.contains_cid and id2code[a.jurisdiction_id] in ("CH", "LU")]
    n = 0
    for i in range(60):
        e = rng.choice(employees)
        if i < 8 and cid_assets:
            asset = rng.choice(cid_assets)
            if id2code[e.jurisdiction_id] == id2code[asset.jurisdiction_id]:
                e = rng.choice([x for x in employees if x.jurisdiction_id != asset.jurisdiction_id])
        else:
            perm_domains = {p.domain for p in e.role.permissions}
            pool = [a for a in assets if a.domain in perm_domains or "*" in perm_domains] or assets
            asset = rng.choice(pool)
        n += 1
        granted = date(2025, 3, 1) + timedelta(days=rng.randint(0, 250))
        db.add(AccessRequest(
            request_ref=f"LEG-2025-{n:04d}", employee_id=e.id, asset_id=asset.id, access_type=rng.choice(["read", "read", "write"]),
            purpose=rng.choice(asset.allowed_purposes), justification="Migrated from legacy IAM", requested_at=datetime.combine(granted, datetime.min.time()),
            decision="APPROVED", decision_reason="Legacy entitlement migrated without evaluation", risk_score=0, risk_rating="Low",
            cross_border=e.jurisdiction_id != asset.jurisdiction_id, evaluation_trace={}, granted_until=granted + timedelta(days=730),
            last_used_at=SEED_TODAY - timedelta(days=rng.choice([5, 20, 40, 120, 200, 260])),
            last_recertified_at=None if rng.random() < 0.3 else granted + timedelta(days=rng.randint(30, 200)),
        ))
    db.flush()
    audit.record(actor="system", action="LEGACY_ENTITLEMENTS_MIGRATED", entity_type="AccessRequest", entity_id="LEG-2025",
                 details={"count": n}, timestamp=datetime(2025, 12, 31, 10, 0))


def _policy_content(title: str, doc_type: str, rcodes: list[str]) -> str:
    return (
        f"# {title}\n\n## 1. Purpose\nDefines the {doc_type.lower()} requirements for {title.lower()} across EMEA entities.\n\n"
        f"## 2. Scope\nAll EMEA legal entities, employees, contractors and third parties processing firm data.\n\n"
        f"## 3. Requirements\n- Comply with the regulatory obligations mapped below.\n- Exceptions require documented approval by the policy owner.\n"
        f"- Compliance is monitored through automated controls in EMEA Guard.\n\n## 4. Regulatory mapping\n"
        + "\n".join(f"- {c}" for c in rcodes)
        + "\n\n_Synthetic document for portfolio demonstration._\n"
    )


def _slug(s: str) -> str:
    import unicodedata
    return "".join(c for c in unicodedata.normalize("NFKD", s.lower()) if c.isalnum())


def _email(name: str) -> str:
    parts = name.split()
    return f"{_slug(parts[0])}.{_slug(parts[-1])}@emeaguard-bank.example"
