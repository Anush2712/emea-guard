"""Reference data: jurisdictions, regulatory requirements, classifications, roles, controls, policies.

All content is a SIMPLIFIED, SYNTHETIC model for a portfolio project. Regulatory references
point to real instruments so the model is realistic, but descriptions are paraphrased summaries,
not legal advice, and not any institution's actual compliance position.
"""

JURISDICTIONS = [
    # code, name, region, is_eu, is_eea, eu_adequacy, DPA, financial regulator, primary law, residency, banking secrecy, breach hrs, inherent risk
    ("IE", "Ireland", "Europe", True, True, False, "Data Protection Commission (DPC)", "Central Bank of Ireland", "GDPR + Data Protection Act 2018", "Open", False, 72, 1.15),
    ("GB", "United Kingdom", "Europe", False, False, True, "Information Commissioner's Office (ICO)", "PRA / FCA", "UK GDPR + Data Protection Act 2018", "Open", False, 72, 1.10),
    ("DE", "Germany", "Europe", True, True, False, "Federal & state DPAs (BfDI)", "BaFin", "GDPR + BDSG", "Conditional", False, 72, 1.10),
    ("FR", "France", "Europe", True, True, False, "CNIL", "ACPR", "GDPR + Loi Informatique et Libertés", "Conditional", True, 72, 1.05),
    ("NL", "Netherlands", "Europe", True, True, False, "Autoriteit Persoonsgegevens", "DNB / AFM", "GDPR + UAVG", "Open", False, 72, 0.95),
    ("LU", "Luxembourg", "Europe", True, True, False, "CNPD", "CSSF", "GDPR + LFS Art. 41", "Strict", True, 72, 1.25),
    ("CH", "Switzerland", "Europe", False, False, True, "FDPIC", "FINMA", "revFADP + Banking Act Art. 47", "Strict", True, 72, 1.30),
    ("PL", "Poland", "Europe", True, True, False, "UODO", "KNF", "GDPR + Polish Banking Law Art. 104", "Conditional", True, 72, 1.00),
    ("AE", "United Arab Emirates", "Middle East", False, False, False, "UAE Data Office / DIFC Commissioner", "CBUAE / DFSA", "PDPL (Decree-Law 45/2021)", "Strict", False, 72, 1.35),
    ("ZA", "South Africa", "Africa", False, False, False, "Information Regulator", "Prudential Authority (SARB)", "POPIA", "Conditional", False, 72, 1.20),
]

