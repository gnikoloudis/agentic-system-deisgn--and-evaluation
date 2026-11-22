# Workshop 1 Transcript: Product Vision, User Personas & Core Task CRUD

**Project Name**: FocusFlow — Enterprise & Personal To-Do Application  
**Artifact ID**: `TBA-WS-01`  
**Date**: November 16, 2026 | **Time**: 09:00 – 10:00 (Duration: 60 Minutes)  
**Location**: Conference Room B / Hybrid Recording  

## Attendees
- **Alex Mercer (TBA)**: Lead Technical Business Analyst  
- **Sarah Jenkins (Customer — Product Sponsor)**: VP of Digital Productivity  
- **Marco Rossi (Customer — Power User Representative)**: Operations Team Lead  
- **Elena Lin (Customer — UX & Customer Advocacy Lead)**: Principal Product Designer  

---

## Session Transcript (00:00 – 60:00)

**[00:00] Alex Mercer (TBA):**  
Good morning everyone, and welcome to Workshop 1 of our 5-hour requirements discovery series for the **FocusFlow To-Do Application**. Over these five 1-hour sessions, my objective as your Technical Business Analyst is to elicit every business objective, functional rule, workflow, boundary condition, and edge case so we can author a complete delivery specification—including Epics, Process Workflows, and Wikipedia-standard User Stories that bridge our Development Team and Testing (QA) Team.  
Today in **Hour 1**, we are covering:
1. Business Problem & Product Vision (`00:00 – 12:00`)
2. Target User Personas & Workspace Boundaries (`12:00 – 24:00`)
3. Core Task Creation ("Quick Add" vs. Detailed Form) & Field Validation Rules (`24:00 – 42:00`)
4. Subtasks / Checklists & Parent-Child Completion Behavior (`42:00 – 53:00`)
5. Task Deletion & 30-Day Trash Retention Lifecycle (`53:00 – 60:00`)

Sarah, let’s start at the top. Why are we building FocusFlow, and what business KPIs define success?

**[02:15] Sarah Jenkins (Customer — Product Sponsor):**  
Thanks, Alex. Our market research shows a massive gap between consumer sticky-note apps—which break down as soon as a user has more than 30 tasks—and bloated enterprise ticket trackers like Jira that require filling out 12 mandatory fields just to remind yourself to send a client contract.  
Our vision for **FocusFlow** is **"Zero-Friction Capture, Structured Execution."**  
Our three business KPIs for the v1 launch are:
- **Speed of Capture**: A user must be able to capture a new to-do in under **2 seconds** using just their keyboard.
- **Daily Active Retention**: 65% 30-day retention driven by clear daily focus views and reliable reminders.
- **Zero Data Loss / Auditability**: Every task change, completion, or deletion must be recoverable and traceable.

**[07:40] Alex Mercer (TBA):**  
"Zero-Friction Capture, Structured Execution" is a very clear north star. Let’s translate that into the **User Personas** who will interact with the system. Elena and Marco, who are the distinct actor roles we need to model in our User Stories?

**[08:30] Elena Lin (Customer — UX Lead):**  
We’ve validated three primary personas during user interviews:
1. **Persona 1 — The Solo Organizer (`Registered User`)**: An individual professional managing daily work deliverables and personal errands. They care about Quick Add, priorities, subtasks, recurring tasks, and the `"Today"` view.
2. **Persona 2 — The Team Contributor (`Shared List Editor`)**: A team member invited to a shared project list (for example, `"Q4 Product Launch"`). They need to claim or be assigned tasks, mark items as `IN_PROGRESS` or `BLOCKED`, and leave status comments.
3. **Persona 3 — The Workspace / List Owner (`List Owner`)**: A manager or coordinator who creates project lists, invites collaborators as `EDITOR` or `VIEWER`, monitors overdue or blocked tasks, and exports completion reports.

**[14:10] Alex Mercer (TBA):**  
Do we support anonymous/guest users without an account, or does every persona require an authenticated account?

**[14:45] Sarah Jenkins (Customer — Product Sponsor):**  
Every user must have an authenticated account (`email + password` or OAuth SSO) so tasks sync across web and mobile. When a user registers for the first time, the system must automatically provision their personal workspace with one built-in system list called **`"Inbox"`** that cannot be deleted or renamed.

