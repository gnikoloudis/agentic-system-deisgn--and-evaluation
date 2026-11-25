# HarnessForge User Guide — From Zero to Benchmarking Agent Architectures

> **New to HarnessForge?** This guide is written for a first-time user with zero prior familiarity. Follow **Part 1** to launch the studio in under 2 minutes, then follow **Part 2** for a hands-on walkthrough of your first architecture design, deployment, evaluation, and AI-assisted upgrade.

---

## What Is HarnessForge? (In Plain English)

Modern AI coding tools—called **Coding Harnesses** (such as **Claude Code**, **Antigravity**, and **OpenCode**)—allow you to define custom **Subagents** (e.g., a Planner, a Coder, a QA Verifier), **Skills/Commands**, and **Hooks** (rules that block bad actions).

However, building these multi-agent setups by hand is hard because:
1. Every harness uses different folders, file formats, and configuration files.
2. You have no visual way to wire how agents hand off work to one another.
3. You have no way to scientifically test if Architecture A (e.g., a 3-agent *Planner → Coder ↔ Verifier* loop) is actually better, faster, or cheaper than Architecture B (e.g., a single *Solo Agent*).

**HarnessForge solves all three problems:**
1. **Design Visually or in YAML**: Draw your agent team on an interactive canvas (or edit a clean `.yaml` file).
2. **Compile to Any Harness**: Automatically translates your design into native files for **Claude Code**, **Antigravity**, and **OpenCode**, plus injects a runtime guardrail script (`.harness-eval/hook_runner.py`) that enforces your workflow rules.
3. **Execute & Benchmark in Safe Sandboxes**: Runs coding tasks inside isolated Git copies so your real files are never harmed, then grades the architecture across **4 evaluation layers** and suggests a **v2 upgrade diff**.

---

## Part 1: Step-by-Step Installation & Startup Guide

### Step 1.1: Check What Is Already Installed
Everything required to run HarnessForge is already installed in your project folder (`d:\Python_Projects\Harness Evaluation Tool`):
- **Backend Python Virtual Environment**: Located at `backend\.venv`
- **Frontend Node Packages**: Located at `frontend\node_modules`
- **Starter Blueprints & Sample Tasks**: Located in `blueprints\` and `tasks\`

> **Do I need Claude Code, Antigravity, or OpenCode installed first?**
> **No!** HarnessForge includes a built-in **Simulated Sandbox Benchmark Mode** that runs your architecture inside real Git sandboxes and runs real `pytest` verifiers even if you have not installed or logged into an external harness CLI yet. When you *do* have `claude`, `agy`, or `opencode` installed on your computer, HarnessForge automatically detects them for **Headless** and **Interactive** modes.

---

### Step 1.2: How to Launch HarnessForge (Two Ways)

#### Option A: One-Click Launcher (Easiest)
Double-click `start_studio.bat` in Windows Explorer, or run it from PowerShell:
```powershell
cd "d:\Python_Projects\Harness Evaluation Tool"
.\start_studio.bat
```
This automatically opens the Backend API Server (`http://127.0.0.1:8765`), starts the Web Studio (`http://localhost:5173`), and opens your browser.

---

#### Option B: Manual Two-Terminal Startup (Recommended for Developers)

**Terminal 1 — Start the Backend Server:**
1. Open PowerShell.
2. Copy and paste these two lines:
   ```powershell
   cd "d:\Python_Projects\Harness Evaluation Tool\backend"
   .\.venv\Scripts\harnessforge.exe serve
   ```
3. You will see:
   `Starting HarnessForge API Server on http://127.0.0.1:8765`
   *(Leave this terminal window open!)*

**Terminal 2 — Start the Visual Web Studio:**
1. Open a **second** PowerShell window.
2. Copy and paste these two lines:
   ```powershell
   cd "d:\Python_Projects\Harness Evaluation Tool\frontend"
   npm run dev
   ```
3. Open your web browser and go to:
   **http://localhost:5173**

---

### Step 1.3: First-Time Installation on a Brand New Computer
If you ever move this folder to another machine and need to install dependencies from scratch:
```powershell
# 1. Setup Backend Python Environment
cd "d:\Python_Projects\Harness Evaluation Tool\backend"
python -m venv .venv
.\.venv\Scripts\pip.exe install -e ".[dev]"

# 2. Setup Frontend Node Environment
cd "d:\Python_Projects\Harness Evaluation Tool\frontend"
npm install
```

---

## Part 2: Your First 5 Minutes (Hands-On Tutorial)

Follow these 6 simple steps in the Web Studio (`http://localhost:5173`) to complete a full design-to-evaluation cycle:

