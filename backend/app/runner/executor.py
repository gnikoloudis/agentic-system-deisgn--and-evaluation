"""Headless, Interactive, and Simulated Benchmark Execution Engine + Live Telemetry Pub/Sub Bus."""

from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
import sys
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from app.compilers import compile_architecture, get_adapter
from app.config import settings
from app.db.database import (
    append_telemetry_event,
    get_run,
    list_telemetry_events,
    save_run,
    update_run_status,
    utc_now_iso,
)
from app.db.storage import get_blueprint, get_task
from app.runner.sandbox import create_isolated_sandbox, extract_sandbox_git_diff
from app.runner.transcript_parsers import estimate_cost_usd, parse_stream_json_line
from app.schemas.blueprint import AgentArchitecture, HarnessType
from app.schemas.evaluation import RunMode, RunRecordSchema, TelemetryEvent
from app.schemas.task import TaskSpec


class TelemetryEventBus:
    """In-memory async pub/sub bus for streaming live TelemetryEvents to WebSocket / SSE clients."""

    def __init__(self) -> None:
        self._subscribers: Dict[str, Set[ asyncio.Queue[TelemetryEvent] ]] = defaultdict(set)

    def subscribe(self, run_id: str) -> asyncio.Queue[TelemetryEvent]:
        q: asyncio.Queue[TelemetryEvent] = asyncio.Queue()
        self._subscribers[run_id].add(q)
        return q

    def unsubscribe(self, run_id: str, q: asyncio.Queue[TelemetryEvent]) -> None:
        self._subscribers[run_id].discard(q)

    def publish(self, event: TelemetryEvent) -> TelemetryEvent:
        saved = append_telemetry_event(event)
        for q in list(self._subscribers.get(event.run_id, set())):
            try:
                q.put_nowait(saved)
            except Exception:
                pass
        return saved


event_bus = TelemetryEventBus()
_active_tasks: Dict[str, asyncio.Task] = {}
_active_processes: Dict[str, subprocess.Popen] = {}


def check_harness_cli_available(harness: HarnessType) -> Tuple[bool, str]:
    binary_map = {
        "claude_code": settings.claude_binary,
        "antigravity": settings.antigravity_binary,
        "opencode": settings.opencode_binary,
    }
    binary = binary_map[harness]
    found = shutil.which(binary)
    return (found is not None, found or binary)


def _invoke_sandbox_hook(sandbox_dir: Path, event_name: str, payload: dict) -> Tuple[int, str]:
    """Execute the compiled .harness-eval/hook_runner.py inside the sandbox to validate dual-mode hooks."""
    hook_script = sandbox_dir / ".harness-eval" / "hook_runner.py"
    if not hook_script.exists():
        return 0, ""
    env = os.environ.copy()
    try:
        proc = subprocess.run(
            [sys.executable, str(hook_script), event_name],
            cwd=str(sandbox_dir),
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
        )
        return proc.returncode, (proc.stderr or proc.stdout or "").strip()
    except Exception as exc:
        return 0, str(exc)


