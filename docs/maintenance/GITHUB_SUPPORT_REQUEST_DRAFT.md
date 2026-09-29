# Draft GitHub Support Request for Cache Invalidation

**To:** GitHub Support (via https://support.github.com/contact/privacy)
**Subject:** Urgent: Request to purge cached blobs containing personal identifiable information (PII)

Hello GitHub Support Team,

I am writing to request the urgent purging of specific cached objects in my repository network that contain sensitive Personally Identifiable Information (PII), specifically resumes/CVs.

**Repository:** `SaedAlsafadi/SA-Job-Orchestrator`

I have already successfully used `git-filter-repo` to rewrite the repository history and force-pushed the cleaned history. The sensitive commits are no longer reachable from any branch or tag. However, the raw object blobs remain accessible via direct URL due to GitHub's server-side caching.

Could you please run a garbage collection and purge the following orphaned objects from the repository cache?

**Affected Commit Hashes (now orphaned):**
- `d84ba0ceebfeaa6878b66cf17fbb8582d1c6df37`
- `[Any other old commits identified in the audit]`

**Examples of Cached Raw Blob URLs that need to be invalidated:**
- `https://raw.githubusercontent.com/SaedAlsafadi/SA-Job-Orchestrator/d84ba0ceebfeaa6878b66cf17fbb8582d1c6df37/backend/data/storage/users/testuser0000000000000000000000aa/uploads/59743746f0834b44a3c56d7fe6c1ed83.pdf`
- `https://raw.githubusercontent.com/SaedAlsafadi/SA-Job-Orchestrator/d84ba0ceebfeaa6878b66cf17fbb8582d1c6df37/backend/data/storage/users/testuser0000000000000000000000aa/uploads/c7354420b04840a3839348ec535df8b8.docx`

These files contain real candidate resumes (both mine and others) and must not remain accessible.

Thank you for your prompt assistance in resolving this privacy concern.

Best regards,
Saed Alsafadi
