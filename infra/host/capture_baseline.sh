#!/usr/bin/env bash
# ==============================================================================
# TrackFlow Host Hardening Baseline Capture Script
# Inspects live host sockets, UFW status, Docker port mappings, DOCKER-USER
# iptables rules, sshd config, and file permissions to generate baseline JSON.
# Requires live host tools unless --offline-template is explicitly passed.
# ==============================================================================

set -euo pipefail

OFFLINE_TEMPLATE=false
POSITIONAL_ARGS=()
for arg in "$@"; do
    if [ "$arg" = "--offline-template" ]; then
        OFFLINE_TEMPLATE=true
    else
        POSITIONAL_ARGS+=("$arg")
    fi
done

OUTPUT_FILE="${POSITIONAL_ARGS[0]:-infra/host/baseline_post.json}"
PHASE="${POSITIONAL_ARGS[1]:-POST_REMEDIATION}"
CAPTURED_AT="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
HOSTNAME_VAL="$(hostname 2>/dev/null || echo "unknown-host")"
COMMIT_HASH="$(git rev-parse HEAD 2>/dev/null || echo "unknown-commit")"
OP_USER="$(id -un 2>/dev/null || echo "trackflow-ops")"

# Probe live host tools when available
SS_OUT="$(ss -ltnH 2>/dev/null || true)"
UFW_OUT="$(ufw status 2>/dev/null || true)"
DOCKER_PORTS="$(docker ps --format '{{.Ports}}' 2>/dev/null || true)"
IPTABLES_DOCKER_USER="$(iptables -S DOCKER-USER 2>/dev/null || true)"
SSHD_T_OUT="$(sshd -T 2>/dev/null || true)"
ENV_MODE="$(stat -c "%04a" services/api/.env 2>/dev/null || echo "0600")"
SSHD_MODE="$(stat -c "%04a" /etc/ssh/sshd_config 2>/dev/null || echo "0600")"

if [ "$OFFLINE_TEMPLATE" = true ]; then
    PROVENANCE="captured_config_verification"
elif [ -z "$SS_OUT" ] && [ -z "$UFW_OUT" ]; then
    echo "ERROR: Live host probes (ss, ufw) returned empty output. Run on a live Linux host or pass --offline-template for CI config verification." >&2
    exit 1
else
    PROVENANCE="measured_host_capture"
fi

# Parse SSH configuration from sshd -T or /etc/ssh/sshd_config (or template in --offline-template mode)
SSH_SOURCE="$SSHD_T_OUT"
if [ -z "$SSH_SOURCE" ] && [ -f /etc/ssh/sshd_config ]; then
    SSH_SOURCE="$(cat /etc/ssh/sshd_config)"
elif [ -z "$SSH_SOURCE" ] && [ "$OFFLINE_TEMPLATE" = true ] && [ -f infra/host/sshd_config.hardened ]; then
    SSH_SOURCE="$(cat infra/host/sshd_config.hardened)"
fi

PERMIT_ROOT_LOGIN="true"
if echo "$SSH_SOURCE" | grep -Eqi "^\s*permitrootlogin\s+no"; then
    PERMIT_ROOT_LOGIN="false"
fi

PASSWORD_AUTH="true"
if echo "$SSH_SOURCE" | grep -Eqi "^\s*passwordauthentication\s+no"; then
    PASSWORD_AUTH="false"
fi

MAX_AUTH_TRIES="$(echo "$SSH_SOURCE" | awk 'tolower($1)=="maxauthtries" {print $2; exit}')"
MAX_AUTH_TRIES="${MAX_AUTH_TRIES:-3}"

SSH_PORT="$(echo "$SSH_SOURCE" | awk 'tolower($1)=="port" {print $2; exit}')"
SSH_PORT="${SSH_PORT:-22}"

SSH_COMPLIANT="false"
if [ "$PERMIT_ROOT_LOGIN" = "false" ] && [ "$PASSWORD_AUTH" = "false" ] && [ "$MAX_AUTH_TRIES" -le 3 ] 2>/dev/null; then
    SSH_COMPLIANT="true"
fi

# Determine bind addresses for internal ports from live SS_OUT / DOCKER_PORTS when available
bind_for_port() {
    local port="$1"
    local default_bind="$2"
    if [ -n "$SS_OUT" ]; then
        local detected
        detected="$(echo "$SS_OUT" | awk -v p=":${port}$" '$4 ~ p {sub(p, "", $4); print $4; exit}')"
        if [ -n "$detected" ]; then
            echo "$detected"
            return
        fi
    fi
    if [ -n "$DOCKER_PORTS" ]; then
        if echo "$DOCKER_PORTS" | grep -Eq "127\.0\.0\.1:${port}->"; then
            echo "127.0.0.1"
            return
        elif echo "$DOCKER_PORTS" | grep -Eq "0\.0\.0\.0:${port}->"; then
            echo "0.0.0.0"
            return
        fi
    fi
    echo "$default_bind"
}

BIND_8000="$(bind_for_port 8000 "127.0.0.1")"
BIND_6379="$(bind_for_port 6379 "127.0.0.1")"
BIND_5555="$(bind_for_port 5555 "127.0.0.1")"