**[18:20] Alex Mercer (TBA):**  
Let’s capture that as **Business Requirement `BR-001`**: *Every newly registered user receives a non-deletable, non-renamable default system list named `"Inbox"` (`is_system_inbox = true`).*  
Now let's move to segment 3 (`24:00 – 42:00`): **Core Task Creation & Field Validation Rules**.  
Marco, walk me through the two ways you create a task: **Quick Add** versus the **Detailed Task Modal**.

**[24:30] Marco Rossi (Customer — Power User):**  
90% of the time, I'm on a call and I just want to click the Quick Add bar at the top of my screen (or press the keyboard shortcut `N`), type `"Send revised SLA pricing to Acme Corp"`, and press `Enter`.  
I don't want to be forced to pick a due date, priority, or project list in that moment.  
Then later, when I organize my day, I click on that task to open the Detail Drawer and add markdown notes, a due date, a priority level, tags, and a 5-step checklist.

**[27:15] Alex Mercer (TBA):**  
Let’s define the exact field schema and validation rules for the `Task` entity so that our **Development Team** and **QA Testing Team** have zero ambiguity in the User Stories:
1. **`task_id`**: System-generated UUID v4, immutable.
2. **`title`**: Required string. What are the exact character bounds and whitespace rules?
3. **`description`**: Optional string. What format, max length, and security sanitization rules apply?
4. **Default values on Quick Add**: When only `title` is supplied, what do all other fields default to?

**[29:00] Sarah Jenkins (Customer — Product Sponsor):**  
Let’s lock these numbers down:
- **`title`**:
  - **Required**: Yes.
  - **Trimming**: Automatically trim leading and trailing whitespace before validation.
  - **Length**: Minimum **1 character**, maximum **120 characters** (post-trim).
  - **Error Handling**: If `title` is empty or whitespace-only after trimming, reject with `HTTP 400 / ERR_TITLE_REQUIRED` (`"Task title cannot be empty."`). If `title` exceeds 120 characters, reject with `HTTP 400 / ERR_TITLE_TOO_LONG` (`"Task title cannot exceed 120 characters."`).
- **`description`**:
  - **Required**: No (nullable / defaults to `""`).
  - **Format**: Supports GitHub-Flavored Markdown (bold, italics, links, code spans, bullet lists).
  - **Length**: Maximum **2,000 characters**. If `> 2,000` characters, reject with `HTTP 400 / ERR_DESCRIPTION_TOO_LONG`.
  - **Security**: Strip/sanitize any executable HTML tags (`<script>`, `<iframe>`, `onload=`, `onerror=`) on save and render to prevent stored XSS.

**[34:50] Elena Lin (Customer — UX Lead):**  
And for the **Quick Add default values** when a user only submits `{ "title": "..." }`:
- `status`: Defaults to **`TODO`**
- `priority`: Defaults to **`MEDIUM`**
- `list_id`: Defaults to the user's **`"Inbox"`** list (unless the user is currently viewing a specific custom list, in which case it defaults to that active list's `list_id`)
- `due_at`: Defaults to **`null`**
- `assignee_id`: Defaults to the creator's `user_id` on personal lists, or `null` on shared lists unless specified
- `tags`: Defaults to empty array `[]`
- `subtasks`: Defaults to empty array `[]`
- `is_deleted`: Defaults to `false`
- `created_at` & `updated_at`: Current UTC timestamp (`ISO-8601`).

**[39:15] Alex Mercer (TBA):**  
What about **Editing a Task**? Can every field be updated at any time, or are there restrictions?

**[40:10] Marco Rossi (Customer — Power User):**  
As long as a task is not `ARCHIVED` or in the `Trash` (`is_deleted = true`), the owner or an `EDITOR` can update `title`, `description`, `priority`, `due_at`, `list_id`, `tags`, and `subtasks` at any time, and every edit updates `updated_at`. If a task is `ARCHIVED` or `is_deleted = true`, any attempt to edit its fields must be blocked with `HTTP 409 Conflict` (`"Cannot edit an archived or deleted task. Restore it first."`).

**[42:30] Alex Mercer (TBA):**  
That is a great state invariant for QA to test. Now let’s move to segment 4 (`42:00 – 53:00`): **Subtasks (Checklists) & Parent-Child Completion Rules**.  
Marco, when you break a task down into smaller steps, how should subtasks work?

