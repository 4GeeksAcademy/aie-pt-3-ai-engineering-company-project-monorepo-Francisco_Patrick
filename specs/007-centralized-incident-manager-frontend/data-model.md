# Data Model: Centralized Incident Manager - Frontend

## Entities & Interfaces

### Incident Model (`packages/shared/types/incidents.ts`)

```typescript
export type IncidentStatus = 'open' | 'in_progress' | 'resolved' | 'discarded';

export type IncidentCategory =
  | 'warehouse'
  | 'reverse_logistics'
  | 'last_mile'
  | 'customer_experience';

export type IncidentOrigin = 'customer' | 'branch' | 'internal';

export interface Incident {
  id: str;
  title: string;
  description: string;
  category: IncidentCategory;
  status: IncidentStatus;
  origin: IncidentOrigin;
  branch: string;
  created_at: string;
  updated_at: string;
  legacy_id?: string;
}

export interface IncidentCreateInput {
  title: string;
  description: string;
  category: IncidentCategory;
  status?: IncidentStatus;
  origin?: IncidentOrigin;
  branch: string;
}

export interface IncidentFilterOptions {
  status?: string;
  origin?: string;
  branch?: string;
  category?: string;
}

export interface IncidentSummaryMetrics {
  total_incidents: number;
  by_status: Record<IncidentStatus, number>;
  by_category: Record<IncidentCategory, number>;
  by_origin: Record<IncidentOrigin, number>;
  by_branch: Record<string, number>;
}
```

### Form Validation Model (`packages/shared/validation/incidents.ts`)

```typescript
export interface IncidentValidationErrors {
  title?: string;
  description?: string;
  category?: string;
  status?: string;
  origin?: string;
  branch?: string;
  general?: string;
}
```

### State Transitions & Status Lifecycle Rules

- `open` -> `in_progress` | `discarded`
- `in_progress` -> `resolved` | `discarded`
- `resolved` -> (terminal state - invalid transition)
- `discarded` -> (terminal state - invalid transition)
