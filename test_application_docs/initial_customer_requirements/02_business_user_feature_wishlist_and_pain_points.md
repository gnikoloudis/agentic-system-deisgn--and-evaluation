# Initial Customer Submission 02: Business User Feature Wishlist & Operational Pain Points

**Submitted By**: Marco Rossi, Operations Team Lead (Business Power-User Representative)  
**Submitted To**: Alex Mercer, Lead Technical Business Analyst (TBA)  
**Date Submitted**: November 11, 2026 *(Prior to Discovery Workshops 1–5)*  
**Subject**: What Our Daily Users Actually Need in the FocusFlow To-Do App  
**Document Reference**: `CUST-REQ-02`  

---

## 1. Day-in-the-Life Operational Pain Points (Why Our Current Setup Fails)

Alex, ahead of our workshops next week, I polled 45 daily task-list users across Operations, Account Management, and Finance. Here are the real-world frustrations we need FocusFlow to solve:

1. **"I lose ideas during phone calls because creating a task takes too long."**
   - Users want a single bar at the top where they type a sentence, hit `Enter`, and the task is saved immediately with sensible defaults.
2. **"People check off tasks that are actually blocked!"**
   - In our current tool, someone marks a task as "Blocked" in a tag, and then another teammate accidentally clicks the Done checkbox without resolving the blocker.
   - Furthermore, people mark tasks as "Blocked" without writing *why* they are blocked or who they are waiting on! We need the app to **force** the user to write a short explanation whenever they mark a task as Blocked, and **prevent** someone from checking it off as Completed until it is unblocked.
3. **"Subtasks get out of sync with the main task."**
   - Users want simple checklists inside a task (no crazy multi-level trees, just 15–20 checklist items max).
   - They want to see `3 / 5 done` right on the main task card. And if someone marks the main task as Completed, the checklist items shouldn't stay half-unchecked.
4. **"Recurring tasks are broken in half the apps we tried."**
   - First problem: Some apps create 365 duplicate rows in the database as soon as you set a daily recurring task, ruining search results. We only want the *next* task created when you finish the current one!
   - Second problem: We have two different types of repeating tasks:
     - **Strict Calendar Deadlines** (e.g., *"Submit monthly payroll on the 1st"*): Even if I finish November's payroll late on Nov 3rd, December's payroll must still be due on **Dec 1st**.
     - **Rolling Maintenance Tasks** (e.g., *"Clean coffee machine every 14 days"*): If I clean it 4 days late on Friday, the next cleaning should be due **14 days from Friday**, not 10 days later!
   - Third problem: When a recurring task with a checklist spawns next month's copy, the checklist items on the new copy must all start **unchecked** again!
5. **"Deleting a project folder wiped out 40 tasks by mistake."**
   - Last month a coordinator deleted an old project folder, and it permanently nuked 40 active tasks inside it.
   - If someone deletes a list, the safest default should be moving its tasks back to `"Inbox"` (unless they explicitly ask to trash the tasks too). And any deleted task must sit in a **Trash bin for 30 days** so we can restore it!

---

## 2. Raw Business User Wishlist (Prioritized by User Vote)

### Must-Have Features for Launch
- **Quick-Add Bar**: Title only required; defaults to `TODO` status, `Medium` priority, and `"Inbox"` list.
- **Rich Task Details**: Markdown notes (for links and bullet points), Priority (`Low`, `Medium`, `High`, `Urgent`), Due Date + optional Due Time, List assignment, and up to 10 color-coded `#tags`.
- **Smart Sorting**: Put **Overdue** tasks at the very top automatically, then sort by Priority (`Urgent` down to `Low`), then by earliest Due Date.
- **4 Essential Smart Views**:
  1. `Today` (everything due today PLUS anything overdue from earlier days).
  2. `Upcoming` (next 7 days).
  3. `Overdue` (only open tasks whose due date/time has passed—never show completed tasks as overdue!).
  4. `Blocked` (all blocked tasks across every project with their blocker reason clearly visible).
- **Shared Project Lists**:
  - Share a list with teammates.
  - Some people (`Editors`) need to add/edit/check off tasks; other stakeholders (`Viewers` like executives) should only be able to read the list without accidentally changing anything.
  - Ability to assign a task to a teammate on the list and `@mention` them in task comments.
- **CSV & JSON Export/Import**:
  - Managers need to export a project list to `.csv` for Excel reporting, or `.json` for full backup.
