"""Export a static snapshot of the API for the GitHub Pages live demo.

Seeds a fresh SQLite database, calls every read endpoint through the real FastAPI app,
and writes the JSON responses + generated reports into frontend/public/demo/.
Also writes parity fixtures: access decisions computed by the Python engine, which the
TypeScript demo engine must reproduce exactly (see frontend/src/demo/parity.test.ts).

Usage:  python -m app.scripts.export_demo [output_dir]
"""
from __future__ import annotations

import json
import os
import random
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

tmp = tempfile.mkdtemp()
os.environ["EMEA_GUARD_DATABASE_URL"] = f"sqlite:///{tmp}/demo.db"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import SessionLocal  # noqa: E402
from app.engine.access import ApprovalCtx, RequestCtx, evaluate  # noqa: E402
from app.main import app  # noqa: E402
from app.models import DataAsset, Employee  # noqa: E402
from app.seed.generate import ALL_PURPOSES, SEED_TODAY  # noqa: E402
from app.services.access_service import build_context  # noqa: E402
from app.services.lookups import Lookups  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "frontend" / "public" / "demo"

ENDPOINTS = {
    "metrics": "/api/metrics", "dashboard": "/api/dashboard/summary", "jurisdictions": "/api/jurisdictions",
    "requirements": "/api/requirements", "adequacy": "/api/transfers/adequacy-matrix", "classifications": "/api/classifications",
    "roles": "/api/roles", "assets": "/api/assets", "employees": "/api/employees", "access-requests": "/api/access-requests",
    "localisation-records": "/api/localisation/records", "transfer-mechanisms": "/api/localisation/transfer-mechanisms",
    "rules": "/api/rules", "controls": "/api/controls", "assessments": "/api/assessments", "gaps": "/api/gaps",
    "remediation-tasks": "/api/remediation-tasks", "risk-latest": "/api/risk/jurisdictions", "risk-history": "/api/risk/history",
    "policies": "/api/policies", "stakeholders": "/api/stakeholders", "projects": "/api/projects",
    "audit": "/api/audit?limit=5000", "audit-verify": "/api/audit/verify",
}


def dump(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False))


def parity_cases(n: int = 400) -> list[dict]:
    rng = random.Random(99)
    db = SessionLocal()
    lk = Lookups(db)
    emps = db.query(Employee).order_by(Employee.id).all()
    assets = db.query(DataAsset).order_by(DataAsset.id).all()
    cases = []
    for _ in range(n):
        e, a = rng.choice(emps), rng.choice(assets)
        req = RequestCtx(rng.choice(["read", "write", "export", "admin"]),
                         rng.choice(a.allowed_purposes) if rng.random() < 0.7 else rng.choice(ALL_PURPOSES),
                         ticket_ref=rng.choice([None, "RITM1234567", "INC000123"]))
        approvals = [ApprovalCtx(t, "Approved", SEED_TODAY - timedelta(days=rng.choice([0, 3, 30, 120])))
                     for t in ("LINE_MANAGER", "DATA_OWNER", "DPO") if rng.random() < 0.6]
        d = evaluate(build_context(lk, e, a, req, approvals, SEED_TODAY), lk.rules)
        cases.append({
            "employee_id": e.id, "asset_id": a.id, "access_type": req.access_type, "purpose": req.purpose, "ticket_ref": req.ticket_ref,
            "approvals": [{"approval_type": x.approval_type, "decided_at": x.decided_at.isoformat()} for x in approvals],
            "as_of": SEED_TODAY.isoformat(),
            "expected": {"decision": d.decision, "risk_score": d.risk_score, "failed": sorted(r.code for r in d.failed),
                         "applicable": sorted(r.code for r in d.rules if r.applicable)},
        })
    db.close()
    return cases


def main() -> None:
    api = OUT / "api"
    with TestClient(app) as client:
        tok = client.post("/api/auth/register", json={"username": "snapshot", "email": "snapshot@example.com",
                                                      "password": "Sn4pshot-export-only"}).json()["access_token"]
        h = {"Authorization": f"Bearer {tok}"}
        for name, path in ENDPOINTS.items():
            r = client.get(path, headers=h)
            r.raise_for_status()
            dump(api / f"{name}.json", r.json())
        details = {}
        for row in client.get("/api/access-requests", headers=h).json():
            details[row["id"]] = client.get(f"/api/access-requests/{row['id']}", headers=h).json()
        dump(api / "access-request-details.json", details)
        evidence = {a["id"]: client.get(f"/api/assessments/{a['id']}", headers=h).json()["evidence"]
                    for a in client.get("/api/assessments", headers=h).json() if a["exceptions"]}
        dump(api / "assessment-evidence.json", evidence)
        rep = OUT / "reports"
        rep.mkdir(parents=True, exist_ok=True)
        (rep / "emea-guard-risk-report.xlsx").write_bytes(client.get("/api/reports/risk-report.xlsx", headers=h).content)
        (rep / "emea-guard-gaps.csv").write_text(client.get("/api/reports/gaps.csv", headers=h).text)
        (rep / "emea-guard-executive-report.html").write_text(client.get("/api/reports/executive.html", headers=h).text)
    dump(api / "parity-cases.json", parity_cases())
    dump(api / "meta.json", {"snapshot_date": SEED_TODAY.isoformat(), "note": "Static snapshot of the EMEA Guard API over synthetic data."})
    print(f"Demo snapshot written to {OUT}")


if __name__ == "__main__":
    main()
