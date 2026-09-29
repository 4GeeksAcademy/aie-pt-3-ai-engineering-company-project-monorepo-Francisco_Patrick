# Quickstart & Verification Guide: Caching & Optimization

## 1. Prerequisites
- Python virtual environment active in `services/api/.venv/`
- Node.js dependencies installed in `uis/backoffice/` and `uis/website/`

---

## 2. Backend Caching Validation

### Running Backend Cache Tests
```powershell
cd services/api
.\.venv\Scripts\pytest tests/unit/test_cache.py tests/api/test_cached_endpoints.py -v
```

### Manual Verification Scenarios
1. **Cache Hit Verification**:
   - Send `GET http://127.0.0.1:8000/api/incidents/summary` (First call: Cache MISS).
   - Send `GET http://127.0.0.1:8000/api/incidents/summary` within 30s (Second call: Cache HIT).
2. **Mutation Invalidation Verification**:
   - Send `POST http://127.0.0.1:8000/api/incidents` to register an incident.
   - Send `GET http://127.0.0.1:8000/api/incidents/summary` -> Verify new counts are immediately returned.

---

## 3. Frontend Lazy Loading & Memoization Validation

### Building and Testing Backoffice
```powershell
cd uis/backoffice
npm test
npm run build
```

### Verification
- Inspect generated `.next` bundle chunks to confirm separate async chunks are emitted for lazy-loaded tables and forms.
- Verify `OrdersHistoryTable` and `ProductTable` render without flicker and maintain memoized metric aggregates during state updates.

---

## 4. Technical Report Presence
- Confirm `CACHING_REPORT.md` exists in the repository root and covers:
  1. Frontend Decisions (Lazy loading & `useMemo`).
  2. Backend Decisions (Matrix, TTLs, invalidation).
  3. Tradeoffs Acknowledged (Freshness vs. speed).
  4. What was not cached and why.
