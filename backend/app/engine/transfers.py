"""Cross-border adequacy model (simplified, synthetic).

Answers: can personal data held in `source` be exposed to someone in `destination`
without an additional transfer mechanism?

Simplifications (documented in docs/REGULATORY_MODEL.md):
* EEA <-> EEA flows freely.
* EEA data may flow to jurisdictions holding an EU adequacy decision (UK, Switzerland).
* UK and Swiss data may flow to the EEA and to each other (UK adequacy regulations / Swiss FDPIC list).
* South African data may flow to EEA/UK/CH (treated as "substantially similar" law under POPIA s.72).
* UAE data has no adequate destinations in this model; every outbound exposure needs a mechanism.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class JurisdictionProfile:
    code: str
    is_eea: bool
    eu_adequacy: bool


def is_adequate(source: JurisdictionProfile, destination: JurisdictionProfile) -> bool:
    if source.code == destination.code:
        return True
    if source.is_eea:
        return destination.is_eea or destination.eu_adequacy
    if source.code in {"GB", "CH"}:
        return destination.is_eea or destination.code in {"GB", "CH"}
    if source.code == "ZA":
        return destination.is_eea or destination.code in {"GB", "CH"}
    return False


def adequacy_matrix(profiles: list[JurisdictionProfile]) -> dict[str, dict[str, bool]]:
    return {s.code: {d.code: is_adequate(s, d) for d in profiles} for s in profiles}
