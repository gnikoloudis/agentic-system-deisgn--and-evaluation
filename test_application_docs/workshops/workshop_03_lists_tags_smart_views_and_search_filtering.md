# Workshop 3 Transcript: Custom Lists, Tags, Smart Views & Multi-Facet Search/Filtering

**Project Name**: FocusFlow — Enterprise & Personal To-Do Application  
**Artifact ID**: `TBA-WS-03`  
**Date**: November 18, 2026 | **Time**: 09:00 – 10:00 (Duration: 60 Minutes)  
**Location**: Conference Room B / Hybrid Recording  

## Attendees
- **Alex Mercer (TBA)**: Lead Technical Business Analyst  
- **Sarah Jenkins (Customer — Product Sponsor)**: VP of Digital Productivity  
- **Marco Rossi (Customer — Power User Representative)**: Operations Team Lead  
- **Elena Lin (Customer — UX & Customer Advocacy Lead)**: Principal Product Designer  

---

## Session Transcript (00:00 – 60:00)

**[00:00] Alex Mercer (TBA):**  
Good morning team, and welcome to **Workshop 3 of 5**. In Workshops 1 and 2, we defined the Task entity, subtasks, soft-delete trash rules, the 5-state lifecycle machine (`TODO`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `ARCHIVED`), and the 4-tier priority sorting engine.  
Today in **Hour 3 (`00:00 – 60:00`)**, we are designing how users organize and find their tasks at scale:
1. Custom Lists / Projects & List Deletion Rules (`00:00 – 18:00`)
2. Color-Coded Tags / Labels & Tagging Constraints (`18:00 – 32:00`)
3. Built-In Smart Views (`Today`, `Upcoming 7 Days`, `Overdue`, `Blocked`) (`32:00 – 47:00`)
4. Full-Text Search & Multi-Facet Filter Combinations (`47:00 – 60:00`)

Sarah, let’s start with **Lists (also known as Projects or Folders)**. Aside from the built-in `"Inbox"` list we established in Workshop 1, how do Custom Lists work?

**[02:20] Sarah Jenkins (Customer — Product Sponsor):**  
Users organize their life and work into Custom Lists—like `"Q4 Marketing Launch"`, `"Home Renovation"`, or `"Weekly Groceries"`.  
Here are the business rules for **Lists**:
- **Fields**: `list_id` (UUID), `owner_id` (UUID), `name` (required, **1 to 60 characters** after trimming), `color_hex` (valid 6-digit hex color code like `#6366F1`, defaults to `#3B82F6`), `icon_name` (optional string identifier), `is_system_inbox` (boolean), and `sort_order` (integer).
- **Uniqueness**: Within a single user's owned lists, list names must be **case-insensitively unique**. You cannot create two lists both named `"Work"` and `"work"` (`HTTP 409 / ERR_DUPLICATE_LIST_NAME`).
- **Workspace Capacity Limit**: A user can create up to **50 custom lists** (excluding the system `"Inbox"`). Attempting to create a 51st list returns `HTTP 422 / ERR_MAX_LISTS_EXCEEDED`.

**[09:45] Alex Mercer (TBA):**  
Now here is a classic business analysis edge case: **What happens to the tasks inside a Custom List when the user deletes that Custom List?**
Do the tasks inside that list get soft-deleted into Trash, OR do they get moved to `"Inbox"`?

**[10:30] Marco Rossi (Customer — Power User):**  
We debated this with our user panel, and we need **an explicit choice with a safe default**:
- First, the system **`"Inbox"` list can never be deleted** (`HTTP 403 / ERR_CANNOT_DELETE_SYSTEM_INBOX`).
- Second, when a user deletes a Custom List, the API accepts a parameter `on_tasks_action` with two valid modes:
  1. **`"move_to_inbox"` (Default)**: All non-deleted tasks currently belonging to that list have their `list_id` automatically reassigned to the owner's system `"Inbox"` list, and the custom list itself is deleted. That way no tasks are accidentally lost!
  2. **`"soft_delete_tasks"`**: If the user explicitly checks *"Also move all tasks in this list to Trash"* in the confirmation dialog, all tasks in that list are soft-deleted (`is_deleted = true`, `deleted_at = now_utc()`) and the custom list is deleted.

**[16:20] Alex Mercer (TBA):**  
That is a rock-solid requirement. Supporting `on_tasks_action = "move_to_inbox" | "soft_delete_tasks"` (defaulting to `"move_to_inbox"`) gives both safety and flexibility.  
Let’s move to segment 2 (`18:00 – 32:00`): **Tags / Labels**.  
Elena, how do Tags differ from Lists, and what are their rules?

**[18:30] Elena Lin (Customer — UX Lead):**  
A task can only belong to **one List** (`list_id`), whereas Tags are **many-to-many cross-cutting labels** that span across lists—for example, `#deep-work`, `#5-min-quick-win`, `#waiting-on-client`, or `#tax-deductible`.
Here are the rules for **Tags**:
- **Tag Name Format**:
  - Must be **1 to 30 characters** after trimming.
  - Normalized to **lowercase**, allowed characters: alphanumeric, hyphens (`-`), and underscores (`_`)—matching regex `^[a-z0-9_-]{1,30}$`. (If a user types `"#Deep Work"`, normalize or validate it as `"deep-work"`).
