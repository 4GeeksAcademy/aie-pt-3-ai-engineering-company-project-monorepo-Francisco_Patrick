# incident-analyzer-script-and-control-panel

## Phase 1: Analysis script (`/scripts`)
- [ ] Create the main script (analyze.py) that accepts the path to the CSV as a command-line argument: python analyze.py incidents-COMPANY.csv.
- [ ] The script must load and read the file (with native reading or pandas — your choice).
- [ ] Detect and count invalid records. Detail how many there are and why (missing field, out-of-range value, etc.).
- [ ] Calculate the following metrics on valid records:
  - [ ] Total number of elements processed (valid and invalid separately).
  - [ ] Breakdown by incident category.
  - [ ] Breakdown by status (open, closed, discarded — or their equivalents in your CONTEXT).
  - [ ] Average satisfaction index for closed cases that have a recorded score.
- [ ] Print the summary to the console in a readable format: use separators, clear labels, and alignment.
- [ ] At the end of execution, ask the user: Export results to CSV? [y / n]. If they choose y, save the results to results.csv (one row per metric).
- [ ] Verify that the results match exactly the expected values in your CONTEXT.

## Phase 2: Integration into the platform
Once the script logic is validated, extract that same logic into reusable services and integrate it into the system.

### Backend (`/services/api`)
- [ ] Create a POST /api/incidents/analyze endpoint that accepts a CSV file as multipart/form-data.
- [ ] The endpoint must run the same validation and analysis logic as the script and return the summary as JSON.
- [ ] Create a GET /api/incidents/results/export endpoint that returns the last analysis as a downloadable CSV.
- [ ] Errors (empty file, incorrect format) must return appropriate HTTP responses with a descriptive message.

### Frontend (`/uis/backoffice`)
- [ ] Create an incident analysis page accessible from the application menu.
- [ ] Include a file upload component (drag & drop or file selector) that sends the CSV to the API endpoint.
- [ ] Display the results summary on screen: general metrics, category breakdown, status breakdown, and satisfaction index.
- [ ] Include a button to download the results as CSV.
- [ ] Inform the user if the file contains invalid records and how many of each type.

## Acceptance Criteria
### Script
- [ ] Accepts the CSV path as a command-line argument and works without modifying the code.
- [ ] Detects, classifies, and shows invalid records with their type of problem.
- [ ] All five required metrics appear in the console output with a readable format.
- [ ] CSV export works and produces a well-structured file.
- [ ] Results match exactly the expected values in the CONTEXT.

### Backend
- [ ] The analysis endpoint accepts the CSV, processes it, and returns the summary as JSON.
- [ ] The export endpoint returns a correctly formatted downloadable CSV.
- [ ] Input errors return appropriate HTTP status codes.

### Frontend
- [ ] The file can be uploaded from the interface without using the terminal.
- [ ] The summary is displayed on screen in a clear and interpretable way.
- [ ] The export button downloads the results CSV.
- [ ] Invalid records are communicated to the user in an understandable way.

### Cross-cutting
- [ ] The analysis and validation logic is the same in the script and the API — not duplicated but extracted into shared functions or modules.
- [ ] Code is organised according to the monorepo folder structure.