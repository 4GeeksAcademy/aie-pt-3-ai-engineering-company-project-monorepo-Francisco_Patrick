"""Read-only Support Ticket Query Tool adapter for the TrackFlow Support Agent.

Implements `SupportTicketToolPort` (FR-016, FR-017, FR-019, FR-020, FR-021, FR-022):
- Reads live incident records directly from TrackFlow's `IncidentService` (TinyDB `db.json`)
  or via optional HTTP transport (`GET /api/incidents/{id}`, `GET /api/incidents`) when
  `AGENT_API_BASE_URL` is configured.
- Strictly read-only: exposes only `query_tickets` with zero mutation capabilities.
- Enforces an explicit numerical timeout (default `4.0` seconds) via `ThreadPoolExecutor` /
  `httpx.Timeout`.
- Caps returned records at 20 most-recent items while reporting `total_matched`.
"""

from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
import time
from typing import Any, Callable, Dict, List, Optional
import warnings

import httpx

from application.services.incident_service import IncidentService
from domain.agent.entities import (
    TicketRecordDTO,
    TicketToolInput,
    TicketToolOutput,
)
from domain.agent.ports import SupportTicketToolPort
from domain.incident_model import Incident
from domain.knowledge.entities import KnowledgeRuntimeConfig

DEFAULT_TOOL_TIMEOUT_SECONDS = 4.0
MAX_TOOL_RECORDS = 20