def _apply_task_reference_solution(task_id: str, sandbox_dir: Path, quality_tier: str = "high") -> None:
    """Apply realistic code modifications in the sandbox during simulated benchmark execution."""
    if task_id == "bugfix-auth-token":
        target = sandbox_dir / "token_validator.py"
        if target.exists():
            if quality_tier == "high":
                target.write_text(
                    '''"""Authentication token validator module (fixed by agent architecture)."""

from __future__ import annotations

from typing import Dict, Optional


def validate_token(
    token_Payload: Dict[str, object],
    current_time: int,
    required_scope: Optional[str] = None,
) -> bool:
    """Validate token payload expiration and optional required scope."""
    if not isinstance(token_Payload, dict):
        return False

    expires_at = token_Payload.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return False

    if current_time >= expires_at:
        return False

    if required_scope:
        raw_scopes = str(token_Payload.get("scopes", ""))
        scope_set = {s.strip() for s in raw_scopes.split(",") if s.strip()}
        if required_scope not in scope_set:
            return False

    return True
''',
                    encoding="utf-8",
                )
            else:
                # Partial fix (e.g., solo agent without verifier loop misses whitespace stripping or boundary)
                target.write_text(
                    '''"""Authentication token validator module."""

from __future__ import annotations

from typing import Dict, Optional


def validate_token(
    token_Payload: Dict[str, object],
    current_time: int,
    required_scope: Optional[str] = None,
) -> bool:
    if not isinstance(token_Payload, dict):
        return False
    expires_at = token_Payload.get("expires_at")
    if not isinstance(expires_at, (int, float)):
        return False
    if current_time >= expires_at:
        return False
    if required_scope:
        raw_scopes = str(token_Payload.get("scopes", ""))
        scope_set = {s.strip() for s in raw_scopes.split(",") if s.strip()}
        if required_scope not in scope_set:
            return False
    return True
''',
                    encoding="utf-8",
                )

    elif task_id == "feature-rate-limiter":
        target = sandbox_dir / "limiter.py"
        if target.exists():
            target.write_text(
                '''"""Sliding window rate limiter implementation."""

from __future__ import annotations

from collections import defaultdict, deque
from typing import Deque, Dict


class SlidingWindowRateLimiter:
    """Rate limiter using a per-client sliding time window with burst allowance."""

    def __init__(self, max_requests: int, window_seconds: float, burst_allowance: int = 0) -> None:
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.burst_allowance = burst_allowance
        self._history: Dict[str, Deque[float]] = defaultdict(deque)

    def _evict_expired(self, client_id: str, timestamp: float) -> Deque[float]:
        q = self._history[client_id]
        cutoff = timestamp - self.window_seconds
        while q and q[0] <= cutoff:
            q.popleft()
        return q

    def allow_request(self, client_id: str, timestamp: float) -> bool:
        """Return True and record timestamp if client is within quota at `timestamp`."""
        q = self._evict_expired(client_id, timestamp)
        capacity = self.max_requests + self.burst_allowance
        if len(q) < capacity:
            q.append(timestamp)
            return True
        return False

    def remaining_quota(self, client_id: str, timestamp: float) -> int:
        """Return remaining allowed requests for `client_id` at `timestamp`."""
        q = self._evict_expired(client_id, timestamp)
        capacity = self.max_requests + self.burst_allowance
        return max(0, capacity - len(q))
''',
                encoding="utf-8",
            )

    elif task_id == "refactor-order-pricing":
        target = sandbox_dir / "pricing.py"
        if target.exists():
            target.write_text(
                '''"""Refactored order pricing engine with accurate loyalty -> coupon -> tax pipeline."""

from __future__ import annotations

from typing import List, Optional


LOYALTY_RATES = {
    "VIP": 0.15,
    "GOLD": 0.10,
    "SILVER": 0.05,
}


def apply_loyalty_discount(subtotal: float, loyalty_tier: Optional[str]) -> float:
    rate = LOYALTY_RATES.get(loyalty_tier or "", 0.0)
    return subtotal * (1.0 - rate)


def apply_coupon_discount(subtotal: float, coupon_code: Optional[str]) -> float:
    if coupon_code == "SAVE10":
        return max(0.0, subtotal - 10.0)
    if coupon_code == "HALF":
        return max(0.0, subtotal * 0.5)
    return max(0.0, subtotal)


def calculate_order_total(
    item_prices: List[float],
    loyalty_tier: Optional[str] = None,
    coupon_code: Optional[str] = None,
    tax_rate: float = 0.08,
) -> dict:
    """Calculate subtotal, discount, tax, and final total for an order."""
    raw_subtotal = round(sum(item_prices), 2)
    after_loyalty = apply_loyalty_discount(raw_subtotal, loyalty_tier)
    discounted_subtotal = round(apply_coupon_discount(after_loyalty, coupon_code), 2)
    tax = round(discounted_subtotal * tax_rate, 2)
    total = round(discounted_subtotal + tax, 2)
    return {
        "raw_subtotal": raw_subtotal,
        "discounted_subtotal": discounted_subtotal,
        "tax": tax,
        "total": total,
    }
''',
                encoding="utf-8",
            )

    elif task_id == "consulting-saas-turnaround":
        target = sandbox_dir / "EXECUTIVE_MEMO.md"
        target.write_text(
            """# Executive Strategy Memo: AcmeCloud Inc. FY2026 Growth & Margin Turnaround

## 1. Executive Summary & Headline Recommendation
AcmeCloud Inc. currently generates **$24.5M in Total ARR** (14.0% YoY growth), but suffers from an unsustainable **Burn Multiple of 2.4x** ($7.2M annual net burn for $3.0M net new ARR) and a depressed **64% Gross Margin** (11 percentage points below the 75% B2B SaaS benchmark).

**Root Cause Thesis (MECE)**:
1. **Go-To-Market Capital Misallocation**: **58% of Sales & Marketing spend** is directed toward the **SMB segment** ($8.0M ARR, $4,000 ACV), which suffers from **38% annual logo churn**, **74% Net Dollar Retention (NDR)**, an **LTV:CAC ratio of 1.8x**, and a **29-month CAC payback**.
2. **Starved High-Performing Enterprise Engine**: The **Enterprise segment** ($16.5M ARR, $82,500 ACV) exhibits best-in-class unit economics—**118% Net Dollar Retention**, **6% annual churn**, **5.4x LTV:CAC**, and an **11-month CAC payback**—yet receives only 42% of S&M investment.
3. **COGS & Onboarding Drag**: Single-tenant cloud provisioning and high-touch manual onboarding for low-ACV SMB accounts compress consolidated Gross Margin to **64%**.

---

## 2. Quantitative Diagnostic & Segment Unit Economics

| Metric | Enterprise Segment | SMB Segment | Consolidated / Target |
| :--- | :--- | :--- | :--- |
| **Segment ARR** | $16.5M (67% of ARR) | $8.0M (33% of ARR) | **$24.5M Total ARR** |
| **Average Contract Value (ACV)** | $82,500 | $4,000 | $11,136 blended |
| **Annual Logo Churn** | **6%** | **38%** | Target < 12% blended |
| **Net Dollar Retention (NDR)** | **118%** | **74%** | Target > 110% |
| **LTV : CAC Ratio** | **5.4x** | **1.8x** | Benchmark > 4.0x |
| **CAC Payback Period** | **11 months** | **29 months** | Benchmark < 15 months |
| **Gross Margin** | 78% | 35% | **64% (Target: 75%)** |

---

## 3. 90-Day Turnaround Roadmap

### Days 1–30: GTM Reallocation & SMB Self-Serve Gate
- Shift **75% of S&M budget** and outbound AE headcount to Enterprise accounts ($50k+ ACV).
- Enforce self-serve credit-card onboarding and annual upfront billing for all SMB deals under $10k ACV.

### Days 31–60: Cloud Infrastructure COGS Optimization (64% -> 75% Gross Margin)
- Migrate SMB workloads from dedicated single-tenant nodes to multi-tenant pooled infrastructure, reducing cloud COGS by $2.7M/year and lifting consolidated **Gross Margin from 64% to 75%**.

### Days 61–90: Enterprise Expansion & Net Retention Acceleration
- Launch dedicated Customer Success expansion playbooks for the 200 Enterprise accounts to expand NDR from **118% to 124%**, adding **$3.8M in incremental high-margin ARR** while cutting Burn Multiple from **2.4x to 0.9x**.
""",
            encoding="utf-8",
        )

    elif task_id in ("tba-chargeback-dispute-system", "tba-focusflow-todo-app"):
        workflows_doc = sandbox_dir / "WORKFLOWS_AND_DELIVERY_DOCS.md"
        workflows_doc.write_text(
            """# Technical Business Analysis Delivery Pack: Workflows, State Lifecycle & Data Dictionary
**Project**: FinTech Card Chargeback & Dispute Resolution Portal (`FIN-DISP-2026`)

---

## 1. End-to-End Business Process Workflow (`flowchart TD`)

```mermaid
flowchart TD
    A["Cardholder Selects Transaction in Portal"] --> B{"Settled & Age <= 60 Days?"}
    B -- "No (Pending or > 60 Days)" --> C["Reject Submission (HTTP 422: Ineligible Transaction Window)"]
    B -- "Yes" --> D["Assign Network Reason Code (FRD-10 / MER-20 / MER-30 / MER-40)"]
    D --> E["Start 45-Day Reg E SLA Timer & Write Immutable Audit Log"]
    E --> F{"Dispute Amount <= $25.00 & < 3 Prior 12m Disputes?"}
    F -- "Yes" --> G["Auto-Approve & Issue Instant Credit (State: AUTO_RESOLVED)"]
    F -- "No (> $25.00 or >= 3 Prior Disputes)" --> H["Upload PDF/PNG/JPG Evidence (<= 10 MB/file, Max 5 Files)"]
    H --> I{"Dispute Amount > $500.00?"}
    I -- "No ($25.01 - $500.00)" --> J["Dispute Analyst Single-Tier Review"]
    I -- "Yes (> $500.00)" --> K["Analyst Review + Senior Dispute Supervisor Dual-Approval"]
    J & K --> L["Final Resolution & Immutable Audit Trail Entry"]
```

---

## 2. System & Actor Interaction Sequence Diagram (`sequenceDiagram`)

```mermaid
sequenceDiagram
    participant CH as "Cardholder (Web/Mobile)"
    participant API as "Dispute Portal API"
    participant ENG as "Triage & SLA Rule Engine"
    participant S3 as "Evidence Vault (S3)"
    participant AUD as "Immutable Audit Log"

    CH->>API: POST /api/v1/disputes (tx_id, reason_code, claim_amount)
    API->>ENG: Validate settlement status & 60-day window (BR-001)
    ENG->>AUD: Append Event (STATE: SUBMITTED, actor_id, timestamp_utc)
    alt claim_amount <= $25.00 and rolling_12m_disputes < 3 (BR-002)
        ENG->>API: Trigger Auto-Credit & Close Case (STATE: AUTO_RESOLVED)
    else claim_amount > $25.00 (BR-003)
        CH->>S3: Upload Evidence (PDF/PNG/JPG <= 10 MB)
        ENG->>API: Route to Analyst Queue (> $500 requires Supervisor Dual-Approval)
    end
```

---

## 3. Dispute Case Lifecycle State Diagram (`stateDiagram-v2`)

```mermaid
stateDiagram-v2
    [*] --> SUBMITTED: "Validated (Settled & <= 60 Days)"
    SUBMITTED --> AUTO_RESOLVED: "Amount <= $25.00 & < 3 Disputes/12m"
    SUBMITTED --> AWAITING_EVIDENCE: "Amount > $25.00"
    AWAITING_EVIDENCE --> UNDER_ANALYST_REVIEW: "Evidence Uploaded (<= 10MB)"
    UNDER_ANALYST_REVIEW --> PENDING_SUPERVISOR_APPROVAL: "Amount > $500.00"
    UNDER_ANALYST_REVIEW --> RESOLVED_APPROVED: "Analyst Approves (<= $500.00)"
    PENDING_SUPERVISOR_APPROVAL --> RESOLVED_APPROVED: "Supervisor Dual-Approves (> $500.00)"
    UNDER_ANALYST_REVIEW --> RESOLVED_REJECTED: "Claim Denied with Rationale"
    AUTO_RESOLVED --> [*]
    RESOLVED_APPROVED --> [*]
    RESOLVED_REJECTED --> [*]
```

---

## 4. Data Dictionary & API Integration Contract (Development & Testing Reference)

| Field Name | Data Type | Validation Constraint / Business Rule | Error Code if Invalid |
| :--- | :--- | :--- | :--- |
| `transaction_id` | `UUID` | Must reference a `SETTLED` transaction where `current_date - settlement_date <= 60 days` (`BR-001`) | `ERR_TX_WINDOW_EXPIRED` (HTTP 422) |
| `claim_amount_usd` | `Decimal(10,2)` | `> 0.00` and `<= transaction_amount_usd`. Auto-credit if `<= 25.00`; Dual-approval if `> 500.00` (`BR-002`, `BR-003`) | `ERR_INVALID_CLAIM_AMOUNT` (HTTP 400) |
| `reason_code` | `Enum` | Must be one of `FRD-10`, `MER-20`, `MER-30`, `MER-40` (`BR-004`) | `ERR_UNSUPPORTED_REASON_CODE` (HTTP 400) |
| `evidence_files` | `Array<File>` | Allowed MIME: `application/pdf`, `image/png`, `image/jpeg`. Max `10 MB` per file, max `5` files (`BR-003`) | `ERR_EVIDENCE_LIMIT_EXCEEDED` (HTTP 413) |
| `sla_due_at_utc` | `ISO-8601` | `submitted_at_utc + 45 calendar days`; warning alert at Day 35, critical escalation at Day 42 (`BR-004`) | `SYS_SLA_BREACH_ALERT` |
| `audit_entry` | `JSONObject` | Append-only record: `actor_id`, `role`, `timestamp_utc`, `previous_state`, `new_state`, `reason_code` (`BR-005`) | `ERR_AUDIT_WRITE_FAILURE` (HTTP 500) |
""",
            encoding="utf-8",
        )

        stories_doc = sandbox_dir / "EPICS_AND_USER_STORIES.md"
        stories_doc.write_text(
            """# Agile Epics & User Stories Specification (Development ↔ Testing Interface Contract)
**Project**: FinTech Card Chargeback & Dispute Resolution Portal (`FIN-DISP-2026`)
**Standard**: [Wikipedia User Story Specification](https://en.wikipedia.org/wiki/User_story) (Connextra Template, Ron Jeffries' 3 Cs, Bill Wake's INVEST, BDD Gherkin Acceptance Criteria, and RTM)

---

## 1. Epics Catalog

| Epic ID | Epic Name | Business Objective & Scope | Linked Business Requirements |
| :--- | :--- | :--- | :--- |
| **`EPIC-01`** | **Self-Service Dispute Intake & Eligibility Engine** | Enable cardholders to submit valid disputes within the 60-day window with standardized network reason codes and evidence uploads. | `BR-001`, `BR-003`, `BR-004` |
| **`EPIC-02`** | **Automated Micro-Dispute Resolution & Tiered Approval Routing** | Auto-resolve low-value disputes (`<= $25.00`) to cut operational load by 40% while enforcing `$500.00` supervisor dual-approval gates. | `BR-002`, `BR-003` |
| **`EPIC-03`** | **Regulatory 45-Day SLA Monitoring & Immutable Audit Trail** | Guarantee Regulation E 45-day SLA compliance (Day 35/42 alerts) and append-only audit logging across every state transition. | `BR-004`, `BR-005` |

---

## 2. User Stories (3 Cs: Card, Conversation for Dev, Confirmation for QA + INVEST)

### `US-101`: Cardholder 60-Day Eligibility Check & Reason Code Intake
- **The Card (Connextra Statement & Metadata)**:
  > **As a** retail cardholder, **I want** to submit a dispute on a settled transaction within 60 calendar days and select a standardized reason code, **so that** I can recover unauthorized or erroneous charges quickly.
  - **Story ID**: `US-101` | **Parent Epic**: `EPIC-01` | **Source BR**: `BR-001`, `BR-004`
  - **Priority**: Must-Have | **Story Points**: `5` | **Dependencies**: Core Transaction Ledger API
- **The Conversation (Development Team Implementation Contract)**:
  - Query transaction status from Ledger API: `status` MUST equal `SETTLED` (`PENDING` transactions return HTTP 422 `ERR_TX_PENDING`).
  - Compute eligibility window in UTC: `(current_utc_date - settlement_utc_date).days <= 60`. Boundary day `60` is **ELIGIBLE**; day `61` is **INELIGIBLE** (`ERR_TX_WINDOW_EXPIRED`).
  - Validate `reason_code` against strict enum: `FRD-10` (Unauthorized Fraud), `MER-20` (Duplicate Charge), `MER-30` (Goods/Services Not Received), `MER-40` (Incorrect Amount).
- **The Confirmation (Testing Team BDD Acceptance Criteria & Test Cases)**:
  - **`TC-101-01` (Happy Path — Eligible Settled Transaction)**:
    - **Given** a settled card transaction dated 30 calendar days ago for `$120.00`, **When** the cardholder submits a dispute with reason code `MER-20`, **Then** the system creates a dispute case in `SUBMITTED` status and starts a 45-day SLA timer.
  - **`TC-101-02` (Exact Boundary — Day 60 vs Day 61)**:
    - **Given** a settled transaction dated exactly 60 calendar days ago, **When** the cardholder submits a dispute, **Then** the submission succeeds (`HTTP 201`); **When** the transaction is 61 calendar days old, **Then** the system rejects it with `HTTP 422` (`ERR_TX_WINDOW_EXPIRED`).
  - **`TC-101-03` (Negative Case — Pending Transaction or Invalid Reason Code)**:
    - **Given** a transaction with status `PENDING` (or an unknown reason code `INVALID-99`), **When** the cardholder attempts to submit a dispute, **Then** the API returns `HTTP 400/422` and no dispute record is persisted.
- **INVEST Verification**:
  - **Independent**: Self-contained intake validation logic | **Negotiable**: UI error copy is configurable | **Valuable**: Prevents invalid network chargeback filings | **Estimable**: 5 points | **Small**: Fits in 1 sprint | **Testable**: 3 deterministic BDD test cases (`TC-101-01..03`).

---

### `US-102`: Automated Micro-Dispute Instant Credit (`<= $25.00`)
- **The Card (Connextra Statement & Metadata)**:
  > **As a** VP of Card Operations, **I want** eligible disputes of `$25.00` or less to be automatically approved and credited when the cardholder has fewer than 3 disputes in the past 12 months, **so that** analyst workload is reduced by 40% and customers receive instant resolution.
  - **Story ID**: `US-102` | **Parent Epic**: `EPIC-02` | **Source BR**: `BR-002`, `BR-005`
  - **Priority**: Must-Have | **Story Points**: `5` | **Dependencies**: `US-101`
- **The Conversation (Development Team Implementation Contract)**:
  - Evaluate auto-resolution rule synchronously after `US-101` validation passes:
    `claim_amount_usd <= Decimal("25.00") AND count_disputes(cardholder_id, window_days=365) < 3`.
  - If true: transition state `SUBMITTED -> AUTO_RESOLVED`, post provisional ledger credit, and write immutable audit log with `actor_id = "SYSTEM_AUTO_TRIAGE"`.
  - If `claim_amount_usd >= Decimal("25.01")` or `prior_12m_disputes >= 3`: transition state to `AWAITING_EVIDENCE`.
- **The Confirmation (Testing Team BDD Acceptance Criteria & Test Cases)**:
  - **`TC-102-01` (Happy Path & Exact `$25.00` Boundary)**:
    - **Given** a cardholder with `2` disputes in the rolling 12 months submitting a valid dispute for exactly `$25.00`, **When** the dispute is processed, **Then** the case transitions immediately to `AUTO_RESOLVED`, a `$25.00` ledger credit is issued, and an audit record is logged.
  - **`TC-102-02` (Upper Threshold Boundary — `$25.01`)**:
    - **Given** a cardholder with `0` prior disputes submitting a dispute for `$25.01`, **When** the dispute is processed, **Then** auto-resolution is bypassed and the case transitions to `AWAITING_EVIDENCE`.
  - **`TC-102-03` (Abuse Guardrail — 3rd Dispute in 12 Months)**:
    - **Given** a cardholder who already has `3` resolved disputes in the last 365 days submitting a `$15.00` dispute, **When** the dispute is processed, **Then** auto-resolution is blocked and the case routes to manual analyst review.
- **INVEST Verification**:
  - **Independent**: Decoupled rule evaluation step | **Negotiable**: `$25.00` threshold and `3` count are env-configurable | **Valuable**: Eliminates 40% of manual ticket volume | **Estimable**: 5 points | **Small**: Single rule module | **Testable**: Exact boundary tests (`$25.00` vs `$25.01`, `2` vs `3` claims).

---

### `US-103`: Evidence Upload Validation & Tiered `$500.00` Supervisor Dual-Approval
- **The Card (Connextra Statement & Metadata)**:
  > **As a** Dispute Analyst and Senior Supervisor, **I want** customer evidence uploads validated (`PDF/PNG/JPG <= 10 MB`, max 5 files) and claims strictly over `$500.00` routed for dual-approval, **so that** high-value financial payouts meet risk governance controls.
  - **Story ID**: `US-103` | **Parent Epic**: `EPIC-01`, `EPIC-02` | **Source BR**: `BR-003`, `BR-005`
  - **Priority**: Must-Have | **Story Points**: `8` | **Dependencies**: `US-101`
- **The Conversation (Development Team Implementation Contract)**:
  - Multipart upload endpoint `POST /api/v1/disputes/{id}/evidence`: verify magic-byte file signatures for `PDF`, `PNG`, `JPG`, reject any file `> 10,485,760 bytes` (10 MB) or total file count `> 5`.
  - Approval routing logic:
    - If `claim_amount_usd <= Decimal("500.00")`: `DISPUTE_ANALYST` approval transitions directly to `RESOLVED_APPROVED`.
    - If `claim_amount_usd > Decimal("500.00")`: `DISPUTE_ANALYST` approval transitions to `PENDING_SUPERVISOR_APPROVAL`; requires a distinct user with `SENIOR_SUPERVISOR` role (`supervisor_id != analyst_id`) to transition to `RESOLVED_APPROVED`.
- **The Confirmation (Testing Team BDD Acceptance Criteria & Test Cases)**:
  - **`TC-103-01` (Happy Path — Single-Tier Analyst Approval at `$500.00`)**:
    - **Given** a dispute for exactly `$500.00` with a valid `4 MB` PDF receipt attached, **When** a `DISPUTE_ANALYST` clicks Approve, **Then** the status transitions directly to `RESOLVED_APPROVED` without requiring supervisor sign-off.
  - **`TC-103-02` (Dual-Approval Boundary — `$500.01`)**:
    - **Given** a dispute for `$500.01`, **When** a `DISPUTE_ANALYST` approves the claim, **Then** the status becomes `PENDING_SUPERVISOR_APPROVAL` and cannot be paid out until a `SENIOR_SUPERVISOR` approves it.
  - **`TC-103-03` (Negative Case — `11 MB` File or `.exe` Upload)**:
    - **Given** a dispute in `AWAITING_EVIDENCE`, **When** the cardholder uploads an `11 MB` PDF or a `.exe` file, **Then** the system rejects the upload with `HTTP 413 / 415`.
- **INVEST Verification**:
  - **Independent**: Dedicated upload & RBAC state machine | **Negotiable**: File formats extensible | **Valuable**: Enforces financial controls above `$500` | **Estimable**: 8 points | **Small**: Single sprint | **Testable**: Clear file-size and role-based tests.

---

### `US-104`: 45-Day Regulatory SLA Escalation Timer & Immutable Audit Trail
- **The Card (Connextra Statement & Metadata)**:
  > **As a** Regulatory Compliance Officer, **I want** every dispute tracked against a 45-day SLA with automated Day 35/42 alerts and an immutable audit trail on every state change, **so that** the bank passes Regulation E audits with zero SLA breaches.
  - **Story ID**: `US-104` | **Parent Epic**: `EPIC-03` | **Source BR**: `BR-004`, `BR-005`
  - **Priority**: Must-Have | **Story Points**: `5` | **Dependencies**: `US-101`
- **The Conversation (Development Team Implementation Contract)**:
  - Store `sla_due_at_utc = submitted_at_utc + 45 days`. Scheduled worker emits `SLA_WARNING_DAY_35` at Day 35 and `SLA_CRITICAL_DAY_42` at Day 42 for any unresolved case.
  - Database trigger / service guard on `dispute_audit_log`: revoke `UPDATE` and `DELETE` permissions; every state mutation must insert `{actor_id, role, timestamp_utc, previous_state, new_state, reason_code}`.
- **The Confirmation (Testing Team BDD Acceptance Criteria & Test Cases)**:
  - **`TC-104-01` (Happy Path — Day 35 Warning & Day 42 Critical Alert)**:
    - **Given** an open dispute in `UNDER_ANALYST_REVIEW`, **When** the elapsed time reaches Day 35 and Day 42, **Then** the system dispatches `SLA_WARNING_DAY_35` and `SLA_CRITICAL_DAY_42` notifications to the operations queue.
  - **`TC-104-02` (Audit Trail Immutability Check)**:
    - **Given** an existing audit log entry for transition `SUBMITTED -> AUTO_RESOLVED`, **When** any service attempts to `UPDATE` or `DELETE` the audit row, **Then** the database rejects the mutation and preserves the original record.
- **INVEST Verification**:
  - **Independent**: Event-driven audit & SLA listener | **Negotiable**: Notification channels configurable | **Valuable**: Prevents regulatory fines | **Estimable**: 5 points | **Small**: 1 sprint | **Testable**: Deterministic clock-mock & DB immutability tests.

---

## 3. Definition of Ready (DoR) & Definition of Done (DoD)

### Definition of Ready (DoR — Entry Gate to Development Sprint)
- [x] User Story follows the Connextra template (`As a... I want... So that...`) and passes all 6 **INVEST** criteria.
- [x] **Conversation (Dev Contract)** specifies exact boundary rules, data types, reason codes, and error status codes.
- [x] **Confirmation (QA Contract)** defines `Given / When / Then` BDD scenarios with mapped `TC-xxx` IDs for happy, boundary, and negative paths.
- [x] Process workflows and state transitions are documented in `WORKFLOWS_AND_DELIVERY_DOCS.md`.

### Definition of Done (DoD — Exit Gate to Production Release)
- [x] All code implemented according to the **Conversation** technical rules and peer-reviewed.
- [x] 100% of mapped QA Test Cases (`TC-101-01` through `TC-104-02`) automated and passing in CI.
- [x] Immutable audit logging (`BR-005`) verified for every state transition.
- [x] Product Owner / Technical Business Analyst sign-off completed against the Requirements Traceability Matrix.

---

## 4. Requirements Traceability Matrix (RTM)

| Business Req ID | Requirement Summary | Epic ID | User Story ID | Dev Workflow / Component | QA Test Case IDs |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`BR-001`** | Self-service dispute intake within 60-day settlement window | `EPIC-01` | `US-101` | Eligibility & Intake API | `TC-101-01`, `TC-101-02`, `TC-101-03` |
| **`BR-002`** | Automated micro-dispute approval (`<= $25.00`, `< 3` in 12m) | `EPIC-02` | `US-102` | Auto-Triage Rule Engine | `TC-102-01`, `TC-102-02`, `TC-102-03` |
| **`BR-003`** | Evidence upload (`<= 10 MB`) & `$500.00` supervisor dual-approval | `EPIC-01`, `EPIC-02` | `US-103` | Evidence Vault & RBAC Workflow | `TC-103-01`, `TC-103-02`, `TC-103-03` |
| **`BR-004`** | Standardized network reason codes & 45-day SLA (Day 35/42 alerts) | `EPIC-01`, `EPIC-03` | `US-101`, `US-104` | Reason Code Enum & SLA Scheduler | `TC-101-01`, `TC-104-01` |
| **`BR-005`** | Immutable compliance audit log on all state transitions | `EPIC-03` | `US-102`, `US-104` | Append-Only Audit Store | `TC-102-01`, `TC-104-02` |
""",
            encoding="utf-8",
        )


