# Codebase Error Handling Audit Report

This audit evaluates the error handling quality across the Next.js frontend in `uis/`, the FastAPI backend in `services/api/`, and Python CLI scripts in `scripts/`. Findings are prioritized by severity: **CRITICAL** > **HIGH** > **MEDIUM** > **LOW**.

---

## 1. CRITICAL Severity

### Finding 1.1: Plaintext Secret & PII Logging in Email Mock
- **File Path & Lines:** `services/api/application/services/email_service.py:11`
- **Category:** SENSITIVE DATA LEAKS
- **Description:** Plaintext password reset link containing secret authentication tokens (`reset_link`) and user email address (PII) are printed directly to standard console logs during mock execution.
- **Suggested Fix:** Sanitize console log outputs by masking user email addresses and logging only token hashes instead of raw reset URL tokens.

### Finding 1.2: Raw Exception Detail Exposure in API 500 Responses
- **File Path & Lines:** `services/api/main.py:180-181`
- **Category:** RAW ERROR EXPOSURE
- **Description:** Generic `Exception` handler in `/api/incidents/analyze` catches arbitrary runtime exceptions and returns `str(e)` directly inside the HTTP 500 `detail` field.
- **Suggested Fix:** Log full exception tracebacks internally via a logger and return a generic user-safe error message (e.g. `"An internal server error occurred while processing the incident file."`).

### Finding 1.3: Omission of Password Recovery Routes in AuthGuard Public Paths
- **File Path & Lines:** `uis/backoffice/components/AuthGuard.tsx:7-28`
- **Category:** MISSING LOADING/ERROR UI STATES
- **Description:** `PUBLIC_PATHS` array only lists `/login` and `/register`, omitting `/forgot-password` and `/reset-password`. Unauthenticated users navigating to password recovery routes trigger an infinite loading spinner followed by a redirect to `/login`.
- **Suggested Fix:** Add `/forgot-password` and `/reset-password` to the `PUBLIC_PATHS` array in `AuthGuard.tsx`.

### Finding 1.4: Unhandled TinyDB Database Operations across Supplier Routes
- **File Path & Lines:** `services/api/routes/suppliers.py:20-125`
- **Category:** MISSING TRY/CATCH
- **Description:** Route handlers (`create_supplier`, `list_suppliers`, `get_supplier`, `update_supplier_rate`, `update_supplier_status`, `delete_supplier`) perform TinyDB queries (`table.insert`, `table.search`, `table.get`, `table.update`, `table.remove`) without any `try/except` error handling.
- **Suggested Fix:** Wrap database interactions in `try/except` blocks and catch I/O or database errors, returning appropriate HTTP error responses (e.g., HTTP 500 or HTTP 503).

### Finding 1.5: Unprotected Seed Loop in Historical Incidents Script
- **File Path & Lines:** `scripts/seed_incidents.py:33-58`
- **Category:** MISSING TRY/CATCH
- **Description:** File opening (`open`), CSV streaming (`DictReader`), record validation, model instantiation, and database writes (`repo.find_by_legacy_id`, `repo.save`) execute in a loop without per-record or function-level `try/except` blocks. A single corrupt row or write error aborts the entire seeding process.
- **Suggested Fix:** Add `try/except` handling inside the iteration loop to capture and report row-level errors while allowing valid records to be processed.

---

## 2. HIGH Severity

### Finding 2.1: Plaintext Email Addresses Logged to Audit Trail
- **File Path & Lines:** `services/api/application/services/auth_service.py:46, 52, 58`
- **Category:** SENSITIVE DATA LEAKS
- **Description:** Plaintext email addresses (PII) are recorded in audit log detail strings (`f"Email: {email}"`) during password reset requests.
- **Suggested Fix:** Hash or anonymize email addresses (e.g. `u***@domain.com` or SHA-256 hash) before passing them to `audit_repo.log_event`.

### Finding 2.2: Swallowed Resend Email Dispatch Failure
- **File Path & Lines:** `services/api/application/services/email_service.py:45-47`
- **Category:** SILENT FAILURES
- **Description:** Generic `Exception` during Resend API email dispatch is caught, printed to `stdout`, and swallowed by returning `False` without raising a domain exception or triggering an alert.
- **Suggested Fix:** Log structured errors via proper logging infrastructure and raise a custom domain exception (e.g., `EmailDeliveryError`) so callers can respond appropriately.

### Finding 2.3: Unhandled Network Errors in Centralized Fetch Utility
- **File Path & Lines:** `uis/backoffice/lib/api.ts:20-23`
- **Category:** MISSING TRY/CATCH
- **Description:** `fetchWithAuth` executes `fetch()` without a `try/catch` block. Low-level network failures, DNS resolution issues, or dropped connections throw uncaught `TypeError` exceptions.
- **Suggested Fix:** Wrap `fetch()` in a `try/catch` block, catch network-level exceptions, and rethrow a structured `ApiNetworkError`.

### Finding 2.4: Missing Catch Clause in Supplier Creation Handler
- **File Path & Lines:** `uis/backoffice/app/suppliers/page.tsx:41-59`
- **Category:** OVERLY BROAD CATCH
- **Description:** `handleAddSupplier` contains a `try...finally` block without a `catch` handler. Unhandled network or HTTP failure exceptions leave form submission state corrupted.
- **Suggested Fix:** Add an explicit `catch` block to set client-facing error state and display user notifications when creation fails.