# code, scope, jurisdiction, regime, reference, title, description, category, min classification
REQUIREMENTS = [
    # ----- GLOBAL
    ("GL-BCBS-01", "GLOBAL", None, "BCBS 239", "Principle 2", "Data architecture and IT infrastructure",
     "Risk data must have defined ownership, data taxonomies and accountable owners across the group.", "Governance", 1),
    ("GL-BCBS-02", "GLOBAL", None, "BCBS 239", "Principle 3", "Accuracy and integrity of risk data",
     "Risk data aggregation must be accurate and reliable, with reconciliation and controls.", "Data Quality", 2),
    # ----- EU
    ("EU-GDPR-01", "EU", None, "GDPR", "Art. 5(1)(b)", "Purpose limitation", "Personal data collected for specified purposes must not be further processed incompatibly.", "Privacy", 2),
    ("EU-GDPR-02", "EU", None, "GDPR", "Art. 5(1)(c)", "Data minimisation", "Personal data must be limited to what is necessary for the purpose.", "Privacy", 2),
    ("EU-GDPR-03", "EU", None, "GDPR", "Art. 5(1)(e)", "Storage limitation", "Personal data must not be kept longer than necessary.", "Retention", 2),
    ("EU-GDPR-04", "EU", None, "GDPR", "Art. 6", "Lawfulness of processing", "Each processing activity needs a lawful basis.", "Privacy", 2),
    ("EU-GDPR-05", "EU", None, "GDPR", "Art. 9", "Special categories of personal data", "Processing of special category data is prohibited unless an Art. 9(2) condition applies.", "Privacy", 3),
    ("EU-GDPR-06", "EU", None, "GDPR", "Art. 25", "Data protection by design and by default", "By default, personal data must only be accessible to those who need it.", "Access Control", 2),
    ("EU-GDPR-07", "EU", None, "GDPR", "Art. 28", "Processor obligations", "Processing by a processor must be governed by a binding contract.", "Third Party", 2),
    ("EU-GDPR-08", "EU", None, "GDPR", "Art. 30", "Records of processing activities", "Controllers must maintain a record of processing activities (RoPA).", "Governance", 2),
    ("EU-GDPR-09", "EU", None, "GDPR", "Art. 32", "Security of processing", "Appropriate technical and organisational measures, including encryption where appropriate.", "Security", 2),
    ("EU-GDPR-10", "EU", None, "GDPR", "Art. 33", "Breach notification", "Notify the supervisory authority within 72 hours of becoming aware of a breach.", "Incident", 2),
    ("EU-GDPR-11", "EU", None, "GDPR", "Art. 35", "Data protection impact assessment", "A DPIA is required for high-risk processing such as large-scale special category data.", "Privacy", 3),
    ("EU-GDPR-12", "EU", None, "GDPR", "Art. 44-46", "International transfers", "Transfers outside the EEA require adequacy or appropriate safeguards such as SCCs.", "Data Localisation", 2),
    ("EU-GDPR-13", "EU", None, "GDPR", "Art. 37-39", "Data protection officer", "Designate a DPO and involve them in all data protection matters.", "Governance", 1),
    ("EU-DORA-01", "EU", None, "DORA", "Art. 9(4)(c)", "ICT access limitation", "Limit logical access to ICT assets to what is required for legitimate and approved functions.", "Access Control", 2),
    ("EU-DORA-02", "EU", None, "DORA", "Art. 12", "Backup and restoration", "Backup policies and restoration procedures for ICT systems and data.", "Security", 2),
    ("EU-DORA-03", "EU", None, "DORA", "Art. 19", "Major ICT incident reporting", "Report major ICT-related incidents to the competent authority.", "Incident", 2),
    ("EU-DORA-04", "EU", None, "DORA", "Art. 28(3)", "Register of information", "Maintain a register of all contractual arrangements with ICT third-party providers.", "Third Party", 2),
    ("EU-DORA-05", "EU", None, "DORA", "Art. 13(6)", "ICT security awareness and training", "Security awareness programmes and digital operational resilience training for all staff.", "Training", 1),
    # ----- Ireland
    ("IE-01", "NATIONAL", "IE", "Data Protection Act 2018", "DPA 2018", "Irish supervisory framework", "National GDPR implementation; breach notification to the DPC.", "Incident", 2),
    ("IE-02", "NATIONAL", "IE", "Central Bank of Ireland", "Cross-Industry Guidance on Outsourcing (2021)", "Outsourcing register", "Maintain an outsourcing register and assess critical or important outsourcing.", "Third Party", 2),
    ("IE-03", "NATIONAL", "IE", "Central Bank of Ireland", "Cross-Industry Guidance on Operational Resilience (2021)", "Operational resilience", "Identify critical business services and set impact tolerances.", "Security", 2),
    ("IE-04", "NATIONAL", "IE", "Criminal Justice (ML & TF) Act 2010", "CDD record keeping", "AML record retention", "Retain customer due diligence records for 5 years after the relationship ends.", "Retention", 2),
    ("IE-05", "NATIONAL", "IE", "Consumer Protection Code 2012", "Record keeping", "Consumer record retention", "Retain consumer records for 6 years after the relationship ends.", "Retention", 2),
    # ----- Germany
    ("DE-01", "NATIONAL", "DE", "BDSG", "§26", "Employee data processing", "Processing of employee personal data for employment purposes.", "Privacy", 2),
    ("DE-02", "NATIONAL", "DE", "KWG / MaRisk", "§25a KWG, MaRisk AT 7.2", "Access rights management", "Access rights granted on a need-to-know basis and reviewed regularly.", "Access Control", 2),
    ("DE-03", "NATIONAL", "DE", "MaRisk", "AT 9", "Outsourcing", "Risk analysis and controls for outsourced activities.", "Third Party", 2),
    ("DE-04", "NATIONAL", "DE", "GwG", "§8", "AML record retention", "Retain AML records for 5 years.", "Retention", 2),
    ("DE-05", "NATIONAL", "DE", "HGB / AO", "§257 HGB, §147 AO", "Commercial record retention", "Retain books and accounting records for 10 years.", "Retention", 1),
    # ----- France
    ("FR-01", "NATIONAL", "FR", "Code monétaire et financier", "Art. L511-33", "Banking secrecy", "Credit institution staff are bound by professional secrecy over client information.", "Confidentiality", 3),
    ("FR-02", "NATIONAL", "FR", "Loi Informatique et Libertés", "Law 78-17", "French data protection law", "National GDPR implementation and CNIL requirements.", "Privacy", 2),
    ("FR-03", "NATIONAL", "FR", "ACPR", "Arrêté du 3 novembre 2014", "Internal control", "Internal control framework including segregation of duties.", "Governance", 1),
    ("FR-04", "NATIONAL", "FR", "Code monétaire et financier", "Art. L561-12", "AML record retention", "Retain AML records for 5 years.", "Retention", 2),
    ("FR-05", "NATIONAL", "FR", "Code de la santé publique", "Art. L1111-8", "Health data hosting (HDS)", "Health data must be hosted by certified (HDS) providers.", "Security", 3),
    # ----- Netherlands
    ("NL-01", "NATIONAL", "NL", "UAVG", "Art. 46", "Citizen service number (BSN)", "BSN may only be processed where required by law.", "Privacy", 3),
    ("NL-02", "NATIONAL", "NL", "Wft", "Art. 3:17", "Sound and controlled operations", "Organise operations to ensure controlled and sound business.", "Governance", 1),
    ("NL-03", "NATIONAL", "NL", "DNB", "Good Practice Information Security", "Information security", "Information security controls expected by DNB.", "Security", 2),
    ("NL-04", "NATIONAL", "NL", "Wwft", "Art. 33", "AML record retention", "Retain AML records for 5 years.", "Retention", 2),
    # ----- Luxembourg
    ("LU-01", "NATIONAL", "LU", "Law of 5 April 1993 (LFS)", "Art. 41", "Professional secrecy", "Financial sector professionals must keep client information secret.", "Confidentiality", 3),
    ("LU-02", "NATIONAL", "LU", "CSSF", "Circular 22/806", "Outsourcing arrangements", "Governance and notification of outsourcing, including cloud.", "Third Party", 2),
    ("LU-03", "NATIONAL", "LU", "CSSF", "Circular 20/750", "ICT and security risk management", "ICT and security risk management requirements.", "Security", 2),
    ("LU-04", "NATIONAL", "LU", "Law of 1 August 2018", "CNPD framework", "National data protection framework", "Organisation of the CNPD and national GDPR provisions.", "Privacy", 2),
    ("LU-05", "NATIONAL", "LU", "AML Law of 12 November 2004", "Record keeping", "AML record retention", "Retain AML records for 5 years.", "Retention", 2),
    # ----- Switzerland
    ("CH-01", "NATIONAL", "CH", "revFADP", "Art. 16", "Cross-border disclosure", "Disclosure abroad requires adequate protection or safeguards such as SCCs.", "Data Localisation", 2),
    ("CH-02", "NATIONAL", "CH", "Banking Act", "Art. 47", "Swiss banking secrecy", "Disclosure of client information is a criminal offence.", "Confidentiality", 3),
    ("CH-03", "NATIONAL", "CH", "FINMA", "Circular 2023/1", "Critical data and CID handling", "Identify critical data and control access to client identifying data.", "Access Control", 3),
    ("CH-04", "NATIONAL", "CH", "revFADP", "Art. 24", "Breach notification", "Notify the FDPIC as soon as possible of high-risk breaches.", "Incident", 2),
    ("CH-05", "NATIONAL", "CH", "revFADP", "Art. 22", "Data protection impact assessment", "DPIA required where processing creates high risk.", "Privacy", 3),
    ("CH-06", "NATIONAL", "CH", "AMLA", "Art. 7", "AML record retention", "Retain AML documentation for at least 10 years.", "Retention", 2),
    # ----- United Kingdom
    ("GB-01", "NATIONAL", "GB", "UK GDPR", "Art. 44-49", "International transfers (IDTA)", "Restricted transfers need adequacy regulations or the IDTA/Addendum.", "Data Localisation", 2),
    ("GB-02", "NATIONAL", "GB", "UK GDPR", "Art. 33", "Breach reporting to the ICO", "Report notifiable breaches to the ICO within 72 hours.", "Incident", 2),
    ("GB-03", "NATIONAL", "GB", "PRA", "SS2/21", "Outsourcing and third-party risk", "Manage material outsourcing and third-party arrangements.", "Third Party", 2),
    ("GB-04", "NATIONAL", "GB", "FCA Handbook", "SYSC 9", "Record keeping", "Keep orderly records of business and internal organisation.", "Retention", 1),
    ("GB-05", "NATIONAL", "GB", "PRA / FCA", "PS21/3 Operational resilience", "Operational resilience", "Identify important business services and impact tolerances.", "Security", 2),
    ("GB-06", "NATIONAL", "GB", "Money Laundering Regulations 2017", "Reg. 40", "AML record retention", "Retain CDD records for 5 years.", "Retention", 2),
    # ----- Poland
    ("PL-01", "NATIONAL", "PL", "Banking Law", "Art. 104", "Polish banking secrecy", "Bank staff must keep banking secrets.", "Confidentiality", 3),
    ("PL-02", "NATIONAL", "PL", "KNF", "Recommendation D", "IT and ICT security management", "Access management and ICT security in banks.", "Access Control", 2),
    ("PL-03", "NATIONAL", "PL", "Act on Personal Data Protection 2018", "UODO", "National data protection law", "National GDPR implementation.", "Privacy", 2),
    ("PL-04", "NATIONAL", "PL", "AML/CFT Act 2018", "Record keeping", "AML record retention", "Retain AML records for 5 years.", "Retention", 2),
    ("PL-05", "NATIONAL", "PL", "KNF", "Cloud Communication (2020)", "Cloud computing", "Requirements for use of public and hybrid cloud.", "Third Party", 2),
    # ----- UAE
    ("AE-01", "NATIONAL", "AE", "PDPL", "Decree-Law 45/2021 Art. 22-23", "Cross-border transfer", "Transfers abroad need adequate protection or permitted exceptions.", "Data Localisation", 2),
    ("AE-02", "NATIONAL", "AE", "DIFC Data Protection Law", "Law No. 5 of 2020", "DIFC transfers", "Transfers out of the DIFC require adequacy or safeguards.", "Data Localisation", 2),
    ("AE-03", "NATIONAL", "AE", "CBUAE", "Consumer Protection Regulation", "Customer data residency", "Customer data to be stored and processed in the UAE unless approved.", "Data Localisation", 2),
    ("AE-04", "NATIONAL", "AE", "Decree-Law 20/2018", "AML record keeping", "AML record retention", "Retain AML records for 5 years.", "Retention", 2),
    ("AE-05", "NATIONAL", "AE", "PDPL", "Art. 9", "Breach notification", "Notify the Data Office of breaches affecting personal data.", "Incident", 2),
    # ----- South Africa
    ("ZA-01", "NATIONAL", "ZA", "POPIA", "s.72", "Transborder information flows", "Transfers need substantially similar law, binding agreement or consent.", "Data Localisation", 2),
    ("ZA-02", "NATIONAL", "ZA", "POPIA", "s.19", "Security safeguards", "Secure integrity and confidentiality of personal information.", "Security", 2),
    ("ZA-03", "NATIONAL", "ZA", "POPIA", "s.22", "Notification of security compromises", "Notify the Information Regulator and data subjects of compromises.", "Incident", 2),
    ("ZA-04", "NATIONAL", "ZA", "FICA", "s.22-23", "Record keeping", "Retain client records for 5 years.", "Retention", 2),
    ("ZA-05", "NATIONAL", "ZA", "Prudential Authority", "Directive 3/2018", "Cloud and offshoring of data", "Prior notification and controls for offshoring material data.", "Third Party", 2),
]

