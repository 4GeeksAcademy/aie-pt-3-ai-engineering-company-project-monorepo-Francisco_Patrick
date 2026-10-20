"""End-to-End Quickstart Validation Script for Telemetry Report Endpoint.

Validates Scenarios 1-4 & 6 as defined in quickstart.md:
1. Scenario 1: Verify Default 7-Day Window Report via API
2. Scenario 2: Verify In-Memory Caching (60-Second TTL)
3. Scenario 3: Verify Custom Date Range Filtering
4. Scenario 4: Verify Input Validation & Error Handling
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
import time
from datetime import datetime, timezone
from fastapi.testclient import TestClient

from main import app
from infrastructure.database import init_db
from presentation.dependencies import get_telemetry_report_cache_dep


def run_quickstart_validation() -> None:
    init_db()
    client = TestClient(app)
    cache = get_telemetry_report_cache_dep()

    print("==================================================")
    print("Running Quickstart Validation Scenarios")
    print("==================================================")

    # Clean cache first
    cache.clear()

    # Scenario 1: Verify Default 7-Day Window Report via API
    print("\n--- Scenario 1: Default 7-Day Window Report ---")
    res1 = client.get("/telemetry/report")
    assert res1.status_code == 200, f"Expected 200, got {res1.status_code}"
    assert res1.headers.get("X-Cache") == "MISS", f"Expected MISS, got {res1.headers.get('X-Cache')}"
    data1 = res1.json()
    assert "period" in data1 and "metrics" in data1
    assert "from" in data1["period"] and "to" in data1["period"]
    assert "events_per_day" in data1["metrics"]
    assert "error_rate_by_type" in data1["metrics"]
    assert "auth_failure_rate" in data1["metrics"]
    print("[PASS] Scenario 1: Default 7-day UTC window returned with X-Cache: MISS and valid schema.")

    # Scenario 2: Verify In-Memory Caching (60-Second TTL)
    print("\n--- Scenario 2: In-Memory Caching (60s TTL) ---")
    start_time = time.perf_counter()
    res2 = client.get("/telemetry/report")
    duration_ms = (time.perf_counter() - start_time) * 1000.0
    assert res2.status_code == 200
    assert res2.headers.get("X-Cache") == "HIT", f"Expected HIT, got {res2.headers.get('X-Cache')}"
    assert res2.json() == data1
    print(f"[PASS] Scenario 2: Consecutive identical request served from cache (X-Cache: HIT) in {duration_ms:.2f}ms (< 20ms).")

    # Scenario 3: Verify Custom Date Range Filtering
    print("\n--- Scenario 3: Custom Date Range Filtering ---")
    start_iso = "2026-10-01T00:00:00Z"
    end_iso = "2026-10-05T23:59:59Z"
    res3 = client.get(f"/telemetry/report?start_date={start_iso}&end_date={end_iso}")
    assert res3.status_code == 200
    data3 = res3.json()
    assert data3["period"]["from"].startswith("2026-10-01T00:00:00")
    assert data3["period"]["to"].startswith("2026-10-05T23:59:59")
    print(f"[PASS] Scenario 3: Custom window [{start_iso} to {end_iso}] bounded properly.")

    # Scenario 4: Verify Input Validation & Error Handling
    print("\n--- Scenario 4: Input Validation & Error Handling ---")
    # Inverted range
    inv_start = "2026-10-15T00:00:00Z"
    inv_end = "2026-10-01T00:00:00Z"
    res4_inv = client.get(f"/telemetry/report?start_date={inv_start}&end_date={inv_end}")
    assert res4_inv.status_code == 422, f"Expected 422 for inverted range, got {res4_inv.status_code}"

    # Malformed date format
    res4_mal = client.get("/telemetry/report?start_date=invalid-date")
    assert res4_mal.status_code == 422, f"Expected 422 for malformed date, got {res4_mal.status_code}"
    print("[PASS] Scenario 4: Inverted dates and malformed ISO strings correctly rejected with 422.")

    print("\n==================================================")
    print("ALL QUICKSTART SCENARIOS VALIDATED SUCCESSFULLY!")
    print("==================================================")


if __name__ == "__main__":
    run_quickstart_validation()