### Step 1: Explore an Architecture in Tab 1 (`1. Architecture Studio`)
1. Look at the **left sidebar** under **Architecture Blueprints**. You will see 3 pre-built architectures:
   - **Solo Generalist Agent (Baseline)**: 1 root agent doing everything alone.
   - **Planner -> Coder <-> Verifier (Actor-Critic Loop)**: 1 root orchestrator coordinating 3 specialized subagents.
   - **Parallel Specialist Swarm**: A triage coordinator fanning out to backend, security, and test specialists.
2. Click on **Planner -> Coder <-> Verifier**.
3. On the **center canvas**, click any node card (for example, click **Architecture Planner (`planner`)** or **Implementation Engineer (`coder`)**).
4. Look at the **right panel (`Node Inspector`)**: you can immediately see and edit that agent's Name, Role, Model Tier, `Allow Write/Edit` checkbox, `Allow Bash/Shell` checkbox, and System Prompt.

### Step 2: Preview the Compiled Harness Files
1. In the **right panel** of Tab 1, click the **`Compiled Harness Files`** tab at the top right.
2. Click between **`Claude Code`**, **`Antigravity (AGY)`**, and **`OpenCode`**.
3. Click the file pills (`CLAUDE.md`, `.claude/agents/planner.md`, `.claude/settings.local.json`, `.harness-eval/hook_runner.py`, `opencode.json`, etc.) to see the exact native configuration files HarnessForge generates for each tool.

### Step 3: Run Your First Benchmark
1. Look at the **top-right corner** of the top navigation bar.
2. Select **`Target: Claude Code`** (or Antigravity / OpenCode) and click the green **`Deploy & Evaluate`** button.
3. HarnessForge automatically switches to **Tab 3 (`3. Execute & Trace`)**, creates a fresh isolated Git sandbox in `.harness-workspaces/run-xxxxxxxx`, deploys the compiled architecture files, runs the task (`Fix Token Expiration Off-by-One & Scope Validation Bug`), and streams every telemetry event live (`SessionStart` → `SubagentStart` → `PreToolUse` → `PostToolUse` → `SubagentStop` → `SessionStop`).

### Step 4: Inspect the 4-Layer Evaluation Scorecard
1. Once the run status says **`COMPLETED`**, click the blue **`View Full Evaluation`** button (or click **Tab 4: `4. Evaluation Scorecard`**).
2. You will see:
   - **Overall Composite Score** (e.g., `96.2 / 100`)
   - **Layer 1: Deterministic Tests** (`100.0%` — `pytest -v` output and Git diff checks)
   - **Layer 2: Topology Adherence** (`100.0%` — confirming the root agent called `planner` → `coder` → `verifier` in the required order)
   - **Per-Node Architecture Breakdown**: Horizontal bars showing exactly how many tokens, dollars, and milliseconds were spent by `root_orchestrator` vs `planner` vs `coder` vs `verifier`.
   - **Captured Sandbox Git Diff**: The exact code lines changed in `token_validator.py`.

### Step 5: Run a Second Architecture & Compare Side-by-Side (A/B Test)
1. In **Tab 3 (`3. Execute & Trace`)**, in the left launchpad box, change **Architecture Blueprint** to **`Solo Generalist Agent (Baseline)`** and click **`Start Execution Run`**.
2. Once it finishes, click **Tab 5 (`5. A/B Matrix`)**.
3. Check the boxes for both runs and click **`Recompute A/B Matrix`**.
4. You now have a side-by-side table comparing the **Solo Agent** against the **Planner-Coder-Verifier** architecture across composite score, token usage, cost, duration, and orchestration quality!

### Step 6: Let the AI Architecture Advisor Upgrade the Solo Agent
1. In **Tab 3**, click your **Solo Generalist Agent** run in the Execution History list to make it the active run.
2. Click **Tab 6 (`6. AI Advisor (v2 Diff)`)**.
3. The Advisor diagnoses that the Solo Agent lacks an independent QA Verifier subagent and automatically generates a **Unified YAML Diff (`v1.0.0 → v1.1.0`)** adding a `verifier` subagent and a topology edge.
4. Click **`Save as New v2 Blueprint`** (or **`Apply Patch`**) — your upgraded architecture immediately opens on the visual canvas in Tab 1!

---

## Part 3: Deep-Dive Reference for Every Tab

### Tab 1: Architecture Studio (Visual Canvas & Inspector)
- **Adding Nodes**:
  - Click **`+ Add Subagent Node`** in the left sidebar to spawn a new specialist subagent on the canvas.
  - Click **`+ Add Lifecycle Guardrail Hook`** to add a `PreToolUse`, `PostToolUse`, `SubagentStop`, or `Stop` guardrail rule.