class IncidentSupportTicketToolAdapter(SupportTicketToolPort):
    """Read-only adapter querying live support tickets from TrackFlow Incident Manager."""

    def __init__(
        self,
        incident_service: Optional[IncidentService] = None,
        incident_service_factory: Optional[Callable[[], IncidentService]] = None,
        config: Optional[KnowledgeRuntimeConfig] = None,
        timeout_seconds: Optional[float] = None,
        api_base_url: Optional[str] = None,
        internal_api_token: Optional[str] = None,
        http_client: Optional[Any] = None,
    ) -> None:
        """Initialize the read-only Support Ticket Query Tool adapter.

        Authentication mode:
        - In-process mode (default): Invokes `IncidentService` directly within the
          trusted backend boundary (no user JWT required for read operations).
        - HTTP mode (when `api_base_url` / `AGENT_API_BASE_URL` is set): Sends `GET`
          requests to `/api/incidents` with optional `Authorization: Bearer <token>`
          loaded exclusively from `AGENT_INTERNAL_API_TOKEN` in environment config.

        Args:
            incident_service: Optional pre-wired IncidentService instance.
            incident_service_factory: Optional factory returning an IncidentService.
            config: Optional KnowledgeRuntimeConfig instance.
            timeout_seconds: Optional numerical timeout override in seconds (defaults to 4.0s).
            api_base_url: Optional HTTP base URL override.
            internal_api_token: Optional bearer token loaded from environment config.
            http_client: Optional httpx-compatible client for testing HTTP transport.
        """
        warnings.warn(
            "IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. "
            "Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        self._config = config or KnowledgeRuntimeConfig.from_env()
        self._incident_service = incident_service
        self._incident_service_factory = incident_service_factory
        resolved_timeout = (
            float(timeout_seconds)
            if timeout_seconds is not None
            else float(self._config.agent_tool_timeout_seconds or DEFAULT_TOOL_TIMEOUT_SECONDS)
        )
        if resolved_timeout <= 0.0:
            raise ValueError("timeout_seconds must be strictly positive (> 0.0).")
        self._timeout_seconds = resolved_timeout
        self._api_base_url = (
            api_base_url.strip().rstrip("/")
            if api_base_url and api_base_url.strip()
            else self._config.agent_api_base_url
        )
        self._internal_api_token = (
            internal_api_token
            if internal_api_token is not None
            else self._config.agent_internal_api_token
        )
        self._http_client = http_client

    @property
    def timeout_seconds(self) -> float:
        """Return the configured numerical timeout in seconds."""
        return self._timeout_seconds

    @property
    def auth_mode(self) -> str:
        """Return documented authentication mode ('in_process', 'http_bearer', or 'http_unauthenticated')."""
        if self._api_base_url:
            return "http_bearer" if self._internal_api_token else "http_unauthenticated"
        return "in_process"

    def _resolve_service(self) -> IncidentService:
        """Resolve the in-process IncidentService collaborator."""
        if self._incident_service is not None:
            return self._incident_service
        if self._incident_service_factory is not None:
            return self._incident_service_factory()
        from infrastructure.adapters.tiny_db_incident_repository import (
            TinyDBIncidentRepository,
        )
        from infrastructure.persistence.tinydb.client import get_tinydb

        return IncidentService(repo=TinyDBIncidentRepository(get_tinydb()))

    @staticmethod
    def _incident_to_dto(incident: Incident | Dict[str, Any]) -> TicketRecordDTO:
        """Convert a domain Incident or raw dictionary to an immutable TicketRecordDTO."""
        if isinstance(incident, dict):
            return TicketRecordDTO(
                id=str(incident.get("id") or incident.get("legacy_id") or ""),
                title=str(incident.get("title") or ""),
                description=str(incident.get("description") or ""),
                status=str(incident.get("status") or "open"),
                category=str(incident.get("category") or "other"),
                origin=str(incident.get("origin") or "customer"),
                branch=str(incident.get("branch") or "central"),
                created_at=str(incident.get("created_at") or ""),
                updated_at=str(incident.get("updated_at") or ""),
            )
        raw = incident.to_dict()
        return TicketRecordDTO(
            id=str(raw.get("id") or ""),
            title=str(raw.get("title") or ""),
            description=str(raw.get("description") or ""),
            status=str(raw.get("status") or "open"),
            category=str(raw.get("category") or "other"),
            origin=str(raw.get("origin") or "customer"),
            branch=str(raw.get("branch") or "central"),
            created_at=str(raw.get("created_at") or ""),
            updated_at=str(raw.get("updated_at") or ""),
        )

    def _execute_http_lookup(self, tool_input: TicketToolInput) -> List[TicketRecordDTO]:
        """Execute read-only ticket query over HTTP against `/api/incidents`."""
        headers: Dict[str, str] = {"Accept": "application/json"}
        if self._internal_api_token:
            headers["Authorization"] = f"Bearer {self._internal_api_token}"

        timeout = httpx.Timeout(self._timeout_seconds)
        base_url = self._api_base_url or "http://127.0.0.1:8000"

        if self._http_client is not None:
            client = self._http_client
            close_client = False
        else:
            client = httpx.Client(timeout=timeout)
            close_client = True

        try:
            if tool_input.ticket_id:
                tid = tool_input.ticket_id.strip()
                resp = client.get(f"{base_url}/api/incidents/{tid}", headers=headers)
                if resp.status_code == 404:
                    return []
                resp.raise_for_status()
                payload = resp.json()
                return [self._incident_to_dto(payload)]

            params: Dict[str, str] = {}
            if tool_input.status:
                params["status"] = tool_input.status
            if tool_input.category:
                params["category"] = tool_input.category
            if tool_input.origin:
                params["origin"] = tool_input.origin
            if tool_input.branch:
                params["branch"] = tool_input.branch

            resp = client.get(f"{base_url}/api/incidents", params=params, headers=headers)
            resp.raise_for_status()
            items = resp.json()
            if not isinstance(items, list):
                return []
            return [self._incident_to_dto(item) for item in items if isinstance(item, dict)]
        finally:
            if close_client and hasattr(client, "close"):
                client.close()

    def _execute_in_process_lookup(self, tool_input: TicketToolInput) -> List[TicketRecordDTO]:
        """Execute read-only ticket query directly via `IncidentService`."""
        service = self._resolve_service()

        if tool_input.ticket_id:
            target_id = tool_input.ticket_id.strip()
            exact = service.get_incident_by_id(target_id)
            if exact is not None:
                return [self._incident_to_dto(exact)]

            repo = getattr(service, "repo", None)
            if repo is not None and hasattr(repo, "find_by_legacy_id"):
                legacy_match = repo.find_by_legacy_id(target_id)
                if legacy_match is not None:
                    return [self._incident_to_dto(legacy_match)]

            # Case-insensitive fallback across live records for user-typed IDs (e.g. inc-001 vs INC-001)
            normalized_target = target_id.lower()
            all_incidents = service.list_all_incidents()
            matched_by_id: List[TicketRecordDTO] = []
            for inc in all_incidents:
                inc_id = str(getattr(inc, "id", "") or "").lower()
                leg_id = str(getattr(inc, "legacy_id", "") or "").lower()
                if normalized_target in (inc_id, leg_id):
                    matched_by_id.append(self._incident_to_dto(inc))
            return matched_by_id

        incidents = service.list_all_incidents(
            status=tool_input.status.lower() if tool_input.status else None,
            origin=tool_input.origin.lower() if tool_input.origin else None,
            branch=tool_input.branch.lower() if tool_input.branch else None,
            category=tool_input.category.lower() if tool_input.category else None,
        )
        # If branch had mixed case in TinyDB, fall back to case-insensitive filter
        if not incidents and tool_input.branch:
            unfiltered_branch = service.list_all_incidents(
                status=tool_input.status.lower() if tool_input.status else None,
                origin=tool_input.origin.lower() if tool_input.origin else None,
                branch=None,
                category=tool_input.category.lower() if tool_input.category else None,
            )
            target_branch = tool_input.branch.strip().lower()
            incidents = [
                inc
                for inc in unfiltered_branch
                if str(getattr(inc, "branch", "") or "").strip().lower() == target_branch
            ]

        return [self._incident_to_dto(inc) for inc in incidents]

    def query_tickets(self, tool_input: TicketToolInput) -> TicketToolOutput:
        """Query live incident tickets with a strict numerical timeout and 20-record cap.

        Args:
            tool_input: Typed TicketToolInput criteria.

        Returns:
            TicketToolOutput with status ('success', 'not_found', 'timeout', 'error'),
            up to 20 most-recent records, total_matched count, and latency_ms.
        """
        start_ns = time.perf_counter()
        criteria_dict = tool_input.to_dict()
        cap_limit = max(1, min(MAX_TOOL_RECORDS, int(tool_input.limit)))

        executor = ThreadPoolExecutor(max_workers=1)
        try:
            future = executor.submit(
                self._execute_http_lookup
                if self._api_base_url
                else self._execute_in_process_lookup,
                tool_input,
            )
            matched_dtos: List[TicketRecordDTO] = future.result(timeout=self._timeout_seconds)
        except (FuturesTimeoutError, TimeoutError, httpx.TimeoutException):
            elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
            return TicketToolOutput(
                status="timeout",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message=(
                    f"Support ticket lookup timed out after {self._timeout_seconds:.1f} seconds."
                ),
                queried_criteria=criteria_dict,
            )
        except Exception:
            elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))
            return TicketToolOutput(
                status="error",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message="The Incident Manager service encountered an error and could not complete the ticket lookup.",
                queried_criteria=criteria_dict,
            )
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        # Sort most recent first by (updated_at, created_at, id)
        sorted_dtos = sorted(
            matched_dtos,
            key=lambda r: (r.updated_at or "", r.created_at or "", r.id or ""),
            reverse=True,
        )
        total_matched = len(sorted_dtos)
        capped_records = sorted_dtos[:cap_limit]
        elapsed_ms = max(0.01, round((time.perf_counter() - start_ns) * 1000.0, 3))

        if total_matched == 0:
            if tool_input.ticket_id:
                not_found_msg = (
                    f"No incident record matched ticket_id='{tool_input.ticket_id}'."
                )
            else:
                not_found_msg = "No incident records matched the requested filter criteria."
            return TicketToolOutput(
                status="not_found",
                records=[],
                total_matched=0,
                latency_ms=elapsed_ms,
                error_message=not_found_msg,
                queried_criteria=criteria_dict,
            )

        return TicketToolOutput(
            status="success",
            records=capped_records,
            total_matched=total_matched,
            latency_ms=elapsed_ms,
            error_message=None,
            queried_criteria=criteria_dict,
        )


__all__ = [
    "DEFAULT_TOOL_TIMEOUT_SECONDS",
    "IncidentSupportTicketToolAdapter",
    "MAX_TOOL_RECORDS",
]
