# Phase 0 Research: TrackFlow OWASP Top 10 Security Audit, Infrastructure Hardening, and Critical Remediation

**Feature Branch**: `feature/owasp-top10-audit`  
**Specification**: [specs/036-owasp-audit-hardening/spec.md](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/036-owasp-audit-hardening/spec.md)  
**Date**: 2026-11-25  

---

## 1. Research Overview & Problem Statement

TrackFlow Tech operates an integrated logistics intelligence platform running across Los Angeles (USA) and Zaragoza (Spain). The monorepo incorporates:
- **Backend Services** (`services/api`): FastAPI REST API, SQLModel/TinyDB storage, telemetry, incident management, inventory, and suppliers.
- **Frontend Applications** (`uis/`): Next.js App Router applications (`uis/backoffice`, `uis/website`, `uis/talent-pipeline-tracker`).
- **Autonomous Agentic Systems** (`agents/`, `services/api/application/services/agent_*`, LangGraph workflows, and `mcps/trackflow-server`): 24/7 CX support agent, carrier selection engine, return approval engine, and Qdrant RAG knowledge base.
- **Host Infrastructure**: Linux server environment running SSH, operational daemons, and reverse proxies.

The goal of this initiative is to execute a rigorous security audit against the **OWASP Top 10 (2021)** and baseline infrastructure hardening benchmarks, remediate all critical findings with reproducible verification proof, and enforce strict human-in-the-loop authorization gates on irreversible actions without regressing existing monorepo capabilities.

---

## 2. Research Findings & Architectural Decisions

### Decision 1: Tri-Track OWASP Top 10 Audit Matrix Architecture

- **Decision**: Structure the OWASP Top 10 audit matrix into three distinct, non-overlapping assessment tracks:
  1. `Backend Track`: FastAPI API endpoints, database interactions, authentication middlewares, background tasks, and CORS configuration.
  2. `Frontend Track`: Next.js client/server components, HTML/DOM sanitation, localStorage/cookie session handling, and Content Security Policy (CSP).
  3. `Agentic System Track`: LangGraph support agent nodes, MCP server tools, Qdrant RAG retriever, prompt injection boundaries, cross-customer/cross-brand tool isolation, and autonomous execution scope.
- **Rationale**: 
  Standard web application scanners and generic OWASP checklists evaluate HTTP requests and static files, completely missing LLM-specific attack vectors such as indirect prompt injection via vector chunks, tool privilege escalation, and cross-tenant memory leakage. The tri-track model ensures 100% of the 10 OWASP categories are evaluated across each layer with explicit applicability verdicts (`applies` vs. `does not apply`) and source code citations.
- **Alternatives Considered**:
  - *Single Unified Matrix*: Rejected because blending agentic vulnerabilities (e.g. prompt injection) with backend issues (e.g. SQL injection) obscures responsibility and creates ambiguous remediation requirements.
  - *OWASP Top 10 for LLM Only*: Rejected because standard web vulnerabilities (e.g., CORS wildcard with credentials in `services/api/main.py`) would be excluded from scope, leaving the monorepo exposed.

---

### Decision 2: Host Server Baseline Hardening Standard

- **Decision**: Define a formal, verifiable host baseline profile covering:
  1. **User Privilege Separation**: Routine administrative and application operations executed under a dedicated non-root user (`trackflow-ops`), with root login disabled.
  2. **SSH Daemon Configuration (`sshd_config`)**: `PermitRootLogin no`, `PasswordAuthentication no` (SSH key only), `MaxAuthTries 3`.
  3. **Host Firewall (`ufw` / `iptables`)**: Default policy `DENY` for incoming traffic; strictly whitelisting port `22/tcp` (administrative SSH), `80/tcp` (HTTP redirect), and `443/tcp` (HTTPS TLS termination).
  4. **Filesystem Permission Segregation**: Application code owned by non-root user (`0755`/`0644`), `.env` and secret credentials set to strict `0600` or `0400` permissions (readable only by process owner), log files restricted to `0750`.
- **Rationale**: 
  Operating system defense-in-depth ensures that an application-level vulnerability (e.g., SSRF or arbitrary file read) cannot immediately pivot into total host compromise or unauthorized access to sensitive carrier integration credentials.
- **Alternatives Considered**:
  - *Container-Only Isolation*: Relying purely on Docker defaults. Rejected because host network ports (such as unfirewalled Docker port bindings) and exposed docker daemon sockets can bypass container restrictions.
  - *Unrecorded Ad-hoc Hardening*: Running arbitrary shell commands without baseline state capture. Rejected because FR-001 and SC-004 mandate verifiable before-and-after audit baselines.

---

### Decision 3: Autonomous Agent Guardrail Boundaries & Human-in-the-Loop (HITL) Gates

