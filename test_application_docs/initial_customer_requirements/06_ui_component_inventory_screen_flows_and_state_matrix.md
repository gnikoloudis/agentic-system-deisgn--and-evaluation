# Initial Customer Submission 06: UI Component Inventory, Screen Flows & Interactive State Matrix

**Submitted By**: Elena Lin (Principal Product Designer) & Maya Patel (Frontend Engineering Lead)  
**Submitted To**: Alex Mercer, Lead Technical Business Analyst (TBA)  
**Date Submitted**: November 18, 2026 *(Prior to UI Discovery Workshops 6–7)*  
**Subject**: Detailed Screen-by-Screen UI Component Specifications, Modals & Role-Based Rendering Rules  
**Document Reference**: `CUST-REQ-06`  

---

## 1. Screen & Shell Architecture

FocusFlow consists of **2 Authentication Screens** (`/login`, `/register`) and **1 Main Authenticated Workspace Shell** (`/` with client-side routes for Smart Views, Custom Lists, Archived, Trash, and Settings).

### 1.1 Authentication Screens (`/login`, `/register`)
- Centered card (`max-width: 420px`) with FocusFlow logo, email + password inputs, show/hide password toggle, inline validation errors, and submit button with loading spinner.
- `/register` includes a live password strength meter (minimum 12 characters per security policy) and timezone auto-detection (`Intl.DateTimeFormat().resolvedOptions().timeZone`) stored on account creation.
- Unauthenticated access to any workspace route redirects to `/login?redirect=<path>`.

---

## 2. Main Workspace Component Inventory

### 2.1 Top Global Header (`56px` height, sticky)
1. **Sidebar Collapse / Mobile Menu Button** (left)
2. **Quick-Add Task Bar** (center-left, `flex-1`, `max-width: 560px`):
   - Placeholder: `Add a task to Inbox... (Press 'N')`
   - Inline quick-chips that expand when focused: `[List Selector: Inbox]`, `[Priority: Medium]`, `[Due Date]`, `[Add]` button.
   - Live character counter appears once input exceeds `100` characters (`105/120`, turns red at `>120` and disables submit).
3. **Global Search Input** (center-right, `width: 260px`, shortcut `/`):
   - Real-time debounced search (`200ms`) across task titles, descriptions, and tags, with an `X` clear button.
4. **Right Utility Cluster**:
   - **Offline / Sync Status Pill** (hidden when online & synced; shows `"Syncing..."` or `"Offline (2 pending)"` when active).
   - **Reminders Bell Icon** with unread count badge; opens Reminder Popover showing active reminders + one-click **`Snooze 15m`**, **`Snooze 1h`**, **`Tomorrow 9:00 AM`**, and current **Quiet Hours** status indicator.
   - **Theme Toggle** (`Light` / `Dark` / `System`).
   - **User Avatar Menu**: Profile, Settings & Quiet Hours, Export / Import Data (CSV/JSON), Keyboard Shortcuts (`?`), Sign Out.

### 2.2 Left Navigation Rail (`256px` desktop)
1. **SMART VIEWS Section**:
   - `Inbox` (system list, cannot be deleted or renamed) + live active task count badge
   - `Today` + count badge
   - `Upcoming (7 Days)` + count badge
   - `Overdue` + red count badge (hidden when `0`)
   - `Blocked` + amber count badge (hidden when `0`)
2. **CUSTOM LISTS Section** with `[+ New List]` icon button:
   - Each list item displays: Color dot, List name, Shared icon (if shared with collaborators) + Role badge (`Editor`/`Viewer` if not owner), and active task count.
   - Hover reveals `...` overflow menu: `Rename List`, `Share & Permissions` (Owner only), `Delete List` (Owner only — opens Safe Delete Modal).
   - Every list row acts as a **drag-and-drop dropzone** to move tasks between lists.
3. **TAGS Section** with `[+ New Tag]` icon button:
   - Color-coded pill list (`#urgent`, `#finance`, `#q4-launch`, etc.); clicking a tag toggles filtering the Center Stream by that tag.
4. **SYSTEM Section** (pinned to bottom of rail):
   - `Archived`
   - `Trash (30d)` + count badge

### 2.3 Center Task Stream
1. **View Header**:
   - Active View/List title, Shared Member Avatars stack + `[Share]` button (for custom lists), Density Toggle (`Comfortable` / `Compact`), and Sort indicator badge (`Priority → Due Date → Created → Title`).
2. **Multi-Facet Filter Bar**:
   - Collapsible horizontal bar with filter dropdowns: `Status` (multi-select), `Priority` (multi-select), `Tags` (multi-select), `Due Window` (`All`, `Overdue`, `Today`, `This Week`, `No Due Date`), `Assignee` (on shared lists), and `[Clear Filters]` link when any filter is active.
3. **Task Row / Card Component**:
   - **Left**: Custom circular Checkbox (`20px x 20px`) with distinct `BLOCKED` lock/amber state; clicking checkbox on a `BLOCKED` task opens the **Unblock-Before-Complete Micro-Prompt** instead of completing.
   - **Middle**:
     - Task Title (single-line truncated in Compact mode; up to 2 lines in Comfortable mode).
     - **Blocker Banner** (shown when `status === 'BLOCKED'`): Full-width amber sub-bar directly below title showing `ShieldAlert` icon + `blocker_reason` text.
     - **Metadata Row**: Priority chip (icon + label), Due Date chip (turns red if overdue), Recurrence icon + tooltip (`Every month on day 31 — Fixed`), Subtask Progress Pill (`✓ 3/5 (60%)`), Tag pills (up to 3 visible + `+N` overflow), Assignee mini-avatar.
   - **Right (on hover/focus)**: Quick action icons — `Set Priority`, `Block / Unblock`, `Move to Trash`.
   - **Selection state**: Clicking a task row highlights it with a `2px` brand-primary left border and opens the **Right Task Detail Drawer**.
