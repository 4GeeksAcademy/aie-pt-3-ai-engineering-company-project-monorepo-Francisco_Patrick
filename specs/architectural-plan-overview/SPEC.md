# Backend Architectural Plan Overview
## Context / Goal
As a software architect, I want to analyze the project to select the best backend architectura pattern for this monorepo project.

## Tasks
 * [x] Create the ARCHITECTURE_PROPOSAL.md file inside your transversal project's /docs directory
 * [x] In the document, identify and justify the most suitable architectural pattern for your company (MVC, layered architecture, serverless, or other). The justification must be tied to your company's real characteristics, not to a generic preference
 * [x] Propose and describe the folder and module structure of the backend project, explaining the domain or responsibility separation criteria used
 * [x] Include a section on how you would organize FastAPI endpoints and routers according to the identified domains. No code is needed: just describe what routes would exist and under what grouping criteria
 * [x] Research how FastAPI projects are typically structured (folder conventions, router separation, models, and configuration) and document in the proposal how that standard structure influences your decisions
 * [x] Research how applications are organized when frontend and backend are separate systems (repo separation or monorepo, API communication, environment variables, CORS) and reflect those considerations in the document
 * [x] Include a risks and points of attention section with at least two considerations about what could go wrong if the team doesn't follow the proposed structure

## Acceptance Criteria
 * [x] The chosen architectural pattern is justified with arguments linked to the nature of the business and the system, not by generic preference
 * [x] The proposed folder structure is consistent with the chosen pattern and reflects a clear separation of responsibilities or domains
 * [x] The router and endpoint organization is recognizable as a valid FastAPI application (routes grouped by domain, not all in a single file)
 * [x] The documented technical decisions are concrete, justified, and do not contradict course content
 * [x] The proposal reflects actual research into the standard structure of FastAPI projects: the identified conventions are present in the proposed structure and their source is explicitly mentioned
 * [x] The document addresses how frontend and backend coexist as separate systems: at minimum, the implications for API communication and CORS or environment variable management are identified