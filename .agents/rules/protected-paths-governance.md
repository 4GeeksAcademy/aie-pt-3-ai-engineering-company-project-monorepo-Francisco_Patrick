# Protected Paths & Read-Only Governance Rule

## Scope Definition
- **Scope Type:** `Agent-Requested / Triggered`
- **Target File Patterns:** `/.github/**`, `/scripts/**`, `/**/package.json`, `/**/*lock*`, `/turbo.json`, `/pnpm-workspace.yaml`, `/**/.env*`, `/AGENTS.md`, `/CONTEXT.md`

---

## Behavioral Guardrails & Requirements

1. **Human Developer Confirmation Required:**
   - AI Agents MUST NOT create, edit, rename, or delete any file within the protected paths without explicit, prior human developer confirmation.

2. **Trigger Protocol:**
   - If a task requires modifying a protected path (such as adding a package to `package.json` or editing a `.env` template), the agent MUST halt execution and ask the human developer for approval.
