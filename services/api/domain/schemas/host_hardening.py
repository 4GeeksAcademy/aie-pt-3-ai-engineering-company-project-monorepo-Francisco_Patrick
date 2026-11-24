"""Domain entities and schemas for host server baseline infrastructure hardening.

Defines schemas for SSH configuration, listening ports, firewall rules,
filesystem permission masks, and host hardening compliance verification.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Literal, Optional

BaselinePhase = Literal["PRE_REMEDIATION", "POST_REMEDIATION"]


@dataclass(frozen=True)
class SSHConfigRecord:
    """SSH daemon configuration parameters and compliance indicator."""

    permit_root_login: bool
    password_authentication: bool
    max_auth_tries: int
    port: int = 22
    is_compliant: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "permit_root_login": self.permit_root_login,
            "password_authentication": self.password_authentication,
            "max_auth_tries": self.max_auth_tries,
            "port": self.port,
            "is_compliant": self.is_compliant,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SSHConfigRecord":
        """Reconstruct record from dictionary."""
        return cls(
            permit_root_login=bool(data["permit_root_login"]),
            password_authentication=bool(data["password_authentication"]),
            max_auth_tries=int(data["max_auth_tries"]),
            port=int(data.get("port", 22)),
            is_compliant=bool(data.get("is_compliant", False)),
        )


@dataclass(frozen=True)
class ListeningPortRecord:
    """Network port listening state and public exposure authorization."""

    port: int
    protocol: Literal["tcp", "udp"]
    process: str
    bind_address: str = "0.0.0.0"
    is_allowed_public: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "port": self.port,
            "protocol": self.protocol,
            "process": self.process,
            "bind_address": self.bind_address,
            "is_allowed_public": self.is_allowed_public,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ListeningPortRecord":
        """Reconstruct record from dictionary."""
        return cls(
            port=int(data["port"]),
            protocol=data["protocol"],
            process=str(data["process"]),
            bind_address=str(data.get("bind_address", "0.0.0.0")),
            is_allowed_public=bool(data.get("is_allowed_public", False)),
        )


@dataclass(frozen=True)
class FirewallRuleRecord:
    """Host firewall policy rule."""

    direction: Literal["IN", "OUT"]
    port: int
    action: Literal["ALLOW", "DENY", "DROP"]
    is_active: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "direction": self.direction,
            "port": self.port,
            "action": self.action,
            "is_active": self.is_active,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FirewallRuleRecord":
        """Reconstruct record from dictionary."""
        return cls(
            direction=data["direction"],
            port=int(data["port"]),
            action=data["action"],
            is_active=bool(data.get("is_active", True)),
        )


@dataclass(frozen=True)
class FilePermissionRecord:
    """Filesystem permission mask, ownership, and compliance status."""

    path: str
    expected_mode: str
    actual_mode: str
    owner: str
    is_compliant: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary."""
        return {
            "path": self.path,
            "expected_mode": self.expected_mode,
            "actual_mode": self.actual_mode,
            "owner": self.owner,
            "is_compliant": self.is_compliant,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "FilePermissionRecord":
        """Reconstruct record from dictionary."""
        return cls(
            path=str(data["path"]),
            expected_mode=str(data["expected_mode"]),
            actual_mode=str(data["actual_mode"]),
            owner=str(data["owner"]),
            is_compliant=bool(data.get("is_compliant", False)),
        )


@dataclass(frozen=True)
class HostHardeningBaseline:
    """Host security hardening snapshot across baseline or post-remediation phases."""

    profile_id: str
    phase: BaselinePhase
    ssh_config: SSHConfigRecord
    operational_user: str
    active_users: List[str] = field(default_factory=list)
    listening_ports: List[ListeningPortRecord] = field(default_factory=list)
    firewall_rules: List[FirewallRuleRecord] = field(default_factory=list)
    filesystem_permissions: List[FilePermissionRecord] = field(default_factory=list)
    captured_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert baseline profile to dictionary."""
        return {
            "profile_id": self.profile_id,
            "captured_at": self.captured_at.isoformat(),
            "phase": self.phase,
            "ssh_config": self.ssh_config.to_dict(),
            "operational_user": self.operational_user,
            "active_users": list(self.active_users),
            "listening_ports": [p.to_dict() for p in self.listening_ports],
            "firewall_rules": [r.to_dict() for r in self.firewall_rules],
            "filesystem_permissions": [f.to_dict() for f in self.filesystem_permissions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HostHardeningBaseline":
        """Reconstruct baseline profile from dictionary."""
        captured_raw = data.get("captured_at")
        if isinstance(captured_raw, str):
            captured_at = datetime.fromisoformat(captured_raw.replace("Z", "+00:00"))
        elif isinstance(captured_raw, datetime):
            captured_at = captured_raw
        else:
            captured_at = datetime.now(timezone.utc)

        return cls(
            profile_id=str(data["profile_id"]),
            phase=data["phase"],
            ssh_config=SSHConfigRecord.from_dict(data["ssh_config"]),
            operational_user=str(data["operational_user"]),
            active_users=[str(u) for u in data.get("active_users", [])],
            listening_ports=[ListeningPortRecord.from_dict(p) for p in data.get("listening_ports", [])],
            firewall_rules=[FirewallRuleRecord.from_dict(r) for r in data.get("firewall_rules", [])],
            filesystem_permissions=[FilePermissionRecord.from_dict(f) for f in data.get("filesystem_permissions", [])],
            captured_at=captured_at,
        )


__all__ = [
    "BaselinePhase",
    "FilePermissionRecord",
    "FirewallRuleRecord",
    "HostHardeningBaseline",
    "ListeningPortRecord",
    "SSHConfigRecord",
]