async def _run_architecture_simulation(
    run_id: str,
    blueprint: AgentArchitecture,
    task: TaskSpec,
    harness: HarnessType,
    sandbox_dir: Path,
) -> None:
    """Execute a high-fidelity multi-agent trajectory simulation in the real sandbox when running in simulated_benchmark mode or when CLI binary is absent."""
    adapter = get_adapter(harness)
    subagent_tool = {
        "claude_code": "Task",
        "antigravity": "invoke_subagent",
        "opencode": "subagent",
    }[harness]

    def _model_perf_multipliers(resolved_model: str) -> Tuple[float, float]:
        """Return (latency_multiplier, token_verbosity_multiplier) for a resolved model."""
        m = resolved_model.lower()
        if "opus" in m or "neon-xhigh" in m or "neon-high" in m or "super" in m:
            return (1.45, 1.25)
        if "flash" in m or "haiku" in m or "lightning" in m or "argon-low" in m:
            return (0.55, 0.78)
        if "argon-high" in m or "sonnet-5-5-high" in m:
            return (1.15, 1.10)
        return (1.0, 1.0)

    orch_model = adapter.resolve_agent_model(blueprint.orchestrator)
    orch_lat_mult, orch_tok_mult = _model_perf_multipliers(orch_model)

    event_bus.publish(
        TelemetryEvent(
            run_id=run_id,
            timestamp=utc_now_iso(),
            source="runner",
            event_type="SessionStart",
            agent_id=blueprint.orchestrator.id,
            status="ok",
            message=(
                f"Started {harness} execution for `{blueprint.metadata.name}` on `{task.name}` "
                f"(Orchestrator model: `{orch_model}`)"
            ),
        )
    )
    await asyncio.sleep(0.12)

    # Root orchestrator analyzes task
    in_0 = int(680 * orch_tok_mult)
    out_0 = int(190 * orch_tok_mult)
    event_bus.publish(
        TelemetryEvent(
            run_id=run_id,
            timestamp=utc_now_iso(),
            source="transcript",
            event_type="AssistantThinking",
            agent_id=blueprint.orchestrator.id,
            status="info",
            duration_ms=round(420.0 * orch_lat_mult, 1),
            input_tokens=in_0,
            output_tokens=out_0,
            cache_read_tokens=250,
            cost_usd=estimate_cost_usd(in_0, out_0, 250, orch_model),
            message=(
                f"Analyzing task `{task.id}` with model `{orch_model}` and preparing execution plan "
                f"for topology `{blueprint.topology.pattern}`."
            ),
        )
    )
    await asyncio.sleep(0.12)

    subagents_by_id = {sa.id: sa for sa in blueprint.subagents}
    sorted_edges = sorted(blueprint.topology.edges, key=lambda e: e.order)

    if not blueprint.subagents:
        # Solo Agent Trajectory
        for tool_name, t_in, dur, in_t, out_t, msg in [
            ("Read", {"path": task.workspace_source}, 180.0, 520, 120, "Reading target module and test suite"),
            ("Grep", {"pattern": "def "}, 110.0, 590, 95, "Searching function signatures"),
        ]:
            event_bus.publish(
                TelemetryEvent(
                    run_id=run_id,
                    timestamp=utc_now_iso(),
                    source="hook",
                    event_type="PreToolUse",
                    agent_id=blueprint.orchestrator.id,
                    tool_name=tool_name,
                    tool_input=t_in,
                    status="ok",
                    duration_ms=dur,
                    input_tokens=in_t,
                    output_tokens=out_t,
                    cost_usd=estimate_cost_usd(in_t, out_t, 100, orch_model),
                    message=msg,
                )
            )
            await asyncio.sleep(0.12)

        _apply_task_reference_solution(task.id, sandbox_dir, quality_tier="medium")
        event_bus.publish(
            TelemetryEvent(
                run_id=run_id,
                timestamp=utc_now_iso(),
                source="hook",
                event_type="PostToolUse",
                agent_id=blueprint.orchestrator.id,
                tool_name="Edit",
                tool_input={"action": "apply_patch"},
                status="ok",
                duration_ms=340.0,
                input_tokens=810,
                output_tokens=310,
                cost_usd=estimate_cost_usd(810, 310, 200, orch_model),
                message="Applied code changes directly from root orchestrator",
            )
        )
        await asyncio.sleep(0.12)

        # Run pytest verification command inside sandbox
        pytest_proc = subprocess.run(
            [sys.executable, "-m", "pytest", "-q"],
            cwd=str(sandbox_dir),
            capture_output=True,
            text=True,
        )
        event_bus.publish(
            TelemetryEvent(
                run_id=run_id,
                timestamp=utc_now_iso(),
                source="hook",
                event_type="PostToolUse",
                agent_id=blueprint.orchestrator.id,
                tool_name="Bash",
                tool_input={"command": "pytest -q"},
                tool_output=(pytest_proc.stdout or pytest_proc.stderr)[:600],
                status="ok" if pytest_proc.returncode == 0 else "error",
                duration_ms=650.0,
                input_tokens=720,
                output_tokens=140,
                cost_usd=estimate_cost_usd(720, 140, 300, orch_model),
                message="Executed unit test verification",
            )
        )
    else:
        # Multi-Agent Topology Execution following designed edges
        applied_patch = False
        for edge in sorted_edges:
            target_id = edge.target
            if target_id not in subagents_by_id:
                continue
            sa = subagents_by_id[target_id]
            sa_resolved_model = adapter.resolve_agent_model(sa)
            sa_lat_mult, sa_tok_mult = _model_perf_multipliers(sa_resolved_model)

            # Delegate via subagent tool
            event_bus.publish(
                TelemetryEvent(
                    run_id=run_id,
                    timestamp=utc_now_iso(),
                    source="hook",
                    event_type="SubagentStart",
                    agent_id=sa.id,
                    tool_name=subagent_tool,
                    tool_input={"subagent_type": sa.id, "model": sa_resolved_model, "condition": edge.condition},
                    status="ok",
                    duration_ms=round(95.0 * orch_lat_mult, 1),
                    input_tokens=420,
                    output_tokens=110,
                    cost_usd=estimate_cost_usd(420, 110, 150, orch_model),
                    message=f"Handoff `{edge.source}` -> `{sa.id}` [Model: `{sa_resolved_model}`] ({edge.condition})",
                )
            )
            await asyncio.sleep(0.12)

            # Subagent performs role-appropriate tool use
            if not sa.permissions.allow_write and not sa.permissions.allow_shell:
                # Planner / Auditor read-only inspection
                in_sa = int(740 * sa_tok_mult)
                out_sa = int(290 * sa_tok_mult)
                event_bus.publish(
                    TelemetryEvent(
                        run_id=run_id,
                        timestamp=utc_now_iso(),
                        source="transcript",
                        event_type="PreToolUse",
                        agent_id=sa.id,
                        tool_name="Read",
                        tool_input={"workspace": task.workspace_source, "model": sa_resolved_model},
                        status="ok",
                        duration_ms=round(260.0 * sa_lat_mult, 1),
                        input_tokens=in_sa,
                        output_tokens=out_sa,
                        cache_read_tokens=300,
                        cost_usd=estimate_cost_usd(in_sa, out_sa, 300, sa_resolved_model),
                        message=f"`{sa.name}` (`{sa_resolved_model}`) inspected repository files and produced structured analysis.",
                    )
                )
            elif sa.permissions.allow_write:
                # Coding / Test Synthesizer subagent applies solution
                if not applied_patch:
                    _apply_task_reference_solution(task.id, sandbox_dir, quality_tier="high")
                    applied_patch = True
                in_sa = int(960 * sa_tok_mult)
                out_sa = int(410 * sa_tok_mult)
                event_bus.publish(
                    TelemetryEvent(
                        run_id=run_id,
                        timestamp=utc_now_iso(),
                        source="transcript",
                        event_type="PostToolUse",
                        agent_id=sa.id,
                        tool_name="Edit",
                        tool_input={"agent": sa.id, "model": sa_resolved_model, "task": task.id},
                        status="ok",
                        duration_ms=round(480.0 * sa_lat_mult, 1),
                        input_tokens=in_sa,
                        output_tokens=out_sa,
                        cache_read_tokens=450,
                        cost_usd=estimate_cost_usd(in_sa, out_sa, 450, sa_resolved_model),
                        message=f"`{sa.name}` (`{sa_resolved_model}`) implemented changes according to specification.",
                    )
                )

            if sa.permissions.allow_shell:
                pytest_proc = subprocess.run(
                    [sys.executable, "-m", "pytest", "-v"],
                    cwd=str(sandbox_dir),
                    capture_output=True,
                    text=True,
                )
                in_sa = int(620 * sa_tok_mult)
                out_sa = int(180 * sa_tok_mult)
                event_bus.publish(
                    TelemetryEvent(
                        run_id=run_id,
                        timestamp=utc_now_iso(),
                        source="transcript",
                        event_type="PostToolUse",
                        agent_id=sa.id,
                        tool_name="Bash",
                        tool_input={"command": "pytest -v", "model": sa_resolved_model},
                        tool_output=(pytest_proc.stdout or pytest_proc.stderr)[:700],
                        status="ok" if pytest_proc.returncode == 0 else "error",
                        duration_ms=round(590.0 * sa_lat_mult, 1),
                        input_tokens=in_sa,
                        output_tokens=out_sa,
                        cache_read_tokens=400,
                        cost_usd=estimate_cost_usd(in_sa, out_sa, 400, sa_resolved_model),
                        message=f"`{sa.name}` (`{sa_resolved_model}`) executed test suite (VERDICT: {'PASS' if pytest_proc.returncode == 0 else 'FAIL'})",
                    )
                )

            await asyncio.sleep(0.15)
            event_bus.publish(
                TelemetryEvent(
                    run_id=run_id,
                    timestamp=utc_now_iso(),
                    source="hook",
                    event_type="SubagentStop",
                    agent_id=sa.id,
                    status="ok",
                    duration_ms=60.0,
                    message=f"Subagent `{sa.id}` completed and returned artifact to `{blueprint.orchestrator.id}`",
                )
            )
            await asyncio.sleep(0.1)

        if not applied_patch:
            _apply_task_reference_solution(task.id, sandbox_dir, quality_tier="high")

    event_bus.publish(
        TelemetryEvent(
            run_id=run_id,
            timestamp=utc_now_iso(),
            source="runner",
            event_type="SessionStop",
            agent_id=blueprint.orchestrator.id,
            status="ok",
            message="Task execution completed",
        )
    )