**[43:15] Marco Rossi (Customer — Power User):**  
Keep subtasks flat—**strictly 1 level of nesting** inside a parent task. We do *not* want subtasks inside subtasks.  
Here are the rules we need for Subtasks:
1. **Fields**: Each subtask has `subtask_id` (UUID), `parent_task_id` (UUID), `title` (required, **1 to 100 characters** after trimming), `is_completed` (boolean, default `false`), and `sort_order` (integer `1..N`).
2. **Maximum Subtasks Limit**: A single parent task can contain at most **20 subtasks**. If a user tries to add a 21st subtask, the system must block it with `HTTP 422 / ERR_MAX_SUBTASKS_EXCEEDED` (`"A task cannot have more than 20 subtasks."`).
3. **Progress Badge**: Whenever a task has `>= 1` subtask, the API and UI must expose `subtasks_total`, `subtasks_completed`, and `progress_pct` (rounded to the nearest integer, e.g., `2` of `3` = `67%`).

**[47:40] Alex Mercer (TBA):**  
Let’s test the two critical boundary interactions between a **Parent Task** and its **Subtasks**:
- **Scenario A**: A task has 4 subtasks. The user checks off the 4th subtask so `4 / 4 (100%)` are now complete. What happens to the Parent Task's `status`?
- **Scenario B**: A task has 4 subtasks, and only 1 is complete (`1 / 4`). The user clicks the main checkbox on the **Parent Task** to mark the Parent Task `COMPLETED`. What happens to the 3 incomplete subtasks?

**[49:05] Sarah Jenkins (Customer — Product Sponsor):**  
Here is the exact behavior we want:
- **In Scenario A (Last subtask checked off)**: Do **not** automatically force the parent task to `COMPLETED` on the backend, because the parent task might still need a final sign-off. Instead, the parent stays in `TODO` or `IN_PROGRESS`, and the frontend UI shows a non-blocking toast prompt: *"All subtasks complete! Complete parent task?"*
- **In Scenario B (Parent task marked `COMPLETED` while subtasks are still open)**: When the parent task transitions to `COMPLETED`, the backend **must automatically cascade `is_completed = true` to all of its subtasks** so the task never appears as `COMPLETED` with `1 / 4` unfinished checklist items.
- **Re-opening the Parent Task**: If that `COMPLETED` parent task is later re-opened back to `TODO` or `IN_PROGRESS`, the subtasks remain `is_completed = true` unless the user manually unchecks individual subtasks.

**[53:10] Alex Mercer (TBA):**  
Crystal clear. In our final 7 minutes of Workshop 1 (`53:00 – 60:00`), let’s define **Task Deletion & Trash Retention**.  
When a user deletes a task, what happens?

**[54:00] Elena Lin (Customer — UX Lead):**  
Accidental deletion is the #1 complaint in productivity apps, so we need a **two-stage Soft Delete & Trash Bin**:
1. **Stage 1 — Soft Delete (Move to Trash)**:
   - When a user deletes an active task, set `is_deleted = true` and `deleted_at = current_utc_timestamp`.
   - Immediately support an `"Undo"` action in the UI for 10 seconds, and move the task to the **`Trash`** view.
   - Soft-deleted tasks must be excluded from `"Inbox"`, custom lists, Smart Views, tag counts, and reminders.
2. **Stage 2 — Restore from Trash**:
   - While in `Trash`, the user can click **`Restore`**.
   - Restoring sets `is_deleted = false` and `deleted_at = null`.
   - **Edge Case**: What if the custom list the task originally belonged to was deleted while the task was in Trash? In that case, restoring the task must automatically reassign its `list_id` to the user's system **`"Inbox"`** list!
3. **Stage 3 — Permanent Hard Delete**:
   - Inside `Trash`, the user can click **`Delete Permanently`** on a single task or **`Empty Trash`** for all trashed tasks, which permanently removes the row and its subtasks from the database.
   - An automated daily cleanup job must also permanently hard-delete any soft-deleted task where `current_utc_timestamp - deleted_at > 30 calendar days`.

**[59:10] Alex Mercer (TBA):**  
That edge case—restoring a trashed task whose original parent list was deleted and automatically routing it to `"Inbox"`—is exactly the kind of specification our Developers and QA Engineers love.  
We are right at the 60-minute mark. Thank you all! In **Workshop 2**, we will dive deep into the **5-State Task Lifecycle State Machine, Blocker Rules, Priority Matrix, and Sorting Algorithms**.
