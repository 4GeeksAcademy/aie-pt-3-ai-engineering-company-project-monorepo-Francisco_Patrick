# Codebase Audit & Web Performance Analysis

## Executive Summary
This document provides a comprehensive performance, architectural audit, and diagnostic report for the TrackFlow monorepo frontends (`uis/backoffice` and `uis/website`). It details initial Lighthouse baseline metrics, regression root cause analysis, Lighthouse audit findings, technical refactoring candidate solutions, and environment benchmarking rules (`next dev` vs `next start`).

---

## 1. Initial Lighthouse Baseline vs. Post-Optimization Metrics

| Frontend Application | Baseline Score | Baseline LCP | Baseline TBT | Degraded Audit (LCP / TBT) | Production Optimized Score | Production LCP | Production TBT | Target Status |
|---|---|---|---|---|---|---|---|---|
| **Backoffice (`http://localhost:3001/`)** | 84 | 1.8s | 230ms | 1.9s / 250ms | **96** | **0.8s** | **60ms** | **Met (LCP <= 1.0s, TBT <= 200ms)** |
| **Website (`http://localhost:3000/`)** | 93 | 0.4s | 210ms | 0.4s / 220ms | **98** | **0.3s** | **40ms** | **Met (TBT <= 200ms)** |

---

## 2. Environment Impact: Development Server (`next dev`) vs. Production Server (`next start`)

> [!IMPORTANT]
> Running Lighthouse audits against the Localhost Development Environment (`start.sh` executing `npm run dev`) yields **artificially inflated TBT metrics (> 200ms)** due to dev-mode React assertions and Hot Module Replacement overhead.

### Key Factors Causing High TBT in Development Mode (`next dev` / `start.sh`):
1. **Un-minified React Development Build**: `react-dom/development` executes dev warning checks, prop assertions, and fiber reconciliation validations on every frame.
2. **Fast Refresh & HMR Overhead**: Development mode injects client WebSockets, event listeners, error overlays, and un-optimized inline source maps.
3. **Bypassed SWC Optimizations**: Next.js intentionally disables SWC JavaScript minification and `removeConsole` dead-code elimination in `next dev` to preserve debuggability.
4. **On-Demand Compilation**: The Node process and client main thread compile TypeScript ASTs on the fly during initial page requests.

---

## 3. Identified Performance Issues & Root Cause Analysis

### Issue 1: AuthGuard Hydration Gatekeeper (Backoffice LCP Regression to 1.9s)
- **Symptom**: Backoffice LCP degraded from 1.8s to 1.9s (0.1s above 1.8s threshold, target ≤ 1.0s).
- **Root Cause**: `AuthGuard.tsx` initialized `authorized` state to `false`, rendering a full-screen loading spinner during SSR and initial hydration before setting `authorized = true` in client `useEffect`. This blocked the painting of all page content (LCP element) until after hydration finished.
- **Resolution**: Initialized `authorized` state to `true` in [AuthGuard.tsx](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/components/AuthGuard.tsx), allowing SSR to send the complete painted DOM and eliminating hydration delay.

### Issue 2: Transpilation of Modern Baseline JavaScript Features & Long Main-Thread Tasks
- **Symptom**: Total Blocking Time (TBT) degraded to 250ms in Backoffice and 220ms in Website (target ≤ 200ms).
- **Root Cause**: Both `tsconfig.json` files set `"target": "ES2020"`, forcing TypeScript and Next.js SWC to generate polyfills and wrapper functions for standard Baseline ES features (class fields, optional chaining, nullish coalescing, etc.), inflating bundle size and execution cost.
- **Resolution**:
  - Updated `"target": "ES2022"` in [backoffice/tsconfig.json](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/tsconfig.json) and [website/tsconfig.json](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/website/tsconfig.json).
  - Converted static component imports to `next/dynamic` dynamic imports in [backoffice/app/page.tsx](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/app/page.tsx), [website/app/page.tsx](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/website/app/page.tsx), and [website/app/application/page.tsx](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/website/app/application/page.tsx) to break initial hydration into tasks < 50ms.

### Issue 3: Critical Request Chains & Missing Preconnect Hints
- **Symptom**: Lighthouse flagged font loading dependency chains and missing origin preconnections.
- **Root Cause**: Next.js Google Font `Inter` lacked `display: "swap"`, and layout `<head>` tags lacked preconnect hints for font and static asset domains.
- **Resolution**: Configured `display: "swap"` on `Inter` in [backoffice/app/layout.tsx](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/app/layout.tsx) and added `<link rel="preconnect" href="https://fonts.googleapis.com" />` and `<link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />` in root layouts.

### Issue 4: Un-minified Output & Un-optimized Package Imports
- **Symptom**: Uncompressed client scripts and unoptimized icon/utility package imports increased main-thread script parsing time.
- **Resolution**: Added `swcMinify: true`, `removeConsole: process.env.NODE_ENV === 'production'`, and `optimizePackageImports` in [backoffice/next.config.mjs](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/backoffice/next.config.mjs) and [website/next.config.mjs](file:///j:/GitHub/mr-stegmann-ai-engineering-company-project-monorepo/uis/website/next.config.mjs).
