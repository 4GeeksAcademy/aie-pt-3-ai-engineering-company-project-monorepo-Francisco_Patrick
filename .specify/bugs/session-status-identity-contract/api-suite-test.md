PS J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api> .venv/Scripts/python.exe -m pytest -q
................s.ss......................FF.FF....FF.........................................................F..................F..... [ 15%]
....................................................................................................................................... [ 30%]
....................................................................................................................................... [ 46%]
....................................................................................................................................... [ 61%]
............................................................................F.........................................F................ [ 76%]
....................................................................................................................................... [ 92%]
...............................FFF..................................                                                                    [100%]
================================================================== FAILURES ================================================================== 
________________________________________________ test_create_supplier_rejects_missing_country ________________________________________________ 

client = <starlette.testclient.TestClient object at 0x0000022E28A55D00>
test_users = {'active': User(email='user@example.com', is_active=True, role='user', id='03e8a072-5d95-4b97-9667-35cf586fc4cc', hash...rd='$2b$12$02BliBEXtNLANC219ImXHe1lQJ13bTj8eRVIoAkWLoeH4wcDNijay', created_at='2026-11-25T12:11:58.842526+00:00'), ...}

    def test_create_supplier_rejects_missing_country(client, test_users):
        """Verify that a supplier without country is rejected with 422 before touching the database."""
        headers = _auth_headers(test_users)
        payload = {
            "name": "No Country Carrier",
            "categories": ["carrier_last_mile"],
            "rate_per_shipment": 10.0,
            "status": "active",
        }
        response = client.post("/suppliers", json=payload, headers=headers)
>       assert response.status_code == 422
E       assert 400 == 422
E        +  where 400 = <Response [400 Bad Request]>.status_code

tests\api\test_suppliers_api.py:71: AssertionError
------------------------------------------------------------ Captured stderr call ------------------------------------------------------------ 
INFO:httpx2:HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
------------------------------------------------------------- Captured log call -------------------------------------------------------------- 
INFO     httpx2:_client.py:1079 HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
________________________________________________ test_create_supplier_rejects_invalid_status _________________________________________________ 

client = <starlette.testclient.TestClient object at 0x0000022E28A57350>
test_users = {'active': User(email='user@example.com', is_active=True, role='user', id='9ea7d66f-0e91-4032-add1-44ee01fe4efb', hash...rd='$2b$12$reo9Dlq0usjTu79Ja8UoGOQH1ibtlx49CjQSGwNtlZz4AdYbXaGTK', created_at='2026-11-25T12:11:59.997845+00:00'), ...}

    def test_create_supplier_rejects_invalid_status(client, test_users):
        """Verify that status values outside 'active' or 'suspended' are rejected with 422."""
        headers = _auth_headers(test_users)
        for invalid_status in ["inactive", "pending", "disabled", "archived", "cancelled"]:
            payload = {
                "name": f"Invalid Status {invalid_status}",
                "country": "USA",
                "categories": ["carrier_last_mile"],
                "rate_per_shipment": 7.50,
                "currency": "USD",
                "status": invalid_status,
            }
            response = client.post("/suppliers", json=payload, headers=headers)
>           assert response.status_code == 422, f"Expected 422 for status '{invalid_status}', got {response.status_code}"
E           AssertionError: Expected 422 for status 'inactive', got 400
E           assert 400 == 422
E            +  where 400 = <Response [400 Bad Request]>.status_code

tests\api\test_suppliers_api.py:87: AssertionError
------------------------------------------------------------ Captured stderr call ------------------------------------------------------------ 
INFO:httpx2:HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
------------------------------------------------------------- Captured log call -------------------------------------------------------------- 
INFO     httpx2:_client.py:1079 HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
_____________________________________________ test_create_supplier_rejects_zero_or_negative_rate _____________________________________________ 

client = <starlette.testclient.TestClient object at 0x0000022E28A548D0>
test_users = {'active': User(email='user@example.com', is_active=True, role='user', id='3322b354-5d0a-48a9-9900-3f77ff6b12e8', hash...rd='$2b$12$F6sXpfzw8hQiP6ybtbLX8uQADOcdQMA2UgJsw02l6fvVkuAxqZtJy', created_at='2026-11-25T12:12:01.536875+00:00'), ...}

    def test_create_supplier_rejects_zero_or_negative_rate(client, test_users):
        """Verify that rate values <= 0 are rejected with 422."""
        headers = _auth_headers(test_users)
        for invalid_rate in [0.0, -0.01, -5.50, -100.0]:
            payload = {
                "name": "Invalid Rate Carrier",
                "country": "USA",
                "categories": ["carrier_last_mile"],
                "rate_per_shipment": invalid_rate,
                "currency": "USD",
                "status": "active",
            }
            response = client.post("/suppliers", json=payload, headers=headers)
