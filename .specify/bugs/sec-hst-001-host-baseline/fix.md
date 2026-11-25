# Bug Fix: Reclassify Unmeasured SEC-HST-001 Host Baseline & Parse Live Host Probes

- **Slug**: sec-hst-001-host-baseline
- **Fixed**: 2026-11-25
- **Assessment**: ./assessment.md
- **Status**: applied

## Summary

Removed `SEC-HST-001` from the resolved `CRITICAL` count (reclassifying it as `HIGH` / `MITIGATED` with documented residual operational risk and deployment runbook across the OWASP audit matrix, executive summary, critical remediation proof, and Spanish cybersecurity report) because `baseline_pre.json` (`illustrative`) and `baseline_post.json` (`captured_config_verification`) are repository/CI configuration artifacts rather than live staging/production Linux captures. Additionally updated `infra/host/capture_baseline.sh` to dynamically parse live host probe outputs (`sshd -T`, `ss -ltnH`, `ufw status`, `docker ps`, `iptables -S DOCKER-USER`) and require `--offline-template` when host utilities are unavailable, and added regression assertions in the unit and integration test suites.

## Changes

| File | Change | Notes |
|------|--------|-------|
| `specs/036-owasp-audit-hardening/audit/owasp_audit_matrix.json` | modified | Reclassified `SEC-HST-001` from `CRITICAL` / `VERIFIED_RESOLVED` to `HIGH` / `MITIGATED`, clarifying CI template verification vs. pending live host OS measurement. |
| `specs/036-owasp-audit-hardening/audit/critical_remediation_proof.md` | modified | Updated resolved criticals count from 3 to 2 (`SEC-BK-005`, `SEC-AG-002`) and documented `SEC-HST-001` residual operational risk and deployment runbook in Sections 2.4 and 3. |
| `specs/036-owasp-audit-hardening/audit/executive_summary.md` | modified | Updated dashboard table and narrative from 3 to 2 code-verified criticals and documented `SEC-HST-001` (`HIGH` / `MITIGATED`) host template status. |
| `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md` | modified | Updated Spanish summary table, matrix row, and Section 7.4 to reflect 2/2 resolved code criticals and `SEC-HST-001` as `HIGH` / `MITIGATED` with live host deployment runbook. |
| `infra/host/capture_baseline.sh` | modified | Parsed `SSHD_T_OUT`, `SS_OUT`, `DOCKER_PORTS`, `UFW_OUT`, and `IPTABLES_DOCKER_USER` into the generated JSON and required `--offline-template` when live host tools are unavailable. |
| `services/api/tests/unit/test_security_audit_matrix.py` | modified | Enforced that `HOST` findings cannot be `CRITICAL` + `VERIFIED_RESOLVED` unless `baseline_post.json` has `"provenance": "measured_host_capture"`. |
| `services/api/tests/integration/test_host_hardening_verification.py` | added test | Added `test_capture_baseline_parses_live_probes_and_guards_unmeasured_provenance` verifying live probe parsing in `capture_baseline.sh` and provenance alignment. |

## Diff Highlights (optional)

```python
    for finding in critical_resolved:
        if finding.component == "HOST":
            assert host_provenance == "measured_host_capture", (
                f"HOST finding {finding.id} cannot be CRITICAL + VERIFIED_RESOLVED when "
                f"baseline_post.json provenance is '{host_provenance}' (requires 'measured_host_capture')"
            )
```

```bash
if [ "$OFFLINE_TEMPLATE" = true ]; then
    PROVENANCE="captured_config_verification"
elif [ -z "$SS_OUT" ] && [ -z "$UFW_OUT" ]; then
    echo "ERROR: Live host probes (ss, ufw) returned empty output. Run on a live Linux host or pass --offline-template for CI config verification." >&2
    exit 1
else
    PROVENANCE="measured_host_capture"
fi
```

## Tests Added or Updated

- `services/api/tests/unit/test_security_audit_matrix.py::test_critical_findings_require_diff_or_test_and_valid_commit_hash` — Rejects any `HOST` finding marked `CRITICAL` + `VERIFIED_RESOLVED` when `infra/host/baseline_post.json` provenance is not `"measured_host_capture"`, and verifies the 2 code-verified criticals (`SEC-BK-005`, `SEC-AG-002`).
- `services/api/tests/integration/test_host_hardening_verification.py::test_capture_baseline_parses_live_probes_and_guards_unmeasured_provenance` — Verifies that `capture_baseline.sh` actively parses `SSH_SOURCE`/`SSHD_T_OUT`, `SS_OUT`, `UFW_OUT`, `DOCKER_PORTS`, and `IPTABLES_DOCKER_USER`, supports `--offline-template`, and prevents unmeasured baselines from certifying `SEC-HST-001` as `VERIFIED_RESOLVED`.

## Local Verification

- Commands run: `uv run --project services/api pytest services/api/tests/unit/test_security_audit_matrix.py services/api/tests/unit/test_host_baseline_schema.py services/api/tests/integration/test_host_hardening_verification.py services/api/tests/unit/test_security_cors_configuration.py services/api/tests/unit/test_error_handling_sanitization.py services/api/tests/unit/test_guardrail_observability_redaction.py -v` → `19 passed in 0.58s`
- Manual checks: Verified summary tables and counts across `owasp_audit_matrix.json`, `critical_remediation_proof.md`, `executive_summary.md`, and `owasp-top10-security-audit-report.md` all consistently total 31 findings (`2 Critical`, `10 High`, `9 Medium`, `3 Low`, `7 Does Not Apply`).

## Deviations from Assessment

None. Applied the preferred Option B remediation since the workspace runs in a local Windows environment without SSH access to a live Linux staging/production host.

## Follow-ups

- During staging/production Linux server provisioning, execute `sudo bash infra/host/verify_hardening.sh` and `sudo bash infra/host/capture_baseline.sh infra/host/baseline_post.json POST_REMEDIATION` on the target host and commit the `"provenance": "measured_host_capture"` output before promoting `SEC-HST-001` to `VERIFIED_RESOLVED`.
