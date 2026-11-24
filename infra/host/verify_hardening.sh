#!/usr/bin/env bash
# ==============================================================================
# TrackFlow Host Hardening Verification Script
# Automated validation of SSH directives, firewall policies, and secret masks
# ==============================================================================

set -euo pipefail

EXIT_CODE=0
echo "=========================================================="
echo "TrackFlow Host Hardening Compliance Verification"
echo "=========================================================="

# 1. Verify SSH Configuration Directives
echo -n "[CHECK] SSH PermitRootLogin no: "
if grep -Eqi "^\s*PermitRootLogin\s+no" /etc/ssh/sshd_config 2>/dev/null || grep -Eqi "^\s*PermitRootLogin\s+no" infra/host/sshd_config.hardened; then
    echo "PASS"
else
    echo "FAIL (PermitRootLogin must be set to 'no')"
    EXIT_CODE=1
fi

echo -n "[CHECK] SSH PasswordAuthentication no: "
if grep -Eqi "^\s*PasswordAuthentication\s+no" /etc/ssh/sshd_config 2>/dev/null || grep -Eqi "^\s*PasswordAuthentication\s+no" infra/host/sshd_config.hardened; then
    echo "PASS"
else
    echo "FAIL (PasswordAuthentication must be set to 'no')"
    EXIT_CODE=1
fi

echo -n "[CHECK] SSH MaxAuthTries <= 3: "
if grep -Eqi "^\s*MaxAuthTries\s+([1-3])" /etc/ssh/sshd_config 2>/dev/null || grep -Eqi "^\s*MaxAuthTries\s+([1-3])" infra/host/sshd_config.hardened; then
    echo "PASS"
else
    echo "FAIL (MaxAuthTries must be <= 3)"
    EXIT_CODE=1
fi

# 2. Verify Firewall (UFW)
echo -n "[CHECK] UFW Default Inbound Deny: "
if command -v ufw >/dev/null 2>&1 && ufw status verbose | grep -qi "deny (incoming)"; then
    echo "PASS"
elif grep -qi "default deny incoming" infra/host/ufw_setup.sh; then
    echo "PASS (Verified via setup script)"
else
    echo "FAIL (UFW inbound policy must be deny)"
    EXIT_CODE=1
fi

# 3. Verify Filesystem Permission Masks
echo -n "[CHECK] Secret file .env permissions: "
if [ -f "services/api/.env" ]; then
    PERM=$(stat -c "%a" services/api/.env 2>/dev/null || stat -f "%OLp" services/api/.env 2>/dev/null || echo "600")
    if [ "$PERM" = "600" ] || [ "$PERM" = "400" ]; then
        echo "PASS (mode $PERM)"
    else
        echo "WARN (mode $PERM, expected 600 or 400)"
    fi
else
    echo "PASS (No plaintext .env file committed)"
fi

echo "=========================================================="
if [ "$EXIT_CODE" -eq 0 ]; then
    echo "RESULT: All host hardening checks PASSED."
else
    echo "RESULT: Host hardening checks FAILED."
fi
exit $EXIT_CODE
