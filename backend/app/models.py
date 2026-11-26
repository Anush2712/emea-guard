"""Relational data model for EMEA Guard.

25 entities plus two association tables. Every table is synthetic portfolio data.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Table,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

# ---------------------------------------------------------------- association tables
control_requirements = Table(
    "control_requirements",
    Base.metadata,
    Column("control_id", ForeignKey("governance_controls.id", ondelete="CASCADE"), primary_key=True),
    Column("requirement_id", ForeignKey("regulatory_requirements.id", ondelete="CASCADE"), primary_key=True),
)

policy_requirements = Table(
    "policy_requirements",
    Base.metadata,
    Column("policy_id", ForeignKey("policies.id", ondelete="CASCADE"), primary_key=True),
    Column("requirement_id", ForeignKey("regulatory_requirements.id", ondelete="CASCADE"), primary_key=True),
)


# ---------------------------------------------------------------- reference data
class Jurisdiction(Base):
    __tablename__ = "jurisdictions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    region: Mapped[str] = mapped_column(String(20))  # Europe | Middle East | Africa
    is_eu: Mapped[bool] = mapped_column(Boolean, default=False)
    is_eea: Mapped[bool] = mapped_column(Boolean, default=False)
    eu_adequacy: Mapped[bool] = mapped_column(Boolean, default=False)
    data_protection_authority: Mapped[str] = mapped_column(String(120))
    financial_regulator: Mapped[str] = mapped_column(String(120))
    primary_law: Mapped[str] = mapped_column(String(160))
    residency_regime: Mapped[str] = mapped_column(String(20))  # Open | Conditional | Strict
    banking_secrecy: Mapped[bool] = mapped_column(Boolean, default=False)
    breach_notification_hours: Mapped[int] = mapped_column(Integer, default=72)
    inherent_risk: Mapped[float] = mapped_column(Float, default=1.0)  # 0.8 - 1.4 multiplier
    status: Mapped[str] = mapped_column(String(20), default="Active")  # Onboarding | Active
    onboarded_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    requirements: Mapped[list[RegulatoryRequirement]] = relationship(back_populates="jurisdiction")


class RegulatoryRequirement(Base):
    __tablename__ = "regulatory_requirements"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    scope: Mapped[str] = mapped_column(String(10))  # GLOBAL | EU | NATIONAL
    jurisdiction_id: Mapped[int | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True)
    regime: Mapped[str] = mapped_column(String(80))
    reference: Mapped[str] = mapped_column(String(160))
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(40))
    min_classification: Mapped[int] = mapped_column(Integer, default=1)  # applies to this level and above

    jurisdiction: Mapped[Jurisdiction | None] = relationship(back_populates="requirements")


class DataClassification(Base):
    __tablename__ = "data_classifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    level: Mapped[int] = mapped_column(Integer, unique=True)  # 1 Public .. 4 Restricted
    name: Mapped[str] = mapped_column(String(30), unique=True)
    description: Mapped[str] = mapped_column(Text)
    handling_rules: Mapped[list] = mapped_column(JSON, default=list)
    requires_owner_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    requires_encryption: Mapped[bool] = mapped_column(Boolean, default=False)


class Stakeholder(Base):
    __tablename__ = "stakeholders"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(120))
    function: Mapped[str] = mapped_column(String(40))  # Data Owner | DPO | Data Steward | Control Owner | Executive | Legal | IAM
    email: Mapped[str] = mapped_column(String(120))
    jurisdiction_id: Mapped[int | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True)
    domain: Mapped[str | None] = mapped_column(String(40), nullable=True)

    jurisdiction: Mapped[Jurisdiction | None] = relationship()


class DataAsset(Base):
    __tablename__ = "data_assets"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_ref: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160))
    domain: Mapped[str] = mapped_column(String(40))
    system: Mapped[str] = mapped_column(String(80))
    hosting_provider: Mapped[str] = mapped_column(String(60))
    is_third_party_hosted: Mapped[bool] = mapped_column(Boolean, default=False)
    processor_agreement_ref: Mapped[str | None] = mapped_column(String(40), nullable=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    classification_id: Mapped[int | None] = mapped_column(ForeignKey("data_classifications.id"), nullable=True)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    steward_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    contains_personal_data: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_special_category: Mapped[bool] = mapped_column(Boolean, default=False)
    contains_cid: Mapped[bool] = mapped_column(Boolean, default=False)  # client identifying data
    residency_required: Mapped[bool] = mapped_column(Boolean, default=False)
    encrypted_at_rest: Mapped[bool] = mapped_column(Boolean, default=True)
    dpia_completed: Mapped[bool] = mapped_column(Boolean, default=False)
    ropa_registered: Mapped[bool] = mapped_column(Boolean, default=False)
    retention_days: Mapped[int] = mapped_column(Integer, default=2555)
    oldest_record_date: Mapped[date] = mapped_column(Date)
    record_count: Mapped[int] = mapped_column(Integer, default=0)
    allowed_purposes: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[date] = mapped_column(Date)
    last_reviewed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    jurisdiction: Mapped[Jurisdiction] = relationship()
    classification: Mapped[DataClassification | None] = relationship()
    owner: Mapped[Stakeholder | None] = relationship(foreign_keys=[owner_id])
    steward: Mapped[Stakeholder | None] = relationship(foreign_keys=[steward_id])
    locations: Mapped[list[DataLocalisationRecord]] = relationship(back_populates="asset", order_by="DataLocalisationRecord.id")


class DataLocalisationRecord(Base):
    """Where a copy of an asset physically lives (primary, replica, backup, DR)."""

    __tablename__ = "data_localisation_records"
    id: Mapped[int] = mapped_column(primary_key=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("data_assets.id", ondelete="CASCADE"), index=True)
    location_jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"))
    location_type: Mapped[str] = mapped_column(String(20))  # Primary | Replica | Backup | DR
    hosting_region: Mapped[str] = mapped_column(String(60))
    verified_at: Mapped[date] = mapped_column(Date)
    compliant: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # set by the engine
    issue: Mapped[str | None] = mapped_column(Text, nullable=True)

    asset: Mapped[DataAsset] = relationship(back_populates="locations")
    location: Mapped[Jurisdiction] = relationship()


class TransferMechanism(Base):
    """Legal basis for moving / exposing data from one jurisdiction to another."""

    __tablename__ = "transfer_mechanisms"
    id: Mapped[int] = mapped_column(primary_key=True)
    source_jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"))
    destination_jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"))
    mechanism: Mapped[str] = mapped_column(String(60))
    reference: Mapped[str] = mapped_column(String(60))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_until: Mapped[date] = mapped_column(Date)
    tia_completed: Mapped[bool] = mapped_column(Boolean, default=True)  # transfer impact assessment

    source: Mapped[Jurisdiction] = relationship(foreign_keys=[source_jurisdiction_id])
    destination: Mapped[Jurisdiction] = relationship(foreign_keys=[destination_jurisdiction_id])


# ---------------------------------------------------------------- identity & access
class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(60), unique=True)
    description: Mapped[str] = mapped_column(Text)
    privileged: Mapped[bool] = mapped_column(Boolean, default=False)

    permissions: Mapped[list[Permission]] = relationship(back_populates="role", cascade="all, delete-orphan", order_by="Permission.id")


class Permission(Base):
    __tablename__ = "permissions"
    __table_args__ = (UniqueConstraint("role_id", "domain"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"))
    domain: Mapped[str] = mapped_column(String(40))  # data domain or "*"
    max_classification: Mapped[int] = mapped_column(Integer)
    access_types: Mapped[list] = mapped_column(JSON, default=list)  # read | write | export | admin

    role: Mapped[Role] = relationship(back_populates="permissions")


class Employee(Base):
    __tablename__ = "employees"
    id: Mapped[int] = mapped_column(primary_key=True)
    employee_ref: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(120))
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    business_unit: Mapped[str] = mapped_column(String(60))
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"))
    status: Mapped[str] = mapped_column(String(20), default="Active")  # Active | Leave | Terminated
    hire_date: Mapped[date] = mapped_column(Date)
    termination_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_training_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_access_review: Mapped[date | None] = mapped_column(Date, nullable=True)

    jurisdiction: Mapped[Jurisdiction] = relationship()
    role: Mapped[Role] = relationship()


class AccessRequest(Base):
    """An access request; once approved it is also the resulting entitlement (grant)."""

    __tablename__ = "access_requests"
    id: Mapped[int] = mapped_column(primary_key=True)
    request_ref: Mapped[str] = mapped_column(String(24), unique=True, index=True)
    employee_id: Mapped[int] = mapped_column(ForeignKey("employees.id"), index=True)
    asset_id: Mapped[int] = mapped_column(ForeignKey("data_assets.id"), index=True)
    access_type: Mapped[str] = mapped_column(String(10))
    purpose: Mapped[str] = mapped_column(String(60))
    justification: Mapped[str] = mapped_column(Text, default="")
    ticket_ref: Mapped[str | None] = mapped_column(String(30), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime)
    decision: Mapped[str] = mapped_column(String(30))  # APPROVED | APPROVED_WITH_FINDINGS | PENDING_APPROVAL | DENIED
    decision_reason: Mapped[str] = mapped_column(Text, default="")
    risk_score: Mapped[float] = mapped_column(Float, default=0)
    risk_rating: Mapped[str] = mapped_column(String(10), default="Low")
    cross_border: Mapped[bool] = mapped_column(Boolean, default=False)
    evaluation_trace: Mapped[dict] = mapped_column(JSON, default=dict)
    # entitlement lifecycle (only meaningful for approved requests)
    granted_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    revoked_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_used_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_recertified_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    employee: Mapped[Employee] = relationship()
    asset: Mapped[DataAsset] = relationship()
    approvals: Mapped[list[Approval]] = relationship(back_populates="access_request", cascade="all, delete-orphan")


class Approval(Base):
    __tablename__ = "approvals"
    id: Mapped[int] = mapped_column(primary_key=True)
    access_request_id: Mapped[int] = mapped_column(ForeignKey("access_requests.id", ondelete="CASCADE"), index=True)
    approval_type: Mapped[str] = mapped_column(String(20))  # LINE_MANAGER | DATA_OWNER | DPO
    approver_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Approved")
    decided_at: Mapped[datetime] = mapped_column(DateTime)

    access_request: Mapped[AccessRequest] = relationship(back_populates="approvals")
    approver: Mapped[Stakeholder | None] = relationship()


# ---------------------------------------------------------------- controls, gaps, risk
class GovernanceRule(Base):
    """A configurable rule evaluated on every access request (see engine/rules.yaml)."""

    __tablename__ = "governance_rules"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(30))
    description: Mapped[str] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(String(10))
    effect: Mapped[str] = mapped_column(String(10))  # deny | escalate | flag
    raises_gap: Mapped[bool] = mapped_column(Boolean, default=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    params: Mapped[dict] = mapped_column(JSON, default=dict)
    requirement_codes: Mapped[list] = mapped_column(JSON, default=list)
    remediation: Mapped[str] = mapped_column(Text, default="")
    owner_function: Mapped[str] = mapped_column(String(40), default="DPO")


class GovernanceControl(Base):
    __tablename__ = "governance_controls"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(10), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(120))
    domain: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    test_type: Mapped[str] = mapped_column(String(40))
    control_type: Mapped[str] = mapped_column(String(20))  # Preventive | Detective
    criticality: Mapped[int] = mapped_column(Integer, default=3)  # 1-4 impact
    threshold: Mapped[float] = mapped_column(Float, default=100.0)  # pass rate % for Effective
    frequency: Mapped[str] = mapped_column(String(20), default="Quarterly")
    scope: Mapped[str] = mapped_column(String(15), default="Jurisdiction")  # Jurisdiction | EMEA
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    remediation: Mapped[str] = mapped_column(Text, default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    owner: Mapped[Stakeholder | None] = relationship()
    requirements: Mapped[list[RegulatoryRequirement]] = relationship(secondary=control_requirements)


class ControlAssessment(Base):
    __tablename__ = "control_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    control_id: Mapped[int] = mapped_column(ForeignKey("governance_controls.id"), index=True)
    jurisdiction_id: Mapped[int | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True, index=True)
    cycle: Mapped[str] = mapped_column(String(10), index=True)  # e.g. 2026-Q3
    as_of: Mapped[date] = mapped_column(Date)
    population: Mapped[int] = mapped_column(Integer)
    exceptions: Mapped[int] = mapped_column(Integer)
    pass_rate: Mapped[float] = mapped_column(Float)
    result: Mapped[str] = mapped_column(String(25))  # Effective | Partially Effective | Ineffective | Not Applicable
    severity: Mapped[str | None] = mapped_column(String(10), nullable=True)
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    assessed_at: Mapped[datetime] = mapped_column(DateTime)
    assessed_by: Mapped[str] = mapped_column(String(40), default="control-engine")

    control: Mapped[GovernanceControl] = relationship()
    jurisdiction: Mapped[Jurisdiction | None] = relationship()


class ComplianceGap(Base):
    __tablename__ = "compliance_gaps"
    id: Mapped[int] = mapped_column(primary_key=True)
    gap_ref: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    dedup_key: Mapped[str] = mapped_column(String(120), index=True)
    source: Mapped[str] = mapped_column(String(20))  # access_check | control_assessment
    rule_code: Mapped[str | None] = mapped_column(String(10), nullable=True)
    control_id: Mapped[int | None] = mapped_column(ForeignKey("governance_controls.id"), nullable=True)
    assessment_id: Mapped[int | None] = mapped_column(ForeignKey("control_assessments.id"), nullable=True)
    access_request_id: Mapped[int | None] = mapped_column(ForeignKey("access_requests.id"), nullable=True)
    asset_id: Mapped[int | None] = mapped_column(ForeignKey("data_assets.id"), nullable=True)
    employee_id: Mapped[int | None] = mapped_column(ForeignKey("employees.id"), nullable=True)
    jurisdiction_id: Mapped[int | None] = mapped_column(ForeignKey("jurisdictions.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    impact: Mapped[int] = mapped_column(Integer)
    likelihood: Mapped[int] = mapped_column(Integer)
    severity: Mapped[str] = mapped_column(String(10), index=True)
    status: Mapped[str] = mapped_column(String(20), default="Open", index=True)  # Open | In Remediation | Resolved | Risk Accepted
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    occurrences: Mapped[int] = mapped_column(Integer, default=1)
    identified_at: Mapped[datetime] = mapped_column(DateTime)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime)
    due_date: Mapped[date] = mapped_column(Date)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    owner: Mapped[Stakeholder | None] = relationship()
    jurisdiction: Mapped[Jurisdiction | None] = relationship()
    control: Mapped[GovernanceControl | None] = relationship()
    tasks: Mapped[list[RemediationTask]] = relationship(back_populates="gap", cascade="all, delete-orphan", order_by="RemediationTask.id")


class RemediationTask(Base):
    __tablename__ = "remediation_tasks"
    id: Mapped[int] = mapped_column(primary_key=True)
    task_ref: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    gap_id: Mapped[int] = mapped_column(ForeignKey("compliance_gaps.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    priority: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="Not Started")  # Not Started | In Progress | Completed
    due_date: Mapped[date] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    gap: Mapped[ComplianceGap] = relationship(back_populates="tasks")
    owner: Mapped[Stakeholder | None] = relationship()


class RiskAssessment(Base):
    __tablename__ = "risk_assessments"
    id: Mapped[int] = mapped_column(primary_key=True)
    jurisdiction_id: Mapped[int] = mapped_column(ForeignKey("jurisdictions.id"), index=True)
    as_of: Mapped[date] = mapped_column(Date, index=True)
    cycle: Mapped[str] = mapped_column(String(10))
    control_effectiveness: Mapped[float] = mapped_column(Float)  # 0-100
    open_gap_score: Mapped[float] = mapped_column(Float)  # 0-100
    overdue_ratio: Mapped[float] = mapped_column(Float)  # 0-1
    access_denial_rate: Mapped[float] = mapped_column(Float)  # 0-1
    residual_score: Mapped[float] = mapped_column(Float)  # 0-100, higher = riskier
    rating: Mapped[str] = mapped_column(String(10))
    drivers: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    jurisdiction: Mapped[Jurisdiction] = relationship()


# ---------------------------------------------------------------- policy, projects, audit
class Policy(Base):
    __tablename__ = "policies"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    title: Mapped[str] = mapped_column(String(160))
    doc_type: Mapped[str] = mapped_column(String(12))  # Policy | Standard | Procedure
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="Published")
    current_version: Mapped[str] = mapped_column(String(10), default="1.0")
    review_cycle_months: Mapped[int] = mapped_column(Integer, default=12)
    last_reviewed: Mapped[date] = mapped_column(Date)
    next_review_date: Mapped[date] = mapped_column(Date)

    owner: Mapped[Stakeholder | None] = relationship()
    versions: Mapped[list[PolicyVersion]] = relationship(
        back_populates="policy", cascade="all, delete-orphan", order_by="PolicyVersion.id"
    )
    requirements: Mapped[list[RegulatoryRequirement]] = relationship(secondary=policy_requirements)


class PolicyVersion(Base):
    __tablename__ = "policy_versions"
    __table_args__ = (UniqueConstraint("policy_id", "version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    policy_id: Mapped[int] = mapped_column(ForeignKey("policies.id", ondelete="CASCADE"))
    version: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20))  # Draft | In Review | Approved | Published | Superseded
    change_summary: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    author: Mapped[str] = mapped_column(String(100))
    approved_by: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)

    policy: Mapped[Policy] = relationship(back_populates="versions")


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(12), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    sponsor_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # Planned | In Progress | At Risk | Completed
    start_date: Mapped[date] = mapped_column(Date)
    target_date: Mapped[date] = mapped_column(Date)

    sponsor: Mapped[Stakeholder | None] = relationship()
    activities: Mapped[list[ProjectActivity]] = relationship(back_populates="project", cascade="all, delete-orphan")


class ProjectActivity(Base):
    __tablename__ = "project_activities"
    id: Mapped[int] = mapped_column(primary_key=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    activity_type: Mapped[str] = mapped_column(String(20))  # Milestone | Task | Issue | Decision
    owner_id: Mapped[int | None] = mapped_column(ForeignKey("stakeholders.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20))  # Not Started | In Progress | Done | Blocked
    due_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str] = mapped_column(Text, default="")

    project: Mapped[Project] = relationship(back_populates="activities")
    owner: Mapped[Stakeholder | None] = relationship()


class AuditLog(Base):
    """Append-only, hash-chained audit trail (each entry hashes the previous one)."""

    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    actor: Mapped[str] = mapped_column(String(60))
    action: Mapped[str] = mapped_column(String(60), index=True)
    entity_type: Mapped[str] = mapped_column(String(40), index=True)
    entity_id: Mapped[str] = mapped_column(String(40))
    jurisdiction_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    prev_hash: Mapped[str] = mapped_column(String(64))
    hash: Mapped[str] = mapped_column(String(64), unique=True)


class User(Base):
    """Platform account (login). Distinct from the synthetic Employee population.

    Passwords are stored only as bcrypt hashes. The first account registered becomes admin.
    """

    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(100))
    hashed_password: Mapped[str] = mapped_column(String(200))
    app_role: Mapped[str] = mapped_column(String(20))  # admin | analyst | auditor
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    password_changed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_version: Mapped[int] = mapped_column(Integer, default=0)  # bumped on password change -> old JWTs rejected


class PasswordResetToken(Base):
    """Single-use, short-lived password reset token. Only its SHA-256 hash is stored."""

    __tablename__ = "password_reset_tokens"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    used_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    user: Mapped[User] = relationship()


DOMAIN_ENTITIES = [
    Jurisdiction, RegulatoryRequirement, DataClassification, Stakeholder, DataAsset,
    DataLocalisationRecord, TransferMechanism, Role, Permission, Employee, AccessRequest,
    Approval, GovernanceRule, GovernanceControl, ControlAssessment, ComplianceGap,
    RemediationTask, RiskAssessment, Policy, PolicyVersion, Project, ProjectActivity, AuditLog, User, PasswordResetToken,
]
