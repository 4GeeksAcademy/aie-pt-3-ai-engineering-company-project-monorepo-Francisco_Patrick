/**
 * Enums and TypeScript interfaces for Centralized Incident Manager domain.
 */

export type IncidentStatus = 'open' | 'in_progress' | 'resolved' | 'discarded';

export type IncidentCategory =
  | 'warehouse'
  | 'reverse_logistics'
  | 'last_mile'
  | 'customer_experience';

export type IncidentOrigin = 'customer' | 'branch' | 'internal';

export interface Incident {
  id: string;
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

export interface BranchOption {
  value: string;
  label: string;
}

export const BRANCH_OPTIONS: readonly BranchOption[] = [
  { value: 'central', label: 'Sede Central (Central)' },
  { value: 'madrid', label: 'Madrid' },
  { value: 'barcelona', label: 'Barcelona' },
  { value: 'zaragoza', label: 'Zaragoza' },
  { value: 'sevilla', label: 'Sevilla' },
  { value: 'valencia', label: 'Valencia' },
  { value: 'bilbao', label: 'Bilbao' },
  { value: 'malaga', label: 'Málaga' },
] as const;
