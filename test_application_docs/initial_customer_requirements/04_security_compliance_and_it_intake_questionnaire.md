# Initial Customer Submission 04: Security, Compliance & IT Intake Questionnaire

**Submitted By**: Vikram Patel, Head of Application Security & Compliance  
**Submitted To**: Alex Mercer, Lead Technical Business Analyst (TBA)  
**Date Submitted**: November 13, 2026 *(Prior to Discovery Workshops 1–5)*  
**Subject**: Mandatory Security, Privacy, Audit & Infrastructure Requirements for FocusFlow  
**Document Reference**: `CUST-REQ-04`  

---

## 1. Security & Access Control Baseline

Alex, please ensure the following security and compliance controls are embedded into the functional requirements, Non-Functional Requirements (NFRs), and Acceptance Criteria for the Development and QA teams:

1. **Authentication & Credential Hygiene**:
   - All endpoints (except `/auth/register`, `/auth/login`, and `/health`) must require a valid bearer JWT access token.
   - Passwords must be hashed using **Argon2id** (or bcrypt with cost factor `>= 12`).
   - Short-lived Access Tokens (`15 minutes`) paired with rotation-enabled Refresh Tokens.

2. **Strict Tenant & Shared-List Authorization (RBAC)**:
   - Every database query for tasks, subtasks, lists, tags, and comments must enforce row-level ownership or shared-list membership checks.
   - A user attempting to read or mutate a task in a list where they are not the `OWNER`, `EDITOR`, or `VIEWER` must receive `HTTP 403 Forbidden` (or `HTTP 404` to prevent resource enumeration).
   - Shared list roles (`OWNER`, `EDITOR`, `VIEWER`) must be enforced on every API mutation endpoint:
     - `VIEWER`: Strictly read-only (`GET` only).
     - `EDITOR`: Can create/update/complete tasks and comments, but **cannot** delete the shared list, modify list membership, or permanently purge the Trash.
     - `OWNER`: Full administrative control over the list.

3. **Input Validation & XSS Prevention**:
   - Since task `description` and `comments` accept Markdown text, all inputs must be sanitized against Stored Cross-Site Scripting (XSS)—stripping `<script>`, `<iframe>`, `object`, `embed`, and inline `on*` JavaScript event handlers before storage and rendering.
   - Enforce strict payload size limits on all string fields, array counts (subtasks, tags, collaborators), and file imports (`<= 5 MB` for CSV/JSON import).

4. **API Rate Limiting & Abuse Protection**:
   - Authentication endpoints (`/auth/login`, `/auth/register`): Max **10 requests per minute per IP**.
   - Authenticated API endpoints: Max **120 requests per minute per `user_id`**.
   - Exceeding limits must return `HTTP 429 Too Many Requests` with a `Retry-After` header.

---

## 2. Auditability, Data Retention & GDPR Privacy

1. **Immutable Task Activity Audit Log**:
   - For enterprise operational accountability, every task creation, status transition (especially `BLOCKED` and `COMPLETED`), priority change, assignee change, and soft-delete/restore action must write an append-only audit event recording:
     - `actor_id`, `task_id`, `event_type`, `field_changed`, `old_value`, `new_value`, and `timestamp_utc`.
   - Application users must have **no endpoint or permission** to edit or delete individual audit history entries.

2. **Trash Retention & Automated Purge**:
   - Soft-deleted tasks in Trash must be retained for **30 calendar days** to allow user self-recovery, after which an automated daily purge job permanently deletes them.

3. **GDPR Data Portability & Right to Erasure**:
   - Users must be able to export all of their personal data and tasks in machine-readable `JSON` and `CSV` formats at any time.
   - Users must be able to request full account deletion (**"Delete My Account"**), which permanently erases their profile, owned lists, tasks, and comments within 24 hours.

---

## 3. Performance & Availability SLAs

- **API Mutation Latency**: Creating a task or toggling task status must complete in **`< 100 ms` (p95)**.
- **Search & Smart View Query Latency**: Filtering or searching across a user workspace of up to 10,000 tasks must complete in **`< 150 ms` (p95)**.
- **Offline Tolerance**: Client applications must queue task creations and status toggles locally when offline and synchronize without data loss upon reconnection.