CLASSIFICATIONS = [
    (1, "Public", "Approved for public release.", ["No restrictions"], False, False),
    (2, "Internal", "General business information for staff.", ["Staff only", "Line manager approval"], False, False),
    (3, "Confidential", "Client or business-sensitive information.", ["Need-to-know", "Data owner approval", "Encrypt at rest"], True, True),
    (4, "Restricted", "Highly sensitive: CID, special category, regulatory.", ["Named access only", "Data owner + DPO where personal", "Encrypt at rest", "No bulk export cross-border"], True, True),
]

DOMAINS = ["Customer", "Payments", "Markets", "Risk", "HR", "Finance", "Compliance", "Marketing"]

# name, description, privileged, [(domain, max_classification, access types)]
ROLES = [
    ("Data Analyst", "Analytics on curated datasets.", False, [("Customer", 3, ["read", "export"]), ("Payments", 3, ["read", "export"]), ("Marketing", 3, ["read", "export"]), ("Finance", 2, ["read"])]),
    ("Relationship Manager", "Client-facing banker.", False, [("Customer", 4, ["read", "write"]), ("Payments", 3, ["read"]), ("Marketing", 2, ["read"])]),
    ("Operations Analyst", "Payments and client operations.", False, [("Payments", 4, ["read", "write"]), ("Customer", 3, ["read"]), ("Finance", 2, ["read"])]),
    ("Software Engineer", "Builds and supports applications.", False, [("Payments", 3, ["read", "write"]), ("Markets", 3, ["read", "write"]), ("Customer", 2, ["read"]), ("Marketing", 2, ["read", "write"])]),
    ("Risk Analyst", "Credit and market risk analytics.", False, [("Risk", 4, ["read", "write", "export"]), ("Markets", 3, ["read"]), ("Finance", 3, ["read"]), ("Customer", 2, ["read"])]),
    ("Trader", "Front-office markets.", False, [("Markets", 4, ["read", "write"]), ("Risk", 2, ["read"])]),
    ("Compliance Officer", "Regulatory compliance and surveillance.", False, [("Compliance", 4, ["read", "write", "export"]), ("Customer", 4, ["read"]), ("Markets", 3, ["read"]), ("Payments", 3, ["read"])]),
    ("HR Specialist", "Human resources.", False, [("HR", 4, ["read", "write", "export"])]),
    ("Finance Controller", "Financial control and reporting.", False, [("Finance", 4, ["read", "write", "export"]), ("Payments", 3, ["read"]), ("Risk", 2, ["read"])]),
    ("Data Steward", "Data quality and metadata.", False, [("*", 3, ["read"])]),
    ("Platform Administrator", "Privileged infrastructure administration.", True, [("*", 4, ["read", "write", "admin"])]),
    ("Internal Auditor", "Third line of defence.", False, [("*", 4, ["read"])]),
    ("Marketing Specialist", "Campaigns and segmentation.", False, [("Marketing", 3, ["read", "write", "export"]), ("Customer", 2, ["read"])]),
]

