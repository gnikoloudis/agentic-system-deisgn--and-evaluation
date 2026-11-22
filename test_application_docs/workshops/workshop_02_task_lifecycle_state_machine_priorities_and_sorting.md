# Workshop 2 Transcript: Task Lifecycle State Machine, Blocker Rules, Priorities & Sorting

**Project Name**: FocusFlow — Enterprise & Personal To-Do Application  
**Artifact ID**: `TBA-WS-02`  
**Date**: November 17, 2026 | **Time**: 09:00 – 10:00 (Duration: 60 Minutes)  
**Location**: Conference Room B / Hybrid Recording  

## Attendees
- **Alex Mercer (TBA)**: Lead Technical Business Analyst  
- **Sarah Jenkins (Customer — Product Sponsor)**: VP of Digital Productivity  
- **Marco Rossi (Customer — Power User Representative)**: Operations Team Lead  
- **Elena Lin (Customer — UX & Customer Advocacy Lead)**: Principal Product Designer  

---

## Session Transcript (00:00 – 60:00)

**[00:00] Alex Mercer (TBA):**  
Welcome back everyone to **Workshop 2 of 5**. Yesterday in Workshop 1, we locked down personas, the core Task schema (`title` 1–120 chars, `description` <= 2,000 chars), the 20-subtask checklist rules, and the 30-day Trash soft-delete lifecycle.  
Today in **Hour 2 (`00:00 – 60:00`)**, we are focusing on:
1. The 5-State Task Lifecycle State Machine & Valid Transitions (`00:00 – 22:00`)
2. The `BLOCKED` Status Guardrails & Mandatory Blocker Rationale (`22:00 – 35:00`)
3. `COMPLETED` & `ARCHIVED` Lifecycle Rules (`35:00 – 45:00`)
4. The 4-Tier Priority Matrix & Deterministic Multi-Key Sorting Algorithm (`45:00 – 60:00`)

Marco, let’s start with the **Task Statuses**. Why isn't a simple binary `Open / Done` checkbox enough for FocusFlow users?

**[02:30] Marco Rossi (Customer — Power User):**  
When you have 40 tasks on your plate, "not done yet" means three completely different things:
- Either I haven't touched it yet (**`TODO`**),
- Or I am actively working on it today (**`IN_PROGRESS`**),
- Or I *want* to finish it, but I'm stuck waiting on someone else—like legal approval or a vendor quote (**`BLOCKED`**).
And once a task is finished (**`COMPLETED`**), after a week or two I want to clear it off my completed list without deleting the history (**`ARCHIVED`**).

**[06:15] Alex Mercer (TBA):**  
So our canonical `TaskStatus` enum has exactly five values:
`TODO`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, and `ARCHIVED`.  
Let’s walk through every transition in this state machine and identify which transitions are **Allowed** and which are **Forbidden**.

**[08:00] Sarah Jenkins (Customer — Product Sponsor):**  
Let’s trace them one by one:
1. **From `TODO`**:
   - Can move to `IN_PROGRESS` (User starts working).
   - Can move to `BLOCKED` (User realizes immediately they are waiting on an external dependency).
   - Can move directly to `COMPLETED` (Quick one-step task checked off immediately).
   - Can move to `ARCHIVED` (Task is no longer relevant/deferred indefinitely, archived for record).
2. **From `IN_PROGRESS`**:
   - Can move back to `TODO` (Paused / put back in backlog).
   - Can move to `BLOCKED` (Hit an obstacle).
   - Can move to `COMPLETED` (Work finished).
   - **Cannot** move directly from `IN_PROGRESS` to `ARCHIVED`! If someone is actively working on a task, they must either complete it or move it back to `TODO` before archiving.

**[14:40] Alex Mercer (TBA):**  
That’s an important guard condition: `IN_PROGRESS -> ARCHIVED` is **Forbidden** (`HTTP 422 / ERR_INVALID_STATE_TRANSITION`).  
Now what about transitions **out of `BLOCKED`**? This brings us into segment 2 (`22:00 – 35:00`).

