# Data Model Specification: Centralized Incident Manager - Part I

## 1. Incident Entity Schema

| Field Name | Type | Required | Allowed Values / Constraints | Description |
| :--- | :--- | :---: | :--- | :--- |
| `id` | String | Yes | Unique system ID (e.g. `inc_...`) | Automatically generated unique identifier. |
| `title` | String | Yes | Non-empty string | Brief incident summary (mapped from CSV `description`). |
| `description` | String | Yes | Non-empty string | Detailed incident description. |
| `category` | Enum | Yes | `warehouse`, `reverse_logistics`, `last_mile`, `customer_experience` | Operational category. |
| `status` | Enum | Yes | `open`, `in_progress`, `resolved`, `discarded` | Incident lifecycle state. |
| `origin` | Enum | Yes | `customer`, `branch`, `internal` | Source of the report (`customer` for historical seeds). |
| `branch` | String | Yes | Non-empty string (default: `central`) | Managing branch identifier. |
| `created_at` | Datetime (ISO-8601) | Yes | Valid ISO timestamp | Creation timestamp, generated automatically. |
| `updated_at` | Datetime (ISO-8601) | Yes | Valid ISO timestamp | Last modification timestamp, updated automatically. |
| `legacy_id` | String | No | Unique string per seed record | Original CSV record ID (used for seed idempotency). |

---

## 2. Legacy CSV to Incident Model Transformation Matrix

| Legacy CSV Field | Target Incident Field | Transformation Rule |
| :--- | :--- | :--- |
| `id` | `legacy_id` | Preserved for idempotency checks; new `id` generated. |
| `description` | `title` | Used as primary title text. |
| `description` / details | `description` | Populated from CSV description or detail context. |
| `category` | `category` | Validated against allowed category set (`warehouse`, `reverse_logistics`, `last_mile`, `customer_experience`). |
| `status` | `status` | Mapped: `closed` -> `resolved`, `open` -> `open`, `discarded` -> `discarded`. |
| `date` | `created_at` & `updated_at` | Parsed and converted to ISO-8601 string format. |
| `location` / `branch` | `branch` | Mapped to branch string, or `central` if empty/unspecified. |
| *(N/A)* | `origin` | Hardcoded to `"customer"` for historical CSV seeds. |

---

## 3. Allowed Enum Definitions & Integrity Rules

```text
Allowed Categories:
  - warehouse
  - reverse_logistics
  - last_mile
  - customer_experience

Allowed Lifecycle Statuses:
  - open
  - in_progress
  - resolved
  - discarded

Allowed Origins:
  - customer
  - branch
  - internal
```

---

## 4. Summary Aggregation DTO Structure

```json
{
  "total_incidents": 95,
  "by_status": {
    "open": 30,
    "in_progress": 0,
    "resolved": 60,
    "discarded": 5
  },
  "by_category": {
    "warehouse": 25,
    "reverse_logistics": 20,
    "last_mile": 30,
    "customer_experience": 20
  }
}
```
