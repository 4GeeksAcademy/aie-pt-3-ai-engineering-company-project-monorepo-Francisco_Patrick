# UI & API Interface Contracts: Centralized Incident Manager - Frontend

## Frontend Component Interfaces

### 1. IncidentRegistrationForm (`components/incidents/IncidentRegistrationForm.tsx`)
- **Props**:
  - `onSuccess?: (incident: Incident) => void`
- **State**:
  - `formData`: `IncidentCreateInput`
  - `errors`: `IncidentValidationErrors`
  - `isSubmitting`: `boolean`
  - `serverError`: `string | null`
  - `successNotice`: `string | null`

### 2. IncidentListPanel (`components/incidents/IncidentListPanel.tsx`)
- **Props**:
  - `refreshTrigger?: number`
- **State**:
  - `incidents`: `Incident[]`
  - `filters`: `IncidentFilterOptions`
  - `isLoading`: `boolean`
  - `error`: `string | null`
  - `updatingId`: `string | null`

### 3. IncidentSummaryPanel (`components/incidents/IncidentSummaryPanel.tsx`)
- **State**:
  - `summary`: `IncidentSummaryMetrics | null`
  - `isLoading`: `boolean`
  - `error`: `string | null`

---

## API Client Endpoint Expectations (`lib/api/incidents.ts`)

| Action | HTTP Method | Route Endpoint | Payload / Params | Expected Success Response | Error Response |
|--------|-------------|----------------|------------------|---------------------------|----------------|
| Create Incident | `POST` | `/api/incidents` | `IncidentCreateInput` | `201 Created` (`Incident`) | `400 Bad Request` with field error array |
| List Incidents | `GET` | `/api/incidents` | `?status=&origin=&branch=&category=` | `200 OK` (`Incident[]`) | `500 Internal Error` |
| Get Detail | `GET` | `/api/incidents/{id}` | path param `id` | `200 OK` (`Incident`) | `404 Not Found` |
| Update Status | `PATCH` | `/api/incidents/{id}/status` | `{ status: IncidentStatus }` | `200 OK` (`Incident`) | `400 Bad Request` |
| Summary Metrics | `GET` | `/api/incidents/summary` | None | `200 OK` (`IncidentSummaryMetrics`) | `500 Internal Error` |
