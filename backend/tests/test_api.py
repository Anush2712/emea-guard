"""API, workflow and integrity tests against a freshly seeded database."""
from sqlalchemy import select

from app.models import AuditLog, ComplianceGap, DataAsset, Employee, Jurisdiction


def test_platform_hits_target_metrics(client):
    m = client.get("/api/metrics").json()
    assert m["jurisdictions"] == 10
    assert m["regulatory_requirements"] >= 50
    assert m["data_assets"] >= 100
    assert m["employees"] >= 200
    assert m["governance_rules"] >= 15
    assert m["control_assessments"] >= 100
    assert m["database_entities"] >= 15
    assert m["severity_levels"] == 4


def test_auth_required_and_roles(client, auditor):
    assert client.get("/api/dashboard/summary").status_code == 401
    assert client.get("/api/dashboard/summary", headers=auditor).status_code == 200
    r = client.post("/api/assessments/run", json={}, headers=auditor)
    assert r.status_code == 403
    assert client.post("/api/auth/login", data={"username": "admin", "password": "wrong"}).status_code == 401


def test_dashboard_shape(client, analyst):
    d = client.get("/api/dashboard/summary", headers=analyst).json()
    assert len(d["risk_by_jurisdiction"]) == 10
    assert set(d["gaps_by_severity"]) == {"Critical", "High", "Medium", "Low"}
    assert d["kpis"]["latest_cycle"]


def _find(db, emp_j, asset_j, **asset_filters):
    emp = db.execute(select(Employee).join(Jurisdiction).where(Jurisdiction.code == emp_j, Employee.status == "Active")).scalars().first()
    q = select(DataAsset).join(Jurisdiction).where(Jurisdiction.code == asset_j)
    for k, v in asset_filters.items():
        q = q.where(getattr(DataAsset, k) == v)
    return emp, db.execute(q).scalars().first()


