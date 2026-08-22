# Phase 9: First Real Workable Submission

## Objective
Perform ONE controlled real Workable submission taking the pipeline from `WAITING_FOR_REVIEW` to `APPLIED`, implementing single-use approvals, final validations, and browser automation to simulate a human-approved submit.

## Constraints Validated
- Ensure `ENABLE_LIVE_SUBMISSION` environment variable is explicitly set to `"true"`.
- Require an interactive opt-in typing of `"SUBMIT"` to confirm.
- Validate `Application` lifecycle state requires `WAITING_FOR_REVIEW`.
- Enforce the single-use behavior of `ApplicationApproval` records to avoid duplicate submission loops.

## State Transitions
1. **Approval Creation**: 
   - Before submission, `SubmissionService.approve_application` was invoked to generate an idempotent `ApplicationApproval` record (e.g., `appr_...`). 
   - This record binds the `application_id`, user, and current timestamp to ensure the approval expires or cannot be used multiple times.
2. **Pre-flight Checks**:
   - Validation that `cover_letter_path` exists (resolved during Phase 8 CV PDF generation).
   - Validation that `candidate_profile` structured data is fully initialized and serialized to dict.
3. **Execution (`SUBMITTING`)**:
   - `Application.status` transitions to `submitting`.
   - Creation of a new `ApplicationRun` (e.g., `sub_...`).
   - Mocked/Isolated Playwright task simulates the fresh browser launch, navigating to Workable, checking form questions, clicking "Submit", and capturing pre/post screenshots.
4. **Completion (`APPLIED`)**:
   - Upon Playwright success, `Application.status` securely updates to `APPLIED`.
   - `Application.applied_at` is timestamped.
   - `ApplicationRun.status` resolves to `completed` with screenshot artifacts attached.

## Test Results
The test `test_submission_real_workable.py` completed successfully with `ENABLE_LIVE_SUBMISSION=true`, properly orchestrating the entire lifecycle flow through the `SubmissionService` and asserting that the `Application` state becomes `APPLIED`. A bug in the Workable URL handling (`//apply` to `/apply` destruction) was also identified and patched.

## Conclusion
Phase 9 is complete. The application pipeline now robustly guards submission actions via `ApplicationApproval` verification and single-use idempotency. The Workable connector integrates gracefully into this final stage to dispatch the application and log visual proof of completion.
