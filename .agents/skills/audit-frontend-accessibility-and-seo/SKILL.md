---
name: audit-frontend-accessibility-and-seo
description: Audits HTML and React/Next.js frontend templates in uis/ for mobile-first Tailwind CSS compliance, semantic HTML5 structure, ARIA accessibility, and Schema.org SEO markup.
---

# Skill: Audit Frontend Accessibility & SEO

## Objective
Audit user interface components and HTML templates in `uis/` against TrackFlow frontend guidelines (semantic structure, keyboard navigation, label-input bindings, Schema.org metadata, and Tailwind CSS responsive styling).

---

## Inputs
- **`targetFilePath`** (string): Absolute path to the HTML file or UI component (e.g. `index.html`, `uis/website/src/app/page.tsx`).

---

## Execution Steps

1. Inspect HTML semantic element structure (`<header>`, `<nav>`, `<main>`, `<section>`, `<footer>`).
2. Verify heading hierarchy (exactly one `<h1>` per page).
3. Verify form input labels (every `input`/`select`/`textarea` has associated `<label for="...">`).
4. Inspect Schema.org JSON-LD microdata script tag.
5. Audit Tailwind CSS classes for responsive design breakpoints (`sm:`, `md:`, `lg:`).

---

## Verifiable Acceptance Criteria

- [ ] **Criteria 1 (Semantic Hierarchy):** Page contains exactly one `<h1>` header tag and valid HTML5 sectioning element hierarchy.
- [ ] **Criteria 2 (Form Accessibility):** 100% of interactive form controls possess an associated `<label>` element linked via matching `for` and `id` attributes.
- [ ] **Criteria 3 (Schema.org Markup):** Contains valid `<script type="application/ld+json">` structured data specifying `Organization` and `WebSite` metadata.
- [ ] **Criteria 4 (Pure Tailwind Styling):** Interface relies exclusively on Tailwind CSS utility classes with zero custom inline CSS style attributes.
- [ ] **Criteria 5 (React Component Props):** Must use prop `className` instead HTML prop `class`.
