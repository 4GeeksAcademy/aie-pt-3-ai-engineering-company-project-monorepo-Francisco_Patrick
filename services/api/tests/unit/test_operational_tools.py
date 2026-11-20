"""Unit tests for read-only operational tools (`ticket_tool` & `inventory_tool`) (T015, T021, T026).

Verifies:
- US2 (T015): `IncidentSupportTicketToolAdapter` exact `ticket_id` lookup, filter queries
  (`status`, `category`, `origin`, `branch`), 20-record cap with `total_matched`, and
  strict read-only contract against real `IncidentService` / `TinyDBIncidentRepository`.
- US3 (T021): Numerical timeout enforcement (`status="timeout"`), service error handling
  (`status="error"`), and missing record handling (`status="not_found"`).
- US4 (T026): `InventoryStockQueryToolAdapter` SKU/product ID lookup, search/low-stock
  filtering, 20-record cap with `total_matched`, timeout enforcement, and read-only
  compliance against real `InventoryService` / `SQLModelInventoryRepository`.
"""

import time
from typing import Any, Dict, List, Optional

from sqlmodel import SQLModel, Session, create_engine
from tinydb import TinyDB
from tinydb.storages import MemoryStorage

from application.inventory.dto import InboundOrderCreateDTO, ProductCreateDTO
from application.inventory.inventory_service import InventoryService
from application.services.incident_service import IncidentService
from domain.agent.entities import (
    InventoryToolInput,
    TicketToolInput,
)
from domain.incident_model import Incident
from domain.knowledge.entities import KnowledgeRuntimeConfig
from infrastructure.adapters.inventory_stock_tool_adapter import (
    InventoryStockQueryToolAdapter,
)
from infrastructure.adapters.support_ticket_tool_adapter import (
    IncidentSupportTicketToolAdapter,
)
from infrastructure.adapters.tiny_db_incident_repository import (
    TinyDBIncidentRepository,
)
from infrastructure.persistence.sqlmodel.inventory_repository import (
    SQLModelInventoryRepository,
)
from shared.incidents.enums import IncidentCategory, IncidentOrigin, IncidentStatus


def _create_seeded_incident_service() -> IncidentService:
    """Create an IncidentService backed by an in-memory TinyDB instance with real Incident records."""
    db = TinyDB(storage=MemoryStorage)
    repo = TinyDBIncidentRepository(db)
    service = IncidentService(repo=repo)

    inc1 = Incident(
        id="INC-001",
        title="Delayed pallet shipment to Zaragoza",
        description="Outbound pallet shipment delayed by 48 hours at hub.",
        category=IncidentCategory.WAREHOUSE,
        status=IncidentStatus.OPEN,
        origin=IncidentOrigin.INTERNAL,
        branch="zaragoza",
        created_at="2026-11-17T09:00:00+00:00",
        updated_at="2026-11-18T10:30:00+00:00",
        legacy_id="1001",
    )
    inc2 = Incident(
        id="INC-002",
        title="Damaged carton reported by customer",
        description="Water damage on outer carton upon delivery.",
        category=IncidentCategory.LAST_MILE,
        status=IncidentStatus.IN_PROGRESS,
        origin=IncidentOrigin.CUSTOMER,
        branch="los_angeles",
        created_at="2026-11-16T08:00:00+00:00",
        updated_at="2026-11-17T14:00:00+00:00",
        legacy_id="1002",
    )
    inc3 = Incident(
        id="INC-003",
        title="Invoice discrepancy on monthly storage fee",
        description="Customer questioned pallet count on October invoice.",
        category=IncidentCategory.CUSTOMER_EXPERIENCE,
        status=IncidentStatus.RESOLVED,
        origin=IncidentOrigin.CUSTOMER,
        branch="central",
        created_at="2026-11-10T11:00:00+00:00",
        updated_at="2026-11-12T16:00:00+00:00",
        legacy_id="1003",
    )
    repo.save(inc1)
    repo.save(inc2)
    repo.save(inc3)
    return service


