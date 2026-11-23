# FocusFlow To-Do Application — Stakeholder Intake, Workshop Transcripts & TBA Standards

This documentation package contains the complete business discovery inputs and Technical Business Analyst (TBA) role governance standards for the **FocusFlow To-Do Application**.

---

## 1. Initial Customer Requirements (`./initial_customer_requirements/`)

Raw intake documents submitted by the Customer Stakeholders prior to the discovery workshops:

1. `./initial_customer_requirements/01_customer_project_charter_and_vision_brief.md` — Executive Vision, Business Need, 90-Day KPIs, Target Segments, and High-Level Scope.
2. `./initial_customer_requirements/02_business_user_feature_wishlist_and_pain_points.md` — Operational Pain Points from 45 Surveyed Users, Blocked-Task & Subtask Needs, Fixed vs. Rolling Recurring Tasks, and Prioritized Wishlist.
3. `./initial_customer_requirements/03_ux_and_customer_experience_concept_notes.md` — 3-Pane Wireframe Concept, Keyboard Shortcuts, Optimistic UI, Snooze/Quiet Hours UX, and WCAG 2.1 AA Accessibility.
4. `./initial_customer_requirements/04_security_compliance_and_it_intake_questionnaire.md` — JWT/Argon2id Authentication, Shared-List RBAC, XSS Sanitization, Rate Limiting, Immutable Audit Trail, GDPR Right to Erasure, and Latency SLAs.
5. `./initial_customer_requirements/05_ui_design_system_brand_tokens_and_responsive_brief.md` — Visual Design System, Light/Dark Mode Brand Tokens, Priority & Status Badges, 4-Tier Responsive Breakpoints, Density Modes, and Loading/Empty/Offline States.
6. `./initial_customer_requirements/06_ui_component_inventory_screen_flows_and_state_matrix.md` — Complete Screen-by-Screen UI Component Inventory, Right Detail Drawer Widgets, Critical Modals & Guardrail Dialogs, and Shared-List Role-Based UI Matrix.

---

## 2. Stakeholder Discovery Workshops (`./workshops/`)

Seven 1-hour (`00:00 – 60:00`) verbatim discovery workshop transcripts between the Lead Technical Business Analyst and the Customer Stakeholders:

1. `./workshops/workshop_01_product_vision_personas_and_core_task_crud.md` — Hour 1: Product Vision, Personas, System `"Inbox"`, Quick-Add Defaults, Title/Description Validation, 20-Subtask Checklists, and 30-Day Soft-Delete Trash Lifecycle.
2. `./workshops/workshop_02_task_lifecycle_state_machine_priorities_and_sorting.md` — Hour 2: 5-State Task Lifecycle Machine (`TODO`, `IN_PROGRESS`, `BLOCKED`, `COMPLETED`, `ARCHIVED`), Mandatory `blocker_reason`, Forbidden Transitions, 4-Tier Priority Matrix, and 4-Key Deterministic Sorting.
3. `./workshops/workshop_03_lists_tags_smart_views_and_search_filtering.md` — Hour 3: Custom Lists & Deletion Modes (`move_to_inbox` vs. `soft_delete_tasks`), Color-Coded Tags, 4 Smart Views (`Today`, `Upcoming 7 Days`, `Overdue`, `Blocked`), and Multi-Facet Search/Filtering.
4. `./workshops/workshop_04_recurring_tasks_due_dates_timezones_and_reminders.md` — Hour 4: Timezones, Dynamic Recurring Tasks Engine, `FIXED_SCHEDULE` vs. `ON_COMPLETION` Regeneration, `Jan 31 -> Feb 28 -> Mar 31` Rollover Clamp, Subtask Reset, Reminders, Snooze, and Quiet Hours.
5. `./workshops/workshop_05_collaboration_permissions_nfrs_and_mvp_release_scope.md` — Hour 5: Shared Lists RBAC (`OWNER`, `EDITOR`, `VIEWER`), Task Assignment, `@mention` Comments, Immutable Activity Log, CSV/JSON Import & Export, Security/Latency/Offline NFRs, and v1.0 MVP Scope.
6. `./workshops/workshop_06_ui_design_system_layout_and_navigation_flows.md` — Hour 6 (UI): Design System Tokens, Light/Dark/System Themes, 4-Tier Responsive 3-Pane Layout, Left Rail Live Counters, Density Modes, Completed Accordion, URL-Synced Filters, and Offline Banner.
7. `./workshops/workshop_07_ui_interactive_components_modals_a11y_and_frontend_acceptance.md` — Hour 7 (UI): Quick-Add Optimistic Flow, Blocker Micro-Prompt, 20-Subtask Cap & Cascade Dialog, Live Recurrence Preview (`Jan 31 -> Feb 28 -> Mar 31`), Safe List Deletion Modal, RBAC UI Rendering, Keyboard Shortcuts, WCAG 2.1 AA Accessibility, and Frontend Performance Budgets.

---

## 3. Universal TBA Role Governance Standards (`./bor_dor_and_dod/`)

Domain-agnostic Technical Business Analyst (TBA) role standards defining how to baseline requirements, what qualifies a User Story as Ready for Development & Testing, and what qualifies TBA deliverables as Done:

1. `./bor_dor_and_dod/01_BoR_baseline_of_requirements.md` — Universal TBA Standard for constructing a Baseline of Requirements (BoR).
2. `./bor_dor_and_dod/02_DoR_definition_of_ready.md` — Universal TBA Role Definition of Ready (DoR) enforcing the Wikipedia User Story Standard (Connextra Template, Ron Jeffries' 3 Cs bridging Development & Testing, and Bill Wake's INVEST Matrix).
3. `./bor_dor_and_dod/03_DoD_definition_of_done.md` — Universal TBA Role Definition of Done (DoD) for TBA Specification Deliverables and Sprint Acceptance.