>           assert response.status_code == 422, f"Expected 422 for rate {invalid_rate}, got {response.status_code}"
E           AssertionError: Expected 422 for rate 0.0, got 400
E           assert 400 == 422
E            +  where 400 = <Response [400 Bad Request]>.status_code

tests\api\test_suppliers_api.py:123: AssertionError
------------------------------------------------------------ Captured stderr call ------------------------------------------------------------ 
INFO:httpx2:HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
------------------------------------------------------------- Captured log call -------------------------------------------------------------- 
INFO     httpx2:_client.py:1079 HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
_____________________________________________ test_create_supplier_rejects_inconsistent_currency _____________________________________________ 

client = <starlette.testclient.TestClient object at 0x0000022E28AFD150>
test_users = {'active': User(email='user@example.com', is_active=True, role='user', id='087ef723-3d6f-4791-9b69-627069682dfa', hash...rd='$2b$12$RL0FAE6o6zQ5qi91nZ6VBuy1jkxG7aasmHnn7VUqqglJmvsOxzBmy', created_at='2026-11-25T12:12:02.184705+00:00'), ...}

    def test_create_supplier_rejects_inconsistent_currency(client, test_users):
        """Verify business restriction: USA must use USD, Spain must use EUR."""
        headers = _auth_headers(test_users)
        # USA with EUR -> reject
        res1 = client.post(
            "/suppliers",
            json={
                "name": "US Carrier Bad Currency",
                "country": "USA",
                "categories": ["carrier_last_mile"],
                "rate_per_shipment": 12.0,
                "currency": "EUR",
                "status": "active",
            },
            headers=headers,
        )
>       assert res1.status_code == 422
E       assert 400 == 422
E        +  where 400 = <Response [400 Bad Request]>.status_code

tests\api\test_suppliers_api.py:142: AssertionError
------------------------------------------------------------ Captured stderr call ------------------------------------------------------------ 
INFO:httpx2:HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
------------------------------------------------------------- Captured log call -------------------------------------------------------------- 
INFO     httpx2:_client.py:1079 HTTP Request: POST http://testserver/suppliers "HTTP/1.1 400 Bad Request"
_________________________________________________ test_rate_update_rejects_zero_or_negative __________________________________________________ 

client = <starlette.testclient.TestClient object at 0x0000022E28AFE7A0>
test_users = {'active': User(email='user@example.com', is_active=True, role='user', id='cb1f27cc-600d-4460-9826-675efaa1fbec', hash...rd='$2b$12$QdHAib.wmOTmjya69TD0WeKiH2V.a.9AFZ1Bjfi/nmDY155/lhvnK', created_at='2026-11-25T12:12:05.796876+00:00'), ...}

    def test_rate_update_rejects_zero_or_negative(client, test_users):
        """Verify that PATCH rate rejects 0 or negative rates with 422."""
        headers = _auth_headers(test_users)
        created_res = client.post(
            "/suppliers",
            json={
                "name": "Rate Guard Test Corp",
                "country": "Spain",
                "categories": ["fleet_maintenance"],
                "rate_per_shipment": 50.00,
                "currency": "EUR",
                "status": "active",
            },
            headers=headers,
        )
        supplier_id = created_res.json()["id"]

        for invalid_rate in [0.0, -10.0]:
            res = client.patch(
                f"/suppliers/{supplier_id}/rate",
                json={"rate_per_shipment": invalid_rate},
                headers=headers,
            )
>           assert res.status_code == 422
E           assert 400 == 422
E            +  where 400 = <Response [400 Bad Request]>.status_code

tests\api\test_suppliers_api.py:289: AssertionError
------------------------------------------------------------ Captured stderr call ------------------------------------------------------------ 
INFO:httpx2:HTTP Request: POST http://testserver/suppliers "HTTP/1.1 201 Created"
INFO:httpx2:HTTP Request: PATCH http://testserver/suppliers/23/rate "HTTP/1.1 400 Bad Request"
------------------------------------------------------------- Captured log call -------------------------------------------------------------- 
INFO     httpx2:_client.py:1079 HTTP Request: POST http://testserver/suppliers "HTTP/1.1 201 Created"
INFO     httpx2:_client.py:1079 HTTP Request: PATCH http://testserver/suppliers/23/rate "HTTP/1.1 400 Bad Request"
________________________________________________________ test_status_update_lifecycle ________________________________________________________ 