- **Tag Color**: Each tag has a `color_hex` (default `#10B981`).
- **Limits**:
  - A single task can have at most **10 tags** attached to it (`HTTP 422 / ERR_MAX_TAGS_PER_TASK` if `> 10`).
  - A workspace can have up to **200 unique tags**.
- **Deleting a Tag**: When a user deletes a tag from their workspace tag manager, it is cleanly detached from all tasks that referenced it without modifying or deleting the tasks themselves.

**[28:50] Alex Mercer (TBA):**  
What if a user attaches the exact same tag twice to a single task (e.g., `["urgent", "URGENT"]`)?

**[29:25] Marco Rossi (Customer — Power User):**  
Since tag names are normalized to lowercase, the backend must automatically deduplicate the tag list on the task so `"urgent"` is only attached once.

**[32:00] Alex Mercer (TBA):**  
Now let’s move to segment 3 (`32:00 – 47:00`): **Built-In Smart Views**.  
Elena, in the left navigation rail of FocusFlow, above the user's Custom Lists, what Smart Views appear automatically, and what are the exact query predicates for each Smart View?

**[33:15] Elena Lin (Customer — UX Lead):**  
We have four mandatory Smart Views in the sidebar, plus badge counters showing how many tasks match each view:
1. **`"Today"` Smart View**:
   - Shows all active tasks (`status IN ('TODO', 'IN_PROGRESS', 'BLOCKED')` and `is_deleted = false`) where:
     - `due_at` falls on **Today** in the user's configured timezone (`start_of_today <= due_at <= end_of_today`), **OR**
     - The task is **Overdue** (`due_at < start_of_today`)—because if you didn't finish yesterday's due task, it still needs your attention today!
2. **`"Upcoming (Next 7 Days)"` Smart View**:
   - Shows all active tasks (`is_deleted = false`, `status NOT IN ('COMPLETED', 'ARCHIVED')`) where `due_at` is between **now** and **end of day + 7 calendar days** (`now <= due_at <= end_of_day(today + 7 days)`), grouped day-by-day.
3. **`"Overdue"` Smart View**:
   - Shows all active tasks (`status IN ('TODO', 'IN_PROGRESS', 'BLOCKED')` and `is_deleted = false`) where `due_at` is strictly in the past (`due_at < current_timestamp`).
   - Note: `COMPLETED` and `ARCHIVED` tasks are **never** considered overdue, even if their historical `due_at` is in the past.
4. **`"Blocked"` Smart View**:
   - Shows all active tasks across all lists where `status == 'BLOCKED'` and `is_deleted = false`, displaying each task's `blocker_reason` and how many days/hours it has been blocked.

**[44:10] Sarah Jenkins (Customer — Product Sponsor):**  
Let’s emphasize that rule Elena just mentioned for QA testing: **A `COMPLETED` or `ARCHIVED` task must NEVER appear in the `"Overdue"` Smart View or trigger an overdue badge**, even if `completed_at > due_at` or `due_at < now`. Only open tasks (`TODO`, `IN_PROGRESS`, `BLOCKED`) can be Overdue.

**[47:00] Alex Mercer (TBA):**  
Now in our final 13 minutes of Workshop 3 (`47:00 – 60:00`), let’s specify **Search & Multi-Facet Filtering**.  
Marco, when you search and filter across your tasks, how should multiple filters combine?

**[48:15] Marco Rossi (Customer — Power User):**  
Users need a fast Search & Filter bar that supports combining any of the following query parameters simultaneously:
- **`q` (Keyword Search)**: Case-insensitive substring match across `title`, `description`, and `subtasks.title`.
- **`status` (Multi-select)**: e.g., `status=TODO,IN_PROGRESS`.
- **`priority` (Multi-select)**: e.g., `priority=HIGH,URGENT`.
- **`list_id`**: Filter to a specific list.
- **`tags` (Multi-select with `tag_match_mode`)**:
  - By default, if I select two tags (`tags=calls,urgent`), use **`AND` logic** (`tag_match_mode=all` — tasks that have *both* `#calls` AND `#urgent`).
  - Also support `tag_match_mode=any` (**`OR` logic** — tasks that have *either* `#calls` OR `#urgent`).
- **`due_before` & `due_after`**: ISO-8601 date range filter.

**[54:40] Alex Mercer (TBA):**  
So across *different* filter dimensions (e.g., `q` + `status` + `priority` + `list_id`), the filters combine with boolean **`AND`**, while within multi-select `status` or `priority` (e.g., `priority=HIGH,URGENT`) it matches `priority IN ('HIGH', 'URGENT')`, and `tags` supports both `all` (`AND`) and `any` (`OR`).  
What is our pagination and performance requirement on search/filter queries?

**[56:30] Sarah Jenkins (Customer — Product Sponsor):**  
Default page size is **50 tasks per page** (configurable up to 100 via `limit` and `offset`/cursor), and search queries across a workspace of up to 10,000 tasks must return in **under 150 milliseconds (p95)**.

**[59:45] Alex Mercer (TBA):**  
Everything for Lists, Tags, Smart Views, and Multi-Facet Search is clearly defined. Tomorrow in **Workshop 4**, we will tackle the most intricate temporal logic in any To-Do application: **Recurring Tasks, Timezones, End-of-Month Rollovers, and Reminder Notifications**.