4. **Completed Tasks Accordion**:
   - Collapsed by default (`> Completed Tasks (14)`) at the bottom of the stream; expanding reveals completed rows with completion timestamp and one-click reopen checkbox.

### 2.4 Right Task Detail Drawer (`420px` desktop)
1. **Drawer Header**: Breadcrumb (`List Name`), `Complete` / `Reopen` toggle button, `Archive` button, `Move to Trash` icon, and `Close (Esc)` button.
2. **Editable Title**: Auto-resizing textarea (`1..120 chars` with inline counter & validation error).
3. **Lifecycle Status Selector**:
   - Dropdown / segmented pills showing ONLY valid transitions from the current state (e.g., from `BLOCKED`, `COMPLETED` is visually disabled with tooltip *"Unblock this task before completing"*).
   - Selecting `BLOCKED` opens an inline required **`Blocker Reason`** textarea (`5..500 chars`) with `[Confirm Block]` and `[Cancel]`.
4. **Properties Grid**:
   - **Priority**: 4-tier selector (`URGENT`, `HIGH`, `MEDIUM`, `LOW`).
   - **List**: Dropdown of accessible lists (disabled for `VIEWER`).
   - **Due Date & Time**: Date picker + optional Time toggle (switches between `Date-Only` and `Due Timestamp` in user's local timezone).
   - **Recurrence Rule Builder**: Toggle `Repeat` → Frequency (`Daily`, `Weekly`, `Monthly`, `Custom Interval`), Mode radio (`Fixed Schedule` vs `On Completion`), and a live **"Next 3 Occurrences"** preview box (demonstrating month-end clamping e.g. `Jan 31 → Feb 28 → Mar 31`).
   - **Reminder**: Offset selector (`At due time`, `15m before`, `1h before`, `1 day before`, `Custom`).
   - **Assignee** (on shared lists): Dropdown of valid list members (`OWNER` and `EDITOR` members).
   - **Tags**: Multi-select tag combobox with `max 10 tags` counter (`4/10`) and inline create-new-tag option.
5. **Markdown Description Editor**:
   - Tabbed `Write` / `Preview` toggle, `2,000` character counter, sanitized HTML preview (no raw `<script>` execution).
6. **Subtasks Checklist (`0/20`)**:
   - Progress bar (`3/5 — 60%`) + ordered list of subtask rows with drag handle, checkbox, inline-editable title, and delete `X`.
   - Bottom `Add subtask...` input; when count reaches `20/20`, input disables with badge `"Maximum 20 subtasks reached"`.
7. **Comments & Immutable Activity Log Tabs**:
   - **Comments Tab**: Chronological comments list + composer supporting `@mention` autocomplete dropdown of shared list members.
   - **Activity Log Tab**: Read-only audit timeline (`Alex changed status from IN_PROGRESS to BLOCKED — "Waiting on CFO" · 10:14 AM`).

---

## 3. Critical Modals & Dialogs

| Modal / Dialog | Trigger | Key UI Elements & Guardrails |
| :--- | :--- | :--- |
| **Unblock-Before-Complete Prompt** | Clicking checkbox or pressing `C` on a `BLOCKED` task | Displays current `blocker_reason`, offers `[Move to In Progress]` or `[Move to Todo]` (never direct complete). |
| **Parent Completion Cascade Dialog** | Completing a task that has `>= 1` incomplete subtasks | Message: *"This task has N open subtasks. Mark all N subtasks as completed?"* with `[Complete All]` and `[Cancel]`. |
| **Safe List Deletion Modal** | Clicking `Delete List` on a custom list with tasks | Mandatory radio choice (neither pre-selected): `( ) Move N tasks to Inbox` OR `( ) Move N tasks to Trash (30-day recovery)` + `[Confirm Delete]` (disabled until a mode is chosen). |
| **Shared List RBAC Modal** | Clicking `Share` on a custom list (`OWNER` only) | Invite by email + Role dropdown (`EDITOR`, `VIEWER`), current members table with role switcher & remove button, clear permission summary table. |
| **Data Export & Import Modal** | User Menu → `Export / Import Data` | Export buttons (`Download JSON`, `Download CSV`) + Drag-and-drop file upload for JSON/CSV import with pre-import validation summary. |
| **Settings & Quiet Hours Modal** | User Menu → `Settings` | Theme (`Light`/`Dark`/`System`), Local Timezone selector, Quiet Hours toggle + Start/End time pickers (`22:00 – 07:00` default), Account Erasure (GDPR) danger zone. |
| **Keyboard Shortcuts Cheat Sheet** | Pressing `?` anywhere outside an input | Two-column modal listing `N`, `/`, `C`, `1–4`, `J/K` (next/prev task), `Enter` (open drawer), `Esc` (close drawer/modal), `Delete` (Trash). |

---

## 4. Role-Based UI Rendering Matrix (Shared Lists)

| UI Control | `OWNER` | `EDITOR` | `VIEWER` |
| :--- | :---: | :---: | :---: |
| View tasks, subtasks, comments, activity log | Yes | Yes | Yes |
| Quick-Add / Create task in list | Yes | Yes | Hidden |
| Edit task fields, status, subtasks, tags | Yes | Yes | Read-only (disabled inputs + `"View-only access"` banner) |
| Post comments & `@mention` members | Yes | Yes | Disabled (`"Viewers cannot post comments"`) |
| Share list / Manage members & roles | Yes | Hidden | Hidden |
| Rename / Delete list | Yes | Hidden | Hidden |
