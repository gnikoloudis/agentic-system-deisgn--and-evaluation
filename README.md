# HarnessForge — Multi-Harness Agent Architecture Design & Evaluation Studio

Design multi-agent architectures visually (**React Flow**) or declaratively (`.yaml`), compile and deploy them into native configurations for **Claude Code**, **Antigravity (`agy`)**, and **OpenCode** with dual-mode runtime topology enforcement, execute benchmark tasks in isolated sandboxes or real external project workspaces, and evaluate performance across **4 layers**:

1. **Layer 1 — Deterministic Outcome Verifiers**: Pytest suites, Git diff audits, and no-code document/BA verifiers (Connextra/3Cs/INVEST User Story compliance, Mermaid diagram validation, required Markdown sections & RTM coverage).
2. **Layer 2 — Trajectory & Topology Adherence**: Per-node token, cost, and latency breakdowns, subagent handoff tracking, and runtime guardrail violation audits.
3. **Layer 3 — Qualitative Judge & Human Rating**: Structured dimension breakdown + side-by-side human rubric review.
4. **Layer 4 — Side-by-Side A/B Matrix & AI Architecture Advisor**: Compare architectures or harnesses (`OpenCode` vs. `Antigravity` vs. `Claude Code`) side-by-side and generate one-click `v2` YAML diff upgrades.

> **User Manuals**:
> - **Non-Technical User Manual (BAs, PMs & Consultants)**: See [docs/NON_TECHNICAL_USER_MANUAL.md](docs/NON_TECHNICAL_USER_MANUAL.md) for a plain-English, zero-code guide to designing, testing, and improving AI teams visually.
> - **Full Technical User Guide**: See [docs/USER_GUIDE.md](docs/USER_GUIDE.md) for a complete technical reference of every studio tab, blueprint schema, CLI command, and evaluation verifier.

---

## Prerequisites

- **Python** `>= 3.10` (tested on Python 3.12)
- **Node.js** `>= 18` and **npm** `>= 9`
- **Git** `>= 2.30`
- *(Optional)* One or more supported agent harness CLIs installed if you want to run live executions:
  - **Claude Code** (`claude`)
  - **Antigravity** (`agy` CLI or Antigravity IDE)
  - **OpenCode** (`opencode`)

---

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/gnikoloudis/agentic-system-deisgn--and-evaluation.git
cd agentic-system-deisgn--and-evaluation
```

### 2. Install the Backend (FastAPI Engine + `harnessforge` CLI)

#### Windows (PowerShell)
```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
cd ..
```

#### macOS / Linux
```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cd ..
```

### 3. Install the Frontend (React + Vite + React Flow Visual Studio)

```bash
cd frontend
npm install
cd ..
```

---

## Running HarnessForge

### Option A: One-Click Launch (Windows)

Double-click **[start_studio.bat](start_studio.bat)** (or run `.\start_studio.bat` in PowerShell). It starts:
- **Backend API Server** at `http://127.0.0.1:8765`
- **Visual Web Studio** at `http://localhost:5173`

### Option B: Manual Launch (Windows / macOS / Linux)

**Terminal 1 — Backend API Server:**
```bash
# Windows: .\backend\.venv\Scripts\harnessforge.exe serve
# macOS/Linux: ./backend/.venv/bin/harnessforge serve
cd backend
harnessforge serve
```

**Terminal 2 — Visual Web Studio:**
```bash
cd frontend
npm run dev
```

Open **`http://localhost:5173`** in your browser.

---

## Deploying & Evaluating on an External Project Workspace

You can deploy any architecture blueprint directly into a separate project folder and link an external documentation folder (such as workshops, customer requirements, and BoR/DoR/DoD governance docs):

1. Open **Tab 1 (`1. Architecture Studio`)** → right panel **`Compiled Files`**.
2. Select your target harness: **`Claude Code`**, **`Antigravity (AGY)`**, or **`OpenCode`**.
3. Enter:
   - **Target Project Workspace Folder** (e.g., `D:\MyProjectWorkspace`)
   - **External Documentation Folder** (e.g., `D:\MyProjectWorkspace\Documentation` or `test_application_docs`)
   - **Evaluation Benchmark Task** (e.g., `FocusFlow To-Do Application — Full Technical BA Discovery & Delivery Pack`)
4. Click **`1. Deploy & Link Docs`** — HarnessForge writes all native agent definitions, skills/commands, rules, and telemetry hooks into your target workspace (without requiring Python to be installed in that workspace).
5. Run the deployed system in your chosen harness (e.g., `/verify-setup` and `/generate-tba-pack` in OpenCode/Claude Code, or *"Run the verify-setup skill"* and *"Run the generate-tba-pack skill"* in Antigravity).
6. Return to HarnessForge Studio and click **`2. Evaluate Project`** to score the generated deliverables, inspect the 4-layer scorecard, compare harnesses in **Tab 5 (`A/B Matrix`)**, and apply `v2` architecture upgrades from **Tab 6 (`AI Advisor`)**.

---

## CLI Usage