### Finding 2.5: Missing Error Handling Around Password Reset Email Dispatch
- **File Path & Lines:** `services/api/application/services/auth_service.py:61`
- **Category:** MISSING TRY/CATCH
- **Description:** `email_service.send_password_reset_email` is invoked inside `request_password_reset` without error handling if the underlying dispatch throws an exception.
- **Suggested Fix:** Wrap `email_service.send_password_reset_email` in a `try/except` block and handle delivery failures gracefully without breaking the anti-enumeration contract.

### Finding 2.6: Unprotected File Writing in Analysis Export Function
- **File Path & Lines:** `scripts/analyze.py:44-55`
- **Category:** MISSING TRY/CATCH
- **Description:** `export_to_csv` opens and writes to the output CSV file (`open(output_path, "w", ...)`) without a `try/except` block. File system permission errors or invalid paths cause an unhandled script crash.
- **Suggested Fix:** Wrap file creation and `csv.writer` operations in a `try/except` block and handle I/O exceptions cleanly with a clear error message and non-zero exit code.

### Finding 2.7: Quiet Interruption Swallowing Without Exit Code in Analysis CLI
- **File Path & Lines:** `scripts/analyze.py:81-82`
- **Category:** MISSING sys.exit ON SCRIPT FAILURE
- **Description:** `except KeyboardInterrupt: pass` catches Ctrl+C interruption and exits with implicit return code 0 instead of setting a non-zero exit code.
- **Suggested Fix:** Replace `pass` with `sys.exit(130)` and print a cancellation message to `stderr`.

---

## 3. MEDIUM Severity

### Finding 3.1: Monolithic Try/Except Block in Incident Analysis Endpoint
- **File Path & Lines:** `services/api/main.py:166-181`
- **Category:** OVERLY BROAD CATCH
- **Description:** `/api/incidents/analyze` route wraps file reading (`await file.read()`), string decoding, and CSV stream processing into a single generic `except Exception as e:` block.
- **Suggested Fix:** Refactor into narrower `try/except` blocks separating file reading, UTF-8 decoding, and CSV analysis stages.

### Finding 3.2: Exposure of Raw Validation Message Text in Routes
- **File Path & Lines:** `services/api/presentation/api/profile_routes.py:27-28` & `services/api/presentation/api/user_routes.py:17-18`
- **Category:** RAW ERROR EXPOSURE
- **Description:** Route handlers catch `ValueError as e` and pass raw `str(e)` directly into `HTTPException` detail fields.
- **Suggested Fix:** Map domain validation errors to structured error response schemas rather than reflecting raw Python exception text.

### Finding 3.3: Static Error Banner Without Retry CTA in Suppliers View
- **File Path & Lines:** `uis/backoffice/app/suppliers/page.tsx:139-143`
- **Category:** NO USER CALL TO ACTION
- **Description:** Renders a static error banner (`{error}`) when supplier data fetching fails, offering no retry button or corrective action link.
- **Suggested Fix:** Provide a "Retry" button within the error banner to trigger `fetchSuppliers()` on click.

### Finding 3.4: Static Error Display Without Call to Action in Profile Page
- **File Path & Lines:** `uis/backoffice/app/account/profile/page.tsx:97-101`
- **Category:** NO USER CALL TO ACTION
- **Description:** Renders a static error message container (`<p className="text-sm text-red-700">{error}</p>`) when profile loading fails, without offering a retry or navigation option.
- **Suggested Fix:** Add a retry CTA button to re-trigger profile data loading.

### Finding 3.5: Broad Top-Level Exception Catching in Seeder Main Function
- **File Path & Lines:** `scripts/seed_incidents.py:90-95`
- **Category:** OVERLY BROAD CATCH
- **Description:** `main()` wraps `seed_incidents_from_csv` in a single broad `except Exception as e:` block and prints raw exception string text to standard output.
- **Suggested Fix:** Catch specific expected exceptions (`FileNotFoundError`, `csv.Error`) separately with targeted error messages.

### Finding 3.6: Missing Explicit sys.exit on Database Seed Failure
- **File Path & Lines:** `services/api/seed.py:58-75`
- **Category:** MISSING sys.exit ON SCRIPT FAILURE
- **Description:** `run_seed` script does not wrap TinyDB database operations in `try/except` or invoke explicit `sys.exit(1)` on database failure.
- **Suggested Fix:** Wrap database seeding in `try/except` and execute `sys.exit(1)` upon catching initialization or insertion errors.

---

## 4. LOW Severity

### Finding 4.1: Broad Exception Block in CSV Analysis Script Main Entry Point
- **File Path & Lines:** `scripts/analyze.py:67-72`
- **Category:** OVERLY BROAD CATCH
- **Description:** `main()` wraps file opening and CSV analysis in a broad `except Exception as e:` block.
- **Suggested Fix:** Catch `IOError`, `UnicodeDecodeError`, and `csv.Error` explicitly to provide context-specific error diagnostic output.

### Finding 4.2: Omission of Dev Console Logging in Auth Form Error Handlers
- **File Path & Lines:** `uis/backoffice/app/login/page.tsx:44-46` & `uis/backoffice/app/register/page.tsx:76-78`
- **Category:** SILENT FAILURES
- **Description:** Form submit handlers catch generic `err: any` and update UI error state strings, but omit logging original error objects to `console.error`.
- **Suggested Fix:** Add `console.error(err)` inside catch blocks for developer observability alongside user UI notifications.

---

*End of Audit Report.*
