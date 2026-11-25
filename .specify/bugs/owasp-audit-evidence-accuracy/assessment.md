# Bug Assessment: OWASP audit evidence is inaccurate (ports, SEC-BK-009, commit refs, host baseline)

- **Slug**: owasp-audit-evidence-accuracy
- **Created**: 2026-11-25
- **Source**: pasted text
- **Verdict**: valid
- **Severity**: high

## Report (verbatim or summarized)

> `docker-compose.yml` continues to expose ports 8000, 6379, and 5555 on 0.0.0.0, and `ufw_setup.sh` fails to block port 5555; since Docker can bypass UFW, the baseline entry specifying 127.0.0.1 is inaccurate. Regarding C06: the report marks `SEC-BK-009` as a resolved critical issue, yet `core/exceptions.py` was already sanitized in the `main` branch—there is no actual diff. Furthermore, both the report and the matrix reference commit `8f4091a` rather than `a15613e` or `602e55c`, and the "before/after" host state is presented as a manually constructed JSON. Please correct the port configurations, remove the spurious critical finding (or provide the actual "before" state), update the evidence to point to the correct commit, and verify the host configuration.

## Symptom

The audit deliverables claim a hardened host (internal ports bound to 127.0.0.1 / blocked) and four resolved CRITICAL findings, with evidence pinned to commit `8f4091a`. The repository contradicts this on several points. Expected: every claim is backed by the current config, a real diff or measurement, and the correct commit.

## Reproduction

1. `docker-compose.yml`: `backend` publishes `"${BACKEND_PORT:-8000}:8000"` (line 38), `redis` publishes `"6379:6379"` (line 72), `flower` publishes `"5555:5555"` (line 116). None has a `127.0.0.1:` prefix, so all bind to 0.0.0.0.
2. `infra/host/ufw_setup.sh:33-35` denies only 8000, 6379 and 6333. 5555 (Flower) is not denied. Flower's default credentials are `admin:admin` (`docker-compose.yml:121`).
3. `infra/host/baseline_post.json:39-52` lists 8000 and 6379 as `bind_address: 127.0.0.1` / `is_allowed_public: false`, and does not list 5555. Docker publishes ports through its own iptables `DOCKER` chain, which bypasses UFW's INPUT rules, so the UFW denies do not take effect for published container ports. The baseline is therefore not what this compose file produces.
4. `git diff main -- services/api/core/exceptions.py` is empty. The file was last changed on `main` in `4a38d68`. `critical_remediation_proof.md:79` admits this, but `backend_audit.md:33` and `owasp_audit_matrix.json:193-203` still set `SEC-BK-009` to CRITICAL / `VERIFIED_RESOLVED`. `executive_summary.md:18` counts it among 4 resolved criticals. `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md:126,236` repeat the claim.
5. `8f4091add62f74d3e578cc5d60f605e75df9d789` is pinned in `agentic_audit.md:11`, `backend_audit.md:7`, `frontend_audit.md:9`, `critical_remediation_proof.md:6`, `executive_summary.md:8,60` and `owasp_audit_matrix.json:6`. Branch history, newest first: `602e55c` (audit report), `a15613e` (PR-findings fix: HITL auth), `2c9b3f7`, `da4841e`, `8f4091a` (a WebSocket/bug-docs commit that predates the OWASP work). The pinned commit predates the code the audit certifies.
6. `infra/host/baseline_pre.json` and `baseline_post.json` have round-number timestamps (`00:00:00Z`, `01:00:00Z`) and the fictional `HOST-BASE-*` profile ids. Tasks T020/T025 describe them as "captured", and `git log` shows they were added in the feature commits with no capture script. They match the schema but are hand-authored. The pre-state lists a uvicorn/redis host install, while the project deploys these services through Docker Compose.

[NEEDS CLARIFICATION: is there a real target host to capture from? Nothing in the repo identifies one, and no live host was inspected during this assessment.]

## Suspected Code Paths

- `docker-compose.yml:37-38, 71-72, 115-116` — 8000, 6379 and 5555 published on all interfaces.
- `infra/host/ufw_setup.sh:31-35` — misses 5555. A `ufw deny` does not stop Docker-published ports. Rules belong in `DOCKER-USER`, or the ports should be bound to loopback.
- `infra/host/baseline_pre.json`, `infra/host/baseline_post.json` — hand-built snapshots, and the post snapshot contradicts the compose file.
- `infra/host/verify_hardening.sh` — check whether it inspects real listeners (`ss -ltn`) or only the UFW status. [NEEDS CLARIFICATION: not re-read in this pass.]
- `specs/036-owasp-audit-hardening/data-model.md:203` — requires internal ports to be bound to 127.0.0.1 or blocked externally.
- `specs/036-owasp-audit-hardening/audit/*.md`, `owasp_audit_matrix.json` — stale commit hash and the spurious critical finding.
- `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md:126,236` and `executive_summary.md:18` — "4 criticals" count.

## Root Cause Hypothesis