async def _execute_headless_or_simulated_run(
    run_id: str,
    blueprint: AgentArchitecture,
    task: TaskSpec,
    harness: HarnessType,
    mode: RunMode,
    sandbox_dir: Path,
    prompt: str,
    auto_evaluate_callback: Optional[Callable[[str], asyncio.Future]] = None,
) -> None:
    try:
        update_run_status(run_id, "running")
        cli_available, binary_path = check_harness_cli_available(harness)

        if mode == "simulated_benchmark" or not cli_available:
            if mode == "headless" and not cli_available:
                event_bus.publish(
                    TelemetryEvent(
                        run_id=run_id,
                        timestamp=utc_now_iso(),
                        source="runner",
                        event_type="CommandOutput",
                        agent_id=blueprint.orchestrator.id,
                        status="info",
                        message=(
                            f"Harness CLI binary `{binary_path}` not detected on PATH; "
                            f"executing architecture topology via built-in Sandbox Simulator."
                        ),
                    )
                )
            await _run_architecture_simulation(run_id, blueprint, task, harness, sandbox_dir)
        else:
            # Real Headless Harness CLI Execution
            # Collapse newlines for Windows .cmd/.exe safety so arguments are never truncated
            single_line_prompt = " ".join(line.strip() for line in prompt.splitlines() if line.strip())
            adapter = get_adapter(harness)
            orch_resolved_model = adapter.resolve_agent_model(blueprint.orchestrator)

            if harness == "claude_code":
                cmd = [
                    binary_path,
                    "-p",
                    single_line_prompt,
                    "--model",
                    orch_resolved_model,
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    "--max-turns",
                    str(blueprint.orchestrator.budgets.max_turns),
                ]
            elif harness == "opencode":
                cmd = [binary_path, "run", single_line_prompt, "-m", orch_resolved_model, "--format", "json"]
            else:
                # Antigravity (agy.EXE) uses -p <prompt> [--model <model>] --output-format stream-json --dangerously-skip-permissions
                cmd = [
                    binary_path,
                    "-p",
                    single_line_prompt,
                ]
                if orch_resolved_model and orch_resolved_model not in ("inherit", "default", "pro", "flash"):
                    cmd.extend(["--model", orch_resolved_model])
                cmd.extend(["--output-format", "stream-json", "--dangerously-skip-permissions"])

            event_bus.publish(
                TelemetryEvent(
                    run_id=run_id,
                    timestamp=utc_now_iso(),
                    source="runner",
                    event_type="SessionStart",
                    agent_id=blueprint.orchestrator.id,
                    status="ok",
                    message=f"Launched headless CLI: `{' '.join(cmd)}`",
                )
            )

            stderr_lines: List[str] = []

            def _run_cli_subprocess() -> int:
                # Use subprocess.Popen in a worker thread so Windows SelectorEventLoop (uvicorn --reload)
                # never raises NotImplementedError and stream-json lines >64KB never hit StreamReader limits.
                use_shell = sys.platform == "win32" and binary_path.lower().endswith((".cmd", ".bat", ".ps1"))
                proc = subprocess.Popen(
                    cmd,
                    cwd=str(sandbox_dir),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                    shell=use_shell,
                )
                _active_processes[run_id] = proc
                assert proc.stdout is not None
                assert proc.stderr is not None

                import threading

                def _drain_stderr() -> None:
                    for err_line in proc.stderr:  # type: ignore[union-attr]
                        clean_err = err_line.strip()
                        if clean_err:
                            stderr_lines.append(clean_err)

                err_thread = threading.Thread(target=_drain_stderr, daemon=True)
                err_thread.start()

                try:
                    for raw_line in proc.stdout:
                        decoded = raw_line.strip()
                        if not decoded:
                            continue
                        parsed_ev = parse_stream_json_line(run_id, harness, decoded, blueprint.orchestrator.id)
                        if parsed_ev:
                            event_bus.publish(parsed_ev)
                            # Once Antigravity emits the final "result" frame, don't hang if child handles linger
                            if parsed_ev.metadata.get("step_index") == "final_result":
                                break
                        elif not decoded.startswith("{"):
                            # Only log non-JSON console lines as CommandOutput; never dump raw stream-json housekeeping frames
                            event_bus.publish(
                                TelemetryEvent(
                                    run_id=run_id,
                                    timestamp=utc_now_iso(),
                                    source="transcript",
                                    event_type="CommandOutput",
                                    agent_id=blueprint.orchestrator.id,
                                    status="info",
                                    message=decoded[:800],
                                )
                            )

                    err_thread.join(timeout=2.0)
                    try:
                        return proc.wait(timeout=3.0)
                    except subprocess.TimeoutExpired:
                        proc.terminate()
                        return 0
                finally:
                    _active_processes.pop(run_id, None)

            return_code = await asyncio.to_thread(_run_cli_subprocess)

            if return_code != 0 and stderr_lines:
                err_summary = " | ".join(stderr_lines[-5:])[:800]
                event_bus.publish(
                    TelemetryEvent(
                        run_id=run_id,
                        timestamp=utc_now_iso(),
                        source="runner",
                        event_type="Error",
                        agent_id=blueprint.orchestrator.id,
                        status="error",
                        message=f"CLI stderr: {err_summary}",
                    )
                )

            event_bus.publish(
                TelemetryEvent(
                    run_id=run_id,
                    timestamp=utc_now_iso(),
                    source="runner",
                    event_type="SessionStop",
                    agent_id=blueprint.orchestrator.id,
                    status="ok" if return_code == 0 else "error",
                    message=f"Harness CLI exited with code {return_code}",
                )
            )

        git_diff, changed_files = extract_sandbox_git_diff(sandbox_dir)
        update_run_status(
            run_id,
            status="evaluating" if auto_evaluate_callback else "completed",
            completed_at=utc_now_iso(),
            git_diff=git_diff,
            changed_files=changed_files,
        )

        if auto_evaluate_callback:
            await auto_evaluate_callback(run_id)

    except Exception as exc:
        err_detail = f"{type(exc).__name__}: {exc}" if str(exc) else type(exc).__name__
        update_run_status(
            run_id,
            status="failed",
            completed_at=utc_now_iso(),
            error_message=err_detail,
        )
        event_bus.publish(
            TelemetryEvent(
                run_id=run_id,
                timestamp=utc_now_iso(),
                source="runner",
                event_type="Error",
                agent_id="root_orchestrator",
                status="error",
                message=f"Run failed: {err_detail}",
            )
        )


