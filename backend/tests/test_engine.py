"""Unit tests for the pure access decision engine and severity model."""
from datetime import date, timedelta
from pathlib import Path

import pytest
import yaml

from app.engine.access import (
    AccessContext,
    ApprovalCtx,
    AssetCtx,
    EmployeeCtx,
    PermissionCtx,
    RequestCtx,
    TransferCtx,
    evaluate,
)
from app.engine.severity import matrix_severity, score_to_rating
from app.engine.transfers import JurisdictionProfile, is_adequate

TODAY = date(2026, 11, 26)
RULES = [dict(r, enabled=True) for r in yaml.safe_load((Path(__file__).parents[1] / "app/engine/rules.yaml").read_text())["rules"]]


def make_ctx(**over) -> AccessContext:
    emp = EmployeeCtx(1, "EMP-0001", "Lena Fischer", "DE", "Data Analyst", False, "Chief Data Office", "Active", TODAY - timedelta(days=100))
    asset = AssetCtx(1, "DA-0001", "Ireland Retail Customer Master", "IE", "Customer", 4, 9, True, False, False, False, True,
                     2555, TODAY - timedelta(days=400), ["Analytics", "Client Servicing"], False, None)
    ctx = AccessContext(
        employee=emp,
        permissions=[PermissionCtx("Customer", 4, ["read", "export"])],
        asset=asset,
        request=RequestCtx("read", "Analytics"),
        approvals=[ApprovalCtx("LINE_MANAGER", "Approved", TODAY), ApprovalCtx("DATA_OWNER", "Approved", TODAY)],
        adequate=True, transfer_mechanism=None, applicable_requirements=["EU-GDPR-06", "IE-01", "DE-02"], as_of=TODAY,
    )
    for k, v in over.items():
        setattr(ctx, k, v)
    return ctx


def failed(decision):
    return {r.code for r in decision.failed}


def test_jd_scenario_germany_employee_irish_data_approved_with_approvals():
    d = evaluate(make_ctx(), RULES)
    assert d.decision == "APPROVED", d.reason
    assert d.cross_border is True
    assert len(d.steps) == 10


def test_missing_data_owner_approval_escalates():
    ctx = make_ctx(approvals=[ApprovalCtx("LINE_MANAGER", "Approved", TODAY)])
    d = evaluate(ctx, RULES)
    assert d.decision == "PENDING_APPROVAL"
    assert "APR-002" in failed(d)


def test_rbac_denies_wrong_domain():
    ctx = make_ctx(permissions=[PermissionCtx("Marketing", 3, ["read"])])
    d = evaluate(ctx, RULES)
    assert d.decision == "DENIED" and "ACC-001" in failed(d)


def test_swiss_cid_from_uk_denied_by_banking_secrecy():
    ctx = make_ctx()
    ctx.asset.jurisdiction, ctx.asset.contains_cid, ctx.asset.residency_required = "CH", True, True
    ctx.employee.jurisdiction = "GB"
    d = evaluate(ctx, RULES)
    assert d.decision == "DENIED"
    assert {"LOC-001", "LOC-003"} <= failed(d)


def test_non_adequate_transfer_with_expired_scc_denied_and_raises_gap():
    ctx = make_ctx(adequate=False, transfer_mechanism=TransferCtx("EU SCCs", "SCC-DE-ZA", TODAY - timedelta(days=10), True),
                   approvals=make_ctx().approvals + [ApprovalCtx("DPO", "Approved", TODAY)])
    ctx.employee.jurisdiction = "ZA"
    d = evaluate(ctx, RULES)
    loc = next(r for r in d.rules if r.code == "LOC-002")
    assert d.decision == "DENIED" and not loc.passed and loc.raises_gap
    assert "expired" in loc.message


def test_valid_mechanism_allows_transfer():
    ctx = make_ctx(adequate=False, transfer_mechanism=TransferCtx("EU SCCs", "SCC-IE-ZA", TODAY + timedelta(days=200), True),
                   approvals=make_ctx().approvals + [ApprovalCtx("DPO", "Approved", TODAY)])
    ctx.employee.jurisdiction = "ZA"
    assert evaluate(ctx, RULES).decision == "APPROVED"


def test_terminated_employee_is_critical_denial():
    ctx = make_ctx()
    ctx.employee.status = "Terminated"
    d = evaluate(ctx, RULES)
    r = next(r for r in d.rules if r.code == "ACC-003")
    assert d.decision == "DENIED" and r.severity == "Critical" and r.raises_gap


def test_unclassified_asset_is_treated_as_restricted_and_flagged():
    ctx = make_ctx(permissions=[PermissionCtx("Customer", 3, ["read"])])
    ctx.asset.classification_level = None
    d = evaluate(ctx, RULES)
    assert d.effective_classification == 4
    assert {"ACC-001", "DAT-001"} <= failed(d)


def test_flag_rules_do_not_block_but_record_findings():
    ctx = make_ctx()
    ctx.asset.encrypted_at_rest = False
    d = evaluate(ctx, RULES)
    assert d.decision == "APPROVED_WITH_FINDINGS" and "DAT-003" in failed(d)


def test_disabled_rule_is_skipped():
    rules = [dict(r, enabled=(r["code"] != "APR-002")) for r in RULES]
    ctx = make_ctx(approvals=[ApprovalCtx("LINE_MANAGER", "Approved", TODAY)])
    assert evaluate(ctx, rules).decision == "APPROVED"


def test_stale_approval_escalates():
    ctx = make_ctx(approvals=[ApprovalCtx("LINE_MANAGER", "Approved", TODAY - timedelta(days=120)),
                              ApprovalCtx("DATA_OWNER", "Approved", TODAY)])
    assert "APR-004" in failed(evaluate(ctx, RULES))


def test_export_of_restricted_personal_data_cross_border_denied():
    ctx = make_ctx(request=RequestCtx("export", "Analytics", ticket_ref="RITM1234567"))
    d = evaluate(ctx, RULES)
    assert "LOC-004" in failed(d) and d.decision == "DENIED"


def test_rule_set_size():
    assert len(RULES) >= 15


@pytest.mark.parametrize("impact,likelihood,expected", [(4, 4, "Critical"), (4, 3, "Critical"), (3, 3, "High"),
                                                        (4, 2, "High"), (2, 2, "Medium"), (1, 3, "Low"), (1, 1, "Low")])
def test_severity_matrix(impact, likelihood, expected):
    assert matrix_severity(impact, likelihood) == expected


def test_rating_scale_has_four_levels():
    assert {score_to_rating(s) for s in (5, 35, 55, 90)} == {"Low", "Medium", "High", "Critical"}


def test_adequacy_model():
    ie, ch, ae, gb = (JurisdictionProfile("IE", True, False), JurisdictionProfile("CH", False, True),
                      JurisdictionProfile("AE", False, False), JurisdictionProfile("GB", False, True))
    assert is_adequate(ie, ch) and is_adequate(ie, gb) and is_adequate(gb, ie)
    assert not is_adequate(ie, ae) and not is_adequate(ae, ie)
