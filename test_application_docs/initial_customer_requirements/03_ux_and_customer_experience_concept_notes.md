# Initial Customer Submission 03: UX, Interface Layout & Accessibility Concept Notes

**Submitted By**: Elena Lin, Principal Product Designer (Customer UX Lead)  
**Submitted To**: Alex Mercer, Lead Technical Business Analyst (TBA)  
**Date Submitted**: November 12, 2026 *(Prior to Discovery Workshops 1–5)*  
**Subject**: Initial UX Wireframe Concepts, Interaction Patterns & Accessibility Requirements  
**Document Reference**: `CUST-REQ-03`  

---

## 1. Application Layout & Navigation Concept

FocusFlow should use a clean, distraction-free **3-Pane Workspace Layout**:

```text
+-----------------------------------------------------------------------------------+
| Top Bar: [Quick-Add Input ("Press 'N' to add task...")]   [Search '/']  [Profile] |
+----------------------+------------------------------------+-----------------------+
| Left Navigation Rail | Center Task List Stream            | Right Task Detail     |
|                      |                                    | Drawer (Collapsible)  |
| SMART VIEWS          | [Filter Bar: Status | Priority |   |                       |
|  * Inbox        (4)  |              Tags   | Due Date ]   | Title (Editable)      |
|  * Today        (7)  |                                    | Status Pill & Blocker |
|  * Upcoming     (12) | > OVERDUE / ACTIVE TASKS           | Priority & Due Date   |
|  * Overdue      (2)  |   [ ] Fix API auth  [URGENT] [Red] | Recurrence & Reminder |
|  * Blocked      (1)  |   [ ] Q4 Budget     [BLOCKED]      | Tags [#finance]       |
|                      |       "Waiting on CFO sign-off"    |                       |
| CUSTOM LISTS   [+]   |   [ ] Send deck     [HIGH]  (2/4)  | Markdown Description  |
|  * Work Launch  (9)  |                                    |                       |
|  * Personal     (5)  | > COMPLETED TASKS (Collapsed: 14)  | Subtasks (2/4 - 50%)  |
|                      |   [x] Setup repo    (Done 10:15am) |  [x] Step 1           |
| SYSTEM               |                                    |  [ ] Step 2           |
|  * Archived          |                                    |                       |
|  * Trash (30d)       |                                    | Comments & Audit Log  |
+----------------------+------------------------------------+-----------------------+
```

---

## 2. Key UX Interaction Requirements

### 2.1 Keyboard-First Productivity
Power users expect to navigate without touching the mouse:
- `N`: Focus the Quick-Add task input bar.
- `Enter`: Submit Quick-Add task.
- `/`: Focus the global Search & Filter bar.
- `C`: Mark the currently focused task as `COMPLETED` (or show the Unblock prompt if the task is currently `BLOCKED`).
- `1`, `2`, `3`, `4`: Set focused task priority to `URGENT (1)`, `HIGH (2)`, `MEDIUM (3)`, or `LOW (4)`.
- `Delete` / `Backspace`: Move focused task to Trash (with a 10-second `"Undo"` toast banner at the bottom of the screen).

### 2.2 Visual Feedback & Optimistic UI
- Checking off a task or subtask must visually respond immediately (`< 16 ms` optimistic UI update).
- If a task is in **`BLOCKED`** status:
  - Display an amber/red border and an inline banner on the task card showing the `blocker_reason`.
  - Disable one-click direct completion from `BLOCKED`; clicking the checkbox opens a micro-prompt asking the user to unblock the task first.
- If a task has **Subtasks**:
  - Show a compact progress pill on the task row: e.g., `[✓ 3/5 (60%)]`.

### 2.3 Reminder Notifications & Quiet Hours UX
- Users hate notification spam late at night.
- Provide a **Quiet Hours (Do Not Disturb)** toggle in User Settings (defaulting to `22:00 – 07:00` in the user's local timezone).
- When a reminder banner pops up, offer one-click **Snooze** buttons:
  - `Snooze 15m`
  - `Snooze 1h`
  - `Tomorrow 9:00 AM`

### 2.4 Accessibility (WCAG 2.1 Level AA)
- Minimum color contrast ratio of `4.5:1` for all text and priority/status badges (never rely on color alone—pair every priority color with a distinct icon and text label).
- Full ARIA screen-reader announcements when tasks are created, completed, blocked, or moved to Trash.
