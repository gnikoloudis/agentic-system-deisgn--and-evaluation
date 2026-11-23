# FocusFlow Discovery Workshop 06 — UI Design System, 3-Pane Layout, Theme Tokens & Navigation Flows

- **Session Date**: November 19, 2026 | **Duration**: 60 Minutes (`00:00 – 60:00`)
- **Facilitator**: Alex Mercer (Lead Technical Business Analyst)
- **Participants**:
  - **Elena Lin** — Principal Product Designer (Customer UX Lead)
  - **Maya Patel** — Frontend Engineering Lead
  - **Marcus Vance** — VP of Product (Executive Sponsor)
  - **David Kim** — QA Automation Lead

---

## Verbatim Transcript

**[00:00] Alex Mercer (Lead TBA):** Welcome everyone to Workshop 6. In Workshops 1 through 5 we locked down the backend domain rules, state machine, recurrence engine, and RBAC. Today and in Workshop 7, we are locking down the **Frontend UI requirements** so the engineering and QA teams can build and test the exact interface without guesswork. Let's start with `CUST-REQ-05`: the Design System, Themes, and the 3-Pane Workspace.

**[03:15] Elena Lin (UX Lead):** The #1 non-negotiable for FocusFlow's UI is visual calm and instant scannability. We want a strict **3-Pane Workspace** on desktop (`>= 1280px`): a `256px` Left Navigation Rail, a fluid Center Task Stream, and a `420px` Right Task Detail Drawer that only opens when a task is selected.

**[06:40] Maya Patel (Frontend Lead):** What happens on a `1024px` laptop screen when a user clicks a task? If we dock `256px + 420px` simultaneously, the center task list gets squeezed to `348px`, which breaks the metadata pills.

**[08:10] Elena Lin (UX Lead):** Great catch. Let's make that an explicit responsive rule:
- At `>= 1280px` (**Desktop Wide**): Left Rail (`256px`) and Right Detail Drawer (`420px`) are both docked side-by-side with the Center Stream (`min-width: 480px`).
- At `1024px – 1279px` (**Laptop / Tablet Landscape**): Left Rail stays docked (`224px`), and the Right Detail Drawer renders as a **right-anchored slide-over overlay** (`400px`) with a subtle translucent backdrop (`rgba(15,23,42,0.25)`), closing on `Esc` or backdrop click.
- At `768px – 1023px` (**Tablet Portrait**): Both Left Rail and Right Drawer are slide-over overlays.
- Below `768px` (**Mobile**): Left Rail becomes a **4-item Bottom Navigation Bar** (`Inbox`, `Today`, `Lists`, `Search`) with a `"More"` drawer for `Overdue`, `Blocked`, `Archived`, and `Trash`, and tapping a task opens a full-screen detail sheet.

**[14:20] Marcus Vance (VP of Product):** And what about Dark Mode? Almost 60% of our beta testers in the survey asked for Dark Mode on day one.

**[15:45] Elena Lin (UX Lead):** Yes — v1.0 MUST ship with **Light Mode**, **Dark Mode**, and **System** (`prefers-color-scheme`) theme modes, driven by CSS custom properties (`--bg-canvas`, `--bg-surface`, `--text-primary`, `--brand-primary`, etc.) as specified in `CUST-REQ-05`. Toggling the theme must apply instantaneously without a page reload and persist in `localStorage` so there is zero white flash on refresh.

**[19:30] David Kim (QA Lead):** For automated visual and accessibility testing, let's confirm the contrast rule. Every priority badge (`URGENT`, `HIGH`, `MEDIUM`, `LOW`) and status badge (`TODO`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `ARCHIVED`) must pass `4.5:1` contrast in **both** Light and Dark modes, AND never rely on color alone — each badge must show both an icon and a text label.

**[22:00] Elena Lin (UX Lead):** Confirmed 100%. Also, let's lock down the **Left Navigation Rail live badges**:
- `Inbox`, `Today`, `Upcoming (7 Days)`, and custom lists show their count of **non-completed, non-archived, non-trashed** tasks.
- `Overdue` shows a **red pill count** only when `count > 0` (hide the badge when `0` so the rail feels calm).
- `Blocked` shows an **amber pill count** only when `count > 0`.
- `Trash (30d)` shows the count of soft-deleted tasks currently recoverable.