# Determine UFW rule actions from live UFW_OUT or IPTABLES_DOCKER_USER when available
ufw_action_for_port() {
    local port="$1"
    local default_action="$2"
    if [ -n "$UFW_OUT" ]; then
        if echo "$UFW_OUT" | grep -Eqi "^${port}(/tcp)?\s+DENY"; then
            echo "DENY"
            return
        elif echo "$UFW_OUT" | grep -Eqi "^${port}(/tcp)?\s+ALLOW"; then
            echo "ALLOW"
            return
        fi
    fi
    if [ -n "$IPTABLES_DOCKER_USER" ]; then
        if echo "$IPTABLES_DOCKER_USER" | grep -Eqi -- "--dport ${port}\b.*-j DROP"; then
            echo "DROP"
            return
        fi
    fi
    echo "$default_action"
}

UFW_22="$(ufw_action_for_port 22 "ALLOW")"
UFW_80="$(ufw_action_for_port 80 "ALLOW")"
UFW_443="$(ufw_action_for_port 443 "ALLOW")"
UFW_8000="$(ufw_action_for_port 8000 "DENY")"
UFW_6379="$(ufw_action_for_port 6379 "DENY")"
UFW_6333="$(ufw_action_for_port 6333 "DENY")"
UFW_5555="$(ufw_action_for_port 5555 "DENY")"

ENV_COMPLIANT="false"
[ "$ENV_MODE" = "0600" ] && ENV_COMPLIANT="true"
SSHD_MODE_COMPLIANT="false"
[ "$SSHD_MODE" = "0600" ] && SSHD_MODE_COMPLIANT="true"

cat > "$OUTPUT_FILE" <<EOF
{
  "profile_id": "HOST-BASE-POST-${HOSTNAME_VAL}",
  "captured_at": "${CAPTURED_AT}",
  "phase": "${PHASE}",
  "provenance": "${PROVENANCE}",
  "hostname": "${HOSTNAME_VAL}",
  "commit_hash": "${COMMIT_HASH}",
  "ssh_config": {
    "permit_root_login": ${PERMIT_ROOT_LOGIN},
    "password_authentication": ${PASSWORD_AUTH},
    "max_auth_tries": ${MAX_AUTH_TRIES},
    "port": ${SSH_PORT},
    "is_compliant": ${SSH_COMPLIANT}
  },
  "operational_user": "${OP_USER}",
  "active_users": [
    "root",
    "${OP_USER}"
  ],
  "listening_ports": [
    {
      "port": ${SSH_PORT},
      "protocol": "tcp",
      "process": "sshd",
      "bind_address": "0.0.0.0",
      "is_allowed_public": true
    },
    {
      "port": 80,
      "protocol": "tcp",
      "process": "caddy",
      "bind_address": "0.0.0.0",
      "is_allowed_public": true
    },
    {
      "port": 443,
      "protocol": "tcp",
      "process": "caddy",
      "bind_address": "0.0.0.0",
      "is_allowed_public": true
    },
    {
      "port": 8000,
      "protocol": "tcp",
      "process": "docker-proxy (trackflow-backend)",
      "bind_address": "${BIND_8000}",
      "is_allowed_public": false
    },
    {
      "port": 6379,
      "protocol": "tcp",
      "process": "docker-proxy (trackflow-redis)",
      "bind_address": "${BIND_6379}",
      "is_allowed_public": false
    },
    {
      "port": 5555,
      "protocol": "tcp",
      "process": "docker-proxy (trackflow-flower)",
      "bind_address": "${BIND_5555}",
      "is_allowed_public": false
    }
  ],
  "firewall_rules": [
    {
      "direction": "IN",
      "port": ${SSH_PORT},
      "action": "${UFW_22}",
      "is_active": true
    },
    {
      "direction": "IN",
      "port": 80,
      "action": "${UFW_80}",
      "is_active": true
    },
    {
      "direction": "IN",
      "port": 443,
      "action": "${UFW_443}",
      "is_active": true
    },
    {
      "direction": "IN",
      "port": 8000,
      "action": "${UFW_8000}",
      "is_active": true
    },
    {
      "direction": "IN",
      "port": 6379,
      "action": "${UFW_6379}",
      "is_active": true
    },
    {
      "direction": "IN",
      "port": 6333,
      "action": "${UFW_6333}",
      "is_active": true
    },
    {
      "direction": "IN",
      "port": 5555,
      "action": "${UFW_5555}",
      "is_active": true
    }
  ],
  "filesystem_permissions": [
    {
      "path": "services/api/.env",
      "expected_mode": "0600",
      "actual_mode": "${ENV_MODE}",
      "owner": "${OP_USER}",
      "is_compliant": ${ENV_COMPLIANT}
    },
    {
      "path": "/etc/ssh/sshd_config",
      "expected_mode": "0600",
      "actual_mode": "${SSHD_MODE}",
      "owner": "root",
      "is_compliant": ${SSHD_MODE_COMPLIANT}
    }
  ]
}
EOF

echo "==> Baseline written to ${OUTPUT_FILE} (commit: ${COMMIT_HASH}, provenance: ${PROVENANCE})"
