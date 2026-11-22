# Workshop 4 Transcript: Recurring Tasks Engine, Due Dates, Timezones & Reminders

**Project Name**: FocusFlow — Enterprise & Personal To-Do Application  
**Artifact ID**: `TBA-WS-04`  
**Date**: November 19, 2026 | **Time**: 09:00 – 10:00 (Duration: 60 Minutes)  
**Location**: Conference Room B / Hybrid Recording  

## Attendees
- **Alex Mercer (TBA)**: Lead Technical Business Analyst  
- **Sarah Jenkins (Customer — Product Sponsor)**: VP of Digital Productivity  
- **Marco Rossi (Customer — Power User Representative)**: Operations Team Lead  
- **Elena Lin (Customer — UX & Customer Advocacy Lead)**: Principal Product Designer  

---

## Session Transcript (00:00 – 60:00)

**[00:00] Alex Mercer (TBA):**  
Good morning everyone, and welcome to **Workshop 4 of 5**. Today in **Hour 4 (`00:00 – 60:00`)**, we are diving into time, recurrence, and notifications—where 80% of date/time bugs happen if requirements aren't specified down to the exact boundary condition:
1. Due Dates, Optional Due Times & User Timezone Handling (`00:00 – 15:00`)
2. The Recurring Tasks Engine (`DAILY`, `WEEKLY`, `MONTHLY`, `CUSTOM_INTERVAL`) (`15:00 – 32:00`)
3. Recurrence Regeneration Modes (*Fixed Schedule* vs. *After Completion*) & Calendar Edge Cases (Jan 31 → Feb 28/29) (`32:00 – 46:00`)
4. Reminders, Snooze Rules & Quiet Hours (`46:00 – 60:00`)

Elena, let’s start with **Due Dates and Timezones**. Can a user set a date-only due date (like `"Due Nov 25"`) as well as a specific date-and-time (`"Due Nov 25 at 14:30"`), and how does timezone travel affect them?

**[02:15] Elena Lin (Customer — UX Lead):**  
Yes! Users think in two modes:
1. **Date-Only Due Date (`has_due_time = false`)**: For example, `"Submit expense report — Due Nov 25"`. That task is due at the **end of that calendar day (`23:59:59`) in the user's current profile timezone** (e.g., `America/New_York` or `Europe/Athens`). It does *not* become overdue until `23:59:59` local time on Nov 25 has passed!
2. **Date-and-Time Due Timestamp (`has_due_time = true`)**: For example, `"Call client — Due Nov 25 at 14:30"`. That task has an exact UTC timestamp `due_at` and becomes overdue the moment `14:30:00` passes (`now_utc > due_at`).

**[07:30] Alex Mercer (TBA):**  
What if a user tries to create a new task with a `due_at` in the past? Should we block it or allow it?

**[08:15] Marco Rossi (Customer — Power User):**  
**Allow it with a visual overdue indicator**—do *not* block past due dates on task creation or edit! Why? Because often I am logging an item that was actually due yesterday so I can track that it's overdue and check it off once done. However, as we’ll discuss in segment 4, a *reminder notification* timestamp (`remind_at`) must be in the future when set.

**[15:00] Alex Mercer (TBA):**  
That distinction—`due_at` can be in the past (immediately marking the task `is_overdue = true`), whereas a newly scheduled `remind_at` must be in the future—is crystal clear.  
Now let’s move to segment 2 (`15:00 – 32:00`): **The Recurring Tasks Engine**.  
Sarah and Marco, how do recurring tasks work in FocusFlow? When I create a recurring task like `"Pay monthly cloud invoice"`, does the system pre-create 100 future rows in the database, or does it spawn the next instance dynamically?

**[16:20] Sarah Jenkins (Customer — Product Sponsor):**  
**Never pre-populate hundreds of future task rows in the database!** That clutters search results and ruins task counts.  
Instead, a recurring task is a single active task with a `recurrence_rule` object attached to it. **When the user marks the current occurrence `COMPLETED`, the system immediately generates the next single occurrence (`status = TODO`)** according to the `recurrence_rule`.

**[20:10] Alex Mercer (TBA):**  
Let’s define the exact schema of `recurrence_rule`:
1. **`frequency`**: What frequencies must we support?
2. **`interval`**: e.g., every `1` week, every `2` weeks, every `3` months.
3. **`days_of_week`**: For weekly recurrences (e.g., `["MON", "WED", "FRI"]`).
4. **`day_of_month`**: For monthly recurrences (`1..31` or `"LAST_DAY"`).
5. **`end_condition`**: Can a recurrence end after a specific date (`ends_on_date`) or after `N` occurrences (`max_occurrences`)?

**[22:40] Marco Rossi (Customer — Power User):**  
Yes, we need four `frequency` types:
- **`DAILY`**: Repeats every `interval` days (`interval >= 1`, e.g., every 1 day, every 3 days).
- **`WEEKLY`**: Repeats every `interval` weeks on specified `days_of_week` (e.g., every 1 week on `MON, THU`).
- **`MONTHLY`**: Repeats every `interval` months on either a specific day number (`1..31`) or `"LAST_DAY"` of the month.
- **`YEARLY`**: Repeats every `interval` years on the same month and day.
And for ending a recurring series:
- Optional `ends_on_date` (ISO date) and optional `max_occurrences` (integer `>= 1`). Once the occurrence counter reaches `max_occurrences` or the next calculated due date exceeds `ends_on_date`, completing the final task does **not** spawn a new task.

