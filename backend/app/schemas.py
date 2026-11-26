"""Pydantic request bodies (responses are documented dicts produced by app/serializers.py)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

AccessType = Literal["read", "write", "export", "admin"]
Severity = Literal["Critical", "High", "Medium", "Low"]


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str
    full_name: str


class ApprovalIn(BaseModel):
    approval_type: Literal["LINE_MANAGER", "DATA_OWNER", "DPO"]
    decided_at: datetime | None = None
    status: Literal["Approved", "Rejected"] = "Approved"


class AccessRequestIn(BaseModel):
    employee_id: int
    asset_id: int
    access_type: AccessType = "read"
    purpose: str
    justification: str = ""
    ticket_ref: str | None = None
    approvals: list[ApprovalIn] = Field(default_factory=list)

    model_config = {"json_schema_extra": {"example": {
        "employee_id": 101, "asset_id": 3, "access_type": "read", "purpose": "Analytics",
        "justification": "Quarterly churn analysis", "ticket_ref": None,
        "approvals": [{"approval_type": "LINE_MANAGER"}, {"approval_type": "DATA_OWNER"}],
    }}}


class RuleUpdate(BaseModel):
    enabled: bool | None = None
    severity: Severity | None = None
    effect: Literal["deny", "escalate", "flag"] | None = None
    params: dict | None = None


class AssessmentRunIn(BaseModel):
    control_codes: list[str] | None = None
    as_of: date | None = None


class GapUpdate(BaseModel):
    status: Literal["Open", "In Remediation", "Resolved", "Risk Accepted"] | None = None
    owner_id: int | None = None
    note: str | None = None


class TaskUpdate(BaseModel):
    status: Literal["Not Started", "In Progress", "Completed"] | None = None
    due_date: date | None = None


class PolicyVersionIn(BaseModel):
    change_summary: str
    content: str
    major: bool = False


class RequirementIn(BaseModel):
    code: str
    regime: str
    reference: str
    title: str
    description: str
    category: str
    min_classification: int = 2


class JurisdictionIn(BaseModel):
    code: str = Field(min_length=2, max_length=2)
    name: str
    region: Literal["Europe", "Middle East", "Africa"]
    is_eu: bool = False
    is_eea: bool = False
    eu_adequacy: bool = False
    data_protection_authority: str
    financial_regulator: str
    primary_law: str
    residency_regime: Literal["Open", "Conditional", "Strict"] = "Conditional"
    banking_secrecy: bool = False
    breach_notification_hours: int = 72
    inherent_risk: float = 1.0
    dpo_name: str | None = None
    requirements: list[RequirementIn] = Field(default_factory=list)
