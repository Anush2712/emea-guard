# Regulatory model

> Simplified and synthetic. References point to real instruments so the model is realistic, but descriptions are paraphrased summaries. This is not legal advice and not a statement of any institution's compliance.

## Jurisdictions

| Code | Jurisdiction | Region | Status | Data protection authority | Financial regulator | Primary framework | Residency | Banking secrecy | Inherent risk |
|---|---|---|---|---|---|---|---|---|---|
| IE | Ireland | Europe | EU/EEA | Data Protection Commission (DPC) | Central Bank of Ireland | GDPR + Data Protection Act 2018 | Open | no | 1.15 |
| GB | United Kingdom | Europe | EU adequacy | Information Commissioner's Office (ICO) | PRA / FCA | UK GDPR + Data Protection Act 2018 | Open | no | 1.1 |
| DE | Germany | Europe | EU/EEA | Federal & state DPAs (BfDI) | BaFin | GDPR + BDSG | Conditional | no | 1.1 |
| FR | France | Europe | EU/EEA | CNIL | ACPR | GDPR + Loi Informatique et Libertés | Conditional | yes | 1.05 |
| NL | Netherlands | Europe | EU/EEA | Autoriteit Persoonsgegevens | DNB / AFM | GDPR + UAVG | Open | no | 0.95 |
| LU | Luxembourg | Europe | EU/EEA | CNPD | CSSF | GDPR + LFS Art. 41 | Strict | yes | 1.25 |
| CH | Switzerland | Europe | EU adequacy | FDPIC | FINMA | revFADP + Banking Act Art. 47 | Strict | yes | 1.3 |
| PL | Poland | Europe | EU/EEA | UODO | KNF | GDPR + Polish Banking Law Art. 104 | Conditional | yes | 1.0 |
| AE | United Arab Emirates | Middle East | Third country | UAE Data Office / DIFC Commissioner | CBUAE / DFSA | PDPL (Decree-Law 45/2021) | Strict | no | 1.35 |
| ZA | South Africa | Africa | Third country | Information Regulator | Prudential Authority (SARB) | POPIA | Conditional | no | 1.2 |

## Adequacy model used for cross-border access

Remote access to personal data from another jurisdiction is treated as a transfer.

- EEA ↔ EEA: free flow.
- EEA data → UK or Switzerland: allowed (EU adequacy decisions).
- UK or Swiss data → EEA, UK, Switzerland: allowed.
- South African data → EEA, UK, Switzerland: allowed (treated as substantially similar law under POPIA s.72; a simplification).
- UAE data: no adequate destinations in the model; any outbound exposure needs a mechanism.
- Everything else needs a valid, unexpired mechanism (EU SCCs 2021/914, UK IDTA, Swiss-adapted SCCs, intra-group agreement) **with a completed transfer impact assessment**.

Strict residency (`LOC-001`) and banking secrecy for client identifying data in Switzerland and Luxembourg (`LOC-003`) apply on top of adequacy.

## Requirements (71)

