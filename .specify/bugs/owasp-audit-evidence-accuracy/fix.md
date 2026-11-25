# Bug Fix: OWASP audit evidence accuracy (ports, SEC-BK-009, commit refs, host baseline)

- **Slug**: owasp-audit-evidence-accuracy
- **Fixed**: 2026-11-25
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Bound internal Docker Compose ports (`8000`, `6379`, `5555`) to `127.0.0.1`, removed the `admin:admin` fallback from `FLOWER_BASIC_AUTH`, added `5555/tcp` and Docker `DOCKER-USER` bypass guidance to `ufw_setup.sh`, introduced `infra/host/capture_baseline.sh` with provenance-tagged baselines, reclassified `SEC-BK-009` as `PRE_EXISTING_MITIGATED` (`INFORMATIONAL` / `DOES_NOT_APPLY`, reducing the resolved critical count from 4 to 3), updated audit commit hashes from `8f4091a` to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`, and added regression tests for compose loopback bindings, UFW coverage, and audit matrix evidence accuracy.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `docker-compose.yml` | modified | Bound `backend` (`8000`), `redis` (`6379`), and `flower` (`5555`) ports to `127.0.0.1:`; required `FLOWER_BASIC_AUTH` without `admin:admin` fallback. |
| `infra/host/ufw_setup.sh` | modified | Added `ufw deny 5555/tcp` and documented Docker `DOCKER` chain / `DOCKER-USER` interaction. |
| `infra/host/capture_baseline.sh` | added | Added automated baseline capture script probing sockets, UFW, Docker ports, `DOCKER-USER`, `sshd`, and file modes with real commit SHA and hostname. |
| `infra/host/baseline_pre.json` | modified | Marked `"provenance": "illustrative"` (`HOST-BASE-PRE-001-ILLUSTRATIVE`) and aligned pre-hardening Docker port listeners (`8000`, `6379`, `5555`). |
| `infra/host/baseline_post.json` | modified | Updated post-remediation snapshot with `127.0.0.1` bindings for `8000`, `6379`, and `5555`, UFW `DENY` rules, `"provenance": "captured_config_verification"`, and commit `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`. |
| `infra/README.md` | modified | Documented loopback port binding (`5555` included), Docker/UFW interaction, and `capture_baseline.sh` invocation. |
| `specs/036-owasp-audit-hardening/audit/owasp_audit_matrix.json` | modified | Pinned `commit_hash` to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`, reclassified `SEC-BK-009` as `PRE_EXISTING_MITIGATED` (`INFORMATIONAL` / `DOES_NOT_APPLY`), and included `SEC-HST-001` (`CRITICAL` / `VERIFIED_RESOLVED`). |
| `specs/036-owasp-audit-hardening/audit/backend_audit.md` | modified | Updated commit hash to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54` and reclassified `SEC-BK-009` to `PRE_EXISTING_MITIGATED` (`INFORMATIONAL`). |
| `specs/036-owasp-audit-hardening/audit/agentic_audit.md` | modified | Updated commit hash to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`. |
| `specs/036-owasp-audit-hardening/audit/frontend_audit.md` | modified | Updated commit hash to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`. |
| `specs/036-owasp-audit-hardening/audit/critical_remediation_proof.md` | modified | Updated commit hash to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`, updated critical count from 4 to 3 (`SEC-BK-005`, `SEC-AG-002`, `SEC-HST-001`), and noted `SEC-BK-009` as pre-existing on `main` (`4a38d68`). |
| `specs/036-owasp-audit-hardening/audit/executive_summary.md` | modified | Updated commit hash to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54` and updated critical count from 4 to 3 (`3/3 Critical Remediated`). |
| `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md` | modified | Updated certified commit reference to `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`, updated critical count from 4 to 3, and reclassified `SEC-BK-009` as `PRE_EXISTING_MITIGATED`. |
| `services/api/presentation/schemas/security_audit.py` | modified | Added `"PRE_EXISTING_MITIGATED"` to `SecurityFindingSchema.verification_status` and optional `provenance`, `hostname`, `commit_hash` fields to `HostHardeningBaselineResponse`. |
| `services/api/domain/agent/entities.py` | modified | Added `"PRE_EXISTING_MITIGATED"` to `VerificationStatus`. |
| `specs/036-owasp-audit-hardening/contracts/owasp-audit-matrix.schema.json` | modified | Added `"PRE_EXISTING_MITIGATED"` to `verification_status` enum. |
| `specs/036-owasp-audit-hardening/contracts/host-hardening-baseline.schema.json` | modified | Added optional `provenance`, `hostname`, and `commit_hash` properties. |
| `services/api/tests/integration/test_host_hardening_verification.py` | added test | Added tests verifying `docker-compose.yml` loopback bindings (`127.0.0.1:`), absence of `admin:admin` fallback, and `ufw_setup.sh` coverage for all internal compose ports (`8000`, `6379`, `5555`). |
| `services/api/tests/unit/test_security_audit_matrix.py` | added test | Added test verifying `commit_hash` resolves via `git cat-file` as an ancestor of `HEAD` and that every `CRITICAL` `VERIFIED_RESOLVED` finding has a real diff relative to `8f4091a` and references a test file. |

## Diff Highlights (optional)

```yaml
# docker-compose.yml
  backend:
    ports:
      - "127.0.0.1:${BACKEND_PORT:-8000}:8000"
  redis:
    ports:
      - "127.0.0.1:6379:6379"
  flower:
    ports:
      - "127.0.0.1:5555:5555"
    environment:
      - FLOWER_BASIC_AUTH=${FLOWER_BASIC_AUTH:?FLOWER_BASIC_AUTH must be set}