**[27:10] Maya Patel (Frontend Lead):** What about task row density? Power users with 80 tasks in a list complained in beta interviews that tall cards require too much scrolling.

**[29:00] Elena Lin (UX Lead):** We'll put a **Density Toggle** (`Comfortable` vs `Compact`) right in the Center Stream header, persisted per user:
- **`Comfortable` (Default)**: `>= 56px` row height, shows Title, full-width amber Blocker Banner (if `BLOCKED`), Priority badge, Due Date chip, Recurrence icon, Subtask progress pill (`✓ 3/5 (60%)`), up to 3 Tag chips (+ `+N` overflow pill), and Assignee avatar.
- **`Compact`**: `40px` single-line row height, shows Checkbox, Title (truncated with ellipsis), Priority dot+icon, Due Date chip, and Subtask fraction (`3/5`). If a task is `BLOCKED`, it shows a compact amber `[BLOCKED]` badge whose tooltip reveals the `blocker_reason`.

**[35:30] Alex Mercer (Lead TBA):** Let's check the **Completed Tasks** section and **Multi-Facet Filter Bar** in the Center Stream.

**[37:00] Marcus Vance (VP of Product):** Completed tasks should NEVER clutter the active list. They must live in a **Completed Tasks Accordion** at the bottom of the stream, **collapsed by default** with a count header like `Completed (14)`. When a user checks off an active task, we show the strikethrough animation (`220ms`), display a subtle toast (`"Task completed"` with `[Undo]`), and move it into the collapsed Completed accordion.

**[41:15] Maya Patel (Frontend Lead):** And for the **Multi-Facet Filter Bar**: when a user applies filters (e.g., `Priority: URGENT, HIGH` + `Tag: #finance` + Search query `"invoice"`), all active filters must render as removable filter chips directly under the bar with a single `[Clear All]` button. Also, the active filter state should sync to URL query parameters (`?priority=URGENT,HIGH&tag=finance&q=invoice`) so refreshing the browser or sharing a link preserves the exact filtered view!

**[46:50] David Kim (QA Lead):** Love URL-synced filters — that makes E2E Playwright assertions deterministic too. What about **Loading, Empty, and Offline States**?

**[48:20] Elena Lin (UX Lead):**
1. **Loading**: Always render 6 shimmer skeleton rows matching the active density mode — never a centered blocking spinner.
2. **Empty States**: Every Smart View, Custom List, Search result, and Trash view must have a tailored empty state message and a primary action button (e.g., `[+ Add Task]` or `[Clear All Filters]`).
3. **Offline Banner**: Whenever the browser goes offline (`offline` event) or API requests queue locally in IndexedDB, show a persistent non-blocking amber banner below the Top Bar: *"You are offline — N change(s) queued and will sync automatically when reconnected."* with a `[Retry Sync]` button once connectivity returns.

**[54:00] Alex Mercer (Lead TBA):** Let's recap our locked-in UI decisions from Workshop 6:
1. Exact 4-tier responsive breakpoints (`>=1280px`, `1024–1279px`, `768–1023px`, `<768px`) with adaptive 3-Pane / Slide-Over / Bottom-Nav behavior.
2. Light, Dark, and System themes using semantic CSS variables with zero-flash persistence and `>= 4.5:1` WCAG AA contrast + icon+text badges.
3. Left Rail smart-view counters (`Overdue` red / `Blocked` amber hidden at `0`), Custom List drag-and-drop dropzones, and `Comfortable` vs `Compact` density modes.
4. Collapsed-by-default Completed Tasks accordion, URL-synced Multi-Facet Filter chips, Shimmer skeletons, Tailored Empty States, and Offline Sync Banner.

**[59:10] Marcus Vance (VP of Product):** Approved. Let's dive into all the interactive widgets, modals, keyboard navigation, and accessibility checks in Workshop 7!