- **Wiring Handoff Edges**:
  - Hover over the bottom handle (dot) of any node on the canvas, click and drag a line to the top handle of another node.
  - This creates a directed handoff rule in the **Workflow Handoff Edges** list in the right inspector.
- **Permission Guardrails (`Read-Only` vs `Write: ON`)**:
  - For a multi-agent setup, uncheck **`Allow Direct File Write`** on the `Root Orchestrator` and on your `Planner` / `Verifier` subagents, leaving it checked **only** on your `Coder` subagent.
  - This guarantees the Root Orchestrator cannot bypass your subagents and edit code itself.
- **`YAML Spec (2-Way)` Sub-Tab**:
  - Every drag, prompt edit, or permission toggle on the visual canvas automatically updates the YAML specification.
  - You can also type or paste YAML directly into the editor and click **`Apply & Save YAML`** to update the visual canvas.
- **`Compiled` Sub-Tab (`1. Deploy & Link Docs` & `2. Evaluate Project`)**:
  - Preview every file generated for **Claude Code**, **Antigravity (AGY)**, or **OpenCode**.
  - **Field 0 — Architecture Blueprint to Deploy**: The active multi-agent blueprint being compiled and exported.
  - **Field 1 — Target Project Workspace Folder**: Any folder on your computer (e.g., `D:\Projects\my-app`) where HarnessForge writes the native agents, skills, commands, and hooks.
  - **Field 2 — External Reference Documentation Folder (Optional)**: A separate folder containing customer requirements, workshops, or specs that your agents need read access to without copying them into the code repo.
  - **Field 3 — Evaluation Benchmark Task *(Verifiers used when clicking "2. Evaluate Project")***:
    - **What it is**: The **grading checklist / automated verifier suite** that HarnessForge runs against your Target Project Workspace Folder when you click **`2. Evaluate Project`**.
    - **Why choosing the right option matters**: Every option in this dropdown defines its own **Layer 1 Deterministic Verifiers** (which account for **45%** of your total Composite Score). Always match the selected option to the work your agents actually performed in that folder.

    #### Detailed Guide to Every Dropdown Option

    1. **`FocusFlow To-Do Application — Full TBA Delivery Pack (From 5 Workshops & Customer Intake) (4 verifiers)`** (`tba-focusflow-todo-app`)
       - **Best for**: Evaluating a **Technical Business Analyst (TBA)** architecture on the FocusFlow To-Do App documentation (`test_application_docs/` or your own copy of `Documentation/`).
       - **Python required in target folder?**: **No** (100% no-code document verifiers).
       - **Exact Verifiers Executed**:
         - `user_story_invest_check` *(weight `2.5`, required)* — Audits `EPICS_AND_USER_STORIES.md` for `>= 2` Connextra stories (`As a... I want... So that...`), 3 Cs Card (`EPIC-xx` & `US-xxx`), Conversation (Dev rules), Confirmation (`>= 2` BDD `Given/When/Then` scenarios & `TC-xxx` IDs), Bill Wake's INVEST checklist, and DoR/DoD.
         - `markdown_sections_present` *(weight `1.5`, required)* — Confirms all 8 sections (`Epics`, `User Stories`, `Conversation`, `Confirmation`, `INVEST`, `Definition of Ready`, `Definition of Done`, `Traceability Matrix`) exist in `EPICS_AND_USER_STORIES.md`.
         - `mermaid_diagram_valid` *(weight `1.5`, required)* — Confirms `WORKFLOWS_AND_DELIVERY_DOCS.md` contains valid fenced ```` ```mermaid ```` diagrams (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`).
         - `file_contains_regex` *(weight `1.5`, required)* — Confirms FocusFlow workshop domain rules (`120`, `BLOCKED`, `30`) are covered in `EPICS_AND_USER_STORIES.md`.

    2. **`Technical BA Delivery Pack: FinTech Card Chargeback & Dispute Resolution Portal (4 verifiers)`** (`tba-chargeback-dispute-system`)
       - **Best for**: Evaluating a **Technical Business Analyst (TBA)** architecture on the built-in FinTech Chargeback sample repo (`tasks/sample_repos/tba_stakeholder_intake`).
       - **Python required in target folder?**: **Yes** (runs `pytest -v` on `test_ba_deliverables.py` in addition to the 3 no-code BA verifiers).
       - **Exact Verifiers Executed**:
         - `user_story_invest_check` *(weight `2.5`, required)* — Audits `EPICS_AND_USER_STORIES.md` for Connextra, 3 Cs, BDD, INVEST, and DoR/DoD.
         - `markdown_sections_present` *(weight `1.5`, required)* — Checks the 8 required BA & Traceability Matrix sections.
         - `mermaid_diagram_valid` *(weight `1.5`, required)* — Validates Mermaid process/sequence/state diagrams in `WORKFLOWS_AND_DELIVERY_DOCS.md`.
         - `pytest_pass` *(weight `1.5`, required)* — Runs `pytest -v` to check Chargeback-specific regulatory thresholds (60-day window, \$25 auto-refund, \$500 approval, 10MB evidence limit).

    3. **`B2B SaaS Growth & Margin Turnaround Strategy Case (AcmeCloud) (3 verifiers)`** (`consulting-saas-turnaround`)
       - **Best for**: Evaluating a **Business Consulting** architecture (`business-consulting-firm`) analyzing `client_metrics.json` and authoring `EXECUTIVE_MEMO.md`.
       - **Python required in target folder?**: **Yes** (runs `pytest -v` on `test_consulting_memo.py`).
       - **Exact Verifiers Executed**:
         - `file_exists` *(weight `1.0`, required)* — Confirms `EXECUTIVE_MEMO.md` was created.
         - `pytest_pass` *(weight `2.0`, required)* — Runs quantitative fact-check & MECE structure tests (`pytest -v`).
         - `file_contains_regex` *(weight `1.0`, required)* — Confirms key unit economics (`38%` SMB churn / `118%` Enterprise NDR) are cited.

    4. **`Fix Token Expiration Off-by-One & Scope Validation Bug (3 verifiers)`** (`bugfix-auth-token`)
       - **Best for**: Quick **Python Bugfix** benchmark on `tasks/sample_repos/auth_service` (`token_validator.py`).
       - **Python required in target folder?**: **Yes** (`pytest -v`).
       - **Exact Verifiers Executed**:
         - `pytest_pass` *(weight `2.0`, required)* — Runs `pytest -v` on `test_token_validator.py`.
         - `git_diff_contains` *(weight `1.0`, required)* — Confirms `token_validator.py` was modified in `git diff`.
         - `git_diff_max_lines` *(weight `0.5`, optional)* — Checks that the fix stays within `60` changed lines.

    5. **`Implement Sliding Window Rate Limiter with Burst Allowance (2 verifiers)`** (`feature-rate-limiter`)
       - **Best for**: Medium **Python Feature Implementation** benchmark on `tasks/sample_repos/rate_limiter` (`limiter.py`).
       - **Python required in target folder?**: **Yes** (`pytest -v`).
       - **Exact Verifiers Executed**:
         - `pytest_pass` *(weight `2.0`, required)* — Runs `pytest -v` on `test_limiter.py`.
         - `file_not_contains_regex` *(weight `1.0`, required)* — Confirms no `NotImplementedError` placeholders remain in `limiter.py`.

    6. **`Refactor Order Pricing Engine & Fix Tiered Discount Rounding (2 verifiers)`** (`refactor-order-pricing`)
       - **Best for**: Hard **Python Refactoring** benchmark on `tasks/sample_repos/order_pricing` (`pricing.py`).
       - **Python required in target folder?**: **Yes** (`pytest -v`).
       - **Exact Verifiers Executed**:
         - `pytest_pass` *(weight `2.0`, required)* — Runs `pytest -v` on `test_pricing.py`.
         - `file_exists` *(weight `0.5`, required)* — Confirms `pricing.py` exists and was preserved.

    7. **Evaluating Your Own Custom Code / React UI / Domain Project?**
       - None of the 6 built-in tasks above will match your custom filenames or test commands (e.g., `npm run build`, `npx tsc -b`, `npx vitest run`).
       - Instead, open **Tab 2 (`2. Benchmark Tasks`)**, duplicate any task YAML with a new `id` (e.g., `my-react-ui-app`), define your own verifiers (`command_exit_code`, `file_exists`, `file_contains_regex`, etc.), and click **`Save Task YAML`**. Your new task immediately appears in this dropdown!

    - **What happens step-by-step when you click `2. Evaluate Project`**:
      1. **Ingests Session Telemetry**: Reads `.harness-eval/state.json` and `.harness-eval/telemetry.jsonl` from your Target Project Workspace Folder (capturing every tool call, subagent handoff, duration, estimated tokens, and any blocked guardrail violations).
      2. **Runs Layer 1 Deterministic Verifiers (45% of score)**: Executes every verifier defined in the selected **Evaluation Benchmark Task** directly inside your Target Project Workspace Folder. *(Note: No-code BA/Document verifiers do **not** require Python to be installed in your target workspace.)*
      3. **Computes Layer 2 & Layer 3 Scores (55% of score)**: Grades **Topology Adherence (20%)**, **Efficiency (15%)**, and **Qualitative Judge Dimensions (20%)**, then opens **Tab 4 (`4. Evaluation Scorecard`)**.
      4. **Feeds Tab 5 & Tab 6**: Saves the evaluated run so you can compare harnesses side-by-side in **Tab 5 (`A/B Matrix`)** (e.g., Antigravity vs. OpenCode) and generate targeted `v2` blueprint fixes in **Tab 6 (`AI Advisor`)** for any verifier that failed.

