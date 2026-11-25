"""Repository adapter for reading NIST CSF 2.0 and AI Governance artifacts.

Loads validated specifications from specs/037-nist-security-practices/data/.
Adheres to Monorepo Constitution Principle I and Principle II.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def find_monorepo_root() -> Path:
    """Resolve the monorepo root directory dynamically."""
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / ".specify").exists() or (parent / "specs").exists():
            return parent
    return Path.cwd()


class NISTGovernanceRepository:
    """File-backed JSON repository providing access to NIST CSF and AI governance catalogs."""

    def __init__(self, data_dir: Optional[Path] = None) -> None:
        """Initialize repository pointing to specification data directory."""
        if data_dir is not None:
            self._data_dir = data_dir
        else:
            root = find_monorepo_root()
            self._data_dir = root / "specs" / "037-nist-security-practices" / "data"

    def _read_json_file(self, filename: str) -> Any:
        """Read and parse a JSON artifact from the data directory."""
        file_path = self._data_dir / filename
        if not file_path.exists():
            raise FileNotFoundError(f"NIST governance artifact not found at: {file_path}")
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def get_csf_report(self) -> Dict[str, Any]:
        """Load the complete 6-function NIST CSF 2.0 assessment report."""
        return self._read_json_file("nist_csf_baseline.json")

    def list_ai_inventory(self) -> List[Dict[str, Any]]:
        """Load the authoritative AI systems inventory catalog across all 5 operational components."""
        return self._read_json_file("ai_systems_inventory.json")

    def list_shared_responsibility(self) -> List[Dict[str, Any]]:
        """Load the demarcated third-party AI provider shared responsibility matrix."""
        return self._read_json_file("shared_responsibility_matrix.json")

    def list_residual_risks(
        self,
        severity: Optional[str] = None,
        nist_function: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Load residual risks ledger with optional severity and NIST function filtering."""
        risks = self._read_json_file("residual_risks.json")
        if severity:
            sev_upper = severity.upper()
            risks = [r for r in risks if r.get("severity") == sev_upper]
        if nist_function:
            fn_upper = nist_function.upper()
            risks = [r for r in risks if r.get("nist_function") == fn_upper]
        return risks


_default_nist_repo: Optional[NISTGovernanceRepository] = None


def get_nist_governance_repository() -> NISTGovernanceRepository:
    """Singleton provider for NIST governance repository."""
    global _default_nist_repo
    if _default_nist_repo is None:
        _default_nist_repo = NISTGovernanceRepository()
    return _default_nist_repo