client = <starlette.testclient.TestClient object at 0x0000022E28AFE580>
test_users = {'active': User(email='user@example.com', is_active=True, role='user', id='ae08a850-aa45-4089-a1d5-ce1e1c7c3b84', hash...rd='$2b$12$qjMu55Dx6gw6u3pIdUgIl.rIpAcyCq8CqDpPNLPIRwR00rw3v/kGu', created_at='2026-11-25T12:12:06.516298+00:00'), ...}

    def test_status_update_lifecycle(client, test_users):
        """Verify updating status between active and suspended."""
        headers = _auth_headers(test_users)
        created = client.post(
            "/suppliers",
            json={
                "name": "Status Lifecycle Corp",
                "country": "USA",
                "categories": ["warehouse_supplies"],
                "rate_per_shipment": 25.00,
                "currency": "USD",
                "status": "active",
            },
            headers=headers,
        ).json()
        supplier_id = created["id"]

        # Suspend
        res_suspend = client.patch(
            f"/suppliers/{supplier_id}/status",
            json={"status": "suspended"},
            headers=headers,
        )
        assert res_suspend.status_code == 200
        assert res_suspend.json()["status"] == "suspended"

        # Reactivate
        res_reactivate = client.patch(
            f"/suppliers/{supplier_id}/status",
            json={"status": "active"},
            headers=headers,
        )
        assert res_reactivate.status_code == 200
        assert res_reactivate.json()["status"] == "active"

        # Invalid status
        res_invalid = client.patch(
            f"/suppliers/{supplier_id}/status",
            json={"status": "invalid_status"},
            headers=headers,
        )
>       assert res_invalid.status_code == 422
E       assert 400 == 422
E        +  where 400 = <Response [400 Bad Request]>.status_code

tests\api\test_suppliers_api.py:335: AssertionError
------------------------------------------------------------ Captured stderr call ------------------------------------------------------------ 
INFO:httpx2:HTTP Request: POST http://testserver/suppliers "HTTP/1.1 201 Created"
INFO:httpx2:HTTP Request: PATCH http://testserver/suppliers/24/status "HTTP/1.1 200 OK"
INFO:httpx2:HTTP Request: PATCH http://testserver/suppliers/24/status "HTTP/1.1 200 OK"
INFO:httpx2:HTTP Request: PATCH http://testserver/suppliers/24/status "HTTP/1.1 400 Bad Request"
------------------------------------------------------------- Captured log call -------------------------------------------------------------- 
INFO     httpx2:_client.py:1079 HTTP Request: POST http://testserver/suppliers "HTTP/1.1 201 Created"
INFO     httpx2:_client.py:1079 HTTP Request: PATCH http://testserver/suppliers/24/status "HTTP/1.1 200 OK"
INFO     httpx2:_client.py:1079 HTTP Request: PATCH http://testserver/suppliers/24/status "HTTP/1.1 200 OK"
INFO     httpx2:_client.py:1079 HTTP Request: PATCH http://testserver/suppliers/24/status "HTTP/1.1 400 Bad Request"
______________________ TestSupportAgentRoutesIntegration.test_t043_query_endpoint_honest_refusal_and_mutation_guardrail ______________________ 

self = <test_agent_routes.TestSupportAgentRoutesIntegration object at 0x0000022E26933790>

    def test_t043_query_endpoint_honest_refusal_and_mutation_guardrail(self) -> None:
        """T043: POST /api/v1/agent/query routes out-of-scope topic and write-mutation attempts to refusal."""
        res = client.post(
            "/api/v1/agent/query",
            json={
                "query": "What are the temperature requirements for pharmaceutical refrigeration?",
                "top_k": 3,
                "min_score": 0.62,
            },
        )
        assert res.status_code == 200
        data = res.json()
>       assert data["is_refusal"] is True
E       assert False is True

tests\integration\test_agent_routes.py:276: AssertionError
------------------------------------------------------------ Captured stderr call ------------------------------------------------------------ 
INFO:httpx2:HTTP Request: POST http://testserver/api/v1/agent/query "HTTP/1.1 200 OK"
------------------------------------------------------------- Captured log call -------------------------------------------------------------- 
INFO     httpx2:_client.py:1079 HTTP Request: POST http://testserver/api/v1/agent/query "HTTP/1.1 200 OK"
__________________________ TestMemoryStorageIsolation.test_zero_qdrant_writes_across_10_memory_proposal_lifecycles ___________________________ 