### Tab 2: Benchmark Tasks & Verifiers
Use this tab to inspect, edit, or create the **Evaluation Benchmark Tasks** that appear in Field 3 (`Evaluation Benchmark Task`) and Tab 3:
- **Task Prompt**: The problem statement sent to the harness when running headless or simulated benchmarks.
- **Deterministic Outcome Verifiers (Layer 1 — 45% of Composite Score)**:
  - **Code & CLI Verifiers**:
    - `pytest_pass`: Runs `pytest -v` (or a specified pytest command) and checks `exit_code == 0`.
    - `command_exit_code`: Runs any custom shell command (e.g., `npm run build`, `npx tsc -b`, `npx vitest run`, `ruff check`, `mypy`) and checks `exit_code == 0`.
    - `git_diff_contains` / `git_diff_max_lines`: Confirms expected source files were modified and changes stay concise.
  - **No-Code Document & Business Analyst Verifiers**:
    - `user_story_invest_check`: Audits `EPICS_AND_USER_STORIES.md` for Connextra user stories (single- or multi-line), Ron Jeffries' 3 Cs (`EPIC-xx`/`US-xxx` Card, Developer Conversation, QA Confirmation with BDD `Given/When/Then` scenarios & `TC-xxx` IDs), Bill Wake's INVEST checklist, and DoR/DoD.
    - `markdown_sections_present`: Confirms all required headings/sections (e.g., `Epics`, `User Stories`, `Traceability Matrix`) exist in a target Markdown file.
    - `mermaid_diagram_valid`: Validates fenced ```` ```mermaid ```` blocks (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`) in `WORKFLOWS_AND_DELIVERY_DOCS.md`.
    - `file_exists` / `file_contains_regex` / `file_not_contains_regex`: Confirms deliverables exist and contain required domain rules (or no `TODO` placeholders).