def _create_seeded_inventory_service() -> TupleInventorySetup:
    """Create an InventoryService backed by an in-memory SQLite SQLModel session with real SKU & StockEntry records."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    session = Session(engine)
    repo = SQLModelInventoryRepository(session=session)
    service = InventoryService(inventory_repo=repo)

    p1 = service.create_product(
        ProductCreateDTO(
            sku="TF-1001",
            name="Industrial Thermal Shipping Label Roll",
            warehouse_id="zaragoza",
            low_stock_threshold=20,
        )
    )
    service.create_inbound_order(
        InboundOrderCreateDTO(
            sku_id=p1.id,
            warehouse_id="zaragoza",
            quantity=145,
        ),
        user_uuid="system-seed",
    )

    p2 = service.create_product(
        ProductCreateDTO(
            sku="TF-2002",
            name="Reinforced Euro Pallet Wrap",
            warehouse_id="los_angeles",
            low_stock_threshold=50,
        )
    )
    service.create_inbound_order(
        InboundOrderCreateDTO(
            sku_id=p2.id,
            warehouse_id="los_angeles",
            quantity=12,
        ),
        user_uuid="system-seed",
    )

    return service


TupleInventorySetup = InventoryService


class TestSupportTicketToolAdapter:
    """Unit test suite for IncidentSupportTicketToolAdapter (T015, T021)."""

    def test_t015_exact_ticket_id_and_legacy_id_lookup(self) -> None:
        """T015: Adapter retrieves exact incident record by ticket_id or legacy_id."""
        service = _create_seeded_incident_service()
        adapter = IncidentSupportTicketToolAdapter(incident_service=service)

        out = adapter.query_tickets(TicketToolInput(ticket_id="INC-001"))
        assert out.status == "success"
        assert out.total_matched == 1
        assert len(out.records) == 1
        rec = out.records[0]
        assert rec.id == "INC-001"
        assert rec.title == "Delayed pallet shipment to Zaragoza"
        assert rec.status == "open"
        assert rec.category == "warehouse"
        assert rec.origin == "internal"
        assert rec.branch == "zaragoza"
        assert out.latency_ms > 0.0
        assert out.error_message is None

        # Case-insensitive / legacy ID lookup
        legacy_out = adapter.query_tickets(TicketToolInput(ticket_id="1002"))
        assert legacy_out.status == "success"
        assert legacy_out.records[0].id == "INC-002"

    def test_t015_filter_queries_by_status_category_origin_and_branch(self) -> None:
        """T015: Adapter filters live incidents by status, category, origin, and branch."""
        service = _create_seeded_incident_service()
        adapter = IncidentSupportTicketToolAdapter(incident_service=service)

        open_out = adapter.query_tickets(
            TicketToolInput(status="open", origin="internal", branch="zaragoza")
        )
        assert open_out.status == "success"
        assert open_out.total_matched == 1
        assert open_out.records[0].id == "INC-001"

        customer_out = adapter.query_tickets(TicketToolInput(origin="customer"))
        assert customer_out.status == "success"
        assert customer_out.total_matched == 2
        # Ordered most-recent updated_at first: INC-002 (Nov 17) before INC-003 (Nov 12)
        assert [r.id for r in customer_out.records] == ["INC-002", "INC-003"]

    def test_t015_enforces_20_record_cap_and_reports_total_matched(self) -> None:
        """T015: Adapter caps returned records at 20 while reporting full total_matched count."""
        db = TinyDB(storage=MemoryStorage)
        repo = TinyDBIncidentRepository(db)
        service = IncidentService(repo=repo)

        for idx in range(1, 26):
            repo.save(
                Incident(
                    id=f"INC-{idx:03d}",
                    title=f"Incident #{idx}",
                    description=f"Test incident {idx}",
                    category=IncidentCategory.WAREHOUSE,
                    status=IncidentStatus.OPEN,
                    origin=IncidentOrigin.INTERNAL,
                    branch="central",
                    created_at=f"2026-11-18T10:{idx:02d}:00+00:00",
                    updated_at=f"2026-11-18T11:{idx:02d}:00+00:00",
                )
            )

        adapter = IncidentSupportTicketToolAdapter(incident_service=service)
        out = adapter.query_tickets(TicketToolInput(status="open", limit=20))

        assert out.status == "success"
        assert out.total_matched == 25
        assert len(out.records) == 20
        # Most recent record (INC-025) must appear first
        assert out.records[0].id == "INC-025"

    def test_t015_strict_read_only_contract_exposes_no_mutation_methods(self) -> None:
        """T015: SupportTicketToolPort and adapter must not expose any create/update/delete methods (FR-019)."""
        service = _create_seeded_incident_service()
        adapter = IncidentSupportTicketToolAdapter(incident_service=service)

        prohibited_methods = (
            "create_incident",
            "update_incident",
            "update_incident_status",
            "delete_incident",
            "close_ticket",
            "save",
            "insert",
        )
        for method_name in prohibited_methods:
            assert not hasattr(adapter, method_name), (
                f"Read-only violation: {method_name} found on adapter"
            )

    def test_t021_not_found_timeout_and_error_handling(self) -> None:
        """T021: Adapter returns structured status='not_found', 'timeout', and 'error' without raising."""
        service = _create_seeded_incident_service()
        adapter = IncidentSupportTicketToolAdapter(
            incident_service=service, timeout_seconds=4.0
        )

        # 1. Missing ticket -> status="not_found"
        missing = adapter.query_tickets(TicketToolInput(ticket_id="INC-999999"))
        assert missing.status == "not_found"
        assert missing.total_matched == 0
        assert missing.records == []
        assert missing.error_message is not None
        assert "INC-999999" in missing.error_message

        # 2. Simulated slow service exceeding numerical timeout -> status="timeout"
        class SlowIncidentService:
            def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
                time.sleep(0.35)
                return None

            def list_all_incidents(self, **kwargs: Any) -> List[Incident]:
                time.sleep(0.35)
                return []

        fast_timeout_adapter = IncidentSupportTicketToolAdapter(
            incident_service=SlowIncidentService(),  # type: ignore[arg-type]
            timeout_seconds=0.05,
        )
        t0 = time.perf_counter()
        timed_out = fast_timeout_adapter.query_tickets(
            TicketToolInput(ticket_id="INC-001")
        )
        elapsed = time.perf_counter() - t0
        assert timed_out.status == "timeout"
        assert timed_out.records == []
        assert timed_out.total_matched == 0
        assert "timed out" in (timed_out.error_message or "").lower()
        assert elapsed < 0.30

        # 3. Simulated service exception -> status="error" with sanitized message
        class BrokenIncidentService:
            def get_incident_by_id(self, incident_id: str) -> Optional[Incident]:
                raise RuntimeError("Database connection failed at /internal/db.json")

        broken_adapter = IncidentSupportTicketToolAdapter(
            incident_service=BrokenIncidentService()  # type: ignore[arg-type]
        )
        errored = broken_adapter.query_tickets(TicketToolInput(ticket_id="INC-001"))
        assert errored.status == "error"
        assert errored.records == []
        assert "/internal/db.json" not in (errored.error_message or "")

    def test_t015_http_transport_and_env_token_configuration(self) -> None:
        """T015: Adapter supports optional HTTP transport with bearer token loaded from config."""
        captured_headers: Dict[str, str] = {}

        class StubHttpResponse:
            status_code = 200

            def raise_for_status(self) -> None:
                pass

            def json(self) -> Dict[str, Any]:
                return {
                    "id": "INC-001",
                    "title": "HTTP Incident",
                    "description": "Fetched via HTTP",
                    "status": "open",
                    "category": "delay",
                    "origin": "warehouse",
                    "branch": "zaragoza",
                    "created_at": "2026-11-18T09:00:00Z",
                    "updated_at": "2026-11-18T10:00:00Z",
                }

        class StubHttpClient:
            def get(self, url: str, headers: Optional[Dict[str, str]] = None, **kwargs: Any) -> StubHttpResponse:
                if headers:
                    captured_headers.update(headers)
                return StubHttpResponse()

        cfg = KnowledgeRuntimeConfig.from_env(
            env={
                "AGENT_API_BASE_URL": "http://127.0.0.1:8000",
                "AGENT_INTERNAL_API_TOKEN": "secret-internal-token-xyz",
                "AGENT_TOOL_TIMEOUT_SECONDS": "4.0",
            },
            load_dotenv_file=False,
        )
        adapter = IncidentSupportTicketToolAdapter(
            config=cfg,
            http_client=StubHttpClient(),
        )
        assert adapter.auth_mode == "http_bearer"
        out = adapter.query_tickets(TicketToolInput(ticket_id="INC-001"))
        assert out.status == "success"
        assert out.records[0].id == "INC-001"
        assert captured_headers.get("Authorization") == "Bearer secret-internal-token-xyz"


class TestInventoryStockQueryToolAdapter:
    """Unit test suite for InventoryStockQueryToolAdapter (T026)."""

    def test_t026_sku_and_product_id_lookup_against_real_inventory_service(self) -> None:
        """T026: Adapter queries real SQLModel InventoryService by SKU and product_id."""
        service = _create_seeded_inventory_service()
        adapter = InventoryStockQueryToolAdapter(inventory_service=service)

        sku_out = adapter.query_inventory(InventoryToolInput(sku="TF-1001"))
        assert sku_out.status == "success"
        assert sku_out.total_matched == 1
        assert len(sku_out.records) == 1
        rec = sku_out.records[0]
        assert rec.sku == "TF-1001"
        assert rec.name == "Industrial Thermal Shipping Label Roll"
        assert rec.stock == 145
        assert rec.min_threshold == 20
        assert rec.is_low_stock is False
        assert rec.warehouse_id == "zaragoza"

        # Lookup by numeric product_id
        pid_out = adapter.query_inventory(InventoryToolInput(product_id=rec.id))
        assert pid_out.status == "success"
        assert pid_out.records[0].sku == "TF-1001"

    def test_t026_low_stock_and_search_query_filtering(self) -> None:
        """T026: Adapter filters by low_stock_only and search_query substring."""
        service = _create_seeded_inventory_service()
        adapter = InventoryStockQueryToolAdapter(inventory_service=service)

        low_out = adapter.query_inventory(InventoryToolInput(low_stock_only=True))
        assert low_out.status == "success"
        assert low_out.total_matched == 1
        assert low_out.records[0].sku == "TF-2002"
        assert low_out.records[0].stock == 12
        assert low_out.records[0].min_threshold == 50
        assert low_out.records[0].is_low_stock is True

        search_out = adapter.query_inventory(
            InventoryToolInput(search_query="Pallet Wrap")
        )
        assert search_out.status == "success"
        assert search_out.records[0].sku == "TF-2002"

    def test_t026_enforces_20_record_cap_and_reports_total_matched(self) -> None:
        """T026: Adapter caps returned inventory records at 20 while reporting full total_matched."""
        engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
        SQLModel.metadata.create_all(engine)
        session = Session(engine)
        repo = SQLModelInventoryRepository(session=session)
        service = InventoryService(inventory_repo=repo)

        for idx in range(1, 26):
            service.create_product(
                ProductCreateDTO(
                    sku=f"TF-{1000 + idx}",
                    name=f"Warehouse Item {idx}",
                    warehouse_id="central",
                    low_stock_threshold=10,
                )
            )

        adapter = InventoryStockQueryToolAdapter(inventory_service=service)
        out = adapter.query_inventory(InventoryToolInput(limit=20))
        assert out.status == "success"
        assert out.total_matched == 25
        assert len(out.records) == 20

    def test_t026_not_found_timeout_error_and_read_only_compliance(self) -> None:
        """T026: Adapter handles missing SKU, enforces timeout, shields errors, and exposes zero mutation methods."""
        service = _create_seeded_inventory_service()
        adapter = InventoryStockQueryToolAdapter(inventory_service=service)

        # 1. Missing SKU -> status="not_found"
        missing = adapter.query_inventory(InventoryToolInput(sku="TF-9999"))
        assert missing.status == "not_found"
        assert missing.total_matched == 0
        assert missing.records == []
        assert "TF-9999" in (missing.error_message or "")

        # 2. Timeout -> status="timeout"
        class SlowInventoryService:
            def list_products(self) -> List[Any]:
                time.sleep(0.35)
                return []

        slow_adapter = InventoryStockQueryToolAdapter(
            inventory_service=SlowInventoryService(),  # type: ignore[arg-type]
            timeout_seconds=0.05,
        )
        t0 = time.perf_counter()
        timed_out = slow_adapter.query_inventory(InventoryToolInput(sku="TF-1001"))
        elapsed = time.perf_counter() - t0
        assert timed_out.status == "timeout"
        assert elapsed < 0.30

        # 3. Service error -> status="error"
        class BrokenInventoryService:
            def list_products(self) -> List[Any]:
                raise RuntimeError("SQLite error at /var/data/inventory.db")

        broken_adapter = InventoryStockQueryToolAdapter(
            inventory_service=BrokenInventoryService()  # type: ignore[arg-type]
        )
        errored = broken_adapter.query_inventory(InventoryToolInput(sku="TF-1001"))
        assert errored.status == "error"
        assert "/var/data/inventory.db" not in (errored.error_message or "")

        # 4. Read-only contract check
        prohibited = (
            "create_product",
            "create_inbound_order",
            "create_outbound_order",
            "update_stock",
            "delete_product",
        )
        for method_name in prohibited:
            assert not hasattr(adapter, method_name)
