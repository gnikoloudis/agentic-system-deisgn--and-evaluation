# Initial Customer Submission 05: UI Design System, Brand Tokens & Responsive Architecture Brief

**Submitted By**: Elena Lin (Principal Product Designer) & Maya Patel (Frontend Engineering Lead)  
**Submitted To**: Alex Mercer, Lead Technical Business Analyst (TBA)  
**Date Submitted**: November 18, 2026 *(Prior to UI Discovery Workshops 6–7)*  
**Subject**: Visual Design System, Theme Tokens, Responsive Breakpoints & UI State Standards for FocusFlow  
**Document Reference**: `CUST-REQ-05`  

---

## 1. Visual Identity & Design Principles

FocusFlow's user interface must feel **calm, crisp, and instantaneous** — engineered for people who spend 6+ hours a day inside their task manager.

1. **Zero-Friction Capture**: Primary actions (`Quick-Add`, `Complete`, `Search`) are always one keypress or one click away without modal bloat.
2. **Clarity Over Decoration**: Visual hierarchy relies on crisp typography, subtle 1px borders, and intentional semantic color accents (never heavy gradients or noisy drop shadows).
3. **Color + Icon + Text Redundancy**: Every status and priority indicator MUST pair color with a distinct icon and text label (WCAG 2.1 AA compliance for color-blind users).
4. **Optimistic First**: User mutations update the UI in `< 16 ms` with graceful rollback and an actionable toast if the backend rejects the change.

---

## 2. Design Tokens (Light Mode & Dark Mode)

Both **Light Mode** (default for new users) and **Dark Mode** (plus `System` auto-detect) MUST be supported in v1.0, persisted in `localStorage` and synced to user preferences.

### 2.1 Surface & Text Color Palette

| Semantic Token | Light Mode Hex | Dark Mode Hex | Usage | Contrast Target |
| :--- | :---: | :---: | :--- | :--- |
| `--bg-canvas` | `#F8FAFC` | `#0B1120` | App outer background & Left Rail | Base surface |
| `--bg-surface` | `#FFFFFF` | `#111827` | Center Task Stream & Right Detail Drawer | Primary content |
| `--bg-elevated` | `#FFFFFF` | `#1E293B` | Modals, Dropdowns, Command Palette, Toasts | Elevated overlays |
| `--bg-subtle` | `#F1F5F9` | `#1E293B` | Hover rows, Filter pills, Input backgrounds | Secondary fill |
| `--border-default` | `#E2E8F0` | `#1F2937` | Pane dividers, Task card borders | Subtle 1px hairline |
| `--border-strong` | `#CBD5E1` | `#334155` | Active inputs, Secondary buttons | Interactive border |
| `--text-primary` | `#0F172A` | `#F8FAFC` | Task titles, Headings, Active labels | `>= 12:1` |
| `--text-secondary` | `#475569` | `#94A3B8` | Metadata, Due dates, Subtitles, Hints | `>= 5.5:1` |
| `--text-muted` | `#64748B` | `#64748B` | Placeholders, Timestamps, Disabled labels | `>= 4.5:1` |
| `--brand-primary` | `#4F46E5` | `#6366F1` | Primary CTA buttons, Active focus rings, Active nav pill | `>= 4.5:1` with white |
| `--brand-hover` | `#4338CA` | `#818CF8` | Primary CTA hover state | Interactive |

### 2.2 Semantic Priority & Lifecycle Status Tokens

| Entity | Value | Accent Color (Light / Dark) | Badge Background (Light / Dark) | Required Icon |
| :--- | :--- | :--- | :--- | :--- |
| **Priority** | `URGENT` | `#DC2626` / `#F87171` | `#FEF2F2` / `#450A0A` | AlertOctagon / Flame |
| **Priority** | `HIGH` | `#D97706` / `#FBBF24` | `#FFFBEB` / `#451A03` | ArrowUp |
| **Priority** | `MEDIUM` | `#2563EB` / `#60A5FA` | `#EFF6FF` / `#172554` | Minus / Equal |
| **Priority** | `LOW` | `#475569` / `#94A3B8` | `#F1F5F9` / `#1E293B` | ArrowDown |
| **Status** | `TODO` | `#475569` / `#CBD5E1` | `#F1F5F9` / `#1E293B` | Circle |
| **Status** | `IN_PROGRESS` | `#2563EB` / `#60A5FA` | `#EFF6FF` / `#172554` | Clock / PlayCircle |
| **Status** | `BLOCKED` | `#B45309` / `#FBBF24` | `#FEF3C7` / `#451A03` | ShieldAlert / Ban |
| **Status** | `COMPLETED` | `#059669` / `#34D399` | `#ECFDF5` / `#064E3B` | CheckCircle2 |
| **Status** | `ARCHIVED` | `#64748B` / `#94A3B8` | `#F1F5F9` / `#1E293B` | Archive |

