# TrackFlow Infrastructure & Host Hardening Operational Runbook

**Environment**: Production & Staging Linux Hosts (Ubuntu/Debian)  
**Security Baseline**: CIS Linux Benchmark, OWASP Top 10 A05 Hardening, ISO 27001  
**Last Updated**: 2026-11-25

---

## 1. Host Hardening Baseline Overview

To prevent lateral movement and container escapes, TrackFlow hosts enforce four primary hardening pillars:

1. **Non-Root Operational User**: Routine management and daemon execution must use the unprivileged user `trackflow-ops`. Direct root logins over SSH are disabled (`PermitRootLogin no`).
2. **SSH Daemon Restrictions**:
   - `PermitRootLogin no`
   - `PasswordAuthentication no` (Ed25519 or RSA-4096 key pairs only)
   - `MaxAuthTries 3`
   - Configuration template: [infra/host/sshd_config.hardened](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/infra/host/sshd_config.hardened)
3. **Default-Deny Host Firewall (UFW)**:
   - Inbound traffic policy: `DENY`
   - Only administrative SSH (`22/tcp`), HTTP (`80/tcp`), and HTTPS (`443/tcp`) are exposed.
   - Internal service ports (`8000` for FastAPI, `6379` for Redis, `6333` for Qdrant) are restricted to `127.0.0.1` or firewalled externally.
   - Setup automation script: [infra/host/ufw_setup.sh](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/infra/host/ufw_setup.sh)
4. **Filesystem Permission Segregation**:
   - Application directories: `0755`
   - Application code & configs: `0644`
   - Secret files (`.env`): `0600` or `0400` owned by `trackflow-ops`
   - Setup script: [infra/host/permissions_setup.sh](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/infra/host/permissions_setup.sh)

---

## 2. Hardening Execution & Verification

### 2.1 Applying Hardening on Host Server

```bash
# 1. Apply hardened SSH configuration
sudo cp infra/host/sshd_config.hardened /etc/ssh/sshd_config.d/99-trackflow-hardened.conf
sudo sshd -t && sudo systemctl reload sshd

# 2. Configure host firewall
sudo chmod +x infra/host/ufw_setup.sh
sudo infra/host/ufw_setup.sh

# 3. Enforce filesystem permissions
sudo chmod +x infra/host/permissions_setup.sh
sudo infra/host/permissions_setup.sh
```

### 2.2 Verifying Hardening Compliance

```bash
# Run automated verification suite
chmod +x infra/host/verify_hardening.sh
./infra/host/verify_hardening.sh
```

---

## 3. Disaster Recovery & Emergency Break-Glass Access

In the event of an operational lockout or SSH failure:

1. **Cloud Provider Console / Serial Console**:
   - Access the server via the cloud provider's out-of-band serial console (AWS EC2 Instance Connect, GCP Serial Console, or Hetzner vKVM).
2. **Break-Glass Audit Logging**:
   - Any break-glass access using root credentials must be logged as a Security Incident in `specs/036-owasp-audit-hardening/audit/regulatory_compliance.md`.
3. **Secret Rotation**:
   - If an operational host compromise is suspected, immediately rotate:
     - `JWT_SECRET_KEY`
     - Database passwords (Supabase connection pooler)
     - Carrier API keys (UPS, FedEx, DHL, MRW, SEUR)
     - Qdrant API token