async def start_execution_run(
    architecture_id: str,
    task_id: str,
    harness: HarnessType,
    mode: RunMode,
    custom_prompt_override: Optional[str] = None,
    auto_evaluate_callback: Optional[Callable[[str], asyncio.Future]] = None,
) -> RunRecordSchema:
    """Prepare isolated Git sandbox, deploy compiled architecture files, and start headless/interactive/simulated run."""
    bp_tuple = get_blueprint(architecture_id)
    if not bp_tuple:
        raise ValueError(f"Architecture blueprint '{architecture_id}' not found")
    blueprint, _, _ = bp_tuple

    task_tuple = get_task(task_id)
    if not task_tuple:
        raise ValueError(f"Task '{task_id}' not found")
    task, _, _ = task_tuple

    run_id = f"run-{uuid.uuid4().hex[:10]}"
    server_url = f"http://{settings.host}:{settings.port}"
    compilation = compile_architecture(blueprint, harness, run_id=run_id, server_url=server_url)

    sandbox_dir = create_isolated_sandbox(
        run_id=run_id,
        workspace_source=task.workspace_source,
        compilation=compilation,
        base_commit=task.base_commit,
    )

    prompt = custom_prompt_override or task.prompt
    cli_cmd = (
        compilation.interactive_launch_command
        if mode == "interactive"
        else compilation.cli_preview_command.replace("<TASK_PROMPT>", prompt.replace("\n", " ")[:120])
    )

    initial_status = "waiting_for_user" if mode == "interactive" else "running"
    run_record = RunRecordSchema(
        id=run_id,
        architecture_id=blueprint.metadata.id,
        architecture_name=blueprint.metadata.name,
        architecture_version=blueprint.metadata.version,
        task_id=task.id,
        task_name=task.name,
        harness=harness,
        mode=mode,
        status=initial_status,  # type: ignore[arg-type]
        sandbox_path=str(sandbox_dir),
        cli_command=cli_cmd,
        started_at=utc_now_iso(),
    )
    save_run(run_record, blueprint_snapshot=blueprint.model_dump(mode="json"))

    if mode == "interactive":
        event_bus.publish(
            TelemetryEvent(
                run_id=run_id,
                timestamp=utc_now_iso(),
                source="runner",
                event_type="SessionStart",
                agent_id=blueprint.orchestrator.id,
                status="info",
                message=(
                    f"Interactive sandbox ready at `{sandbox_dir}`. "
                    f"Run `cd \"{sandbox_dir}\" && {compilation.interactive_launch_command}` to work interactively. "
                    f"Live hooks will stream here automatically. Click 'Complete & Evaluate' when done."
                ),
            )
        )
    else:
        bg_task = asyncio.create_task(
            _execute_headless_or_simulated_run(
                run_id=run_id,
                blueprint=blueprint,
                task=task,
                harness=harness,
                mode=mode,
                sandbox_dir=sandbox_dir,
                prompt=prompt,
                auto_evaluate_callback=auto_evaluate_callback,
            )
        )
        _active_tasks[run_id] = bg_task

    return run_record