ROLE_BUSINESS_UNIT = {
    "Data Analyst": "Chief Data Office", "Relationship Manager": "Commercial Banking", "Operations Analyst": "Payments Operations",
    "Software Engineer": "Technology", "Risk Analyst": "Risk Management", "Trader": "Markets", "Compliance Officer": "Compliance",
    "HR Specialist": "Human Resources", "Finance Controller": "Finance", "Data Steward": "Chief Data Office",
    "Platform Administrator": "Technology", "Internal Auditor": "Internal Audit", "Marketing Specialist": "Marketing",
}

# Regional (EMEA-level) stakeholders: name, title, function, domain
EMEA_STAKEHOLDERS = [
    ("Aoife Brennan", "Chief Data Officer, EMEA", "Executive", None),
    ("Marcus Webb", "Head of Identity & Access Management, EMEA", "IAM", None),
    ("Sofia Moreau", "Head of Compliance, EMEA", "Executive", None),
    ("Daniel Okafor", "Chief Information Security Officer, EMEA", "Control Owner", None),
    ("Hannah Kowalski", "Head of Records Management", "Data Steward", None),
    ("Pieter de Vries", "Head of Third-Party Risk", "Control Owner", None),
    ("Elena Rossi", "Senior Counsel, Data Protection", "Legal", None),
    ("Ciara Walsh", "Data Owner, Customer", "Data Owner", "Customer"),
    ("Tomasz Nowak", "Data Owner, Payments", "Data Owner", "Payments"),
    ("Lukas Brandt", "Data Owner, Markets", "Data Owner", "Markets"),
    ("Amelia Clarke", "Data Owner, Risk", "Data Owner", "Risk"),
    ("Noura Al Mansoori", "Data Owner, HR", "Data Owner", "HR"),
    ("Jean-Luc Bernard", "Data Owner, Finance", "Data Owner", "Finance"),
    ("Priya Raman", "Data Owner, Compliance", "Data Owner", "Compliance"),
    ("Oliver Hughes", "Data Owner, Marketing", "Data Owner", "Marketing"),
]