**[32:10] Alex Mercer (TBA):**  
Now let’s cover segment 3 (`32:00 – 46:00`): **Recurrence Regeneration Modes & Calendar Edge Cases**.  
In productivity tools, there are two fundamentally different kinds of recurring tasks:
- **Type 1 (`"FIXED_SCHEDULE"` — e.g., "Pay rent on the 1st of every month")**: Even if I pay the November 1st rent late on November 5th, the next rent is still due on **December 1st** (based on the *original due date*).
- **Type 2 (`"ON_COMPLETION"` — e.g., "Water office plants every 7 days" or "Get haircut every 30 days")**: If I was supposed to water the plants on Monday, but I didn't actually water them until Thursday, the next watering should be **7 days from Thursday** (based on the *actual `completed_at` timestamp*)!

Do we need to support both regeneration modes?

**[34:50] Sarah Jenkins (Customer — Product Sponsor):**  
**Yes! Supporting both `"FIXED_SCHEDULE"` and `"ON_COMPLETION"` is a huge differentiator for FocusFlow.**
- **`anchor_mode = "FIXED_SCHEDULE"` (Default)**: Next `due_at` is calculated by adding the recurrence interval to the completed task's **`due_at`** (if that calculated date is still in the past because the user missed multiple cycles, advance forward by intervals until `next_due_at >= today`).
- **`anchor_mode = "ON_COMPLETION"`**: Next `due_at` is calculated by adding the recurrence interval to the completed task's **`completed_at`** timestamp!

**[38:45] Alex Mercer (TBA):**  
And when the next occurrence of a recurring task is spawned upon completion, what properties are copied over from the completed task to the new task occurrence?
- Specifically: what happens to **Subtasks**, **Tags**, **Priority**, **Description**, and **Comments**?

**[40:00] Marco Rossi (Customer — Power User):**  
Great question:
- **Copied over as-is**: `title`, `description`, `list_id`, `priority`, `tags`, `assignee_id`, and `recurrence_rule` (with `occurrence_count` incremented by 1).
- **Subtasks are copied AND reset**: All subtasks are cloned to the new task occurrence, with every subtask's **`is_completed` reset back to `false`**! (So my `"Monthly Payroll Checklist"` spawns next month's task with all 8 checklist items unchecked and ready to go).
- **Comments are NOT copied**: Comments belong only to the historical completed occurrence.
- **Duplicate Spawn Guard**: What if a user marks a recurring task `COMPLETED` (which spawns Occurrence #2), then immediately clicks "Undo" / re-opens Occurrence #1 and completes it again? The system must link `spawned_next_task_id` on Occurrence #1 so it **never spawns duplicate next occurrences** if toggled twice!

**[43:50] Alex Mercer (TBA):**  
And what about the **Monthly End-of-Month Calendar Rollover Edge Case**? Suppose a monthly recurring task is scheduled for `day_of_month = 31` (e.g., January 31st). When January 31st is completed, February only has 28 days (or 29 in a leap year). What date should the February occurrence be scheduled for, and what happens in March?

**[44:45] Elena Lin (Customer — UX Lead):**  
Clamp to the **last valid day of the target month** without losing the original `day_of_month = 31` anchor in `recurrence_rule`!
- So **Jan 31** → rolls to **Feb 28** (or **Feb 29** in a leap year: 2028 is a leap year, 2026 is not).
- Then when the **Feb 28** task is completed, because `recurrence_rule.day_of_month` is still `31`, the March occurrence is scheduled for **Mar 31** (not Mar 28)!

**[46:15] Alex Mercer (TBA):**  
That `Jan 31 -> Feb 28 -> Mar 31` clamping rule is a classic QA boundary test (`TC-xxx`).  
Now in our final 14 minutes (`46:00 – 60:00`), let’s cover **Reminders, Snooze Presets & Quiet Hours**.

**[47:10] Elena Lin (Customer — UX Lead):**  
Here is how **Reminders** work:
1. A user can attach up to **3 reminders** per task (either an absolute UTC timestamp `remind_at` or a relative offset before `due_at`, such as `15 minutes before`, `1 hour before`, `1 day before`).
2. **Validation**: A newly created reminder must have `remind_at > current_utc_timestamp` (`HTTP 422 / ERR_REMINDER_IN_PAST` otherwise).
3. **Auto-Cancellation**: If a task is marked **`COMPLETED`**, **`ARCHIVED`**, or **Soft-Deleted (`is_deleted = true`)** before its reminder fires, all pending reminders for that task must be **automatically cancelled** (`status = CANCELLED`). Nobody wants a reminder ping at 5 PM for a task they already finished at 2 PM!
4. **Snoozing a Fired Reminder**: When a reminder notification fires, the user can click **Dismiss** or **Snooze** with three presets:
   - `+15 minutes`
   - `+1 hour`
   - `Tomorrow at 09:00 (user local timezone)`
5. **Quiet Hours (Do Not Disturb)**:
   - Users can enable Quiet Hours in their profile (default: **`22:00` to `07:00` local time**).
   - During Quiet Hours, non-urgent reminders are held/muted from push/sound alerts and delivered in the morning digest at `07:00`, **except** tasks with **`priority == URGENT`** where the user checked `"Override Quiet Hours for Urgent Tasks"`.

**[59:30] Alex Mercer (TBA):**  
That wraps up Hour 4 with complete precision on timezones, recurring task regeneration (`FIXED_SCHEDULE` vs `ON_COMPLETION`), subtask resetting on recurrence, the Jan 31 → Feb 28 → Mar 31 calendar clamp, and reminder snooze/cancellation rules. In our final session tomorrow—**Workshop 5**—we will cover **Team Collaboration, Permissions (`OWNER`, `EDITOR`, `VIEWER`), Activity Logs, Data Import/Export, Non-Functional Requirements, and MVP Scope Sign-off**.
