# Control engine reference

Generated from `backend/app/engine/rules.yaml` and `backend/app/seed/reference.py`.

## Access decision rules (evaluated on every request)

| Code | Rule | Category | Severity | Effect | Raises gap | Maps to |
|---|---|---|---|---|---|---|
| `ACC-001` | Role-based permission covers domain, classification and access type | Access Control | High | deny | no | EU-DORA-01, EU-GDPR-06, DE-02, CH-03, PL-02 |
| `ACC-002` | Administrative access requires a privileged role | Access Control | High | deny | no | EU-DORA-01, DE-02, GB-05 |
| `ACC-003` | Requester must be an active employee | Identity Lifecycle | Critical | deny | yes | EU-DORA-01, EU-GDPR-09 |
| `ACC-004` | Data protection training is current | Training | Medium | deny | yes | EU-DORA-05, EU-GDPR-09, ZA-02 |
| `ACC-005` | No segregation-of-duties conflict | Access Control | High | deny | no | FR-03, NL-02, EU-DORA-01 |
| `ACC-006` | Write, export and admin access need a change ticket | Change Management | Low | escalate | no | EU-DORA-01, GB-05 |
| `APR-001` | Line manager approval | Approvals | Medium | escalate | no | EU-GDPR-06, DE-02 |
| `APR-002` | Data owner approval for Confidential and Restricted data | Approvals | High | escalate | no | GL-BCBS-01, EU-GDPR-06, CH-03 |
| `APR-003` | DPO approval for special category data and non-adequate transfers | Approvals | High | escalate | no | EU-GDPR-05, EU-GDPR-12, ZA-01, AE-01 |
| `APR-004` | Approvals are recent | Approvals | Low | escalate | no | EU-DORA-01 |
| `LOC-001` | Data residency restriction | Data Localisation | Critical | deny | no | AE-03, CH-02, LU-01, ZA-05 |
| `LOC-002` | Cross-border access needs adequacy or a valid transfer mechanism | Data Localisation | High | deny | yes | EU-GDPR-12, GB-01, CH-01, AE-01, AE-02, ZA-01 |
| `LOC-003` | Banking secrecy for client identifying data | Data Localisation | Critical | deny | no | CH-02, CH-03, LU-01, FR-01, PL-01 |
| `LOC-004` | No cross-border export of Restricted personal data | Data Localisation | High | deny | no | EU-GDPR-12, EU-GDPR-02 |
| `PUR-001` | Purpose limitation | Privacy | Medium | deny | no | EU-GDPR-01, EU-GDPR-04, FR-02 |
| `DAT-001` | Asset is classified | Data Governance | Medium | flag | yes | GL-BCBS-01, EU-GDPR-08 |
| `DAT-002` | Asset has an accountable data owner | Data Governance | High | flag | yes | GL-BCBS-01, EU-GDPR-08 |
| `DAT-003` | Encryption at rest for Confidential and Restricted data | Security | High | flag | yes | EU-GDPR-09, ZA-02, LU-03, NL-03 |
| `DAT-004` | Retention period not exceeded | Retention | Medium | flag | yes | EU-GDPR-03, DE-05, GB-04, CH-06 |
| `PUR-002` | Third-party hosting has a processor agreement | Third Party | Medium | flag | yes | EU-GDPR-07, EU-DORA-04, IE-02, LU-02, GB-03 |

**Decision logic:** any failed `deny` rule → `DENIED`; otherwise any failed `escalate` rule → `PENDING_APPROVAL`; otherwise any failed `flag` rule → `APPROVED_WITH_FINDINGS`; otherwise `APPROVED`. Disabled rules are skipped. Unclassified assets are treated as Restricted (fail-safe).

**Request risk score (0-100):** classification level × 12 + access type weight (read 0, write 6, export 10, admin 14) + 12 if personal data crosses a border + 8 special category + 6 client identifying data + failed-rule points (Critical 25, High 15, Medium 8, Low 3), capped at 100.

**Gap de-duplication:** gaps key on the underlying weakness, not the request: `ACC-003`/`ACC-004` per employee, `LOC-002` per jurisdiction flow, data rules per asset, control gaps per control × jurisdiction. Repeat findings increment `occurrences` and can escalate severity.

## Automated control tests (run per jurisdiction each cycle)

