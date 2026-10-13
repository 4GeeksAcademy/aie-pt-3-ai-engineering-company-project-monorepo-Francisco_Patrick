# Quickstart Validation Guide

## Setup

1. Start Backend:
   ```bash
   cd services/api
   uv run uvicorn main:app --reload
   ```

2. Seed Data:
   ```bash
   cd services/api
   uv run seed
   ```

3. Start Frontend:
   ```bash
   cd uis/backoffice
   npm install
   npm run dev
   ```

## Validation Scenarios

1. **Verify Backend API**:
   - `GET http://localhost:8000/suppliers` should return seeded suppliers.
2. **Verify Frontend UI**:
   - Open `http://localhost:3000/suppliers`.
   - Ensure you can see the table with suppliers.
   - Filter by country and see immediate updates.
   - Change a status and see it reflect visually.
