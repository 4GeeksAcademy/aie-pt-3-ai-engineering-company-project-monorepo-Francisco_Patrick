# Quickstart & Error Handling Validation Guide

**Feature**: [`spec.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/spec.md) | **Plan**: [`plan.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/plan.md)

This guide provides end-to-end verification steps for testing error handling behavior across Frontend, Backend, and Python CLI scripts.

---

## 1. Frontend Error UI Verification

### Scenario A: Unauthenticated Password Recovery Access
1. Open a browser and navigate to `http://localhost:3000/forgot-password` without logging in.
2. **Expected Outcome**: The password recovery page loads immediately. `AuthGuard` allows access to public routes without hanging in a loading state or redirecting to `/login`.

### Scenario B: 3-State Async Data Fetching & Call to Action
1. Stop the FastAPI backend (`http://localhost:8000`).
2. Navigate to `http://localhost:3000/suppliers`.
3. **Expected Outcome**:
   - Initial state shows loading indicator.
   - When request fails, loading spinner disappears (`finally` block cleanup).
   - An error banner is displayed with a human-readable message.
   - A **"Retry"** button is present. Clicking retry attempts to re-fetch suppliers.

---

## 2. Backend Structured Error & Privacy Verification

### Scenario A: Malformed Upload in Incident Analysis
1. Send a non-CSV file or trigger a parsing error on `POST /api/incidents/analyze`.
2. **Expected Outcome**: HTTP 400 or 500 response returned with clean JSON:
   ```json
   {
     "error": "Server Error",
     "message": "An unexpected error occurred while processing the incident file."
   }
   ```
   Zero Python tracebacks or `str(e)` raw dumps are exposed in the JSON response.

### Scenario B: Sensitive PII & Token Logging Check
1. Trigger a password reset request via `POST /auth/forgot-password`.
2. Check backend console logs.
3. **Expected Outcome**: Reset URLs and emails are masked in console output (`[EmailService] Password reset link sent to u***@domain.com`). Raw secret tokens are NOT printed in plain text.

---

## 3. Python CLI Script Robustness Verification

### Scenario A: Non-Existent File Input
1. Execute `python scripts/analyze.py non_existent_file.csv`.
2. **Expected Outcome**:
   - Message written to `stderr`: `Error: File 'non_existent_file.csv' not found.`
   - Shell exit code is `1` (`echo $?` or `$LASTEXITCODE` in PowerShell equals `1`).

### Scenario B: Interrupt Signal Trapping
1. Run `python scripts/seed_incidents.py` and press `Ctrl+C` immediately.
2. **Expected Outcome**:
   - Message written to `stderr`: `[CANCELLED] Operation aborted by user.`
   - Exit code is `130`.
