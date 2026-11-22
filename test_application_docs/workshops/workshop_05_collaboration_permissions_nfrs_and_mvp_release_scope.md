# Workshop 5 Transcript: Collaboration, RBAC Permissions, Audit Trail, NFRs & MVP Scope

**Project Name**: FocusFlow — Enterprise & Personal To-Do Application  
**Artifact ID**: `TBA-WS-05`  
**Date**: November 20, 2026 | **Time**: 09:00 – 10:00 (Duration: 60 Minutes)  
**Location**: Conference Room B / Hybrid Recording  

## Attendees
- **Alex Mercer (TBA)**: Lead Technical Business Analyst  
- **Sarah Jenkins (Customer — Product Sponsor)**: VP of Digital Productivity  
- **Marco Rossi (Customer — Power User Representative)**: Operations Team Lead  
- **Elena Lin (Customer — UX & Customer Advocacy Lead)**: Principal Product Designer  
- **Vikram Patel (Customer — Security & Compliance Architect)**: Head of Application Security  

---

## Session Transcript (00:00 – 60:00)

**[00:00] Alex Mercer (TBA):**  
Good morning everyone, and welcome to **Workshop 5 of 5**—our final 1-hour requirements discovery workshop for the **FocusFlow To-Do Application**. We also have Vikram Patel joining us today from Security & Compliance.  
Our agenda for **Hour 5 (`00:00 – 60:00`)** covers:
1. Shared Lists & Role-Based Access Control (`OWNER`, `EDITOR`, `VIEWER`) (`00:00 – 16:00`)
2. Task Assignment, `@mention` Comments & Activity Audit Log (`16:00 – 30:00`)
3. Data Portability: CSV / JSON Export & Import (`30:00 – 40:00`)
4. Non-Functional Requirements (Security, Performance SLAs, Offline Resilience, Accessibility) (`40:00 – 52:00`)
5. MVP In-Scope vs. Out-of-Scope Boundaries & Final Stakeholder Sign-Off (`52:00 – 60:00`)

Sarah and Marco, let’s start with **Shared Lists & Collaboration**. How does a user share a custom list with teammates, and what are the exact permission boundaries?

**[02:10] Sarah Jenkins (Customer — Product Sponsor):**  
First, a user's system **`"Inbox"` list is strictly private** and can **never** be shared with other users (`HTTP 403 / ERR_CANNOT_SHARE_INBOX`).  
Any **Custom List**, however, can be shared by its Owner with up to **25 collaborators** by email address. We have three strict Role-Based Access Control (RBAC) roles per shared list:
1. **`OWNER`** (The creator of the list):
   - Full control: Can rename/recolor/delete the list, invite or remove collaborators, change collaborator roles, and create/edit/complete/archive/delete any task in the list.
