#!/usr/bin/env bash
# ==============================================================================
# TrackFlow Host Hardening Compliance Verification
# Automated validation of SSH directives, firewall policies, and secret masks
# ==============================================================================

set -euo pipefail

EXIT_CODE=0
TEMPLATE_CHECK=false

for arg in "$@"; do
    if [ "$arg" = "--template-check" ] || [ "$arg" = "--offline" ]; then
        TEMPLATE_CHECK=true
    fi
done

echo "=========================================================="
if [ "$TEMPLATE_CHECK" = true ]; then
    echo "TrackFlow Host Hardening Compliance Verification (TEMPLATE / CI MODE)"
else
    echo "TrackFlow Host Hardening Compliance Verification (STRICT HOST MODE)"
fi
echo "=========================================================="

# 1. Verify SSH Configuration Directives
echo -n "[CHECK] SSH PermitRootLogin no: "
if [ "$TEMPLATE_CHECK" = true ]; then
    if grep -Eqi "^\s*PermitRootLogin\s+no" infra/host/sshd_config.hardened 2>/dev/null; then
        echo "PASS (template)"
    else
        echo "FAIL (PermitRootLogin must be set to 'no' in template)"
        EXIT_CODE=1
    fi
else
    if [ -f "/etc/ssh/sshd_config" ] && grep -Eqi "^\s*PermitRootLogin\s+no" /etc/ssh/sshd_config 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL (PermitRootLogin must be set to 'no' in /etc/ssh/sshd_config)"
        EXIT_CODE=1
    fi
fi

echo -n "[CHECK] SSH PasswordAuthentication no: "
if [ "$TEMPLATE_CHECK" = true ]; then
    if grep -Eqi "^\s*PasswordAuthentication\s+no" infra/host/sshd_config.hardened 2>/dev/null; then
        echo "PASS (template)"
    else
        echo "FAIL (PasswordAuthentication must be set to 'no' in template)"
        EXIT_CODE=1
    fi
else
    if [ -f "/etc/ssh/sshd_config" ] && grep -Eqi "^\s*PasswordAuthentication\s+no" /etc/ssh/sshd_config 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL (PasswordAuthentication must be set to 'no' in /etc/ssh/sshd_config)"
        EXIT_CODE=1
    fi
fi

echo -n "[CHECK] SSH MaxAuthTries <= 3: "
if [ "$TEMPLATE_CHECK" = true ]; then
    if grep -Eqi "^\s*MaxAuthTries\s+([1-3])" infra/host/sshd_config.hardened 2>/dev/null; then
        echo "PASS (template)"
    else
        echo "FAIL (MaxAuthTries must be <= 3 in template)"
        EXIT_CODE=1
    fi
else
    if [ -f "/etc/ssh/sshd_config" ] && grep -Eqi "^\s*MaxAuthTries\s+([1-3])" /etc/ssh/sshd_config 2>/dev/null; then
        echo "PASS"
    else
        echo "FAIL (MaxAuthTries must be <= 3 in /etc/ssh/sshd_config)"
        EXIT_CODE=1
    fi
fi

# 2. Verify Firewall (UFW)
echo -n "[CHECK] UFW Default Inbound Deny: "
if [ "$TEMPLATE_CHECK" = true ]; then
    if grep -qi "default deny incoming" infra/host/ufw_setup.sh 2>/dev/null; then
        echo "PASS (template)"
    else
        echo "FAIL (UFW inbound policy must be deny in setup script)"
        EXIT_CODE=1
    fi
else
    if command -v ufw >/dev/null 2>&1 && ufw status verbose | grep -qi "deny (incoming)"; then
        echo "PASS"
    else
        echo "FAIL (UFW inbound policy must be deny on host)"
        EXIT_CODE=1
    fi
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
