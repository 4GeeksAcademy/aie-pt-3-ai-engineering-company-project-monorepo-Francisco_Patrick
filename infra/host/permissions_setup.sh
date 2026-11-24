#!/usr/bin/env bash
# ==============================================================================
# TrackFlow Host Filesystem Permission Enforcement Script
# Restricts secret files (.env) to 0600 and directories to 0755
# ==============================================================================

set -euo pipefail

OPERATIONAL_USER="${HOST_OPERATIONAL_USER:-trackflow-ops}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Enforcing filesystem security masks for operational user: ${OPERATIONAL_USER}..."

# 1. Ensure dedicated operational user exists
if ! id -u "${OPERATIONAL_USER}" >/dev/null 2>&1; then
    echo "Creating operational user ${OPERATIONAL_USER}..."
    useradd -m -s /bin/bash "${OPERATIONAL_USER}" || true
fi

# 2. Restrict repository directory permissions (0755)
echo "==> Restricting repository directories..."
find "${REPO_ROOT}" -type d -not -path "*/.*" -exec chmod 755 {} +

# 3. Restrict code and standard files (0644)
echo "==> Restricting code and documentation files..."
find "${REPO_ROOT}" -type f \( -name "*.py" -o -name "*.ts" -o -name "*.tsx" -o -name "*.json" -o -name "*.md" \) -exec chmod 644 {} +

# 4. Strict permissions on secret environment files (0600)
echo "==> Setting strict 0600 mask on all secret .env files..."
find "${REPO_ROOT}" -type f -name ".env*" -not -name "*.example" -exec chmod 600 {} +

# If operational user exists, adjust ownership
if id -u "${OPERATIONAL_USER}" >/dev/null 2>&1; then
    echo "==> Assigning ownership to ${OPERATIONAL_USER}..."
    chown -R "${OPERATIONAL_USER}:${OPERATIONAL_USER}" "${REPO_ROOT}" 2>/dev/null || true
fi

echo "==> Filesystem permission enforcement completed successfully."
