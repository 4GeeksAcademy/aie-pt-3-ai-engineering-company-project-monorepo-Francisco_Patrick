# Functional and Technical Specification (`SPEC.md`)

This specification outlines the technical architecture, project structure, component hierarchy, and data requirements for the Candidate Management System based on the Next.js App Router, TypeScript, and native React state primitives.

---

## 1. Executive Overview & Company Context Adaptation

Per company guidelines (`CONTEXT.md`), all user-facing terminology, empty states, headings, and notification messaging must match the internal tool identity.

* **System Identity:** TrackFlow Talent Gateway / Internal ATS
* **Target Scope:** Internal HR & Recruiting Operations
* **Data Source Integration:** RESTful API endpoints at `/records` with domain-specific UI mapping (e.g., mapping raw `status` and `stage` backend values into TrackFlow brand terminology).

---

## 2. Technical Stack & Constraints

* **Framework:** Next.js (App Router)
* **Language:** TypeScript (Strict mode enabled)
* **Styling:** Native CSS Modules or Tailwind CSS
* **State Management:** Native React Hooks (`useState`, `useTransition`, `useOptimistic`, `useContext` where appropriate). **No external state libraries allowed.**
* **Data Fetching:** Native `fetch` with `async/await` wrapped inside dedicated service modules.

---

## 3. Project Architecture & Directory Structure

```text
uis/talent-pipeline-tracker/
├── app/
│   ├── layout.tsx                  # Global layout (TrackFlow Navbar & Shell)
│   ├── page.tsx                    # Candidate List Page (/)
│   ├── candidates/
│   │   ├── new/
│   │   │   └── page.tsx            # Candidate Registration Form (/candidates/new)
│   │   └── [id]/
│   │       ├── page.tsx            # Candidate Detail Page (/candidates/[id])
│   │       └── edit/
│   │           └── page.tsx        # Candidate Edit Form (/candidates/[id]/edit)
├── components/
│   ├── ui/                         # Base design tokens (Button, Input, Badge, Toast, Loader)
│   ├── candidates/
│   │   ├── CandidateTable.tsx      # Core list view component
│   │   ├── CandidateFilters.tsx    # Search bar & status/stage select dropdowns
│   │   ├── CandidateCard.tsx       # Summary item view
│   │   ├── CandidateForm.tsx       # Shared form component for POST / PUT
│   │   ├── StatusStageControl.tsx  # Interactive PATCH controls
│   │   └── NotesSection.tsx        # Notes list, add form, and deletion actions
│   └── layout/
│       ├── Header.tsx              # TrackFlow header & quick stats
│       └── Navigation.tsx          # Router links
├── hooks/
│   ├── useCandidates.ts            # Hook for list fetching, filtering & search logic
│   ├── useCandidateDetail.ts       # Hook for single candidate retrieval & mutations
│   └── useNotes.ts                 # Hook for async notes handling (GET, POST, DELETE)
├── services/
│   └── api.ts                      # Isolated async API layer handling HTTP verbs
├── types/
│   └── candidate.ts                # TypeScript interfaces and backend payloads
└── lib/
    └── utils.ts                    # Helper functions (query param stringifiers, formatters)

```

---

## 4. TypeScript Domain Specifications (`types/candidate.ts`)

```typescript
export type CandidateStatus = 'active' | 'on_hold' | 'rejected' | 'hired';
export type CandidateStage = 'applied' | 'screening' | 'interview' | 'offer' | 'hired';

export interface Candidate {
  id: string;
  name: string;
  email: string;
  phone: string;
  position: string;
  linkedIn: string;
  cvLink: string;
  yearsOfExperience: number;
  status: CandidateStatus;
  stage: CandidateStage;
  appliedDate: string; // ISO date string
}

export interface CandidateNote {
  id: string;
  candidateId: string;
  content: string;
  createdAt: string;
  author?: string;
}

export type CreateCandidateDTO = Omit<Candidate, 'id' | 'appliedDate'>;
export type UpdateCandidateDTO = Partial<CreateCandidateDTO>;
export type PatchCandidateStatusDTO = Pick<Candidate, 'status' | 'stage'>;

export interface AsyncState<T> {
  data: T | null;
  loading: boolean;
  error: string | null;
}

```

---

## 5. API Layer Design (`services/api.ts`)

All API calls wrap native `fetch` requests with explicit `async/await` and standardized error handling.

| Operation | Method | Endpoint | Request Body | Description |
| --- | --- | --- | --- | --- |
| **List Candidates** | `GET` | `/records` | N/A | Fetches candidate collection |
| **Get Candidate** | `GET` | `/records/:id` | N/A | Fetches detailed candidate record |
| **Create Candidate** | `POST` | `/records` | `CreateCandidateDTO` | Registers a new candidate |
| **Update Candidate** | `PUT` | `/records/:id` | `UpdateCandidateDTO` | Full update of candidate profile |
| **Patch Status/Stage** | `PATCH` | `/records/:id` | `PatchCandidateStatusDTO` | Inline update for status or stage |
| **Fetch Notes** | `GET` | `/records/:id/notes` | N/A | Retrieves notes for candidate |
| **Add Note** | `POST` | `/records/:id/notes` | `{ content: string }` | Attaches a note |
| **Delete Note** | `DELETE` | `/records/:id/notes/:note_id` | N/A | Removes a note |

---

## 6. Route & Component Breakdown

### 6.1 Candidate List View (`/`)

* **Query State Integration:** Uses `useSearchParams` and `useRouter` from `next/navigation` to read and push URL parameters (`?status=...&stage=...`).
* **Search Engine:** Client-side input filter matching `name` or `email` dynamically without causing full document reloads.
* **States Covered:**
* `Loading`: TrackFlow skeleton UI placeholders.
* `Error`: Visual alert displaying error details with a retry action.
* `Success`: Interactive data table featuring candidate details, current stage badges, and action shortcuts.



### 6.2 Candidate Detail View (`/candidates/[id]`)

* **Data Aggregation:** Parallel async resolution of candidate metadata (`GET /records/:id`) and activity history (`GET /records/:id/notes`).
* **Interactive Controls:**
* **Quick-Action Status/Stage Mutators:** Dropdowns triggering `PATCH /records/:id`. Updates state locally upon receipt of a 200 response code.
* **Notes Subsystem:** Integrated form and list with immediate deletion confirmation via UI triggers.



### 6.3 Candidate Form Modules (`/candidates/new` & `/candidates/[id]/edit`)

* **Form Validation Engine:** Native client-side validation asserting mandatory input parameters before network dispatch.
* *Required Fields:* Full Name, Email, Position, Status, Stage, Years of Experience.


* **Async Post-Submission Pipeline:**
* `POST /records` -> Redirects to `/` on success with a confirmation toast.
* `PUT /records/:id` -> Updates view and redirects back to `/candidates/[id]` upon resolution.



---

## 7. State Management & Lifecycle Guidelines

Every asynchronous interaction must enforce the 3-state UI lifecycle:

```
[ Idle / Initial ] ──> [ Pending / Loading ] ┬──> [ Success State (UI Refreshed) ]
                                             └──> [ Error State (Feedback Alert) ]

```

1. **No Full Reloads:** Navigations leverage Next.js `<Link>` components or programmatic `router.push()`.
2. **Immediate UI Reconciliation:** Data modification triggers (PATCH, PUT, POST, DELETE) immediately refresh localized state or re-fetch active dynamic segments seamlessly.
3. **Local State Scope:** Component state handles input buffers, status updates, and temporary UI state cleanly without prop-drilling or external stores.