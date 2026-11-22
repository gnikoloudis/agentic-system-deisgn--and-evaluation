# Stakeholder Requirements Intake Transcript: FinTech Card Chargeback & Dispute Resolution Portal

**Project Code**: FIN-DISP-2026
**Stakeholders Interviewed**:
- **Elena Rostova** (VP of Card Operations)
- **Marcus Vance** (Head of Regulatory Compliance & Risk)
- **David Kim** (Lead Backend Developer)
- **Priya Nair** (QA & Test Automation Manager)

---

## 1. Raw Interview Notes & Business Requirements

### Elena Rostova (VP of Card Operations)
- "**BR-001 (Self-Service Dispute Submission & 60-Day Window)**: Cardholders need to submit transaction disputes directly from the mobile/web portal. Only settled transactions within **60 calendar days** of the settlement date are eligible. If a transaction is still pending or older than 60 days, the system must block submission with a clear explanation."
- "**BR-002 (Automated Micro-Dispute Resolution <= $25.00)**: Right now our agents waste 40% of their time on tiny disputes. Any valid dispute for **$25.00 or less** (where the cardholder has fewer than 3 disputes in the rolling 12-month period) must be **automatically approved and credited** without human agent review."
- "**BR-003 (Evidence Upload & Tiered Agent/Supervisor Review)**: For disputes over **$25.00**, the cardholder can upload supporting evidence (receipts, merchant emails) as **PDF, PNG, or JPG files up to 10 MB per file (max 5 files)**. Dispute Analysts can approve provisional credits up to **$500.00**; any dispute strictly greater than **$500.00** requires **Senior Dispute Supervisor** dual-approval."

### Marcus Vance (Head of Regulatory Compliance & Risk)
- "**BR-004 (Regulation E / Card Network 45-Day SLA & Reason Codes)**: Every dispute must be mapped to a standardized network reason code (`FRD-10` Unauthorized Fraud, `MER-20` Duplicate Charge, `MER-30` Goods/Services Not Received, `MER-40` Incorrect Amount). Once submitted, a strict **45-day Regulatory Resolution SLA timer** starts. Alerts must trigger at **Day 35** (Warning) and **Day 42** (Critical Escalation)."
- "**BR-005 (Immutable Compliance Audit Trail)**: Every state transition, evidence upload, auto-credit, or analyst/supervisor decision must write an immutable audit log record with `actor_id`, `role`, `timestamp_utc`, `previous_state`, `new_state`, and `reason_code`."

### David Kim (Lead Backend Developer) & Priya Nair (QA Manager)
- **Dev & QA Alignment Request**:
  - "Our biggest pain point is vague user stories. We need every User Story to serve as the **single source of truth between Development and Testing**."
  - "Please use the standard Wikipedia User Story structure:
    1. **Card**: Connextra format (`As a <role>, I want <goal>, so that <benefit>`), Story ID (`US-101`..), Epic link (`EPIC-01`..), MoSCoW Priority, and Story Point estimate.
    2. **Conversation (For Dev)**: Exact field names, data types, boundary math (`<= 60 days`, `<= $25.00`, `> $500.00`, `<= 10 MB`), API status codes, and state transitions.
    3. **Confirmation (For QA)**: Explicit `Given / When / Then` BDD scenarios with Test Case IDs (`TC-101-01`, `TC-101-02`, etc.) covering happy paths, exact boundary edges, and negative rejection cases.
    4. **INVEST Checklist**, **Definition of Ready (DoR)**, **Definition of Done (DoD)**, **Requirements Traceability Matrix (RTM)**, and **Mermaid Workflows** (`WORKFLOWS_AND_DELIVERY_DOCS.md`)."
