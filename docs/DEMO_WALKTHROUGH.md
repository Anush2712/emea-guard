# 5-minute walkthrough

Use the live demo (https://anush2712.github.io/emea-guard/) or `docker compose up` (http://localhost:8080). Create an account (the first account on a fresh database is the admin).

1. **Dashboard.** Residual risk per jurisdiction, coloured and labelled on the 4-level scale. Use the trend selector to highlight one jurisdiction against the others. Point out the priority gaps: each has an owner and an SLA date.
2. **Access control → "JD scenario: Germany employee → Irish customer data" → Evaluate.** Walk the 10-step pipeline and the 20-rule table. Untick *Data owner* and re-evaluate: the decision becomes *Pending approval* (escalate rule `APR-002`).
3. **"UK employee → Swiss client identifying data".** Denied by residency (`LOC-001`) and banking secrecy (`LOC-003`). Those are preventive controls doing their job, so they raise no gap themselves. The gap you do see comes from an unrelated weakness the same check surfaced on that asset (`DAT-004`: records held past their retention period), which shows how one access check doubles as a detective control on the data.
4. **"South Africa hub → German personal data".** Denied by `LOC-002` because the DE→ZA SCC expired, and a compliance gap is raised and routed to the German DPO with a deadline. That is the difference between a control working and a control being broken.
5. **Data localisation → Adequacy matrix.** Which flows are adequate, covered by a mechanism, or exposed.
6. **Control assessments.** 16 automated tests × 10 jurisdictions per cycle. Click a red cell to see the exact exceptions (evidence). Show the Governance rules tab: an admin can switch a rule off or change its severity at runtime.
7. **Gaps & remediation.** Open a control gap, *Apply corrective action & resolve*, then *Run control tests now*: the control passes on retest (in the full stack, gaps auto-close on retest).
8. **Risk & reports.** Driver decomposition per jurisdiction; download the Excel risk report (10 sheets built with Pandas) and the Plotly executive report.
9. **Policies.** Draft a new version as one user; an admin who isn't the author approves it (maker-checker).
10. **Audit trail → Verify chain integrity.** Every action above is in the hash-chained log.

## Talking points

- **Pure engine, thin services.** `engine/access.py` has no database or I/O, so it is unit-tested directly and mirrored in TypeScript for the static demo, with a parity test in CI.
- **Configurable, not hard-coded.** Rules live in YAML and in a database table that admins can change at runtime; every change is audited.
- **Preventive vs detective.** Denials are logged; only failures that reveal a broken control become gaps, which keeps the gap register meaningful.
- **Generated history.** The seed replays a year through the real engines, so the trends and gap lifecycle are the system's own output.
- **Tamper evidence.** The audit log is a hash chain; tests prove that editing a past row is detected.
