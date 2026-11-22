# Initial Customer Submission 01: Project Charter & Executive Vision Brief

**Submitted By**: Sarah Jenkins, VP of Digital Productivity (Customer Sponsor)  
**Submitted To**: Alex Mercer, Lead Technical Business Analyst (TBA)  
**Date Submitted**: November 10, 2026 *(Prior to Discovery Workshops 1–5)*  
**Subject**: Project Kickoff Intake — "FocusFlow" To-Do & Task Management Application  
**Document Reference**: `CUST-REQ-01`  

---

## 1. Executive Summary & Business Need

Our division needs to build **FocusFlow**, a modern, cross-platform (Web & Mobile-responsive) To-Do and Task Management application designed for both individual professionals and small collaborative teams.

Over the past 12 months, our customer feedback surveys (3,400 respondents) revealed two major frustrations with existing tools in the market:
1. **Simple consumer to-do apps are too shallow**: They only offer a flat list with a basic checkbox (`Done` / `Not Done`). As soon as a professional has 30+ tasks, they cannot tell which tasks are actively being worked on, which tasks are **blocked waiting on someone else**, or which tasks are overdue priorities.
2. **Enterprise project trackers (Jira, Asana, Monday) are too slow and heavy**: Adding a simple daily task takes 6–10 clicks across mandatory form fields, discouraging users from capturing quick action items during meetings.

### Our Core Value Proposition
> **"Capture a task in 2 seconds; organize, track blockers, and collaborate when you need structure."**

---

## 2. Target Customer Segments

We expect the TBA to help us formalize these into detailed User Personas, but from a business standpoint we are targeting:
- **Individual Professionals / Freelancers**: Need a fast personal `"Inbox"`, a daily `"Today"` focus sheet, recurring habits/reminders, and simple sub-checklists.
- **Small Operational & Project Teams (2–25 people)**: Need to share specific task lists (like *"Client Onboarding"*, *"Monthly Close"*, or *"Product Launch"*), assign tasks to teammates, leave `@mention` updates, and immediately see which tasks are **Blocked** and why.

---

## 3. High-Level Business Goals & Success Metrics (KPIs)

| Business Goal | Target Metric (90 Days Post-Launch) |
| :--- | :--- |
| **Instant Task Capture** | Median time to create a new task via Quick-Add `< 2.0 seconds` |
| **Daily Habit Engagement** | `>= 65%` of active users review their `"Today"` view at least 5 days/week |
| **Team Blocker Visibility** | `>= 80%` reduction in "silently stalled" team tasks via explicit `Blocked` tracking |
| **Zero Accidental Data Loss** | `100%` of accidentally deleted tasks recoverable by the user via a self-service Trash bin |
| **Customer Retention & Portability** | Full CSV/JSON export & import so customers trust they own their data |

---

## 4. Initial Functional Scope Requested by Executive Sponsor

At a high level, the v1.0 application must deliver:
1. **User Accounts & Personal Workspace**:
   - Secure sign-up and login.
   - A permanent default `"Inbox"` list where rapid tasks land automatically.
2. **Rich To-Do Tasks**:
   - Title, rich notes/description, due date (with optional specific time), priority level (Low, Medium, High, Urgent), and custom tags.
   - Multi-step status workflow: not just "Open/Done", but also "In Progress", "Blocked" (with a reason!), and "Archived".
   - Checklists / Subtasks inside a task so users can break a task into smaller steps.
3. **Lists, Smart Views & Search**:
   - Custom project lists with colors/icons.
   - Automatic views for `"Today"`, `"Upcoming"`, `"Overdue"`, and `"Blocked"`.
   - Fast keyword search and filtering by tag, priority, and status.
4. **Recurring Tasks & Reminders**:
   - Ability to repeat tasks daily, weekly, monthly, or on custom intervals.
   - Notifications/reminders before a task is due, with ability to snooze.
5. **Team Sharing & Collaboration**:
   - Share any custom list with teammates as either an **Editor** or a read-only **Viewer**.
   - Assign tasks to list members and post comments.

---

## 5. Open Questions for the TBA Discovery Workshops

Alex, during our upcoming 5-hour workshop series, we need your help translating this business brief into concrete rules for the Development and QA teams—specifically:
- Exact character limits, default values, and error messages for every field.
- Which status transitions should be allowed or blocked (especially around `Blocked` and `Archived` tasks).
- What happens to tasks when a user deletes a project list or removes a teammate.
- How recurring tasks behave when completed late or scheduled at the end of a month (like the 31st).
