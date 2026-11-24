# Quickstart Validation Guide: TrackFlow OWASP Top 10 Security Audit, Infrastructure Hardening, and Critical Remediation

**Feature Branch**: `feature/owasp-top10-audit`  
**Specification**: [specs/036-owasp-audit-hardening/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/spec.md)  
**Data Model**: [specs/036-owasp-audit-hardening/data-model.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/data-model.md)  
**Contracts**: [specs/036-owasp-audit-hardening/contracts/](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/contracts/)  
**Date**: 2026-11-25  

---

## 1. Prerequisites & Environment Setup

### 1.1 Development Environment
- Python >= 3.14 with `uv` package manager.
- Node.js >= 20.x and npm / tsc for monorepo frontend packages.
- Linux / POSIX shell environment (or local WSL2/PowerShell) with `openssh-server`, `ufw` or `iptables`, and standard POSIX permission utilities (`chmod`, `chown`).
- Local environment variables configured in `services/api/.env` (validated against `JWT_SECRET_KEY`, non-wildcard `CORS_ALLOWED_ORIGINS`).

### 1.2 Preparation Commands

```bash
# 1. Monorepo root check & dependencies
npm run typecheck

# 2. Python service environment sync
cd services/api
uv sync
```

---

## 2. Validation Scenarios

### Scenario 1: OWASP Audit Matrix Completeness & Schema Validation
**Goal**: Verify that all 10 OWASP Top 10 categories are independently evaluated across Backend, Frontend, and Agentic components with explicit verdicts and citations according to [contracts/owasp-audit-matrix.schema.json](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/contracts/owasp-audit-matrix.schema.json).

```bash
# Run automated validation of the audit findings matrix schema
cd services/api
uv run python -m pytest tests/unit/test_security_audit_matrix.py -v
```

**Expected Outcome**:
- 100% of the 10 OWASP categories are evaluated for backend, frontend, and agentic tracks.
- Zero categories omitted or marked as untracked.
- Explicit source citations (file path + lines/endpoints) recorded for all findings.

---

### Scenario 2: Host Server Baseline & SSH Hardening Verification
**Goal**: Verify that direct root SSH logins are rejected, operational tasks run as non-root, sensitive files have strict masks, and non-essential ports are denied.

```bash
# 1. Verify SSH daemon configuration directives
sshd -T | grep -E "permitrootlogin|passwordauthentication|maxauthtries"
# Expected:
# permitrootlogin no
# passwordauthentication no
# maxauthtries 3

# 2. Verify non-root SSH authentication acceptance vs. root rejection
ssh -o BatchMode=yes root@localhost echo "SHOULD_FAIL" || echo "ROOT_LOGIN_REJECTED"
# Expected: ROOT_LOGIN_REJECTED

# 3. Verify firewall status and listening ports
sudo ufw status verbose
# Expected:
# Default: deny (incoming), allow (outgoing)
# To Action From
# 22/tcp ALLOW IN Anywhere
# 80/tcp ALLOW IN Anywhere
# 443/tcp ALLOW IN Anywhere

# 4. Verify filesystem permission masks on secrets
stat -c "%a %U:%G" services/api/.env
# Expected: 600 or 400 with non-root owner
```

**Expected Outcome**:
- Direct root SSH connection attempts are 100% rejected.
- Only necessary public ports (22, 80, 443) accept inbound packets.
- Sensitive environment files are readable solely by the service operational user.

---

### Scenario 3: Agentic Broken Access Control & Tool IDOR Protection
**Goal**: Verify that autonomous support agent tools reject cross-customer order queries and cross-brand metric requests without revealing data or order existence.

```bash
cd services/api
uv run python -m pytest tests/unit/test_agent_guardrails_authorization.py -k "test_cross_customer_order_refusal" -v
```

**Expected Outcome**:
- Querying order `#45821` from a session authenticated as `cust_es_01` (who does not own `#45821`) returns fail-closed access refusal: `ORDER_NOT_IN_AUTHENTICATED_SESSION`.
- Order details, recipient addresses, and carrier tracking links are not leaked.
- Event is logged to the redacted audit registry with masked identifiers.

---

### Scenario 4: Irreversible Action Human-in-the-Loop Gates
**Goal**: Verify that high-impact actions (returns exceeding 100 EUR, carrier changes on in-transit parcels) halt autonomous execution and enter the human approval queue according to [contracts/agent-guardrail-hitl.schema.json](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/contracts/agent-guardrail-hitl.schema.json).

```bash
cd services/api
# 1. Test high-value return approval threshold gate (> 100 EUR)
uv run python -m pytest tests/unit/test_agent_action_policies.py -k "test_return_approval_threshold_gate" -v

# 2. Test in-transit carrier reassignment refusal
uv run python -m pytest tests/unit/test_agent_action_policies.py -k "test_in_transit_carrier_reassignment_gate" -v
```

**Expected Outcome**:
- Return requests with refund value $\le 100.00$ EUR process autonomously if standard policies match.
- Return requests with refund value $> 100.00$ EUR return `PENDING_HUMAN_APPROVAL` with queue assignment.
- Carrier modification for shipments with status `IN_TRANSIT` returns `HUMAN_AUTHORIZATION_REQUIRED`.

---

### Scenario 5: Critical Finding Remediation Proof (CORS & Secret Hygiene)
**Goal**: Verify that identified critical vulnerabilities (such as permissive wildcard CORS with credentials) are remediated with verifiable before-and-after proof.

```bash
cd services/api
# Run CORS security configuration test suite
uv run python -m pytest tests/unit/test_security_cors_configuration.py -v
```

**Expected Outcome**:
- `Origin: https://evil-attacker.com` with `credentials=true` is rejected or not reflected in `Access-Control-Allow-Origin`.
- Configured production frontend domains (`https://app.trackflow.io`) are permitted.
- Zero raw exceptions (`str(e)`) exposed in API responses.

---

### Scenario 6: Full Monorepo Regression & Static Type Gates
**Goal**: Verify that zero regressions or compiler errors exist across the monorepo following all hardening fixes.

```bash
# 1. TypeScript Static Analysis (all uis and packages)
npm run typecheck

# 2. Monorepo Production Build Compilation
npm run build

# 3. Python Service Test Suites
cd services/api
uv run python -m pytest tests/ -v
```

**Expected Outcome**:
- 0 TypeScript compiler errors.
- 0 build failures.
- 100% backend test suites passing.