| Code | Control | Test | Type | Criticality | Threshold | Frequency | Requirements |
|---|---|---|---|---|---|---|---|
| `GC-01` | Data asset ownership coverage | Every data asset has an accountable owner. | Detective | 3 | 100% | Quarterly | GL-BCBS-01, EU-GDPR-08 |
| `GC-02` | Data classification coverage | Every data asset is classified. | Detective | 3 | 100% | Quarterly | GL-BCBS-01 |
| `GC-03` | Encryption at rest | Confidential and Restricted assets are encrypted at rest. | Preventive | 4 | 100% | Quarterly | EU-GDPR-09, LU-03, NL-03, ZA-02 |
| `GC-04` | Retention compliance | No asset holds records beyond its retention period. | Detective | 3 | 95% | Quarterly | EU-GDPR-03, DE-05, GB-04, CH-06 |
| `GC-05` | Data residency compliance | Copies of residency-restricted assets stay in-jurisdiction. | Preventive | 4 | 100% | Monthly | AE-03, CH-02, LU-01, ZA-05 |
| `GC-06` | Transfer mechanism validity | Copies stored abroad are covered by adequacy or a valid mechanism with TIA. | Detective | 4 | 100% | Quarterly | EU-GDPR-12, GB-01, CH-01, AE-01, ZA-01 |
| `GC-07` | Data protection training | Active staff completed training in the last 12 months. | Preventive | 2 | 95% | Monthly | EU-DORA-05, EU-GDPR-09 |
| `GC-08` | Leaver access revocation | Terminated staff hold no active entitlements. | Detective | 4 | 100% | Monthly | EU-DORA-01, DE-02, PL-02 |
| `GC-09` | Privileged access review | Privileged users reviewed in the last 90 days. | Detective | 4 | 100% | Quarterly | EU-DORA-01, DE-02, GB-05 |
| `GC-10` | Access recertification | Active entitlements recertified within 180 days. | Detective | 3 | 90% | Semi-annual | EU-DORA-01, DE-02, CH-03 |
| `GC-11` | Dormant access removal | Entitlements unused for 90 days are removed. | Detective | 2 | 90% | Quarterly | EU-GDPR-06, EU-DORA-01 |
| `GC-12` | Processor agreements registered | Third-party hosted assets have a processor agreement on the register. | Detective | 3 | 100% | Quarterly | EU-GDPR-07, EU-DORA-04, IE-02, LU-02, GB-03 |
| `GC-13` | DPIA for special category data | Assets with special category data have a completed DPIA. | Preventive | 3 | 100% | Annual | EU-GDPR-11, CH-05 |
| `GC-14` | Records of processing coverage | Personal data assets are registered in the RoPA. | Detective | 2 | 95% | Annual | EU-GDPR-08 |
| `GC-15` | CID banking secrecy access | Client identifying data in CH/LU is only entitled to local staff. | Preventive | 4 | 100% | Monthly | CH-02, CH-03, LU-01 |
| `GC-16` | Policy review currency | Governance policies are reviewed before their review date. | Detective | 2 | 100% | Quarterly | NL-02, FR-03 |

**Rating:** pass rate ≥ threshold → Effective; within 15 points below threshold → Partially Effective; lower → Ineffective; empty population → Not Applicable.

**Gap from a control:** severity = matrix(control criticality, likelihood from exception rate: ≤5% → 1, ≤15% → 2, ≤30% → 3, >30% → 4). An open control gap is **auto-resolved** when the same control passes for that jurisdiction in a later cycle.

## Severity model (shared)

| Impact × likelihood | Severity | Remediation SLA |
|---|---|---|
| 12–16 | Critical | 7 days |
| 8–11 | High | 30 days |
| 4–7 | Medium | 60 days |
| 1–3 | Low | 90 days |

## Residual risk per jurisdiction

```
residual = inherent_multiplier × (0.45 × (100 − control effectiveness)
                                + 0.30 × open-gap pressure
                                + 0.15 × overdue ratio × 100
                                + 0.10 × access denial rate (180 days) × 100)   capped at 100
```

- Control effectiveness: latest result per control, Effective 100 / Partial 50 / Ineffective 0, weighted by criticality.
- Open-gap pressure: sum of severity weights of open gaps (Critical 10, High 6, Medium 3, Low 1) ÷ 60 × 100, capped at 100.
- Rating uses the same 4 levels: ≥70 Critical, ≥50 High, ≥30 Medium, otherwise Low.

## Stakeholder routing

| Rule / control owner function | Routed to |
|---|---|
| DPO | Data Protection Officer of the affected jurisdiction |
| Data Steward | Data steward of the affected jurisdiction |
| Data Owner | The asset's accountable owner (or the domain data owner) |
| IAM | Head of Identity & Access Management, EMEA |
| Control Owner | CISO, EMEA |
| Executive | Chief Data Officer, EMEA |