**[22:10] Marco Rossi (Customer — Power User):**  
Here is the #1 rule for **`BLOCKED`**:
- **You CANNOT transition a task directly from `BLOCKED` to `COMPLETED`** (`BLOCKED -> COMPLETED` is strictly **Forbidden**).
- Nor can you transition directly from `BLOCKED` to `ARCHIVED` (`BLOCKED -> ARCHIVED` is **Forbidden**).
- Why? Because in our operations team, people accidentally tap the completion checkbox on a blocked item, or try to sweep blocked tasks under the rug by archiving them.
- To complete a `BLOCKED` task, you **must first unblock it** by transitioning it to `IN_PROGRESS` (or `TODO`), and only then can you transition it to `COMPLETED`.

**[26:45] Alex Mercer (TBA):**  
And what data is required when a task enters **`BLOCKED`**, and what happens to that data when the task leaves **`BLOCKED`**?

**[27:30] Sarah Jenkins (Customer — Product Sponsor):**  
We require a **`blocker_reason`** field on the task:
- **Entering `BLOCKED`**: Any request that transitions `status` to `BLOCKED` **must** include a non-empty `blocker_reason` string between **5 and 300 characters** (after trimming).
  - If `blocker_reason` is missing, null, or shorter than 5 characters (e.g., `"wait"`), the API must reject the transition with `HTTP 422 / ERR_BLOCKER_REASON_REQUIRED` (`"A blocker reason of 5 to 300 characters is required when marking a task as BLOCKED."`).
- **While in `BLOCKED`**: The user can edit/update the `blocker_reason` text (still adhering to 5–300 characters), and the UI displays a red/amber warning banner on the task card showing the `blocker_reason` and a timestamp `blocked_at`.
- **Leaving `BLOCKED` (Unblocking)**: When the user transitions the task from `BLOCKED` to `IN_PROGRESS` or `TODO`, the system automatically clears `blocker_reason = null` and `blocked_at = null` (while recording the historical unblock event in the task activity log).

**[33:20] Elena Lin (Customer — UX Lead):**  
From a UX perspective, if a user clicks the completion checkbox on a task card that is currently `BLOCKED`, the UI should block the check action and pop up a clear modal: *"This task is currently BLOCKED ('Waiting on vendor API key'). Would you like to unblock it and move it to In Progress first?"*

**[35:15] Alex Mercer (TBA):**  
Now let’s examine segment 3 (`35:00 – 45:00`): **`COMPLETED` and `ARCHIVED` Lifecycle Rules**.  
What exact state side-effects occur when a task enters or leaves `COMPLETED` and `ARCHIVED`?