### 2.3 Typography, Spacing & Radius Scale

- **UI Font Stack**: `'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif`
- **Monospace Font Stack**: `'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, monospace` (for keyboard shortcut badges `N`, `/`, `1–4`, task IDs, and JSON export previews)
- **Type Scale**:
  - `Page / View Title`: `20px` / `28px` line-height, `600` weight (`-0.01em` tracking)
  - `Section Header`: `12px` / `16px`, `700` weight, `UPPERCASE`, `0.06em` tracking
  - `Task Card Title`: `14px` / `20px`, `500` weight (strikethrough + muted when `COMPLETED`)
  - `Body / Description`: `14px` / `22px`, `400` weight
  - `Metadata / Chips`: `12px` / `16px`, `500` weight
  - `Micro Badges / Shortcut Keys`: `11px` / `14px`, `600` weight
- **Spacing Scale**: Strict `4px` base grid (`4, 8, 12, 16, 20, 24, 32, 48px`).
- **Border Radius**: `6px` (chips, inputs, buttons), `10px` (task cards, dropdown menus), `14px` (modals, dialogs).

---

## 3. Responsive Breakpoints & Adaptive 3-Pane Behavior

| Viewport Tier | Breakpoint | Left Navigation Rail | Center Task Stream | Right Task Detail Drawer |
| :--- | :--- | :--- | :--- | :--- |
| **Desktop Wide** | `>= 1280px` | Persistent (`256px` fixed width, collapsible to `64px` icon rail) | Fluid (`flex-1`, min `480px`) | Docked side pane (`420px` fixed when a task is selected; hidden when none selected) |
| **Laptop / Tablet Landscape** | `1024px – 1279px` | Persistent (`224px` width, collapsible) | Fluid (`flex-1`) | Slide-over overlay drawer (`400px` right-anchored with subtle backdrop) |
| **Tablet Portrait** | `768px – 1023px` | Hidden behind hamburger toggle (slide-over left drawer `260px`) | Full width (`100%`) | Slide-over overlay drawer (`420px` right-anchored) |
| **Mobile** | `< 768px` | Bottom navigation bar (`Inbox`, `Today`, `Lists`, `Search`) + drawer for extra views | Full width (`100%`), touch-friendly `44px` min tap targets | Full-screen modal sheet with back arrow header |

---

## 4. Task Density Modes & Motion Standards

- **Display Density Toggle** (in View Header):
  - **`Comfortable` (Default)**: `56px` min row height, displays blocker banner, tag chips, subtask progress pill, due date, and assignee avatar.
  - **`Compact`**: `40px` single-line row height for power users scanning 50+ tasks at once.
- **Motion & Reduced Motion**:
  - Drawer slide transitions: `180ms cubic-bezier(0.16, 1, 0.3, 1)`.
  - Task completion strikethrough & fade-to-completed-group: `220ms ease-out`.
  - MUST respect `@media (prefers-reduced-motion: reduce)` by disabling slide/bounce animations.

---

## 5. System UI States (Loading, Empty, Error, Offline)

1. **Loading States**: Shimmer skeleton rows (6 placeholder task rows matching active density mode) — never a blank white screen or blocking full-page spinner.
2. **Empty States**: Context-aware illustrations + concise CTA for every view:
   - `Inbox` empty: *"Inbox Zero — Press `N` to capture your next task."*
   - `Blocked` empty: *"No blocked tasks right now. Smooth sailing."*
   - `Search` zero results: *"No tasks match your active filters."* + `[Clear All Filters]` button.
   - `Trash` empty: *"Trash is empty. Deleted tasks stay here for 30 days before automatic purge."*
3. **Offline & Sync Indicator**:
   - When `navigator.onLine === false`, display a persistent subtle amber top strip: *"Offline mode — changes are saved locally and will sync automatically when reconnected (N pending)."*
4. **Toast Notification Stack** (Bottom-right on desktop, top-center on mobile, max 3 visible):
   - Delete / Trash toast: *"Moved 'Q4 Budget' to Trash."* + **`[Undo]`** button active for **10 seconds**.
   - Error / Rollback toast: Red left-border with clear API error message (e.g., *"Task title must be 1–120 characters"* or *"Cannot complete a Blocked task — unblock it first"*).