- **Weights & Required Flag**: Each verifier has a `weight` (controls its share of the 100% Layer 1 score) and `required: true/false` (if any `required` verifier fails, the run is flagged as incomplete and surfaced in **Tab 6: AI Advisor**).

### Tab 3: Execute & Trace (3 Execution Modes)
When launching a run from the left panel of Tab 3, you can choose between **3 Execution Modes**:
1. **`Simulated Sandbox Benchmark (Fast Topology Test)`**:
   - Creates a real isolated Git sandbox, deploys all compiled harness files, simulates the multi-agent handoff trajectory across your graph nodes, applies the task solution, and runs the real `pytest` verifiers.
   - Best for rapid topology testing and A/B comparisons without spending API credits.
2. **`Headless Automated Harness CLI`**:
   - Invokes your installed harness CLI headlessly (`claude -p "<prompt>" --output-format stream-json`, `opencode run "<prompt>" --format json`, or `agy chat --prompt "<prompt>"`).
   - Streams live tool calls, thinking steps, and token counts to the UI and auto-evaluates upon exit.
3. **`Interactive User Session`**:
   - Prepares the isolated Git worktree sandbox and deploys your compiled architecture.
   - Displays a copy-paste command:
     `cd "d:\Python_Projects\Harness Evaluation Tool\.harness-workspaces\run-xxxx" && claude` (or `opencode` / `agy .`).
   - While you chat and execute tasks interactively in your terminal/IDE, `.harness-eval/hook_runner.py` streams your subagent handoffs and tool calls live into the HarnessForge UI!
   - When you finish working, click **`Complete & Evaluate Interactive Session`** in the UI to grade your session.

### Tab 4: 4-Layer Evaluation Scorecard
Every completed run is graded on a 0–100 composite scale:
`Composite Score = 0.45 * Deterministic + 0.20 * Topology Adherence + 0.15 * Efficiency + 0.20 * Judge`
- **Layer 1 — Deterministic Score (45%)**: Weighted pass rate of all `pytest`, command, file, and git diff checks.
- **Layer 2 — Topology Adherence (20%) & Efficiency (15%)**:
  - Did the orchestrator invoke all `required: true` subagent edges in the right order?
  - Were there blocked hook violations, failed tool retries, or redundant file reads?
  - Includes a **Per-Node Breakdown** showing exact tokens, cost, and time spent by each subagent.