# Jurisdiction DPOs and data stewards
JURISDICTION_STAKEHOLDERS = {
    "IE": ("Siobhán Kelly", "Rory Byrne"), "GB": ("James Whitfield", "Grace Patel"), "DE": ("Katrin Vogel", "Jonas Richter"),
    "FR": ("Camille Laurent", "Hugo Martin"), "NL": ("Femke Jansen", "Daan Bakker"), "LU": ("Anne Schmit", "Marc Weber"),
    "CH": ("Reto Keller", "Lea Meier"), "PL": ("Agnieszka Wiśniewska", "Piotr Zieliński"), "AE": ("Omar Haddad", "Layla Rahman"),
    "ZA": ("Thandiwe Nkosi", "Pieter van Wyk"),
}

# code, name, domain, description, test_type, control_type, criticality, threshold, frequency, scope, owner function, requirement codes, remediation
CONTROLS = [
    ("GC-01", "Data asset ownership coverage", "Data Governance", "Every data asset has an accountable owner.", "asset_ownership", "Detective", 3, 100, "Quarterly", "Jurisdiction", "Data Steward", ["GL-BCBS-01", "EU-GDPR-08"], "Assign accountable owners to all unowned assets."),
    ("GC-02", "Data classification coverage", "Data Governance", "Every data asset is classified.", "asset_classification", "Detective", 3, 100, "Quarterly", "Jurisdiction", "Data Steward", ["GL-BCBS-01"], "Classify all unclassified assets."),
    ("GC-03", "Encryption at rest", "Security", "Confidential and Restricted assets are encrypted at rest.", "encryption_at_rest", "Preventive", 4, 100, "Quarterly", "Jurisdiction", "Control Owner", ["EU-GDPR-09", "LU-03", "NL-03", "ZA-02"], "Enable encryption at rest and evidence key management."),
    ("GC-04", "Retention compliance", "Retention", "No asset holds records beyond its retention period.", "retention", "Detective", 3, 95, "Quarterly", "Jurisdiction", "Data Steward", ["EU-GDPR-03", "DE-05", "GB-04", "CH-06"], "Execute retention purge with legal-hold checks."),
    ("GC-05", "Data residency compliance", "Data Localisation", "Copies of residency-restricted assets stay in-jurisdiction.", "residency", "Preventive", 4, 100, "Monthly", "Jurisdiction", "DPO", ["AE-03", "CH-02", "LU-01", "ZA-05"], "Relocate non-compliant replicas/backups in-jurisdiction."),
    ("GC-06", "Transfer mechanism validity", "Data Localisation", "Copies stored abroad are covered by adequacy or a valid mechanism with TIA.", "transfer_mechanisms", "Detective", 4, 100, "Quarterly", "Jurisdiction", "DPO", ["EU-GDPR-12", "GB-01", "CH-01", "AE-01", "ZA-01"], "Renew expired mechanisms and complete TIAs."),
    ("GC-07", "Data protection training", "Training", "Active staff completed training in the last 12 months.", "training", "Preventive", 2, 95, "Monthly", "Jurisdiction", "DPO", ["EU-DORA-05", "EU-GDPR-09"], "Chase overdue training completion."),
    ("GC-08", "Leaver access revocation", "Access Control", "Terminated staff hold no active entitlements.", "leaver_access", "Detective", 4, 100, "Monthly", "Jurisdiction", "IAM", ["EU-DORA-01", "DE-02", "PL-02"], "Revoke residual leaver access and fix the JML feed."),
    ("GC-09", "Privileged access review", "Access Control", "Privileged users reviewed in the last 90 days.", "privileged_review", "Detective", 4, 100, "Quarterly", "Jurisdiction", "IAM", ["EU-DORA-01", "DE-02", "GB-05"], "Complete the privileged access review."),
    ("GC-10", "Access recertification", "Access Control", "Active entitlements recertified within 180 days.", "recertification", "Detective", 3, 90, "Semi-annual", "Jurisdiction", "IAM", ["EU-DORA-01", "DE-02", "CH-03"], "Run the recertification campaign for overdue entitlements."),
    ("GC-11", "Dormant access removal", "Access Control", "Entitlements unused for 90 days are removed.", "dormant_access", "Detective", 2, 90, "Quarterly", "Jurisdiction", "IAM", ["EU-GDPR-06", "EU-DORA-01"], "Remove dormant entitlements."),
    ("GC-12", "Processor agreements registered", "Third Party", "Third-party hosted assets have a processor agreement on the register.", "processor_agreements", "Detective", 3, 100, "Quarterly", "Jurisdiction", "Control Owner", ["EU-GDPR-07", "EU-DORA-04", "IE-02", "LU-02", "GB-03"], "Execute and register processor agreements."),
    ("GC-13", "DPIA for special category data", "Privacy", "Assets with special category data have a completed DPIA.", "dpia", "Preventive", 3, 100, "Annual", "Jurisdiction", "DPO", ["EU-GDPR-11", "CH-05"], "Complete DPIAs for in-scope assets."),
    ("GC-14", "Records of processing coverage", "Privacy", "Personal data assets are registered in the RoPA.", "ropa", "Detective", 2, 95, "Annual", "Jurisdiction", "DPO", ["EU-GDPR-08"], "Register missing processing activities."),
    ("GC-15", "CID banking secrecy access", "Data Localisation", "Client identifying data in CH/LU is only entitled to local staff.", "cid_access", "Preventive", 4, 100, "Monthly", "Jurisdiction", "DPO", ["CH-02", "CH-03", "LU-01"], "Revoke non-local CID entitlements."),
    ("GC-16", "Policy review currency", "Governance", "Governance policies are reviewed before their review date.", "policy_review", "Detective", 2, 100, "Quarterly", "EMEA", "Executive", ["NL-02", "FR-03"], "Complete overdue policy reviews."),
]

