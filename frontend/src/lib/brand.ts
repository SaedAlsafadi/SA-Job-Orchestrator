/**
 * Centralized brand configuration for SA Job Orchestrator.
 *
 * This is the ONLY place product identity strings are defined.
 * Import from here instead of hard-coding brand text in components.
 *
 * NOTE: This is a temporary internal identity. Do not treat as a permanent
 * commercial brand name. Replace with a final brand decision when ready.
 */

export const BRAND = {
  /** Full product name shown in headers, auth, and landing pages. */
  name: 'SA Job Orchestrator',
  /** Short form for compact contexts. */
  shortName: 'SAJ',
  /** Tagline shown under the logo in the sidebar (compact). */
  tagline: 'Career Operations Platform',
  /** Icon name for the logo mark (from the Icon component). */
  logoIcon: 'cpu' as const,
  /** Document/tab title. */
  pageTitle: 'SA Job Orchestrator',
  /** Auth subtitle on login page. */
  authSubtitle: 'Sign in to your career workspace.',
  /** Register page subtitle. */
  registerSubtitle: 'Start your career operations in minutes.',
} as const;
