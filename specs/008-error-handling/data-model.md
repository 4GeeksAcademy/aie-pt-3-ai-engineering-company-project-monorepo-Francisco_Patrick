# Phase 1 Data Model: Comprehensive Error Handling

**Feature**: [`spec.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/spec.md) | **Plan**: [`plan.md`](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/specs/008-error-handling/plan.md)

## 1. Backend Error Response Entities

### `ErrorResponsePayload` (API Response Model)
Standardized JSON error model returned by all FastAPI exception handlers.

| Field Name | Type | Required | Description | Example |
| :--- | :--- | :---: | :--- | :--- |
| `error` | `string` | Yes | High-level error classification category | `"Validation Error"`, `"Server Error"`, `"Not Found"` |
| `message` | `string` | Yes | Human-readable user-safe explanation | `"Failed to process supplier request. Please check inputs."` |
| `detail` | `string` | No | Additional context or user-facing detail (optional) | `"Supplier ID 42 was not found."` |
| `details` | `array<ValidationErrorDetail>` | No | Structured field-level validation errors (if applicable) | `[{"field": "email", "issue": "Invalid email domain"}]` |

### `ValidationErrorDetail` (Field Error Model)
Nested error structure for request validation failures.

| Field Name | Type | Required | Description | Example |
| :--- | :--- | :---: | :--- | :--- |
| `field` | `string` | Yes | Target field path or parameter name | `"email"`, `"cost_per_kg"` |
| `issue` | `string` | Yes | Specific validation rule violated | `"Value must be greater than 0"` |

---

## 2. Frontend Error UI State Entities

### `AsyncState<T>` (Component State Model)
Three-state UI interface implemented in Next.js React components.

| Field Name | Type | Description | State Transitions |
| :--- | :--- | :--- | :--- |
| `isLoading` | `boolean` | Indicates if an async request is currently in flight | Set `true` on trigger; set `false` in `finally` |
| `data` | `T \| null` | Fulfilled payload data when request succeeds | Set data on success; reset or keep existing on retry |
| `error` | `string \| null` | Human-readable error message on rejection | Set error text on catch; reset `null` on new attempt |

### `CallToAction` (UI Recovery Action Model)
Props for interactive error recovery banners.

| Field Name | Type | Required | Description |
| :--- | :--- | :---: | :--- |
| `label` | `string` | Yes | Button label (e.g. `"Retry Loading"`, `"Back to Home"`) |
| `action` | `() => void` | Yes | Execution callback function |
| `variant` | `'primary' \| 'secondary'` | No | Visual button hierarchy styling |

---

## 3. Sanitized Audit Log Entity

### `AuditLogEntry` (Sanitized Model)
Database model for security and authentication audit logs in TinyDB.

| Field Name | Type | Required | Description | PII Protection Rule |
| :--- | :--- | :---: | :--- | :--- |
| `id` | `string` | Yes | Unique UUID string | N/A |
| `event_type` | `string` | Yes | Action type (e.g. `"forgot_password_request"`) | N/A |
| `user_id` | `string \| null` | No | Associated user ID if known | N/A |
| `ip_address` | `string` | Yes | Client IP address | N/A |
| `details` | `string \| null` | No | Event metadata string | **Must mask email addresses (`u***@domain.com`)** |
| `timestamp` | `string` | Yes | ISO 8601 UTC timestamp | N/A |