self = <test_memory_storage_isolation.TestMemoryStorageIsolation object at 0x0000022E26965BD0>

    def test_zero_qdrant_writes_across_10_memory_proposal_lifecycles(self) -> None:
        """Scenario 6: 10 proposals (5 approved, 5 discarded) produce delta=0 in Qdrant trackflow_knowledge."""
        vector_store = _ReadOnlyTrackedVectorStore(initial_count=24)
        memory_repo = TinyDBAgentMemoryRepository()
        audit_repo = TinyDBMemoryAuditLogRepository()
        memory_service = AgentMemoryService(
            memory_repository=memory_repo,
            audit_repository=audit_repo,
            guardrail_validator=MemoryGuardrailValidator(),
            intent_classifier=UserIntentClassifier(),
        )
        agent_service = SupportAgentService(
            vector_store=vector_store,
            embedding_service=_StubEmbedder(),
            llm_generator=_StubLLM(),
            ticket_tool=_NoOpTicketTool(),
            inventory_tool=_NoOpInventoryTool(),
            trace_registry=TraceRegistry(),
            memory_service=memory_service,
        )

        initial_qdrant_count = vector_store.get_health_status()["indexed_points_count"]
        assert initial_qdrant_count == 24

        carriers = [
            ("SEUR", "Zaragoza"),
            ("GLS", "Zaragoza"),
            ("Correos", "Zaragoza"),
            ("DHL", "Zaragoza"),
            ("MRW", "Zaragoza"),
            ("FedEx", "Los Angeles"),
            ("UPS", "Los Angeles"),
            ("USPS", "Los Angeles"),
            ("OnTrac", "Los Angeles"),
            ("LaserShip", "Los Angeles"),
        ]

        for idx, (carrier, region) in enumerate(carriers):
            thread_id = f"isolation_thread_{idx}"
            # Generate proposal
            prop_res = agent_service.query(
                AgentQueryRequest(
                    query=f"{carrier} no longer covers the rural {region} zone; local carriers must be used starting this month.",
                    thread_id=thread_id,
                )
            )
>           assert prop_res.memory_proposal is not None
E           AssertionError: assert None is not None
E            +  where None = AgentQueryResult(query='GLS no longer covers the rural Zaragoza zone; local carriers must be used starting this month....t be used starting this month.', trace_id='652134ac-805f-4a4d-9548-0344e7539b1a', metadata={})], resolved_country='ES').memory_proposal 

tests\integration\test_memory_storage_isolation.py:164: AssertionError
________________________________________ test_inventory_service_stock_guard_insufficient_stock_error _________________________________________ 

    def test_inventory_service_stock_guard_insufficient_stock_error():
        repo = MockInventoryRepository()
        service = InventoryService(inventory_repo=repo)

        prod = service.create_product(
            ProductCreateDTO(
                sku="SKU-BRAKE-01",
                name="Brake Disc",
                warehouse_id="wh-central",
                low_stock_threshold=5,
            )
        )

        # Inbound 20 units
        service.create_inbound_order(
            InboundOrderCreateDTO(sku_id=prod.id, warehouse_id="wh-central", quantity=20),
            user_uuid="usr_test",
        )

        # Current stock is 20
        assert service.calculate_stock(prod.id, "wh-central") == 20

        # Requesting 25 units must raise InsufficientStockError
        with pytest.raises(InsufficientStockError) as exc_info:
            service.create_outbound_order(
                OutboundOrderCreateDTO(
                    sku_id=prod.id, warehouse_id="wh-central", quantity=25
                ),
                user_uuid="usr_test",
            )
>       assert "Insufficient stock for SKU 1: requested 25, available 20" in str(exc_info.value)
E       assert 'Insufficient stock for SKU 1: requested 25, available 20' in "Insufficient stock for SKU 'SKU-BRAKE-01'. Available: 20, requested: 25."
E        +  where "Insufficient stock for SKU 'SKU-BRAKE-01'. Available: 20, requested: 25." = str(InsufficientStockError("Insufficient stock for SKU 'SKU-BRAKE-01'. Available: 20, requested: 25."))
E        +    where InsufficientStockError("Insufficient stock for SKU 'SKU-BRAKE-01'. Available: 20, requested: 25.") = <ExceptionInfo InsufficientStockError("Insufficient stock for SKU 'SKU-BRAKE-01'. Available: 20, requested: 25.") tblen=2>.value