The audit documents were written from the intended design (a hardened baseline plus default-deny UFW) rather than from measured state. The compose file was never changed to match, and the commit hash was stamped when the audit started and never refreshed. SEC-BK-009 was classified as an in-PR remediation although the fix already existed on `main`, so it is pre-existing, already-mitigated behavior and not a remediation delivered by this branch. Confidence: high. The claims can be checked directly against the files.

## Proposed Remediation

**Preferred**:
1. **Ports.** In `docker-compose.yml`, bind to loopback: `"127.0.0.1:${BACKEND_PORT:-8000}:8000"`, `"127.0.0.1:6379:6379"` and `"127.0.0.1:5555:5555"`. Remove the `admin:admin` default for `FLOWER_BASIC_AUTH` and require the variable to be set. Also decide whether the `ui` ports (3000/3001) are meant to be public. Keep reaching the app through Caddy on 80/443. In `ufw_setup.sh`, add `5555/tcp` to the deny list for consistency, and add a comment or `DOCKER-USER` rules stating that UFW alone does not govern published Docker ports.
2. **Baseline.** Replace the hand-built JSON with a capture script, for example `infra/host/capture_baseline.sh`. It would emit `ss -ltnH`, `ufw status`, `docker ps --format '{{.Ports}}'`, `iptables -S DOCKER-USER`, `sshd -T` and `stat`, with real timestamp, hostname and commit SHA, and write `baseline_post.json` from it. Run it on the actual host and commit the output. If no "before" capture exists, label `baseline_pre.json` as `"provenance": "illustrative"` or delete it, and state that no pre-state was measured. Do not present it as evidence.
3. **SEC-BK-009.** Either remove it from the findings as not applicable to this change set, or reclassify it as `PRE_EXISTING_MITIGATED` with no severity claim. Add a note that it is covered by `test_error_handling_sanitization.py`. Update the "4 criticals" figures to 3 in `executive_summary.md`, `critical_remediation_proof.md`, the matrix and the report. Alternatively, supply the real "before" by pointing to the commit in which `str(e)` leaked, if one exists in history.
4. **Commit references.** Pin the evidence to the commit the audit certifies, and stamp the reviewed commit (`602e55c` or its successor) in the matrix `commit_hash` and the markdown headers. Prefer short SHAs generated by a script, or a "reviewed at" field set at release time, to avoid drift.
5. **Verify.** Run `docker compose config`, then `docker compose up -d`, then `ss -ltn` on the host. Confirm that 8000, 6379 and 5555 appear only on 127.0.0.1 and that external connections to them fail.

**Alternatives**:
- Keep the ports published but enforce `DOCKER-USER` iptables rules. This is more fragile and easy to misconfigure.
- Remove the `ports:` mapping for redis and flower entirely and reach them with `docker exec` or an SSH tunnel. This is the strictest option, but it hurts dev ergonomics (Flower UI).

**Files likely to change**:
- `docker-compose.yml`
- `infra/host/ufw_setup.sh`
- `infra/host/baseline_pre.json`, `infra/host/baseline_post.json` (and a new capture script)
- `infra/README.md`
- `specs/036-owasp-audit-hardening/audit/*.md` and `owasp_audit_matrix.json`
- `docs/cybersecurity-analysis/owasp-top10-security-audit-report.md`
- `services/api/tests/integration/test_host_hardening_verification.py`

**Tests to add or update**:
- A test that parses `docker-compose.yml` and asserts every published port other than 3000/3001 starts with `127.0.0.1:`.
- A test that every internal port in the compose file (8000, 6379, 5555) is also covered by `ufw_setup.sh`.
- A matrix test asserting that no CRITICAL finding is `VERIFIED_RESOLVED` unless a fixing diff or test is referenced, and that `commit_hash` resolves via `git cat-file` and is an ancestor of HEAD.

## Risks & Considerations

- Loopback binding breaks direct remote access to the Flower UI and to Redis from other hosts, and any workflow that uses them (monitoring, remote debugging). Docker Desktop on Windows/macOS still forwards localhost, so local dev is unaffected.
- The UI container reaches the backend over `trackflow-net` (`http://backend:8000`), so the loopback change should not affect it. `NEXT_PUBLIC_API_URL=http://localhost:8000` is used by the browser, so it works only on the same machine. Production routing through Caddy needs confirming.
- Lowering the critical count (4 to 3) changes the "0 unresolved criticals" sign-off text and regulatory messaging. Have a reviewer approve it.
- `SEC-BK-009` still deserves a residual check: confirm `generic_exception_handler` is registered in `main.py` and that logs do not contain secrets.
- No live host was inspected here, so the `127.0.0.1` baseline cannot be called either right or wrong for the real server. It is only inconsistent with the repo's compose file.

## Open Questions

- [NEEDS CLARIFICATION: which host/environment is the audited target, and is there a real pre-hardening capture?]
- [NEEDS CLARIFICATION: should the audit be pinned to `602e55c`, or to a new commit created after these corrections?]
- [NEEDS CLARIFICATION: should Flower and Redis be loopback-only, or removed from the host network entirely in production?]