```

```json
    {
      "id": "SEC-BK-009",
      "component": "BACKEND",
      "category": "A09_LOGGING_MONITORING_FAILURES",
      "title": "Pre-Existing Global Exception Handler Sanitization",
      "location": "services/api/core/exceptions.py",
      "severity": "INFORMATIONAL",
      "applicability": "DOES_NOT_APPLY",
      "verification_status": "PRE_EXISTING_MITIGATED",
      "verification_proof": "Pre-existing mitigation on main (commit 4a38d68); verified by services/api/tests/unit/test_error_handling_sanitization.py."
    }
```

## Tests Added or Updated

- `services/api/tests/integration/test_host_hardening_verification.py::test_docker_compose_internal_ports_bound_to_loopback` — Parses `docker-compose.yml` and asserts every published port other than `3000`/`3001` starts with `127.0.0.1:`, and that `admin:admin` is not used as a fallback.
- `services/api/tests/integration/test_host_hardening_verification.py::test_ufw_setup_covers_all_compose_internal_ports` — Asserts every internal port in `docker-compose.yml` (`8000`, `6379`, `5555`) is covered by a `ufw deny <port>/tcp` rule in `infra/host/ufw_setup.sh`.
- `services/api/tests/unit/test_security_audit_matrix.py::test_critical_findings_require_diff_or_test_and_valid_commit_hash` — Asserts `commit_hash` resolves via `git cat-file -e` and is an ancestor of `HEAD` (not `8f4091a`), and that no `CRITICAL` finding is `VERIFIED_RESOLVED` unless its target file has a real diff relative to `8f4091a` and its `verification_proof` references a test file.

## Local Verification

- Commands run:
  - `uv run --project services/api pytest services/api/tests/unit/test_security_audit_matrix.py services/api/tests/unit/test_audit_matrix_completeness.py services/api/tests/unit/test_host_baseline_schema.py services/api/tests/integration/test_host_hardening_verification.py services/api/tests/unit/test_security_cors_configuration.py services/api/tests/unit/test_error_handling_sanitization.py services/api/tests/unit/test_guardrail_observability_redaction.py -v` → 21 passed in 0.64s
  - `$env:FLOWER_BASIC_AUTH="flower_admin:verify_pass" ; docker compose config --services` → Validated compose configuration (`redis`, `flower`, `backend`, `ui`, `worker`)
- Manual checks: Verified `git grep "8f4091a"` no longer matches any active audit header or `owasp_audit_matrix.json` metadata.

## Deviations from Assessment

- Expanded scope to update `services/api/presentation/schemas/security_audit.py`, `services/api/domain/agent/entities.py`, `specs/036-owasp-audit-hardening/contracts/owasp-audit-matrix.schema.json`, and `specs/036-owasp-audit-hardening/contracts/host-hardening-baseline.schema.json`: because the Pydantic schemas use `ConfigDict(extra="forbid")`, adding `"PRE_EXISTING_MITIGATED"` to the `verification_status` enum and optional `provenance`, `hostname`, and `commit_hash` fields to `HostHardeningBaselineResponse` was necessary so that `test_security_audit_matrix.py`, `test_audit_matrix_completeness.py`, and `test_host_baseline_schema.py` validate cleanly.
- Added `SEC-HST-001` (`HOST` / `A05_SECURITY_MISCONFIGURATION` / `CRITICAL` / `VERIFIED_RESOLVED`) directly into `specs/036-owasp-audit-hardening/audit/owasp_audit_matrix.json` so that the matrix JSON itself lists all 3 resolved CRITICAL findings (`SEC-BK-005`, `SEC-AG-002`, `SEC-HST-001`), matching `executive_summary.md`, `critical_remediation_proof.md`, and `owasp-top10-security-audit-report.md`.
- No live target Linux host was available in the local Windows development environment to run `docker compose up -d` and `ss -ltn`; instead, `infra/host/capture_baseline.sh` was created to support both live Linux host socket probing and config verification snapshots (`"provenance": "captured_config_verification"`).

## Follow-ups

- Execute `./infra/host/capture_baseline.sh infra/host/baseline_post.json` on the staging/production Linux host after deployment to record a `"measured_host_capture"` snapshot from the live environment.
- Ensure `FLOWER_BASIC_AUTH` is populated in deployment secret managers / root `.env` before invoking `docker compose up -d`.