2. **`EDITOR`** (Team Contributor):
   - Can create new tasks in the list, edit task details (`title`, `description`, `priority`, `due_at`, `tags`, `subtasks`), assign tasks to any member of the shared list, change task status (`TODO`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`), and post comments.
   - **Restrictions on `EDITOR`**: An `EDITOR` **cannot** delete the shared list itself, **cannot** invite or remove other collaborators, and **cannot** permanently empty the Trash (`HTTP 403 Forbidden`).
3. **`VIEWER`** (Read-Only Stakeholder):
   - Can view all tasks, subtasks, comments, and activity logs in the shared list.
   - **Restrictions on `VIEWER`**: Cannot create, edit, status-change, comment on, or delete any task (`HTTP 403 Forbidden`).

**[11:30] Alex Mercer (TBA):**  
What happens if the `OWNER` removes an `EDITOR` from a shared list while 5 active tasks in that list are currently assigned to that removed user (`assignee_id == removed_user_id`)?

**[12:15] Marco Rossi (Customer — Power User):**  
Great edge case! When a collaborator is removed from a shared list (or leaves the list voluntarily):
- Any active task (`status IN ('TODO', 'IN_PROGRESS', 'BLOCKED')`) in that list currently assigned to that user must automatically have its **`assignee_id` unassigned (`assignee_id = null`)** and an activity log entry written (`"Unassigned from [User] due to removal from list"`).
- Historical `COMPLETED` tasks keep their record of who completed them.
- Also, you can only assign a task to a `user_id` who is currently a member (`OWNER` or `EDITOR`) of that list (`HTTP 422 / ERR_ASSIGNEE_NOT_IN_LIST` if someone tries to assign a task to a `VIEWER` or a user outside the list).

**[16:10] Alex Mercer (TBA):**  
Assigning tasks only to `OWNER` or `EDITOR` members of the list (never `VIEWER` or external users) and auto-unassigning open tasks on member removal is a great Dev-to-QA specification rule.  
Let’s move to segment 2 (`16:00 – 30:00`): **Task Comments, `@mentions` & Activity Audit History**.

**[17:00] Marco Rossi (Customer — Power User):**  
On any task (especially `BLOCKED` or shared tasks), `OWNER` and `EDITOR` members can post **Comments**:
- **Comment Schema**: `comment_id` (UUID), `task_id` (UUID), `author_id` (UUID), `body` (Markdown text, **1 to 1,000 characters** after trimming), `mentioned_user_ids` (array of UUIDs parsed from `@username` / `@email`), `created_at` (UTC), `updated_at` (UTC).
- **Author Rules**: A user can edit or delete **their own** comments, and the List `OWNER` can delete any comment in their list, but an `EDITOR` cannot edit or delete another user's comment (`HTTP 403`).
- **`@mention` Notifications**: If a comment contains `@user` referencing a member of the shared list, trigger an in-app notification to that member.

**[23:40] Vikram Patel (Customer — Security & Compliance Architect):**  
And alongside comments, we require an **Immutable Task Activity Audit Log** (`task_activity_log`):
- Every state-changing event on a task—creation, status transition (including `blocker_reason`), priority change, due date change, assignee change, soft-delete, restore, archive, unarchive—must append an immutable record:
  `{ event_id, task_id, actor_id, event_type, field_changed, old_value, new_value, timestamp_utc }`.
- No user (not even the `OWNER`) can modify or delete rows from `task_activity_log` (`UPDATE` and `DELETE` are strictly forbidden until the parent task is permanently purged after 30 days in Trash).

**[30:15] Alex Mercer (TBA):**  
Now let’s cover segment 3 (`30:00 – 40:00`): **Data Portability — Import & Export (`JSON` and `CSV`)**.  
Sarah, what export and import capabilities must be included in v1?

**[31:00] Sarah Jenkins (Customer — Product Sponsor):**  
Enterprise and prosumer users refuse to get locked into a productivity tool without an exit ramp:
1. **Export (`GET /api/v1/export?format=json|csv`)**:
   - Users can export either a single list or their entire workspace in **`JSON`** (full fidelity including subtasks, tags, recurrence rules, and comments) or **`CSV`** (flattened columns: `task_id, title, status, priority, list_name, due_at, tags_pipe_delimited, subtasks_completed, subtasks_total, completed_at`).
2. **Import (`POST /api/v1/import`)**:
   - Users can upload a `.csv` or `.json` file up to **5 MB** (max **1,000 tasks per import batch**).
   - **Atomicity / Validation Report**: If rows have validation errors (e.g., empty `title` or `title > 120 chars`), the importer must skip invalid rows, import all valid rows, and return a structured summary: `{ imported_count, skipped_count, errors: [{ row_number, reason }] }`.

**[40:10] Alex Mercer (TBA):**  
Now let’s move to segment 4 (`40:00 – 52:00`): **Non-Functional Requirements (NFRs)** with Vikram and Elena.

**[41:00] Vikram Patel (Customer — Security & Compliance Architect):**  
Here are our non-negotiable Security, Performance, and Reliability NFRs:
- **`NFR-001` (Authentication & Session Security)**: Passwords hashed with Argon2id (or bcrypt cost >= 12); short-lived JWT access tokens (15-minute expiry) + HTTP-only refresh tokens; strict row-level authorization ensuring user A can never read or mutate user B's tasks (`HTTP 403/404`).
- **`NFR-002` (API Rate Limiting)**: Protect endpoints with sliding-window rate limiting: **120 requests per minute per authenticated user** and **10 requests per minute per IP** on login/registration endpoints (`HTTP 429 Too Many Requests` with `Retry-After` header).
- **`NFR-003` (Performance & Latency SLAs)**:
  - Task Quick-Add & Status Toggle API response time: **< 100 ms (p95)**.
  - List / Smart View / Search query response time (up to 10,000 tasks): **< 150 ms (p95)**.
- **`NFR-004` (Offline Draft Queue & Optimistic UI)**: In the web/mobile client, checking off a task or typing a Quick Add task must update the UI optimistically in `< 16 ms`; if the user's network drops temporarily, queue mutations locally in `IndexedDB` and sync automatically on reconnect.
- **`NFR-005` (Accessibility & Keyboard Navigation)**: WCAG 2.1 AA compliance; full keyboard shortcuts (`N` for New Task, `C` to Complete selected task, `/` to focus Search, `1..4` to set Priority `URGENT..LOW`).
- **`NFR-006` (GDPR Right to Erasure)**: Users can trigger **"Delete My Account"**, which permanently purges all owned lists, tasks, comments, and personal data within 24 hours.

**[52:00] Alex Mercer (TBA):**  
In our final 8 minutes (`52:00 – 60:00`), let’s lock down **MVP Release Scope (In-Scope vs. Out-of-Scope)** so our Epics and User Stories stay tightly bounded.

**[53:10] Sarah Jenkins (Customer — Product Sponsor):**  
- **In-Scope for v1.0 MVP**:
  1. Authentication & Auto-Provisioned `"Inbox"` list (`EPIC-01`).
  2. Core Task CRUD, 5-State Lifecycle Machine (`TODO`, `IN_PROGRESS`, `BLOCKED` with mandatory reason, `COMPLETED`, `ARCHIVED`), 4-Tier Priorities, 20-Subtask Checklists, and 30-Day Soft-Delete Trash Bin (`EPIC-02`).
  3. Custom Lists (max 50), Color-Coded Tags (max 10/task), 4 Smart Views (`Today`, `Upcoming 7 Days`, `Overdue`, `Blocked`), and Multi-Facet Search/Filtering (`EPIC-03`).
  4. Recurring Tasks (`DAILY`, `WEEKLY`, `MONTHLY`, `YEARLY` with `FIXED_SCHEDULE` and `ON_COMPLETION` modes + Jan 31 → Feb 28 rollover) and Due-Date Reminders with Snooze & Quiet Hours (`EPIC-04`).
  5. Shared Lists (`OWNER`, `EDITOR`, `VIEWER`), Task Assignment, `@mention` Comments, Immutable Activity Log, and CSV/JSON Import/Export (`EPIC-05`).
- **Explicitly Out-of-Scope for v1.0 (Deferred to v2.0)**:
  - Gantt charts and critical-path dependency graphs between separate parent tasks.
  - Native two-way calendar sync with external Google Calendar / Outlook Exchange.
  - Built-in Pomodoro time-tracking billing invoices.
  - AI autonomous task execution.

**[59:20] Alex Mercer (TBA):**  
That concludes our 5-hour workshop series for the **FocusFlow To-Do Application**! We have a complete, verifiable transcript record across all 5 hours. I will now catalog these transcripts in the repository and wait for instructions on the next TBA artifacts to generate.