- **Decision**: Implement explicit programmatic boundary gates for irreversible and high-impact agentic actions:
  1. **Return Approval Engine Threshold Gate**: Automated return claims evaluate refund value against `MAX_AUTONOMOUS_RETURN_REFUND_EUR` (default: 100.00 EUR). If claim value $\le 100.00$, the engine may approve autonomously if all return window and receipt criteria pass. If claim value $> 100.00$, the engine halts autonomous approval and transitions state to `PENDING_HUMAN_APPROVAL`.
  2. **In-Transit Carrier Reassignment Gate**: If a parcel status is `IN_TRANSIT` or `OUT_FOR_DELIVERY`, autonomous carrier re-selection requests are blocked at the engine layer, returning an explicit `HUMAN_AUTHORIZATION_REQUIRED` response.
  3. **Cross-Customer Order & Cross-Brand Data Isolation**: Agent tool execution queries (`lookup_order`, `get_brand_metrics`) must validate that `session.customer_id == order.customer_id` and `session.brand_id == brand.id`. Mismatches must result in fail-closed access denial (`ORDER_NOT_IN_AUTHENTICATED_SESSION` / `CROSS_BRAND_METRIC_ACCESS_DENIED`) without leaking order existence.
- **Rationale**: 
  Directly addresses OWASP A01 (Broken Access Control) and A04 (Insecure Design) in autonomous workflows, enforcing Section 5 of the system briefing and FR-004/FR-007.
- **Alternatives Considered**:
  - *LLM Prompt-Level Guidance Only*: Instructing the model via system prompt to "only approve returns under 100 euros". Rejected because prompt injections and linguistic confusion can override LLM instructions. Programmatic code boundaries are deterministic and non-bypassable.
  - *Disabling All Autonomous Approvals*: Requiring human review for 100% of claims. Rejected because low-value, zero-risk returns must remain automated to fulfill business SLAs.

---

### Decision 4: Cryptographic Failures & Security Misconfiguration Remediation

- **Decision**:
  1. **CORS Misconfiguration Fix**: In `services/api/main.py`, replace `allow_origins=["*"]` with `allow_credentials=True` (which violates browser security and OWASP A05) with explicit configurable trusted origins from environment (`CORS_ALLOWED_ORIGINS`, defaulting to trusted frontend domains, e.g. `http://localhost:3000`, `https://app.trackflow.io`).
  2. **Secret Management & Logging Hygiene**: Ensure all carrier API tokens (UPS, FedEx, DHL, MRW, SEUR) and webhook signing secrets are read exclusively from environment variables with fail-fast initialization. Extend log masking in `GuardrailObservabilityService` to sanitize carrier credentials, auth tokens, and customer PII.
- **Rationale**: 
  Wildcard CORS with credentials enabled allows arbitrary malicious websites to perform authenticated cross-origin requests against TrackFlow APIs. Hardcoded secret risks violate Constitution Principle IV and OWASP A02.
- **Alternatives Considered**:
  - *Hardcoding staging CORS domains*: Rejected because production environments must dynamically configure trusted origin domains.

---

### Decision 5: Regulatory Compliance (GDPR/RGPD & CCPA/CPRA) Alignment

- **Decision**: Incorporate data privacy controls directly into the audit findings and security incident response procedures:
  - **GDPR / RGPD (Spain/EU)**: Establish technical telemetry for data breaches that logs security violation events to support the mandatory **72-hour AEPD incident notification** window. Enforce recipient PII masking (names, shipping addresses, phone numbers).
  - **CCPA / CPRA (California/USA)**: Implement access control verification that protects consumer personal data from unauthorized profiling, selling, or third-party leakage across brand boundaries.
- **Rationale**: 
  TrackFlow operates between Los Angeles and Zaragoza. Compliance is a legal and contractual requirement under EU Regulation 2016/679 and California Civil Code § 1798.100+.
- **Alternatives Considered**:
  - *Treating Regulatory Compliance as a Separate Legal Artifact*: Rejected because technical architecture and software access controls directly determine regulatory liability.

---

## 3. Best Practices & References

- **OWASP Top 10:2021**:
  - A01:2021 – Broken Access Control
  - A02:2021 – Cryptographic Failures
  - A03:2021 – Injection
  - A04:2021 – Insecure Design
  - A05:2021 – Security Misconfiguration
  - A06:2021 – Vulnerable and Outdated Components
  - A07:2021 – Identification and Authentication Failures
  - A08:2021 – Software and Data Integrity Failures
  - A09:2021 – Security Logging and Monitoring Failures
  - A10:2021 – Server-Side Request Forgery (SSRF)
- **OWASP Top 10 for Large Language Model Applications (2025/2026)**:
  - LLM01: Prompt Injection
  - LLM02: Sensitive Information Disclosure
  - LLM06: Excessive Agency
  - LLM08: Vector and Embedding Weaknesses
- **CIS Linux Benchmark**: Section 5.2 (SSH Server Configuration), Section 3.5 (Firewall Configuration).
- **TrackFlow Constitution**: Principles I, II, III, IV, VI, VII.