The `harnessforge` CLI is installed inside `backend/.venv`:

```bash
# List all architecture blueprints and benchmark tasks
harnessforge list

# Preview compiled native files for Claude Code, Antigravity, or OpenCode
harnessforge compile technical-business-analyst --harness antigravity
harnessforge compile technical-business-analyst --harness opencode
harnessforge compile planner-coder-verifier --harness claude_code

# Export/deploy an architecture directly into an external workspace directory
harnessforge compile technical-business-analyst --harness antigravity --output "/path/to/target-workspace"

# Run a benchmark task in an isolated sandbox and generate a 4-layer evaluation report
harnessforge run planner-coder-verifier bugfix-auth-token --harness claude_code

# Inspect available MCP servers (built-in presets and host-detected)
harnessforge mcp list

# Start the FastMCP Server (stdio default or SSE)
harnessforge mcp start --transport stdio
```

---

## Model Context Protocol (MCP) Support

HarnessForge exposes its full multi-agent design, compilation, deployment, benchmark creation, evaluation, and AI Advisor capabilities directly to external AI coding harnesses (**Antigravity**, **Claude Code**, **OpenCode**, **Cursor**) via the **Model Context Protocol (MCP)**.

### Exposed MCP Tools

1. **`list_mcp_catalog`**: Returns auto-detected host MCP servers (`mcp.json`, etc.) alongside built-in presets (`sqlite`, `yahoofinance`, `code-graph`, `stitch`, `postgres`, `github`, `playwright`, `filesystem`).
2. **`describe_and_build_system`**: Translates a plain-English description of an agentic system into a fully validated `AgentArchitecture` blueprint with assigned subagents, topology routing, and least-privilege MCP bindings.
3. **`validate_and_save_blueprint`**: Commits and validates an architecture YAML blueprint to persistent storage.
4. **`compile_and_deploy_system`**: Compiles an architecture for `antigravity`, `claude_code`, or `opencode` and deploys native configuration files (prompts, skills, rules, hooks, and `mcp.json`) directly into the target project workspace.
5. **`create_benchmark_task`**: Authors an evaluation benchmark task with deterministic verifiers (pytest, file presence, regex assertions, BA/INVEST checks) and LLM judge rubrics.
6. **`run_benchmark_task`**: Launches an automated benchmark execution run in an isolated sandbox or workspace.
7. **`evaluate_workspace_deliverables`**: Computes the 4-layer scorecard (deterministic verifiers, trajectory adherence, judge rating) on deliverables generated in a workspace.
8. **`get_advisor_recommendations`**: Generates AI Architecture Advisor diagnostic findings and `v2` YAML diff upgrades.
9. **`inspect_blueprint`**: Reads full YAML and metadata for an existing architecture.
10. **`list_blueprints_and_tasks`**: Lists all available blueprints and benchmark tasks in the repository.

### MCP Configuration

To add HarnessForge to your harness (e.g. `mcp.json`):

```json
{
  "mcpServers": {
    "harnessforge": {
      "command": "python",
      "args": ["-m", "app.mcp.server"],
      "env": {
        "PYTHONPATH": "D:/Python_Projects/Harness Evaluation Tool/backend"
      }
    }
  }
}
```

### End-to-End Demos

Three runnable end-to-end demos showcase the complete MCP lifecycle:

```bash
# Demo 1: Financial Analysis & News Correlation using SQLite and YahooFinance MCPs
python demos/demo_1_financial_analysis.py

# Demo 2: Complete TDD System (User Story to Tests First, then Implementation & Pytest)
python demos/demo_2_tdd_pipeline.py

# Demo 3: Security & Bugfix Triage using Code-Graph AST Analysis and Pytest Verifiers
python demos/demo_3_security_triage.py
```

---

## Running Tests

### Backend Test Suite
```bash
cd backend
pytest -v
```

### Frontend Type-Check & Production Build
```bash
cd frontend
npm run build
```

---

## Repository Structure

```text
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (blueprints, tasks, runs, evaluations)
│   │   ├── compilers/      # Native compilers for Claude Code, Antigravity & OpenCode + hook templates
│   │   ├── db/             # SQLite persistence & YAML blueprint/task storage
│   │   ├── evaluator/      # 4-layer evaluation engine, A/B comparator & AI Advisor
│   │   ├── runner/         # Isolated Git sandbox runner & stream-JSON transcript parsers
│   │   └── schemas/        # Pydantic models for blueprints, tasks & evaluation reports
│   ├── tests/              # End-to-end pytest suite
│   └── pyproject.toml
├── frontend/               # React + TypeScript + Vite + Tailwind + React Flow Studio
├── blueprints/             # Starter & custom YAML multi-agent architecture blueprints
├── tasks/                  # Code & no-code (BA/Consulting) benchmark tasks with verifiers
├── test_application_docs/  # Sample FocusFlow To-Do App requirements, workshops & BoR/DoR/DoD docs
├── docs/
│   └── USER_GUIDE.md       # Detailed Studio & CLI guide
└── start_studio.bat        # Windows one-click launcher
```