def test_jd_scenario_end_to_end(client, analyst, db):
    """Employee in Germany requests customer data held in Ireland: full pipeline, audit and risk refresh."""
    emp, asset = _find(db, "DE", "IE", domain="Customer")
    before = db.execute(select(AuditLog)).scalars().all()
    r = client.post("/api/access-requests/evaluate", headers=analyst, json={
        "employee_id": emp.id, "asset_id": asset.id, "access_type": "read", "purpose": asset.allowed_purposes[0]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["decision"] in {"APPROVED", "APPROVED_WITH_FINDINGS", "PENDING_APPROVAL", "DENIED"}
    assert len(body["trace"]["steps"]) == 10
    assert body["employee_jurisdiction"] == "DE" and body["asset_jurisdiction"] == "IE"
    db.expire_all()
    after = db.execute(select(AuditLog)).scalars().all()
    assert len(after) > len(before)
    assert any(a.action == "ACCESS_REQUEST_EVALUATED" and a.entity_id == body["request_ref"] for a in after)


def test_failed_detective_control_creates_routed_gap_with_deadline(client, analyst, db):
    emp, asset = _find(db, "IE", "IE")
    asset.encrypted_at_rest = False
    asset.classification_id = 4
    db.commit()
    r = client.post("/api/access-requests/evaluate", headers=analyst, json={
        "employee_id": emp.id, "asset_id": asset.id, "access_type": "read", "purpose": asset.allowed_purposes[0],
        "approvals": [{"approval_type": "LINE_MANAGER"}, {"approval_type": "DATA_OWNER"}, {"approval_type": "DPO"}]}).json()
    assert "DAT-003" in {x["code"] for x in r["trace"]["rules"] if not x["passed"]}
    assert r["trace"].get("gaps")
    gap = db.execute(select(ComplianceGap).where(ComplianceGap.gap_ref == r["trace"]["gaps"][0])).scalar_one()
    assert gap.owner_id is not None and gap.due_date is not None and gap.tasks


def test_rule_reconfiguration_changes_outcome(client, admin, analyst, db):
    emp, asset = _find(db, "IE", "IE", classification_id=3)
    payload = {"employee_id": emp.id, "asset_id": asset.id, "access_type": "read", "purpose": asset.allowed_purposes[0],
               "approvals": [{"approval_type": "LINE_MANAGER"}]}
    first = client.post("/api/access-requests/evaluate", headers=analyst, json=payload).json()
    assert "APR-002" in {x["code"] for x in first["trace"]["rules"] if not x["passed"]}
    assert client.patch("/api/rules/APR-002", headers=analyst, json={"enabled": False}).status_code == 403
    assert client.patch("/api/rules/APR-002", headers=admin, json={"enabled": False}).status_code == 200
    second = client.post("/api/access-requests/evaluate", headers=analyst, json=payload).json()
    assert "APR-002" not in {x["code"] for x in second["trace"]["rules"]}
    client.patch("/api/rules/APR-002", headers=admin, json={"enabled": True})


def test_control_cycle_and_remediation_loop(client, analyst):
    run = client.post("/api/assessments/run", headers=analyst, json={}).json()
    assert run["assessments"] >= 100
    gaps = client.get("/api/gaps?status=Open", headers=analyst).json() + client.get("/api/gaps?status=In%20Remediation", headers=analyst).json()
    ctrl_gap = next(g for g in gaps if g["source"] == "control_assessment" and g["control_code"] in ("GC-01", "GC-03", "GC-12", "GC-14"))
    fixed = client.post(f"/api/gaps/{ctrl_gap['id']}/remediate", headers=analyst).json()
    assert fixed["status"] == "Resolved" and all(t["status"] == "Completed" for t in fixed["tasks"])
    client.post("/api/assessments/run", headers=analyst, json={"control_codes": [ctrl_gap["control_code"]]})
    latest = [a for a in client.get("/api/assessments", headers=analyst).json()
              if a["control_code"] == ctrl_gap["control_code"] and a["jurisdiction"] == ctrl_gap["jurisdiction"]][-1]
    assert latest["result"] == "Effective"


def test_audit_chain_verifies_and_detects_tampering(client, auditor, db):
    assert client.get("/api/audit/verify", headers=auditor).json()["valid"] is True
    entry = db.execute(select(AuditLog).order_by(AuditLog.id).offset(5).limit(1)).scalar_one()
    original = entry.actor
    entry.actor = "tampered"
    db.commit()
    res = client.get("/api/audit/verify", headers=auditor).json()
    assert res["valid"] is False and res["broken_at_id"] == entry.id
    entry.actor = original
    db.commit()
    assert client.get("/api/audit/verify", headers=auditor).json()["valid"] is True


def test_reports_download(client, auditor):
    x = client.get("/api/reports/risk-report.xlsx", headers=auditor)
    assert x.status_code == 200 and x.content[:2] == b"PK"
    c = client.get("/api/reports/gaps.csv", headers=auditor)
    assert c.status_code == 200 and c.text.startswith("gap_ref,")
    h = client.get("/api/reports/executive.html", headers=auditor)
    assert h.status_code == 200 and "Plotly.newPlot" in h.text


def test_policy_versioning_maker_checker(client, analyst, admin):
    pol = client.get("/api/policies", headers=analyst).json()[0]
    r = client.post(f"/api/policies/{pol['id']}/versions", headers=analyst,
                    json={"change_summary": "Add DORA Art. 28 references", "content": "# Updated", "major": False})
    assert r.status_code == 201
    draft = next(v for v in r.json()["versions"] if v["status"] == "In Review")
    pub = client.post(f"/api/policies/{pol['id']}/versions/{draft['id']}/approve", headers=admin)
    assert pub.status_code == 200 and pub.json()["current_version"] == draft["version"]


def test_jurisdiction_onboarding_workflow(client, admin):
    body = {"code": "SA", "name": "Saudi Arabia", "region": "Middle East", "data_protection_authority": "SDAIA",
            "financial_regulator": "SAMA", "primary_law": "PDPL (Royal Decree M/19)", "residency_regime": "Strict",
            "requirements": [{"code": "SA-01", "regime": "PDPL", "reference": "Art. 29", "title": "Cross-border transfer",
                              "description": "Transfers outside the Kingdom are restricted.", "category": "Data Localisation"}]}
    r = client.post("/api/jurisdictions", headers=admin, json=body)
    assert r.status_code == 201 and r.json()["status"] == "Onboarding"
    assert r.json()["readiness"]["checks"]["has_dpo"] is False
    assert client.post("/api/jurisdictions/SA/activate", headers=admin).status_code == 422