| Code | Scope | Regime | Reference | Requirement | Category |
|---|---|---|---|---|---|
| `GL-BCBS-01` | GLOBAL | BCBS 239 | Principle 2 | Data architecture and IT infrastructure | Governance |
| `GL-BCBS-02` | GLOBAL | BCBS 239 | Principle 3 | Accuracy and integrity of risk data | Data Quality |
| `EU-GDPR-01` | EU | GDPR | Art. 5(1)(b) | Purpose limitation | Privacy |
| `EU-GDPR-02` | EU | GDPR | Art. 5(1)(c) | Data minimisation | Privacy |
| `EU-GDPR-03` | EU | GDPR | Art. 5(1)(e) | Storage limitation | Retention |
| `EU-GDPR-04` | EU | GDPR | Art. 6 | Lawfulness of processing | Privacy |
| `EU-GDPR-05` | EU | GDPR | Art. 9 | Special categories of personal data | Privacy |
| `EU-GDPR-06` | EU | GDPR | Art. 25 | Data protection by design and by default | Access Control |
| `EU-GDPR-07` | EU | GDPR | Art. 28 | Processor obligations | Third Party |
| `EU-GDPR-08` | EU | GDPR | Art. 30 | Records of processing activities | Governance |
| `EU-GDPR-09` | EU | GDPR | Art. 32 | Security of processing | Security |
| `EU-GDPR-10` | EU | GDPR | Art. 33 | Breach notification | Incident |
| `EU-GDPR-11` | EU | GDPR | Art. 35 | Data protection impact assessment | Privacy |
| `EU-GDPR-12` | EU | GDPR | Art. 44-46 | International transfers | Data Localisation |
| `EU-GDPR-13` | EU | GDPR | Art. 37-39 | Data protection officer | Governance |
| `EU-DORA-01` | EU | DORA | Art. 9(4)(c) | ICT access limitation | Access Control |
| `EU-DORA-02` | EU | DORA | Art. 12 | Backup and restoration | Security |
| `EU-DORA-03` | EU | DORA | Art. 19 | Major ICT incident reporting | Incident |
| `EU-DORA-04` | EU | DORA | Art. 28(3) | Register of information | Third Party |
| `EU-DORA-05` | EU | DORA | Art. 13(6) | ICT security awareness and training | Training |
| `IE-01` | IE | Data Protection Act 2018 | DPA 2018 | Irish supervisory framework | Incident |
| `IE-02` | IE | Central Bank of Ireland | Cross-Industry Guidance on Outsourcing (2021) | Outsourcing register | Third Party |
| `IE-03` | IE | Central Bank of Ireland | Cross-Industry Guidance on Operational Resilience (2021) | Operational resilience | Security |
| `IE-04` | IE | Criminal Justice (ML & TF) Act 2010 | CDD record keeping | AML record retention | Retention |
| `IE-05` | IE | Consumer Protection Code 2012 | Record keeping | Consumer record retention | Retention |
| `DE-01` | DE | BDSG | §26 | Employee data processing | Privacy |
| `DE-02` | DE | KWG / MaRisk | §25a KWG, MaRisk AT 7.2 | Access rights management | Access Control |
| `DE-03` | DE | MaRisk | AT 9 | Outsourcing | Third Party |
| `DE-04` | DE | GwG | §8 | AML record retention | Retention |
| `DE-05` | DE | HGB / AO | §257 HGB, §147 AO | Commercial record retention | Retention |
| `FR-01` | FR | Code monétaire et financier | Art. L511-33 | Banking secrecy | Confidentiality |
| `FR-02` | FR | Loi Informatique et Libertés | Law 78-17 | French data protection law | Privacy |
| `FR-03` | FR | ACPR | Arrêté du 3 novembre 2014 | Internal control | Governance |
| `FR-04` | FR | Code monétaire et financier | Art. L561-12 | AML record retention | Retention |
| `FR-05` | FR | Code de la santé publique | Art. L1111-8 | Health data hosting (HDS) | Security |
| `NL-01` | NL | UAVG | Art. 46 | Citizen service number (BSN) | Privacy |
| `NL-02` | NL | Wft | Art. 3:17 | Sound and controlled operations | Governance |
| `NL-03` | NL | DNB | Good Practice Information Security | Information security | Security |
| `NL-04` | NL | Wwft | Art. 33 | AML record retention | Retention |
| `LU-01` | LU | Law of 5 April 1993 (LFS) | Art. 41 | Professional secrecy | Confidentiality |
| `LU-02` | LU | CSSF | Circular 22/806 | Outsourcing arrangements | Third Party |
| `LU-03` | LU | CSSF | Circular 20/750 | ICT and security risk management | Security |
| `LU-04` | LU | Law of 1 August 2018 | CNPD framework | National data protection framework | Privacy |
| `LU-05` | LU | AML Law of 12 November 2004 | Record keeping | AML record retention | Retention |
| `CH-01` | CH | revFADP | Art. 16 | Cross-border disclosure | Data Localisation |
| `CH-02` | CH | Banking Act | Art. 47 | Swiss banking secrecy | Confidentiality |
| `CH-03` | CH | FINMA | Circular 2023/1 | Critical data and CID handling | Access Control |
| `CH-04` | CH | revFADP | Art. 24 | Breach notification | Incident |
| `CH-05` | CH | revFADP | Art. 22 | Data protection impact assessment | Privacy |
| `CH-06` | CH | AMLA | Art. 7 | AML record retention | Retention |
| `GB-01` | GB | UK GDPR | Art. 44-49 | International transfers (IDTA) | Data Localisation |
| `GB-02` | GB | UK GDPR | Art. 33 | Breach reporting to the ICO | Incident |
| `GB-03` | GB | PRA | SS2/21 | Outsourcing and third-party risk | Third Party |
| `GB-04` | GB | FCA Handbook | SYSC 9 | Record keeping | Retention |
| `GB-05` | GB | PRA / FCA | PS21/3 Operational resilience | Operational resilience | Security |
| `GB-06` | GB | Money Laundering Regulations 2017 | Reg. 40 | AML record retention | Retention |
| `PL-01` | PL | Banking Law | Art. 104 | Polish banking secrecy | Confidentiality |
| `PL-02` | PL | KNF | Recommendation D | IT and ICT security management | Access Control |
| `PL-03` | PL | Act on Personal Data Protection 2018 | UODO | National data protection law | Privacy |
| `PL-04` | PL | AML/CFT Act 2018 | Record keeping | AML record retention | Retention |
| `PL-05` | PL | KNF | Cloud Communication (2020) | Cloud computing | Third Party |
| `AE-01` | AE | PDPL | Decree-Law 45/2021 Art. 22-23 | Cross-border transfer | Data Localisation |
| `AE-02` | AE | DIFC Data Protection Law | Law No. 5 of 2020 | DIFC transfers | Data Localisation |
| `AE-03` | AE | CBUAE | Consumer Protection Regulation | Customer data residency | Data Localisation |
| `AE-04` | AE | Decree-Law 20/2018 | AML record keeping | AML record retention | Retention |
| `AE-05` | AE | PDPL | Art. 9 | Breach notification | Incident |
| `ZA-01` | ZA | POPIA | s.72 | Transborder information flows | Data Localisation |
| `ZA-02` | ZA | POPIA | s.19 | Security safeguards | Security |
| `ZA-03` | ZA | POPIA | s.22 | Notification of security compromises | Incident |
| `ZA-04` | ZA | FICA | s.22-23 | Record keeping | Retention |
| `ZA-05` | ZA | Prudential Authority | Directive 3/2018 | Cloud and offshoring of data | Third Party |