POLICIES = [
    ("POL-001", "EMEA Data Governance Policy", "Policy", "Executive", 12, ["GL-BCBS-01", "EU-GDPR-13"]),
    ("STD-001", "Data Classification Standard", "Standard", "Data Steward", 12, ["GL-BCBS-01", "EU-GDPR-08"]),
    ("STD-002", "Access Management Standard", "Standard", "IAM", 12, ["EU-DORA-01", "EU-GDPR-06", "DE-02", "PL-02"]),
    ("PRC-001", "Cross-Border Data Transfer Procedure", "Procedure", "DPO", 12, ["EU-GDPR-12", "GB-01", "CH-01", "AE-01", "ZA-01"]),
    ("STD-003", "Data Retention and Disposal Standard", "Standard", "Data Steward", 24, ["EU-GDPR-03", "DE-05", "GB-04", "CH-06"]),
    ("STD-004", "Encryption and Key Management Standard", "Standard", "Control Owner", 12, ["EU-GDPR-09", "LU-03"]),
    ("PRC-002", "Privileged Access Management Procedure", "Procedure", "IAM", 12, ["EU-DORA-01", "GB-05"]),
    ("PRC-003", "Personal Data Breach Response Procedure", "Procedure", "DPO", 12, ["EU-GDPR-10", "EU-DORA-03", "GB-02", "CH-04", "ZA-03", "AE-05"]),
    ("PRC-004", "Third-Party Data Sharing Procedure", "Procedure", "Control Owner", 12, ["EU-GDPR-07", "EU-DORA-04", "IE-02", "LU-02"]),
    ("PRC-005", "Jurisdiction Onboarding Procedure", "Procedure", "Executive", 24, ["GL-BCBS-01"]),
    ("STD-005", "Banking Secrecy and CID Handling Standard", "Standard", "DPO", 12, ["CH-02", "CH-03", "LU-01", "FR-01", "PL-01"]),
    ("STD-006", "Data Quality Standard", "Standard", "Data Steward", 12, ["GL-BCBS-02"]),
]

