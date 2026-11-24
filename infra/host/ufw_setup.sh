#!/usr/bin/env bash
# ==============================================================================
# TrackFlow Host Firewall Setup Script (UFW / iptables)
# Enforces Default-Deny Inbound Policy & Whitelists Essential Public Ports (22, 80, 443)
# ==============================================================================

set -euo pipefail

echo "==> Configuring Host Firewall Baseline..."

if ! command -v ufw >/dev/null 2>&1; then
    echo "ERROR: ufw command not found. Please install ufw or execute via apt/yum." >&2
    exit 1
fi

# Reset UFW rules to default state
echo "==> Resetting existing UFW rules..."
ufw --force reset

# Set default policies: deny all incoming, allow all outgoing
echo "==> Setting default-deny incoming policy..."
ufw default deny incoming
ufw default allow outgoing

# Whitelist administrative and public service ports
echo "==> Whitelisting essential ports (22, 80, 443)..."
ufw allow 22/tcp comment 'TrackFlow Administrative SSH'
ufw allow 80/tcp comment 'HTTP Webhook & Inbound Redirect'
ufw allow 443/tcp comment 'HTTPS TLS API & Application'

# Explicitly ensure internal service ports are blocked externally
echo "==> Denying external access to internal backend and storage ports..."
ufw deny 8000/tcp comment 'Block direct external access to FastAPI backend'
ufw deny 6379/tcp comment 'Block external Redis port'
ufw deny 6333/tcp comment 'Block external Qdrant port'

# Enable firewall non-interactively
echo "==> Enabling UFW firewall..."
ufw --force enable

echo "==> UFW configuration completed successfully."
ufw status verbose
