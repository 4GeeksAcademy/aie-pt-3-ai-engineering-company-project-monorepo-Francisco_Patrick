# Agent Governance & Operational Guidelines — TrackFlow

This document defines the mandatory operating protocols, session initialization rules, pre-commit workflows, and permission boundaries for any AI Agent working within the TrackFlow monorepo.

---

## 1. Session Initialization: Required Memory Bank Reading

At the start of **every** development session or before undertaking any code edit, task implementation, or refactoring, the agent **MUST** read and synthesize the following core Memory Bank files:

1. **`memory-bank/projectbrief.md`**
   - **Purpose:** Understand TrackFlow's business context, multi-national logistics operations (Los Angeles & Zaragoza), core customer problems, internal operational challenges, and departmental objectives across all 7 business units.
2. **`memory-bank/techContext.md`**
   - **Purpose:** Understand the actual monorepo layout, current tech stack (TypeScript 5.9+, Node.js, Tailwind CSS, Next.js, Python, MCP), architectural decisions (unified monorepo, API facades, strict typing), and technical constraints (disparate SGAs, 8 carrier APIs, 24/7 continuous operation requirements).
3. **`memory-bank/progress.md`**
   - **Purpose:** Understand the current state of development, active milestone status, completed deliverables, in-progress backlog, and known anti-patterns.

> **Rule:** Never attempt to generate code, alter schemas, or design architecture without first loading these three memory bank files into active context.

---

## 2. Mandatory Pre-Commit Workflow

No code changes or implementations may be finalized or committed without proceeding sequentially through the following **4 explicit steps**:

```mermaid
flowchart LR
    Step1[1. Type & Lint Audit] --> Step 2[2. Empirical Verification]
    Step2 --> Step3[3. Memory Bank Sync]
    Step3 --> Step4[4. Commit Message & Audit]
```

### Step 1: Type Validation & Syntax Audit
- Run static type-checking and build validation commands across affected packages/apps (e.g., `npm run typecheck` or `npm run build`).
- Ensure zero TypeScript compiler errors (`tsc`), missing property warnings, or syntax flaws exist.

### Step 2: Empirical Verification & Testing
- Gather concrete runtime evidence demonstrating that the implementation works correctly and introduces no regressions.
- Execute unit/integration test suites if available, or test logic using manual playgrounds (e.g., `operations-playground.html` or UI dev servers under `uis/`).
- **Rule:** Editing a file is NOT completing a task. You must verify runtime behavior.

### Step 3: Memory Bank & Documentation Synchronization
- Update `memory-bank/progress.md` to reflect completed tasks, updated milestone status, and next backlog items.
- If architectural patterns or technical decisions changed, update `memory-bank/techContext.md` accordingly.

### Step 4: Conventional Commit Message & Scope Review
- Draft a concise, descriptive Git commit message following conventional standards (e.g., `feat: ...`, `fix: ...`, `docs: ...`, `refactor: ...`).
- Audit all staged/modified files against the Read-Only Protection Rules below to guarantee no protected files were mutated without developer authorization.

---

## 3. Read-Only Protection Rules (Explicit Human Confirmation Required)

To preserve repository stability, CI/CD pipelines, workspace dependencies, and core governance structures, the agent **MUST NOT** create, modify, or delete any of the following files or directories without **explicit, prior human developer approval**:

### Protected Paths:
- `/.github/**` — CI/CD workflows, GitHub Actions, issue templates, and repository automation configurations.
- `/scripts/**` — Root-level maintenance, build, and operational automation scripts.
- `/**/package.json` — Dependency manifests and project configurations across the monorepo.
- `/**/*lock*` — Package lockfiles (`package-lock.json`, `pnpm-lock.yaml`, `yarn.lock`).
- `/turbo.json` — Turborepo pipeline and build cache configurations.
- `/pnpm-workspace.yaml` — Monorepo workspace member declarations.
- `/**/.env*` — Environment variables, secrets, and environment configurations.
- `/AGENTS.md` — Repository governance rules and agent operational guidelines (this file).
- `/CONTEXT.md` — Primary business briefing document provided by 4Geeks Academy / TrackFlow.

> **Enforcement:** If a task requires modifying a protected path (e.g., adding a npm dependency to a `package.json`), the agent must explicitly ask the human developer for confirmation before proceeding.
