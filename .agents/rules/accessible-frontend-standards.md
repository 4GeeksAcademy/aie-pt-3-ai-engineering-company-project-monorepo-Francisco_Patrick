# Accessible, Mobile-First & Semantic Frontend Standards

## Scope Definition
- **Scope Type:** `File-Pattern Based`
- **Target File Patterns:** `uis/**/*`, `*.html`

---

## Behavioral Guardrails & Requirements

1. **Responsive Mobile-First Styling:**
   - Develop interfaces using Tailwind CSS with mobile-first breakpoints (`sm:`, `md:`, `lg:`).
   - Ensure components adapt fluidly across mobile, tablet, and desktop viewports.

2. **Semantic HTML5 Structure:**
   - Use native semantic HTML elements (`<header>`, `<nav>`, `<main>`, `<section>`, `<article>`, `<aside>`, `<footer>`) instead of unsemantic `<div>` wrapping.
   - Every page must contain a single `<h1>` tag followed by a logical heading hierarchy (`<h2>`, `<h3>`).

3. **Accessibility & Keyboard Navigation (ARIA):**
   - Ensure all interactive elements (buttons, links, form inputs) are fully focusable and navigable via keyboard (`Tab` / `Enter` / `Space`).
   - Every input element must have a corresponding `<label>` element correctly associated via `for`/`id`.
   - Maintain color contrast ratios compliant with WCAG AA standards.
   - Include Schema.org structured JSON-LD / HTML microdata for organization and webpage metadata.