- **Layer 3 — LLM-as-a-Judge & Human Rating (20%)**:
  - Grades the run from 1.0–5.0 across **Task Correctness**, **Code Quality**, and **Orchestration Fidelity**.
  - Lets you save your own 1–5 star human rating and review notes.

### Tabs 5 & 6: A/B Matrix & AI Architecture Advisor
- **Tab 5 (`A/B Matrix`)**:
  - Select 2 or more runs to compare different architectures (*Solo* vs *Actor-Critic* vs *Swarm*) or different harnesses (*Claude Code* vs *Antigravity* vs *OpenCode*) on the exact same task.
  - Highlights the **WINNER** badge and auto-generates takeaways for **Top Performer**, **Most Cost-Efficient**, and **Lowest Latency**.
- **Tab 6 (`AI Advisor (v2 Diff)`)**:
  - Inspects your run's telemetry and verifier outputs for architectural weaknesses (e.g., missing QA verifier node, root agent direct-write risk, bloated turn budgets on read-only planners, or failed tests).
  - Shows a color-coded **Unified YAML Diff** and lets you apply the upgrade with one click.

---

## Part 4: How to Add Your Own Project & Custom Benchmark Task

Want to evaluate an agent architecture on **your own real codebase**?

1. Open **Tab 2 (`2. Benchmark Tasks`)**.
2. Select any existing task as a template, edit the YAML in the right editor, change its `id` (e.g. `my-custom-feature`), and click **`Save Task YAML`**:

```yaml
api_version: harnessforge/v1
kind: TaskSpec
id: my-custom-feature
name: "Add CSV Export Endpoint to My Project"
category: feature
difficulty: medium
description: "Tests whether the architecture plans, implements, and tests a CSV export utility."
prompt: |
  Add a `export_users_to_csv(users)` function in `exporter.py` and write unit tests in `test_exporter.py`.
  Run `pytest -v` to confirm all tests pass.
workspace_source: "D:/Path/To/Your/Local/Git/Repo"   # <-- Can be any local folder or Git repo!
expected_subagents:
  - planner
  - coder
  - verifier
verifiers:
  - id: unit_tests
    name: "Run Pytest Suite"
    type: pytest_pass
    command: "pytest -v"
    weight: 2.0
    required: true
    timeout_seconds: 60
  - id: exporter_created
    name: "exporter.py exists"
    type: file_exists
    target_path: "exporter.py"
    weight: 1.0
    required: true
    timeout_seconds: 10
```

> **Your original folder at `workspace_source` is never modified!**
> Whenever you start a run, HarnessForge creates an isolated Git worktree or fresh copy inside `.harness-workspaces/run-<id>` and runs the agent and tests inside that sandbox.

---

## Part 5: Command-Line Interface (`harnessforge` CLI) Reference

Everything you can do in the Web Studio can also be automated from PowerShell using `backend\.venv\Scripts\harnessforge.exe`:

| Goal | PowerShell Command |
| :--- | :--- |
| **List all blueprints & tasks** | `.\.venv\Scripts\harnessforge.exe list` |
| **Preview compiled files for Claude Code** | `.\.venv\Scripts\harnessforge.exe compile planner-coder-verifier --harness claude_code` |
| **Preview compiled files for Antigravity** | `.\.venv\Scripts\harnessforge.exe compile planner-coder-verifier --harness antigravity` |
| **Preview compiled files for OpenCode** | `.\.venv\Scripts\harnessforge.exe compile planner-coder-verifier --harness opencode` |
| **Deploy an architecture into a project folder** | `.\.venv\Scripts\harnessforge.exe compile planner-coder-verifier --harness claude_code --output "D:\MyProject"` |
| **Run a benchmark & AI Advisor from terminal** | `.\.venv\Scripts\harnessforge.exe run planner-coder-verifier bugfix-auth-token --harness claude_code` |
| **Start the Backend API server** | `.\.venv\Scripts\harnessforge.exe serve --port 8765` |

---

## Part 6: Troubleshooting & FAQ

1. **"Failed to connect to backend" in the Web Studio**:
   - Make sure the Backend API terminal is running (`.\.venv\Scripts\harnessforge.exe serve`).
   - Check that `http://127.0.0.1:8765/api/health` opens in your browser and returns `{"status":"ok"}`.
2. **Custom Harness CLI Binary Locations**:
   - If `claude`, `opencode`, or `agy` is installed in a non-standard directory, set its path before starting the backend:
     ```powershell
     $env:CLAUDE_BINARY = "C:\path\to\claude.exe"
     $env:OPENCODE_BINARY = "C:\path\to\opencode.exe"
     $env:AGY_BINARY = "C:\path\to\agy.exe"
     .\.venv\Scripts\harnessforge.exe serve
     ```