**[36:05] Sarah Jenkins (Customer — Product Sponsor):**  
1. **Entering `COMPLETED`**:
   - Allowed from: `TODO` or `IN_PROGRESS`.
   - Side effects:
     - Set `completed_at = current_utc_timestamp`.
     - Cascade `is_completed = true` to all child subtasks (as we agreed in Workshop 1).
     - If the task is a **Recurring Task** (which we'll detail in Workshop 4), trigger generation of the next occurrence.
2. **Leaving `COMPLETED` (Re-opening a task)**:
   - Allowed to: `TODO` or `IN_PROGRESS`.
   - Side effects:
     - Clear `completed_at = null`.
3. **Entering `ARCHIVED`**:
   - Allowed from: `COMPLETED` or `TODO` only.
   - Side effects:
     - Set `archived_at = current_utc_timestamp`.
     - The task is hidden from active list boards and only visible in the `"Archived Tasks"` filter view.
     - While in `ARCHIVED`, the task and its subtasks are **strictly read-only** (no field edits, no adding/toggling subtasks).
4. **Leaving `ARCHIVED` (Unarchiving)**:
   - Allowed to: `TODO` only (via the `"Unarchive"` action).
   - Side effects:
     - Clear `archived_at = null`, set `status = TODO`, and restore full editability.

**[43:10] Alex Mercer (TBA):**  
Let’s summarize the complete **State Transition Matrix** for our Development and QA teams:

| Current Status | Allowed Target Statuses | Forbidden Target Statuses (`HTTP 422`) |
| :--- | :--- | :--- |
| **`TODO`** | `IN_PROGRESS`, `BLOCKED` *(req reason)*, `COMPLETED`, `ARCHIVED` | — |
| **`IN_PROGRESS`** | `TODO`, `BLOCKED` *(req reason)*, `COMPLETED` | `ARCHIVED` |
| **`BLOCKED`** | `TODO`, `IN_PROGRESS` *(clears reason)* | `COMPLETED`, `ARCHIVED` |
| **`COMPLETED`** | `TODO`, `IN_PROGRESS` *(clears completed_at)*, `ARCHIVED` | `BLOCKED` |
| **`ARCHIVED`** | `TODO` *(via Unarchive only)* | `IN_PROGRESS`, `BLOCKED`, `COMPLETED` |

Does everyone sign off on this transition table?

**[44:30] Sarah Jenkins & Marco Rossi:**  
100% approved.

**[45:00] Alex Mercer (TBA):**  
Now for segment 4 (`45:00 – 60:00`): **The 4-Tier Priority Matrix & Deterministic Sorting Rules**.  
Elena, how do priorities work and how should lists sort tasks when the user hasn't applied a manual custom sort?

**[46:10] Elena Lin (Customer — UX Lead):**  
We have four priority levels. Each has an enum string, a numeric `priority_weight`, and a visual color token:
- **`URGENT`**: Weight = `4` (Color: `#EF4444` Crimson Red, Icon: Double Exclamation / Flame)
- **`HIGH`**: Weight = `3` (Color: `#F97316` Amber Orange, Icon: Up Chevron)
- **`MEDIUM`**: Weight = `2` (Color: `#3B82F6` Royal Blue, Icon: Equals Bar — **System Default**)
- **`LOW`**: Weight = `1` (Color: `#64748B` Slate Gray, Icon: Down Chevron)

**[50:25] Marco Rossi (Customer — Power User):**  
And for sorting: nothing is worse than a to-do app where items jump around randomly on refresh. We need a **deterministic 4-level default sort order** for active (`TODO`, `IN_PROGRESS`, `BLOCKED`) tasks in any list:
1. **Primary Sort Key — Overdue Status (`is_overdue` descending)**: Any active task whose `due_at` is in the past (`due_at < now_utc`) appears at the very top of the list so emergencies are never buried.
2. **Secondary Sort Key — Priority Weight (`priority_weight` descending)**: `URGENT (4)` → `HIGH (3)` → `MEDIUM (2)` → `LOW (1)`.
3. **Tertiary Sort Key — Due Date (`due_at` ascending, nulls last)**: Within the same priority tier, tasks due sooner appear above tasks due later, and tasks with a due date appear above tasks with `due_at = null`.
4. **Quaternary Tie-Breaker — Creation Timestamp (`created_at` descending, then `task_id` ascending)**: Newer tasks first, with `task_id` ensuring 100% deterministic pagination.

**[56:40] Sarah Jenkins (Customer — Product Sponsor):**  
And where do **`COMPLETED`** tasks appear when viewing a list?
- By default, `COMPLETED` tasks are grouped in a collapsible **"Completed (N)"** section at the bottom of the list, sorted by `completed_at` descending (most recently completed at the top of the Completed section).

**[59:30] Alex Mercer (TBA):**  
That gives our developers an exact SQL/query `ORDER BY` specification and gives QA deterministic assertions for list ordering tests. That concludes Hour 2! Tomorrow in **Workshop 3**, we will cover **Custom Lists/Projects, Color-Coded Tags, Smart Views (`Today`, `Upcoming`, `Overdue`, `Blocked`), and Search/Filtering**.