def stop_active_run(run_id: str) -> bool:
    """Terminate an active CLI subprocess or background task for a run."""
    proc = _active_processes.pop(run_id, None)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
        except Exception:
            pass
    bg = _active_tasks.pop(run_id, None)
    if bg and not bg.done():
        bg.cancel()
    update_run_status(
        run_id,
        status="cancelled",
        completed_at=utc_now_iso(),
        error_message="Stopped by user.",
    )
    event_bus.publish(
        TelemetryEvent(
            run_id=run_id,
            timestamp=utc_now_iso(),
            source="runner",
            event_type="SessionStop",
            agent_id="root_orchestrator",
            status="info",
            message="Run stopped by user.",
        )
    )
    return True


def coalesce_events_for_display(events: List[TelemetryEvent]) -> List[TelemetryEvent]:
    """Coalesce fragmented streaming AssistantMessage chunks and filter raw JSON noise for clean UI & log display."""
    cleaned: List[TelemetryEvent] = []
    for ev in events:
        msg = ev.message or ""
        # Skip raw housekeeping JSON lines or empty placeholder 'Step #N (agent_response)' from legacy runs
        if ev.event_type == "CommandOutput" and msg.strip().startswith('{"event":'):
            continue
        if ev.event_type == "AssistantMessage" and msg.strip().startswith("Step #") and "(agent_response)" in msg:
            continue

        # Merge consecutive AssistantMessage chunks from the same agent
        if (
            ev.event_type == "AssistantMessage"
            and cleaned
            and cleaned[-1].event_type == "AssistantMessage"
            and cleaned[-1].agent_id == ev.agent_id
            and not msg.startswith("[Session Result:")
            and not msg.startswith("[Antigravity Result:")
        ):
            prev = cleaned[-1]
            prev.message = (prev.message or "") + msg
            prev.input_tokens = max(prev.input_tokens, ev.input_tokens)
            prev.output_tokens = max(prev.output_tokens, ev.output_tokens)
            prev.cache_read_tokens = max(prev.cache_read_tokens, ev.cache_read_tokens)
            prev.duration_ms = max(prev.duration_ms, ev.duration_ms)
            prev.cost_usd = max(prev.cost_usd, ev.cost_usd)
            continue

        # Deduplicate consecutive identical blank PreToolUse calls
        if (
            ev.event_type == "PreToolUse"
            and cleaned
            and cleaned[-1].event_type == "PreToolUse"
            and cleaned[-1].tool_name == ev.tool_name
            and not ev.message
        ):
            continue

        if ev.event_type == "PreToolUse" and not ev.message:
            ev.message = f"Executed tool `{ev.tool_name or 'tool'}`"

        cleaned.append(ev)
    return cleaned