3. **Resetting Run History**:
   - Delete `.harness-data\harnessforge.db` and `.harness-workspaces\` to clear previous runs while keeping all your `.yaml` blueprints and tasks intact.

---

## Part 7: Designing & Evaluating a Technical Business Analyst (TBA) System

> **Non-Coding / Specification Delivery Mode**: When you use HarnessForge for **Technical Business Analysis (TBA)** or **Business Consulting**, your agents produce **Epics, User Stories, Mermaid Process Workflows, Data Dictionaries, and Traceability Matrices** rather than application source code. Most importantly, the **User Story** is the formal interface contract between the **Development Team** and the **Testing (QA) Team** (following the Connextra, Ron Jeffries' 3 Cs, and Bill Wake's INVEST User Story standard).

### 7.1 Built-In Technical Business Analyst Architecture (`technical-business-analyst.yaml`)

HarnessForge includes a ready-to-run **Technical Business Analyst Practice** blueprint (`blueprints/technical-business-analyst.yaml`) with 4 specialized subagents and 2 BA skills:
1. **`root_orchestrator` (Lead Technical Business Analyst)**: Read-only coordinator (`allow_write: false`) that enforces the 4-stage BA delivery pipeline.
2. **`requirements_elicitor` (Requirements Discovery & Domain Analyst)**: Reads raw stakeholder transcripts (`stakeholder_interview_notes.md`) and extracts numbered Business Requirements (`BR-001`..), Personas, SLAs, and Non-Functional Requirements (`NFR-001`..).
3. **`workflow_architect` (Process & Workflow Architect)**: Authors `WORKFLOWS_AND_DELIVERY_DOCS.md` containing Mermaid Process Flowcharts (`flowchart TD`), Sequence Diagrams (`sequenceDiagram`), Lifecycle State Diagrams (`stateDiagram-v2`), and a Data Dictionary / API Contract.
4. **`user_story_author` (Agile Epics & User Story Author — Dev/QA Bridge)**: Authors `EPICS_AND_USER_STORIES.md` following the Wikipedia User Story standard.
5. **`ba_qa_gatekeeper` (BA Quality & Traceability Gatekeeper)**: Audits both deliverables against the 3 Cs, INVEST, and BDD testability rules before approving completion.

### 7.2 How User Stories Bridge the Development Team & Testing Team (Wikipedia Standard)

Every User Story generated by `user_story_author` (and verified by `user_story_invest_check`) enforces 4 mandatory sections:
1. **Part A — The Card (Connextra Template & Agile Metadata)**:
   - Canonical format: **`As a <role/persona>, I want <capability/goal>, so that <measurable business benefit>.`**
   - Metadata: Story ID (`US-101`), Parent Epic (`EPIC-01`), Source Requirement (`BR-001`), MoSCoW Priority, Story Points (Fibonacci), and Dependencies.
2. **Part B — The Conversation (Development Team Interface)**:
   - Gives **Developers** unambiguous implementation rules: exact field names, data types, boundary math (`<= 60 days`, `<= $25.00`, `> $500.00`, `<= 10 MB`), API status codes (`HTTP 422`), and state transitions.
3. **Part C — The Confirmation (Testing Team Interface / BDD Acceptance Criteria)**:
   - Gives **QA Engineers** directly executable test cases (`TC-101-01`, `TC-101-02`, `TC-101-03`) written in strict **Gherkin (`Given ... When ... Then ...`)** syntax covering Happy Path, Boundary/Threshold Conditions, and Negative Rejection Scenarios.
4. **Part D — Bill Wake's INVEST Checklist + DoR / DoD + RTM**:
   - Explicitly verifies **I**ndependent, **N**egotiable, **V**aluable, **E**stimable, **S**mall, **T**estable, plus **Definition of Ready (DoR)**, **Definition of Done (DoD)**, and a **Requirements Traceability Matrix (RTM)** mapping `BR-xxx` → `EPIC-xx` → `US-xxx` → `Dev Component` → `QA Test Case (TC-xxx)`.

### 7.3 Using No-Code BA & Document Verifiers (Zero Python Required!)

In **Tab 2 (`2. Benchmark Tasks`)**, under **Deterministic Outcome Verifiers**, you can click any of the 3 one-click buttons to grade non-coding Business Analysis and Consulting deliverables:

| One-Click Button / Verifier Type | Target File Example | What It Grades Automatically |
| :--- | :--- | :--- |
| **`+ Wikipedia User Story (3Cs + INVEST + BDD)`**<br>(`type: user_story_invest_check`) | `EPICS_AND_USER_STORIES.md` | Checks Connextra statements (`As a... I want... So that...`), **3 Cs** (`Card` Epic/Story IDs, `Conversation` Dev notes, `Confirmation` `Given/When/Then` BDD scenarios & `TC-xxx` QA test IDs), all 6 **INVEST** criteria, and **DoR/DoD**. |
| **`+ Required Markdown Sections`**<br>(`type: markdown_sections_present`) | `EPICS_AND_USER_STORIES.md` | Verifies that every comma-separated heading in `pattern` (e.g. `Epics,User Stories,Conversation,Confirmation,INVEST,Traceability Matrix`) is present. |
| **`+ Mermaid Workflow Validator`**<br>(`type: mermaid_diagram_valid`) | `WORKFLOWS_AND_DELIVERY_DOCS.md` | Verifies that the document contains valid ` ```mermaid ` workflow diagrams (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`). |

### 7.4 Deploying Your Technical Business Analyst Team to OpenCode

```powershell
cd "d:\Python_Projects\Harness Evaluation Tool\backend"

# 1. Benchmark the TBA architecture on the Chargeback & Dispute Portal Stakeholder Intake task
.\.venv\Scripts\harnessforge.exe run technical-business-analyst tba-chargeback-dispute-system --harness opencode

# 2. Export the compiled OpenCode TBA system into any real project directory
.\.venv\Scripts\harnessforge.exe compile technical-business-analyst --harness opencode --output "D:\BA_Projects\My_Initiative"
```

---

## Part 8: The 5-Step Continuous Improvement Loop with OpenCode & External Documentation

When your **OpenCode workspace** lives in one folder (e.g. `tba_opencode_workspace`) and your **customer documentation / workshop transcripts** live in a different folder (e.g. `test_application_docs`), follow this 5-step closed loop:

1. **Step 1 — Deploy to OpenCode & Link External Documentation Folder**:
   - In **Tab 1 (`1. Architecture Studio` → `Compiled Files` → `OpenCode`)**:
     - Set **Box 1 (`Target OpenCode / Project Workspace Folder`)** to `tba_opencode_workspace`.
     - Set **Box 2 (`External Documentation Folder`)** to `test_application_docs`.
     - Click **`1. Deploy & Link Docs`**.
   - In PowerShell:
     ```powershell
     cd "d:\Python_Projects\Harness Evaluation Tool\tba_opencode_workspace"
     opencode agent list
     opencode
     ```
   - Inside OpenCode, type **`/verify-setup`** to verify all 5 agents are installed and confirm read access to the 13 documents in `test_application_docs`.
2. **Step 2 — Run the System in OpenCode to Produce User Stories & Project Documentation**:
   - Inside OpenCode, type **`/generate-tba-pack`** (or your custom task prompt).
   - Your OpenCode agents will read `initial_customer_requirements/`, `workshops/`, and `bor_dor_and_dod/` from the external documentation folder and generate `BOR_FOCUSFLOW.md`, `WORKFLOWS_AND_DELIVERY_DOCS.md`, and `EPICS_AND_USER_STORIES.md` inside `tba_opencode_workspace`.
3. **Step 3 — Measure Performance & Report the 4-Layer Scorecard**:
   - Type **`/evaluate-project`** in OpenCode, OR click **`2. Evaluate Project`** in HarnessForge Studio (or run `.\.venv\Scripts\harnessforge.exe evaluate-dir "d:\Python_Projects\Harness Evaluation Tool\tba_opencode_workspace" --task tba-focusflow-todo-app`).
   - Inspect your score across Deterministic BA Verifiers (Wikipedia 3Cs + INVEST + BDD `TC-xxx` + Mermaid Workflows), Topology Adherence, Per-Node Tokens/Latency, and Rubric Judge in **Tab 4 (`4. Evaluation Scorecard`)**.
4. **Step 4 — Make Updates to the Architecture in HarnessForge**:
   - Open **Tab 6 (`6. AI Advisor (v2 Diff)`)** to inspect project-specific diagnoses and the proposed `v1.1.0` YAML patch (or manually adjust prompts, skills, hooks, and per-subagent models in **Tab 1**).
5. **Step 5 — Re-Deploy & Repeat**:
   - Click **`Apply Patch & Re-Deploy to Project`** in **Tab 6** (or **`1. Deploy & Link Docs`** in **Tab 1**) to push the upgraded agents back into `tba_opencode_workspace`, re-run in OpenCode, and compare `v1.0.0` vs. `v1.1.0` in **Tab 5 (`5. A/B Matrix`)**!
