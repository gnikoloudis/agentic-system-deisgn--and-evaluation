# FocusFlow Discovery Workshop 07 — Interactive UI Widgets, Modals, Keyboard Accessibility & Frontend Acceptance Criteria

- **Session Date**: November 20, 2026 | **Duration**: 60 Minutes (`00:00 – 60:00`)
- **Facilitator**: Alex Mercer (Lead Technical Business Analyst)
- **Participants**:
  - **Elena Lin** — Principal Product Designer (Customer UX Lead)
  - **Maya Patel** — Frontend Engineering Lead
  - **Marcus Vance** — VP of Product (Executive Sponsor)
  - **David Kim** — QA Automation Lead

---

## Verbatim Transcript

**[00:00] Alex Mercer (Lead TBA):** Welcome to Workshop 7 — our final UI discovery session. Today we'll walk through every interactive component, modal guardrail, keyboard shortcut, RBAC UI state, and frontend performance/accessibility acceptance criterion from `CUST-REQ-06`.

**[02:30] Maya Patel (Frontend Lead):** Let's start at the top with the **Quick-Add Bar**. When the user presses `N` (while not focused inside another text input or textarea), focus jumps immediately to the Quick-Add input.
- Typing a title and hitting `Enter` immediately inserts the task optimistically at the top of the current list (or `"Inbox"` if on a Smart View) in `< 16 ms`.
- If the title is blank or whitespace-only, `Enter` does NOT fire an API call — it shows an inline subtle shake and helper text: `"Enter a task title (1–120 characters)"`.
- Once the user types `>= 100` characters, a live counter (`108/120`) appears inside the input; above `120` characters, the counter turns red (`124/120`) and the `[Add]` button is disabled.
- If the backend `POST /api/v1/tasks` fails (e.g., `HTTP 400` or `HTTP 500`), the optimistic card is smoothly rolled back and an error toast appears with the server's message.

**[09:15] Elena Lin (UX Lead):** Next, let's lock down the **Blocker Guardrail UI** — this is one of FocusFlow's signature features.
- In the **Right Task Detail Drawer**, the Status dropdown lists `TODO`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, and `ARCHIVED`.
- When the task's current status is `BLOCKED`, the `COMPLETED` option in the Status dropdown is **disabled** with the inline hint `"Unblock first"`.
- If a user clicks the checkbox on a `BLOCKED` task card (or presses `C` while focused on it), the checkbox MUST NOT check off. Instead, a compact **Unblock-Before-Complete Micro-Prompt** pops open showing the current `blocker_reason` and two buttons: **`[Move to In Progress]`** and **`[Move to Todo]`** (plus `[Cancel]`).
- Conversely, when transitioning **into** `BLOCKED` from `TODO` or `IN_PROGRESS`, an inline required **`Blocker Reason`** box expands immediately (`placeholder: "Why is this task blocked? (5–500 chars)"`). The **`[Confirm Block]`** button remains disabled until the trimmed text is between `5` and `500` characters.

**[17:40] David Kim (QA Lead):** What about the **20-Subtask Checklist** and **Parent Completion Cascade** in the Right Drawer?

**[19:00] Maya Patel (Frontend Lead):**
- The Subtasks section displays a live header `Subtasks (3/5 — 60%)` and a horizontal progress bar.
- Users can add a subtask via the inline `Add subtask...` input (`Enter` to add), toggle checkboxes optimistically, drag-and-drop to reorder (`position 0..19`), edit titles inline, or delete a subtask.
- When `subtasks.length === 20`, the `Add subtask...` input is replaced/disabled with an informational badge: `"Maximum 20 subtasks reached"` so the user never hits an unexpected `HTTP 422` error.
- **Parent Completion Cascade Dialog**: If a user attempts to complete a parent task that still has `>= 1` unchecked subtasks, the UI opens a confirmation modal: *"This task has 3 open subtasks. Mark all 3 remaining subtasks as completed?"* with **`[Complete Parent & Subtasks]`** and **`[Cancel]`**. On confirm, both parent and children update atomically.

**[25:20] Elena Lin (UX Lead):** Now let's review the **Recurrence Rule Builder** inside the Right Detail Drawer. Recurring tasks confuse users when they don't know what date comes next.
- Toggling `Repeat` reveals:
  1. **Frequency**: `Daily`, `Weekly` (with Mon–Sun day pills), `Monthly`, or `Custom Interval` (`Every [N] [days/weeks/months]`).
  2. **Schedule Mode Radio**:
     - `Fixed Schedule` (*"Always repeats on the scheduled calendar date"*)
     - `On Completion` (*"Repeats N days/weeks/months after you check it off"*)
  3. **Live "Next 3 Occurrences" Preview Box**: As the user edits the due date and recurrence rule, the UI computes and displays the next 3 dates in real time — for example, if Due Date is `Jan 31` and Frequency is `Monthly (Fixed Schedule)`, the preview explicitly shows: **`Feb 28 → Mar 31 → Apr 30`** so users immediately trust the month-end clamping behavior!