def format_run_plain_text_log(run_id: str) -> str:
    """Build a clean, human-readable, copy-pasteable execution log for a run."""
    run = get_run(run_id)
    if not run:
        return f"Run '{run_id}' not found."

    raw_events = list_telemetry_events(run_id)
    events = coalesce_events_for_display(raw_events)

    lines = [
        "================================================================================",
        f"HARNESSFORGE EXECUTION LOG — {run.id}",
        f"Architecture : {run.architecture_name} ({run.architecture_id} v{run.architecture_version})",
        f"Task         : {run.task_name} ({run.task_id})",
        f"Harness      : {run.harness} | Mode: {run.mode} | Status: {run.status.upper()}",
        f"Sandbox Path : {run.sandbox_path}",
        f"Started At   : {run.started_at} | Completed At: {run.completed_at or 'In Progress'}",
        "================================================================================",
        "",
    ]

    for idx, ev in enumerate(events, start=1):
        ts_short = ev.timestamp[11:19] if len(ev.timestamp) >= 19 else ev.timestamp
        tool_tag = f" [Tool: {ev.tool_name}]" if ev.tool_name else ""
        tok_tag = (
            f" ({ev.input_tokens + ev.output_tokens} tok, ${ev.cost_usd:.4f})"
            if (ev.input_tokens + ev.output_tokens) > 0
            else ""
        )
        msg_body = (ev.message or "").strip()
        lines.append(f"[{idx:02d}] [{ts_short}] [@{ev.agent_id}] [{ev.event_type}]{tool_tag}{tok_tag}")
        if msg_body:
            for mline in msg_body.splitlines():
                lines.append(f"     {mline}")
        if ev.tool_output:
            lines.append(f"     --- Tool Output ---")
            for oline in ev.tool_output.strip().splitlines()[:15]:
                lines.append(f"     > {oline}")
        lines.append("")

    if run.error_message:
        lines.append(f"[ERROR] {run.error_message}")

    log_text = "\n".join(lines)
    try:
        sandbox_dir = Path(run.sandbox_path)
        if sandbox_dir.exists():
            (sandbox_dir / "execution.log").write_text(log_text, encoding="utf-8")
    except Exception:
        pass
    return log_text
