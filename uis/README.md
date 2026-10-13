# TrackFlow User Interfaces (`/uis`)

This directory contains the user interface applications for TrackFlow.

## Applications Overview

| Application | Path | Type | Purpose | Target Audience |
| --- | --- | --- | --- | --- |
| **Corporate Website** | `./website` | Next.js (App Router) + TypeScript | Public corporate website, logistics overview, value proposition, and intake form | External e-commerce brands, prospective clients |
| **Internal Backoffice** | `./backoffice` | Next.js (App Router) + TypeScript | Operations dashboard, hub status monitoring, and interactive execution suite for core business logic (`src/utils`) | Internal warehouse managers, logisticians, account leads |

## Setup & Running Locally

### 1. Corporate Website (`./uis/website`)
```bash
cd uis/website
npm install
npm run dev
```

### 2. Internal Backoffice (`./uis/backoffice`)
```bash
cd uis/backoffice
npm install
npm run dev
```

## TypeScript & Build Validation

```bash
# Typecheck monorepo domain logic
npm run typecheck

# Build individual applications
cd uis/website && npm run build
cd ../backoffice && npm run build
```