PROJECTS = [
    ("PRJ-001", "DORA Register of Information uplift", "Complete the DORA Art. 28 register for all ICT third-party arrangements across EMEA entities.", "Control Owner", "In Progress", "2026-02-01", "2026-12-31", [
        ("Inventory all ICT third-party contracts", "Task", "Done", "2026-04-30"),
        ("Map contracts to data assets", "Task", "Done", "2026-06-30"),
        ("Close missing processor agreements", "Task", "In Progress", "2026-12-15"),
        ("Submit register to competent authorities", "Milestone", "Not Started", "2026-12-31")]),
    ("PRJ-002", "Swiss CID remediation", "Remove non-local access to Swiss client identifying data and relocate DR copies onshore.", "DPO", "At Risk", "2026-05-01", "2026-12-20", [
        ("Identify non-local CID entitlements", "Task", "Done", "2026-06-15"),
        ("Relocate DR backups to Swiss region", "Task", "Blocked", "2026-11-30"),
        ("FINMA status update", "Milestone", "Not Started", "2026-12-20")]),
    ("PRJ-003", "Access recertification Q4 campaign", "Recertify all active entitlements older than 180 days.", "IAM", "In Progress", "2026-10-01", "2026-12-31", [
        ("Launch campaign", "Milestone", "Done", "2026-10-05"),
        ("Chase managers with overdue certifications", "Task", "In Progress", "2026-12-10"),
        ("Auto-revoke uncertified entitlements", "Task", "Not Started", "2026-12-31")]),
    ("PRJ-004", "UAE data residency programme", "Keep CBUAE-regulated customer data onshore and document approved exceptions.", "DPO", "In Progress", "2026-03-01", "2027-03-31", [
        ("Assess offshore replicas of UAE customer data", "Task", "Done", "2026-07-31"),
        ("Execute SCC-equivalent agreements for approved flows", "Task", "In Progress", "2026-12-31"),
        ("Decide on in-region analytics platform", "Decision", "In Progress", "2027-01-31")]),
    ("PRJ-005", "Retention purge automation", "Automate retention purges with legal-hold checks for all EMEA platforms.", "Data Steward", "Planned", "2027-01-15", "2027-06-30", [
        ("Agree purge scheduling with platform owners", "Task", "Not Started", "2027-02-15"),
        ("Pilot purge on Finance platforms", "Milestone", "Not Started", "2027-04-01")]),
]
