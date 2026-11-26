"""The 4-level severity model shared by access checks, control assessments and risk reporting."""
from __future__ import annotations

SEVERITIES = ["Critical", "High", "Medium", "Low"]
SEVERITY_RANK = {"Low": 1, "Medium": 2, "High": 3, "Critical": 4}
SEVERITY_WEIGHT = {"Low": 1, "Medium": 3, "High": 6, "Critical": 10}

# Remediation SLA (days from identification) per severity.
REMEDIATION_SLA_DAYS = {"Critical": 7, "High": 30, "Medium": 60, "Low": 90}

CLASSIFICATION_NAMES = {1: "Public", 2: "Internal", 3: "Confidential", 4: "Restricted"}


def matrix_severity(impact: int, likelihood: int) -> str:
    """Impact (1-4) x likelihood (1-4) risk matrix -> severity.

    score 12-16 Critical, 8-11 High, 4-7 Medium, 1-3 Low.
    """
    impact = max(1, min(4, int(impact)))
    likelihood = max(1, min(4, int(likelihood)))
    score = impact * likelihood
    if score >= 12:
        return "Critical"
    if score >= 8:
        return "High"
    if score >= 4:
        return "Medium"
    return "Low"


def likelihood_from_exception_rate(rate: float) -> int:
    """Map a control test exception rate (0-1) to a likelihood score (1-4)."""
    if rate > 0.30:
        return 4
    if rate > 0.15:
        return 3
    if rate > 0.05:
        return 2
    return 1


def score_to_rating(score: float) -> str:
    """0-100 risk score -> 4-level rating."""
    if score >= 70:
        return "Critical"
    if score >= 50:
        return "High"
    if score >= 30:
        return "Medium"
    return "Low"
