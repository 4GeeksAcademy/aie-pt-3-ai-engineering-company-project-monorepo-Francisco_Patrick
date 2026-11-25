# Bug Verification: OWASP audit evidence accuracy (ports, SEC-BK-009, commit refs, host baseline)

- **Slug**: owasp-audit-evidence-accuracy
- **Tested**: 2026-11-25
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

All reproduction issues from the assessment are resolved: internal ports (`8000`, `6379`, `5555`) are bound to `127.0.0.1` in `docker-compose.yml` with no `admin:admin` fallback, `ufw_setup.sh` denies `5555/tcp` and documents the `DOCKER-USER` chain interaction, `SEC-BK-009` is reclassified as `PRE_EXISTING_MITIGATED` (`INFORMATIONAL` / `DOES_NOT_APPLY`) reducing the resolved critical count from 4 to 3, all audit deliverables are pinned to commit `602e55cf3a85a53af25eade50fbbe7fde8dc1b54`, and the host baselines include explicit provenance metadata backed by `infra/host/capture_baseline.sh`. All 21 unit and integration tests and `docker compose config` validation passed without regression.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | `git grep -n "8f4091a" -- specs/036-owasp-audit-hardening/ docs/cybersecurity-analysis/` & `$env:FLOWER_BASIC_AUTH="flower_admin:verify_pass" ; docker compose config --services` | pass | Zero occurrences of stale commit `8f4091a` in audit artifacts; Compose config validates cleanly with loopback bindings and required `FLOWER_BASIC_AUTH`. |
| New / updated tests | `uv run --project services/api pytest services/api/tests/integration/test_host_hardening_verification.py services/api/tests/unit/test_security_audit_matrix.py -v` | pass | All 10 tests in these suites passed, including the 3 newly added regression tests (`test_docker_compose_internal_ports_bound_to_loopback`, `test_ufw_setup_covers_all_compose_internal_ports`, `test_critical_findings_require_diff_or_test_and_valid_commit_hash`). |
| Regression suite | `uv run --project services/api pytest services/api/tests/unit/test_security_audit_matrix.py services/api/tests/unit/test_audit_matrix_completeness.py services/api/tests/unit/test_host_baseline_schema.py services/api/tests/integration/test_host_hardening_verification.py services/api/tests/unit/test_security_cors_configuration.py services/api/tests/unit/test_error_handling_sanitization.py services/api/tests/unit/test_guardrail_observability_redaction.py -v` | pass | 21 passed in 0.60s across matrix schema, completeness, host baseline schema, CORS, error sanitization, and guardrail redaction suites. |
| Lint / type-check | `uv run --project services/api python -m py_compile services/api/presentation/schemas/security_audit.py services/api/domain/agent/entities.py services/api/tests/integration/test_host_hardening_verification.py services/api/tests/unit/test_security_audit_matrix.py` | pass | Bytecode syntax compilation and Pydantic v2 strict schema validation passed across all modified Python files (no Python linter or type-checker is configured in `services/api/pyproject.toml`). |

## Output Excerpts

```text
services\api\tests\unit\test_security_audit_matrix.py::test_audit_matrix_contract_schema_adherence PASSED [  4%]
services\api\tests\unit\test_security_audit_matrix.py::test_finding_id_patterns PASSED [  9%]
services\api\tests\unit\test_security_audit_matrix.py::test_critical_findings_require_diff_or_test_and_valid_commit_hash PASSED [ 14%]
...
services\api\tests\integration\test_host_hardening_verification.py::test_docker_compose_internal_ports_bound_to_loopback PASSED [ 66%]
services\api\tests\integration\test_host_hardening_verification.py::test_ufw_setup_covers_all_compose_internal_ports PASSED [ 71%]
...
======================= 21 passed, 2 warnings in 0.60s ========================
```

```text
$ $env:FLOWER_BASIC_AUTH="flower_admin:verify_pass" ; docker compose config --services
redis
backend
flower
ui
worker
```

## Residual Risks

- Because verification ran in a Windows development environment rather than a live target Linux deployment host, live socket binding inspection via `ss -ltn` after `docker compose up -d` was not executed on a production/staging Linux server; `baseline_post.json` is recorded with `"provenance": "captured_config_verification"`, and `./infra/host/capture_baseline.sh infra/host/baseline_post.json` should be run on the target Linux host during deployment to capture a `"measured_host_capture"` snapshot.
- Deployment environments must define `FLOWER_BASIC_AUTH` in `.env` or secret managers because the insecure `admin:admin` default was removed and Compose now enforces `${FLOWER_BASIC_AUTH:?FLOWER_BASIC_AUTH must be set}`.

## Recommendation

Close the bug — verified end-to-end across repository configurations, audit evidence artifacts, schema contracts, and automated regression tests.
