# SA Job Orchestrator - Portfolio Walkthrough Script

## Recommended Screens for Screenshots/Demo (Sanitized Data Only)
1. **Dashboard** - Overview of application metrics and recent activity
2. **System State (Health)** - View of system metrics and status checks
3. **Candidate Profile View** - Demonstration of structured candidate data extraction
4. **Match Intelligence View** - Highlighting the multi-factor scoring against a job
5. **CV Tailoring Workbench (Diff)** - Showcasing proposed CV changes (before/after view)
6. **Package Review & Approval** - The final step where a package is bound to a specific hash before submission
7. **Telegram Bot Conversation** - Showing the intake flow from Telegram

## 90-Second Walkthrough Script (Loom / Video Format)

**(Screen 1: Landing / Overview)**
"Hi, I'm Saed. Welcome to a quick walkthrough of SA Job Orchestrator, an AI-assisted job application system I built to demonstrate a modern, full-stack workflow combining AI with human-in-the-loop controls."

**(Screen 2: Dashboard & Telegram Intake)**
"The journey starts with opportunity intake. A user can forward a job posting URL via the Telegram bot or web dashboard. The orchestrator's backend picks this up via Redis queue and triggers a discovery workflow."

**(Screen 3: Candidate Profile & Match Intelligence)**
"Once the job details are extracted, the system runs a multi-dimensional match assessment against the candidate's profile. Here in the Match Intelligence View, you can see the system evaluating skills, market eligibility, and experience—creating a transparent score rather than a black box."

**(Screen 4: CV Tailoring Workbench)**
"If the match is good, the AI proposes CV tailoring. In this Workbench view, every change is discrete and explainable. The user can review the diffs and accept or reject changes. The system prevents hallucinations by grounding every change in factual candidate evidence."

**(Screen 5: Package Review & Application Run)**
"After tailoring, the system generates a final PDF and DOCX package. Crucially, the user must explicitly approve this specific package hash. Once approved, the backend Playwright automation takes over to securely submit the application to the ATS, keeping the user updated via WebSocket events and Telegram notifications."

**(Screen 6: System State / Architecture wrap-up)**
"The backend uses FastAPI and LiteLLM, routing tasks based on complexity. With over 900 automated tests across frontend and backend, this project prioritizes reliability and correctness over blind automation. Feel free to check out the GitHub repository to read through the architecture and implementation details. Thanks for watching."