**[33:00] Marcus Vance (VP of Product):** That live preview is going to cut support tickets in half. Now let's check **Safe List Deletion** and **Shared Lists RBAC UI**.

**[34:40] Elena Lin (UX Lead):**
- Clicking `Delete List` on any custom list with `>= 1` active tasks opens the **Safe List Deletion Modal**.
- The modal displays the list name and task count (`"Work Launch contains 9 active tasks"`) and presents **two unselected radio cards**:
  1. **`Move 9 tasks to Inbox`** (keeps all tasks active in `"Inbox"`)
  2. **`Move 9 tasks to Trash`** (soft-deletes tasks with 30-day recovery)
- The red **`[Delete List]`** button stays **disabled** until the user explicitly selects one of the two options. (If the list has `0` tasks, a simple confirmation dialog is shown instead.) The system `"Inbox"` list never renders a delete option.

**[39:50] Maya Patel (Frontend Lead):** For **Shared Lists RBAC UI**:
- When a user opens a shared list where their role is **`VIEWER`**:
  - A subtle top info strip renders: `"View-Only List — Owned by <Owner Name>. You can view tasks and history, but cannot edit."`
  - The Quick-Add bar defaults to `"Inbox"` (not the read-only list).
  - Inside the Right Detail Drawer, all mutation inputs (Title, Status, Priority, Due Date, Subtasks, Description, Comment Composer) are disabled/read-only, and `Delete`/`Archive` buttons are hidden.
- For **`EDITOR`**: Can create/edit/complete/comment on tasks and assign tasks to any list member (`OWNER` or `EDITOR`), but `Share & Permissions` and `Delete List` remain hidden.
- For **`OWNER`**: Full access, including the **Share & Permissions Modal** to invite users by email, change roles (`EDITOR` / `VIEWER`), or revoke access.

**[45:10] David Kim (QA Lead):** Let's nail down **Keyboard Navigation, Accessibility (WCAG 2.1 AA), and Frontend Performance Budgets** so QA can write automated Playwright + Axe-core tests.

**[46:45] Elena Lin (UX Lead):** Every core workflow must be 100% completable using only the keyboard:
- `N` → Focus Quick-Add bar.
- `/` → Focus Global Search bar.
- `J` / `K` or `ArrowDown` / `ArrowUp` → Move focus ring between task rows in the Center Stream.
- `Enter` → Open Right Detail Drawer for the focused task.
- `C` → Complete focused task (or trigger Unblock Micro-Prompt if `BLOCKED`).
- `1`, `2`, `3`, `4` → Set focused task priority (`URGENT`, `HIGH`, `MEDIUM`, `LOW`).
- `Delete` / `Backspace` → Move focused task to Trash + show 10-second **`[Undo]`** toast.
- `Esc` → Close active modal, popover, or Right Detail Drawer (returning focus to the previously focused task row).
- `?` → Open Keyboard Shortcuts Cheat Sheet modal.
- **Guard**: Single-key shortcuts (`N`, `/`, `C`, `1–4`, `J`, `K`, `?`, `Delete`) MUST be suppressed whenever focus is inside an `<input>`, `<textarea>`, `<select>`, or `[contenteditable]` element!

**[52:30] David Kim (QA Lead):** And for ARIA & screen readers:
- All modals must trap keyboard focus (`role="dialog"`, `aria-modal="true"`, `aria-labelledby`) and restore focus on close.
- A polite ARIA live region (`aria-live="polite"`) must announce task creation, completion, priority changes, blocker updates, and Trash/Undo events.
- Automated `axe-core` scan must report **0 critical or serious WCAG 2.1 AA violations** in both Light and Dark modes.

**[55:15] Maya Patel (Frontend Lead):** And our **Frontend Performance Budgets**:
- First Contentful Paint (FCP) `< 1.2s`; Time to Interactive (TTI) `< 2.0s`.
- Optimistic task/subtask toggle visual response `< 16 ms` (1 frame).
- Task lists with **500+ tasks** must render smoothly at `60 fps` (using windowed/virtualized rendering or memoized row components without re-rendering untouched rows).
- Markdown descriptions MUST be rendered through a strict HTML sanitizer (e.g., DOMPurify) to block all XSS vectors (`<script>`, `onerror=`, `javascript:` URLs).

**[58:40] Alex Mercer (Lead TBA):** Fantastic session everyone. Workshops 6 and 7 give us a crystal-clear UI Requirements Baseline covering Design Tokens, Responsive 3-Pane Layout, Density Modes, Every Interactive Widget & Modal, RBAC UI Rendering, Full Keyboard & WCAG 2.1 AA Accessibility, and Frontend Performance Budgets. Ready for BA synthesis into UI Epics, User Stories, Component Specs, and Frontend Development!
