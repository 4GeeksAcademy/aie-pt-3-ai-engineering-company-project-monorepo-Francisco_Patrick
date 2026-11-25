# Bug Verification: Reclassify Unmeasured SEC-HST-001 Host Baseline & Parse Live Host Probes

- **Slug**: sec-hst-001-host-baseline
- **Tested**: 2026-11-25
- **Assessment**: ./assessment.md
- **Fix**: ./fix.md
- **Result**: verified

## Summary

The bug no longer reproduces: `SEC-HST-001` has been removed from the resolved `CRITICAL` count and reclassified as `HIGH` / `MITIGATED` with explicit documentation of its repository template provenance (`baseline_pre.json` = `illustrative`, `baseline_post.json` = `captured_config_verification`), residual operational risk, and mandatory live host provisioning runbook across the OWASP audit matrix, executive summary, critical remediation proof, and Spanish cybersecurity report. In addition, `infra/host/capture_baseline.sh` now actively parses live host probe outputs (`sshd -T`, `ss -ltnH`, `ufw status`, `docker ps`, `iptables -S DOCKER-USER`) and fails closed when host probes are unavailable unless `--offline-template` is passed, and all 19 unit/integration tests pass with zero regressions.

## Checks Performed

| Check | Command / Action | Result | Notes |
|-------|------------------|--------|-------|
| Reproduction (post-fix) | Inspect `owasp_audit_matrix.json`, `critical_remediation_proof.md`, `executive_summary.md`, `owasp-top10-security-audit-report.md`, and `capture_baseline.sh` | pass | `SEC-HST-001` is `HIGH` / `MITIGATED` (2 resolved criticals: `SEC-BK-005`, `SEC-AG-002`); `capture_baseline.sh` parses `SSHD_T_OUT`, `SS_OUT`, `UFW_OUT`, `DOCKER_PORTS`, and `IPTABLES_DOCKER_USER` and requires `--offline-template` when host tools are absent. |
| New / updated tests | `uv run --project services/api pytest services/api/tests/unit/test_security_audit_matrix.py services/api/tests/integration/test_host_hardening_verification.py -v` | pass | 11/11 tests passed, including `test_critical_findings_require_diff_or_test_and_valid_commit_hash` and `test_capture_baseline_parses_live_probes_and_guards_unmeasured_provenance`. |
| Regression suite | `uv run --project services/api pytest services/api/tests/unit/test_security_audit_matrix.py services/api/tests/unit/test_host_baseline_schema.py services/api/tests/integration/test_host_hardening_verification.py services/api/tests/unit/test_security_cors_configuration.py services/api/tests/unit/test_error_handling_sanitization.py services/api/tests/unit/test_guardrail_observability_redaction.py -v` | pass | 19/19 security audit and host baseline unit/integration tests passed in 0.53s. |
| Lint / type-check | `bash -n infra/host/capture_baseline.sh infra/host/verify_hardening.sh infra/host/ufw_setup.sh infra/host/permissions_setup.sh` | pass | Exit code 0; zero shell syntax errors across all host hardening scripts. |

## Output Excerpts

```text
services\api\tests\unit\test_security_audit_matrix.py::test_audit_matrix_contract_schema_adherence PASSED [  5%]
services\api\tests\unit\test_security_audit_matrix.py::test_finding_id_patterns PASSED [ 10%]
services\api\tests\unit\test_security_audit_matrix.py::test_critical_findings_require_diff_or_test_and_valid_commit_hash PASSED [ 15%]
services\api\tests\unit\test_host_baseline_schema.py::test_baseline_pre_schema_adherence PASSED [ 21%]
services\api\tests\unit\test_host_baseline_schema.py::test_baseline_post_schema_adherence PASSED [ 26%]
services\api\tests\integration\test_host_hardening_verification.py::test_capture_baseline_parses_live_probes_and_guards_unmeasured_provenance PASSED [ 68%]
...
======================= 19 passed, 2 warnings in 0.53s ========================
BASH_SYNTAX_EXIT=0
```

## Residual Risks

- Because the local Windows development workspace and CI runner do not have SSH access to a live Linux staging or production server, `infra/host/baseline_post.json` remains tagged `"provenance": "captured_config_verification"` and `SEC-HST-001` is accurately classified as `HIGH` / `MITIGATED` rather than `VERIFIED_RESOLVED`. During actual Linux host provisioning, operations must run `sudo bash infra/host/verify_hardening.sh` (strict host mode) and `sudo bash infra/host/capture_baseline.sh infra/host/baseline_post.json POST_REMEDIATION` to record `"provenance": "measured_host_capture"` before promoting `SEC-HST-001` to `VERIFIED_RESOLVED`.
- On Windows with WSL installed, invoking `bash` in PowerShell resolves to WSL's `C:\WINDOWS\system32\bash.exe` (where `ss -ltnH` is non-empty inside the WSL VM and Windows CRLF line endings in `verify_hardening.sh` trigger `\r` errors unless LF is enforced via `.gitattributes`).

## Recommendation

Close the bug — verified end-to-end against Option B of the assessment. The false certification of `SEC-HST-001` as a resolved critical finding backed by unmeasured baseline files has been eliminated, contract tests now forbid any `HOST` finding from claiming `CRITICAL` + `VERIFIED_RESOLVED` without `"provenance": "measured_host_capture"`, and `capture_baseline.sh` parses live host probes and fails closed when host utilities are unavailable.