tests\unit\test_application_services.py:449: AssertionError
__________________________________________________ test_supplier_categories_synchronization __________________________________________________ 

    def test_supplier_categories_synchronization():
        """Happy Path: Categories list and category single value synchronize bidirectionally."""
>       s1 = Supplier(
            name="Maritime Freight Corp",
            country="Netherlands",
            categories=["ocean_freight", "customs"],
            cost_per_kg=2.75,
        )
E       pydantic_core._pydantic_core.ValidationError: 1 validation error for Supplier
E       status
E         Field required [type=missing, input_value={'name': 'Maritime Freigh...ght', 'currency': 'USD'}, input_type=dict]
E           For further information visit https://errors.pydantic.dev/2.13/v/missing

tests\unit\test_domain_models.py:45: ValidationError
_____________________________________________________ test_sqlmodel_manager_custom_port ______________________________________________________ 

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000022E26C28FA0>

    def test_sqlmodel_manager_custom_port(monkeypatch) -> None:
        monkeypatch.setenv("user", "test_user")
        monkeypatch.setenv("password", "test_pass")
        monkeypatch.setenv("host", "custom.pooler.supabase.com")
        monkeypatch.setenv("port", "6543")
        monkeypatch.setenv("dbname", "test_db")

        manager = SQLModelClientManager()
        url = manager.build_database_url()
>       assert "@custom.pooler.supabase.com:6543/test_db" in url
E       AssertionError: assert '@custom.pooler.supabase.com:6543/test_db' in 'sqlite:///J:\\GitHub\\mr-stegmann-ai-engineering-company-project-monorepo\\services\\api\\test_inventory.db'

tests\unit\test_sqlmodel_client.py:57: AssertionError
___________________________________________________ test_sqlmodel_manager_db_port_fallback ___________________________________________________ 

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000022E314DAA50>

    def test_sqlmodel_manager_db_port_fallback(monkeypatch) -> None:
        monkeypatch.setenv("user", "test_user")
        monkeypatch.setenv("password", "test_pass")
        monkeypatch.setenv("host", "custom.pooler.supabase.com")
        monkeypatch.delenv("port", raising=False)
        monkeypatch.setenv("DB_PORT", "7654")
        monkeypatch.setenv("dbname", "test_db")

        manager = SQLModelClientManager()
        url = manager.build_database_url()
>       assert "@custom.pooler.supabase.com:7654/test_db" in url
E       AssertionError: assert '@custom.pooler.supabase.com:7654/test_db' in 'sqlite:///J:\\GitHub\\mr-stegmann-ai-engineering-company-project-monorepo\\services\\api\\test_inventory.db'

tests\unit\test_sqlmodel_client.py:70: AssertionError
________________________________________________ test_sqlmodel_manager_default_port_fallback _________________________________________________ 

monkeypatch = <_pytest.monkeypatch.MonkeyPatch object at 0x0000022E286E4130>

    def test_sqlmodel_manager_default_port_fallback(monkeypatch) -> None:
        monkeypatch.setenv("user", "test_user")
        monkeypatch.setenv("password", "test_pass")
        monkeypatch.setenv("host", "custom.pooler.supabase.com")
        monkeypatch.delenv("port", raising=False)
        monkeypatch.delenv("DB_PORT", raising=False)
        monkeypatch.setenv("dbname", "test_db")

        manager = SQLModelClientManager()
        url = manager.build_database_url()
>       assert "@custom.pooler.supabase.com:5432/test_db" in url
E       AssertionError: assert '@custom.pooler.supabase.com:5432/test_db' in 'sqlite:///J:\\GitHub\\mr-stegmann-ai-engineering-company-project-monorepo\\services\\api\\test_inventory.db'

tests\unit\test_sqlmodel_client.py:83: AssertionError
============================================================== warnings summary ============================================================== 
main.py:43
main.py:43
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\main.py:43: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    from services.reporting.presentation import routes as reporting  # noqa: E402

