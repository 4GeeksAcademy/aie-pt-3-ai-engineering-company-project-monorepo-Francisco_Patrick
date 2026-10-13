# Phase 0: Research

## Decisions

### Client-side Route Protection
- **Decision**: Use a custom React client component (`AuthGuard`) or a layout hook to protect routes client-side.
- **Rationale**: The JWT token is stored in `localStorage`, which is not accessible during Server-Side Rendering (SSR) or in Next.js Middleware. Client-side checks via `useEffect` are required.
- **Alternatives considered**: Next.js Middleware with cookies (rejected because requirements explicitly stated `localStorage`).

### API Call Authentication
- **Decision**: Use a centralized `fetch` wrapper or API utility to attach the `Authorization: Bearer <token>` header to all outgoing protected API requests. Also handle `401` responses globally to trigger logout and redirection.
- **Rationale**: Prevents code duplication and ensures all protected calls consistently attach the token and handle expiration.
- **Alternatives considered**: Manually adding the header and error handling to every API call (rejected due to maintainability issues).
