# Phase 1: Quickstart Validation Guide

## Setup
Ensure the local Next.js development server is running for the `uis/backoffice` application (`npm run dev`).
Ensure the backend API services are available and running.

## Run Validation

### Scenario 1: Unauthenticated Access
1. Open an incognito browser window.
2. Navigate to a protected route (e.g., `http://localhost:3000/account/profile` or the backoffice root).
3. **Expected**: The application immediately redirects you to `/login`.
4. Navigate to the public website (`uis/website/`).
5. **Expected**: The page loads normally without redirection.

### Scenario 2: Login and Protected Route Access
1. On the `/login` page, enter valid test credentials and submit.
2. **Expected**: You are redirected to the main authenticated view.
3. Open browser developer tools -> Application -> Local Storage.
4. **Expected**: A valid JWT token is present.

### Scenario 3: Profile Update
1. Navigate to `/account/profile`.
2. **Expected**: Your current profile data is displayed (fetched via `GET /auth/me`).
3. Edit the name and phone fields, then submit.
4. **Expected**: The UI indicates success, and refreshing the page shows the updated data.

### Scenario 4: Logout
1. Click the "Logout" button.
2. **Expected**: You are redirected to `/login`, and the token is removed from `localStorage`.