tests/api/test_telemetry_report.py::test_get_telemetry_report_inverted_date_range_returns_422
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\anyio\_backends\_asyncio.py:1033: StarletteDeprecationWarning: 'HTTP_422_UNPROCESSABLE_ENTITY' is deprecated. Use 'HTTP_422_UNPROCESSABLE_CONTENT' instead.
    result = context.run(func, *args)

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t015_exact_ticket_id_and_legacy_id_lookup
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:147: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    adapter = IncidentSupportTicketToolAdapter(incident_service=service)

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t015_filter_queries_by_status_category_origin_and_branch
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:171: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    adapter = IncidentSupportTicketToolAdapter(incident_service=service)

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t015_enforces_20_record_cap_and_reports_total_matched
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:207: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    adapter = IncidentSupportTicketToolAdapter(incident_service=service)

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t015_strict_read_only_contract_exposes_no_mutation_methods
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:219: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    adapter = IncidentSupportTicketToolAdapter(incident_service=service)

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t021_not_found_timeout_and_error_handling
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:238: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    adapter = IncidentSupportTicketToolAdapter(

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t021_not_found_timeout_and_error_handling
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:260: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    fast_timeout_adapter = IncidentSupportTicketToolAdapter(

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t021_not_found_timeout_and_error_handling
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:280: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    broken_adapter = IncidentSupportTicketToolAdapter(

tests/unit/test_operational_tools.py::TestSupportTicketToolAdapter::test_t015_http_transport_and_env_token_configuration
  J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\tests\unit\test_operational_tools.py:325: DeprecationWarning: IncidentSupportTicketToolAdapter is deprecated and decommissioned in active agent workflows. Use McpTicketToolAdapter from infrastructure.adapters.mcp_ticket_tool_adapter instead.
    adapter = IncidentSupportTicketToolAdapter(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
========================================================== short test summary info =========================================================== 
FAILED tests/api/test_suppliers_api.py::test_create_supplier_rejects_missing_country - assert 400 == 422
FAILED tests/api/test_suppliers_api.py::test_create_supplier_rejects_invalid_status - AssertionError: Expected 422 for status 'inactive', got 400
FAILED tests/api/test_suppliers_api.py::test_create_supplier_rejects_zero_or_negative_rate - AssertionError: Expected 422 for rate 0.0, got 400FAILED tests/api/test_suppliers_api.py::test_create_supplier_rejects_inconsistent_currency - assert 400 == 422
FAILED tests/api/test_suppliers_api.py::test_rate_update_rejects_zero_or_negative - assert 400 == 422
FAILED tests/api/test_suppliers_api.py::test_status_update_lifecycle - assert 400 == 422
FAILED tests/integration/test_agent_routes.py::TestSupportAgentRoutesIntegration::test_t043_query_endpoint_honest_refusal_and_mutation_guardrail - assert False is True
FAILED tests/integration/test_memory_storage_isolation.py::TestMemoryStorageIsolation::test_zero_qdrant_writes_across_10_memory_proposal_lifecycles - AssertionError: assert None is not None
FAILED tests/unit/test_application_services.py::test_inventory_service_stock_guard_insufficient_stock_error - assert 'Insufficient stock for SKU 1: requested 25, available 20' in "Insufficient stock for SKU 'SKU-BRAKE-01'. Available: 20, requested:...
FAILED tests/unit/test_domain_models.py::test_supplier_categories_synchronization - pydantic_core._pydantic_core.ValidationError: 1 validation 
error for Supplier
FAILED tests/unit/test_sqlmodel_client.py::test_sqlmodel_manager_custom_port - AssertionError: assert '@custom.pooler.supabase.com:6543/test_db' in 'sqlite:///J:\\GitHub\\mr-stegmann-ai-engineering-company-project-mon...
FAILED tests/unit/test_sqlmodel_client.py::test_sqlmodel_manager_db_port_fallback - AssertionError: assert '@custom.pooler.supabase.com:7654/test_db' in 'sqlite:///J:\\GitHub\\mr-stegmann-ai-engineering-company-project-mon...
FAILED tests/unit/test_sqlmodel_client.py::test_sqlmodel_manager_default_port_fallback - AssertionError: assert '@custom.pooler.supabase.com:5432/test_db' in 'sqlite:///J:\\GitHub\\mr-stegmann-ai-engineering-company-project-mon...
13 failed, 862 passed, 3 skipped, 11 warnings in 110.95s (0:01:50)
--- Logging error ---
Traceback (most recent call last):
  File "C:\Users\pjste\AppData\Roaming\uv\python\cpython-3.14-windows-x86_64-none\Lib\logging\__init__.py", line 1154, in emit
    stream.write(msg + self.terminator)
    ~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^
ValueError: I/O operation on closed file.
Call stack:
  File "J:\GitHub\mr-stegmann-ai-engineering-company-project-monorepo\services\api\.venv\Lib\site-packages\prefect\server\api\server.py", line 
1270, in stop
    subprocess_server_logger.info(
Message: 'Stopping temporary server on http://127.0.0.1:8461'
Arguments: ()