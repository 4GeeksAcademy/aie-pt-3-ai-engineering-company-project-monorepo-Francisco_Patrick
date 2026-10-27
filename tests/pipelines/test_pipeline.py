"""Isolated In-Memory Unit Tests for Pipeline Transformation Tasks.

Validates transformation tasks in 100% memory isolation with zero live database
or external network dependencies:
- FR-006: Dedicated test module with transformation unit tests.
- FR-007: Zero database and zero network dependencies; executed entirely in-memory.
- FR-008: Defensive handling of invalid, malformed, or missing input fields.
- FR-009: Exact mathematical validation against company-BRIEFING.md ground truth formulas.
- FR-010: Terminates cleanly with exit code 0 via pytest.
"""

from datetime import datetime, timezone
from typing import Any, Dict
import numpy as np
import pandas as pd
import pytest

from data.pipelines.pipeline import (
    compute_regional_metrics,
    transform_executive_kpis,
)


@pytest.fixture
def empty_raw_datasets() -> Dict[str, pd.DataFrame]:
    """In-memory fixture providing completely empty DataFrames for all domain entities."""
    return {
        "orders": pd.DataFrame(
            columns=["order_id", "warehouse_code", "total_cost_eur", "destination_country", "timestamp"]
        ),
        "tracking": pd.DataFrame(
            columns=["tracking_number_hash", "origin_warehouse", "timestamp", "is_delivered", "is_delivered_on_time"]
        ),
        "returns": pd.DataFrame(
            columns=["return_id", "warehouse_code", "timestamp"]
        ),
        "cx": pd.DataFrame(
            columns=["ticket_id", "warehouse_code", "csat_rating", "first_contact_resolution", "timestamp"]
        ),
    }


