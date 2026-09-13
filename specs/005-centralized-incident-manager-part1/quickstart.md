# Quickstart & Verification Guide: Centralized Incident Manager - Part I

## Prerequisites

- Python 3.11+
- Monorepo dependencies installed (`pip install -r services/api/requirements.txt` or `uv sync`)

---

## 1. Execute Data Seeding Script

Run the seed script to load historical CSV records into TinyDB:

```bash
python scripts/seed_incidents.py scripts/incidents-COMPANY.csv
```

**Expected Output**:
- Console report showing count of valid records inserted into database with origin `customer`.
- Console output detailing any invalid CSV records skipped with failure reasons.

---

## 2. Test Idempotency

Execute the seed script a second time against the same dataset:

```bash
python scripts/seed_incidents.py scripts/incidents-COMPANY.csv
```

**Expected Output**:
- Console report indicating 0 new records inserted (all records recognized as existing).
- Zero duplicate records in the database.

---

## 3. Verify Aggregated Summary via API

Start the API service:

```bash
cd services/api
uvicorn main:app --reload --port 8000
```

Query the summary endpoint:

```bash
curl http://localhost:8000/api/incidents/summary
```

**Expected Response**:
- JSON response with `total_incidents`, `by_status`, and `by_category` counts matching historical transformed valid totals.