@pytest.fixture
def deterministic_ground_truth_datasets() -> Dict[str, pd.DataFrame]:
    """In-memory deterministic dataset with hand-calculated ground truth metrics."""
    # US Hub: 4 orders, 4 tracking (3 on-time), 1 return, 2 CX tickets (ratings 4.0 & 5.0, FCR 1.0 & 0.0)
    orders_data = [
        {"order_id": "ORD-US-01", "warehouse_code": "US-LAX-01", "total_cost_eur": 100.00, "destination_country": "US", "timestamp": "2026-10-15T10:00:00Z"},
        {"order_id": "ORD-US-02", "warehouse_code": "US-LAX-01", "total_cost_eur": 250.50, "destination_country": "US", "timestamp": "2026-10-15T11:00:00Z"},
        {"order_id": "ORD-US-03", "warehouse_code": "US-LAX-01", "total_cost_eur": 50.00, "destination_country": "US", "timestamp": "2026-10-15T12:00:00Z"},
        {"order_id": "ORD-US-04", "warehouse_code": "US-LAX-01", "total_cost_eur": 199.50, "destination_country": "US", "timestamp": "2026-10-15T13:00:00Z"},
        # ES Hub: 6 orders, 5 tracking (5 on-time), 0 returns, 1 CX ticket (rating 5.0, FCR 1.0)
        {"order_id": "ORD-ES-01", "warehouse_code": "ES-ZAZ-01", "total_cost_eur": 50.00, "destination_country": "ES", "timestamp": "2026-10-16T08:00:00Z"},
        {"order_id": "ORD-ES-02", "warehouse_code": "ES-ZAZ-01", "total_cost_eur": 50.00, "destination_country": "ES", "timestamp": "2026-10-16T09:00:00Z"},
        {"order_id": "ORD-ES-03", "warehouse_code": "ES-ZAZ-01", "total_cost_eur": 100.00, "destination_country": "ES", "timestamp": "2026-10-16T10:00:00Z"},
        {"order_id": "ORD-ES-04", "warehouse_code": "ES-ZAZ-01", "total_cost_eur": 150.00, "destination_country": "ES", "timestamp": "2026-10-16T11:00:00Z"},
        {"order_id": "ORD-ES-05", "warehouse_code": "ES-ZAZ-01", "total_cost_eur": 200.00, "destination_country": "ES", "timestamp": "2026-10-16T12:00:00Z"},
        {"order_id": "ORD-ES-06", "warehouse_code": "ES-ZAZ-01", "total_cost_eur": 50.00, "destination_country": "ES", "timestamp": "2026-10-16T13:00:00Z"},
    ]

    tracking_data = [
        {"tracking_number_hash": "TRK-US-1", "origin_warehouse": "US-LAX-01", "timestamp": "2026-10-15T14:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
        {"tracking_number_hash": "TRK-US-2", "origin_warehouse": "US-LAX-01", "timestamp": "2026-10-15T15:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
        {"tracking_number_hash": "TRK-US-3", "origin_warehouse": "US-LAX-01", "timestamp": "2026-10-15T16:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
        {"tracking_number_hash": "TRK-US-4", "origin_warehouse": "US-LAX-01", "timestamp": "2026-10-15T17:00:00Z", "is_delivered": True, "is_delivered_on_time": 0.0},
        {"tracking_number_hash": "TRK-ES-1", "origin_warehouse": "ES-ZAZ-01", "timestamp": "2026-10-16T14:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
        {"tracking_number_hash": "TRK-ES-2", "origin_warehouse": "ES-ZAZ-01", "timestamp": "2026-10-16T15:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
        {"tracking_number_hash": "TRK-ES-3", "origin_warehouse": "ES-ZAZ-01", "timestamp": "2026-10-16T16:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
        {"tracking_number_hash": "TRK-ES-4", "origin_warehouse": "ES-ZAZ-01", "timestamp": "2026-10-16T17:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
        {"tracking_number_hash": "TRK-ES-5", "origin_warehouse": "ES-ZAZ-01", "timestamp": "2026-10-16T18:00:00Z", "is_delivered": True, "is_delivered_on_time": 1.0},
    ]

    returns_data = [
        {"return_id": "RET-US-1", "warehouse_code": "US-LAX-01", "timestamp": "2026-10-17T09:00:00Z"},
    ]

    cx_data = [
        {"ticket_id": "CX-US-1", "warehouse_code": "US-LAX-01", "csat_rating": 4.0, "first_contact_resolution": 1.0, "timestamp": "2026-10-17T11:00:00Z"},
        {"ticket_id": "CX-US-2", "warehouse_code": "US-LAX-01", "csat_rating": 5.0, "first_contact_resolution": 0.0, "timestamp": "2026-10-17T12:00:00Z"},
        {"ticket_id": "CX-ES-1", "warehouse_code": "ES-ZAZ-01", "csat_rating": 5.0, "first_contact_resolution": 1.0, "timestamp": "2026-10-17T13:00:00Z"},
    ]

    return {
        "orders": pd.DataFrame(orders_data),
        "tracking": pd.DataFrame(tracking_data),
        "returns": pd.DataFrame(returns_data),
        "cx": pd.DataFrame(cx_data),
    }


# ---------------------------------------------------------------------------
# Test 1: Zero-Division Guardrails and Neutral Defaults (FR-008)
# ---------------------------------------------------------------------------

def test_transformation_zero_division_guardrails(empty_raw_datasets: Dict[str, pd.DataFrame]) -> None:
    """Verify neutral fallbacks and zero-division protection when event DataFrames are empty.

    Guarantees:
    - shipments_volume == 0
    - on_time_delivery_rate == 1.0 (nominal default when no deliveries exist)
    - operational_cost_eur == 0.0
    - returns_rate == 0.0 (prevents 0 / 0 division)
    - customer_satisfaction_score == 100.0 (nominal default when no inquiries exist)
    """
    for scope in ["US", "ES", "GLOBAL"]:
        metrics = compute_regional_metrics(
            df_orders=empty_raw_datasets["orders"],
            df_tracking=empty_raw_datasets["tracking"],
            df_returns=empty_raw_datasets["returns"],
            df_cx=empty_raw_datasets["cx"],
            country_code=scope,
        )

        assert metrics["country"] == scope
        assert metrics["shipments_volume"] == 0
        assert metrics["on_time_delivery_rate"] == 1.0
        assert metrics["operational_cost_eur"] == 0.0
        assert metrics["returns_rate"] == 0.0
        assert metrics["customer_satisfaction_score"] == 100.0

    # Also test with returns present but orders volume = 0
    returns_with_items = pd.DataFrame([{"return_id": "RET-1", "warehouse_code": "US-LAX-01", "timestamp": "2026-10-15"}])
    metrics_with_orphan_return = compute_regional_metrics(
        df_orders=empty_raw_datasets["orders"],
        df_tracking=empty_raw_datasets["tracking"],
        df_returns=returns_with_items,
        df_cx=empty_raw_datasets["cx"],
        country_code="US",
    )
    assert metrics_with_orphan_return["returns_rate"] == 0.0


# ---------------------------------------------------------------------------
# Test 2: Defensive Handling of Malformed and Missing Payloads (FR-008)
# ---------------------------------------------------------------------------

def test_transformation_malformed_and_missing_payloads() -> None:
    """Verify graceful recovery from corrupted data types, nulls, missing columns, and out-of-range ratings."""
    malformed_orders = pd.DataFrame([
        {"order_id": "ORD-BAD-1", "warehouse_code": "US-LAX-01", "total_cost_eur": "invalid_cost_string"},
        {"order_id": "ORD-BAD-2", "warehouse_code": "US-LAX-01", "total_cost_eur": None},
        {"order_id": "ORD-BAD-3", "warehouse_code": "US-LAX-01", "total_cost_eur": 120.50},
    ])

    malformed_tracking = pd.DataFrame([
        {"origin_warehouse": "US-LAX-01", "is_delivered": None, "is_delivered_on_time": "not_a_number"},
        {"origin_warehouse": "US-LAX-01", "is_delivered": True, "is_delivered_on_time": None},
        {"origin_warehouse": "US-LAX-01", "is_delivered": True, "is_delivered_on_time": 1.0},
    ])

    # CSAT with extreme out-of-range values and missing FCR column
    malformed_cx = pd.DataFrame([
        {"warehouse_code": "US-LAX-01", "csat_rating": -10.0},  # Below 1.0 -> dropped
        {"warehouse_code": "US-LAX-01", "csat_rating": 99.0},   # Above 5.0 -> dropped
        {"warehouse_code": "US-LAX-01", "csat_rating": 5.0},    # Valid
    ])

    metrics = compute_regional_metrics(
        df_orders=malformed_orders,
        df_tracking=malformed_tracking,
        df_returns=pd.DataFrame(),  # completely missing expected columns
        df_cx=malformed_cx,
        country_code="US",
    )

    assert metrics["shipments_volume"] == 3
    # Only 120.50 is valid numeric
    assert metrics["operational_cost_eur"] == 120.50
    # Delivery rate with 1 valid on_time entry
    assert metrics["on_time_delivery_rate"] == 1.0
    # CSAT bounded between 0.0 and 100.0, only rating 5.0 retained: (5.0/5.0)*100*0.70 + 100*0.30 = 100.0
    assert metrics["customer_satisfaction_score"] == 100.0
    assert metrics["returns_rate"] == 0.0

    # Test with totally empty / missing columns DataFrames
    empty_unstructured_dict: Dict[str, pd.DataFrame] = {
        "orders": pd.DataFrame(),
        "tracking": pd.DataFrame(),
        "returns": pd.DataFrame(),
        "cx": pd.DataFrame(),
    }
    snapshots = transform_executive_kpis(
        raw_data=empty_unstructured_dict,
        period_start=datetime(2026, 10, 12, tzinfo=timezone.utc),
        period_end=datetime(2026, 10, 18, tzinfo=timezone.utc),
    )
    assert len(snapshots) == 3
    assert set(s["country"] for s in snapshots) == {"US", "ES", "GLOBAL"}


# ---------------------------------------------------------------------------
# Test 3: Exact Mathematical Precision against Ground Truth (FR-009)
# ---------------------------------------------------------------------------

def test_transformation_exact_mathematical_precision(
    deterministic_ground_truth_datasets: Dict[str, pd.DataFrame]
) -> None:
    """Validate all 5 executive KPIs against hand-calculated expected values per company briefing.

    Hand-Calculated Ground Truth:
    US Hub ('US-LAX-01'):
    - Shipments Volume: 4 orders
    - Operational Cost: 100.00 + 250.50 + 50.00 + 199.50 = €600.00
    - On-Time Delivery Rate: 3 / 4 = 0.75 (75.0%)
    - Returns Rate: (1 / 4) * 100 = 25.0%
    - CSAT Score: ( ( (4.5 / 5.0) * 100.0 ) * 0.70 ) + ( (0.5 * 100.0) * 0.30 ) = 63.0 + 15.0 = 78.0

    ES Hub ('ES-ZAZ-01'):
    - Shipments Volume: 6 orders
    - Operational Cost: 50 + 50 + 100 + 150 + 200 + 50 = €600.00
    - On-Time Delivery Rate: 5 / 5 = 1.0 (100.0%)
    - Returns Rate: 0 / 6 = 0.0%
    - CSAT Score: (100.0 * 0.70) + (100.0 * 0.30) = 100.0

    GLOBAL Consolidation:
    - Shipments Volume: 4 + 6 = 10 orders
    - Operational Cost: 600.00 + 600.00 = €1,200.00
    - On-Time Delivery Rate: (3 + 5) / (4 + 5) = 8 / 9 = 0.8889
    - Returns Rate: (1 / 10) * 100 = 10.0%
    - CSAT Score:
      - Ratings: [4.0, 5.0, 5.0] -> mean = 14/3 = 4.6667 -> pct = (14/15)*100 = 93.3333%
      - FCR: [1.0, 0.0, 1.0] -> mean = 2/3 = 66.6667%
      - CSAT = (93.3333 * 0.70) + (66.6667 * 0.30) = 65.3333 + 20.0 = 85.33
    """
    raw_data = deterministic_ground_truth_datasets
    period_start = datetime(2026, 10, 12, 0, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2026, 10, 18, 23, 59, 59, tzinfo=timezone.utc)

    snapshots = transform_executive_kpis(
        raw_data=raw_data,
        period_start=period_start,
        period_end=period_end,
    )

    snapshots_by_country: Dict[str, Dict[str, Any]] = {s["country"]: s for s in snapshots}

    # Verify US Hub
    us = snapshots_by_country["US"]
    assert us["shipments_volume"] == 4
    assert us["operational_cost_eur"] == 600.00
    assert us["on_time_delivery_rate"] == 0.75
    assert us["returns_rate"] == 25.0
    assert us["customer_satisfaction_score"] == 78.0

    # Verify ES Hub
    es = snapshots_by_country["ES"]
    assert es["shipments_volume"] == 6
    assert es["operational_cost_eur"] == 600.00
    assert es["on_time_delivery_rate"] == 1.0
    assert es["returns_rate"] == 0.0
    assert es["customer_satisfaction_score"] == 100.0

    # Verify GLOBAL Consolidated
    glb = snapshots_by_country["GLOBAL"]
    assert glb["shipments_volume"] == 10
    assert glb["operational_cost_eur"] == 1200.00
    assert glb["on_time_delivery_rate"] == 0.8889
    assert glb["returns_rate"] == 10.0
    assert glb["customer_satisfaction_score"] == 85.33
