import type { Job } from '@/types/job';
import type { Application } from '@/types/application';

export type CtaAction = 'analyze' | 'tailor' | 'continue_tailoring' | 'prepare' | 'continue_preparation' | 'review' | 'view' | 'retry' | 'processing';

export interface OpportunityCta {
  label: string;
  action: CtaAction;
  disabled: boolean;
  hint?: string;
}

/** Resolve exactly one next workflow action from backend related-record state. */
export function resolveOpportunityCta(job: Job, legacyApplication?: Application | null): OpportunityCta {
  const state = job.operational_state ?? {
    match_exists: job.match_score != null,
    tailoring_session_id: null,
    tailoring_status: null,
    tailored_resume_id: null,
    tailored_resume_verified: false,
    application_id: legacyApplication?.id ?? null,
    application_status: legacyApplication?.status ?? null,
    package_id: null,
    package_version: null,
    package_ready: false,
    package_approved: false,
    route_type: null,
    route_url: null,
  };
  if (['received', 'processing'].includes(job.status)) return { label: 'Processing…', action: 'processing', disabled: true, hint: 'Job information is still being processed' };
  if (job.status === 'failed' || state.application_status === 'failed') return { label: 'Retry', action: 'retry', disabled: false };
  if (['applied', 'interview', 'offer', 'rejected', 'withdrawn'].includes(state.application_status ?? '')) return { label: 'View Application', action: 'view', disabled: false };
  if (state.package_approved) {
    if (state.route_type === 'EMAIL') return { label: 'Review Email', action: 'review', disabled: false };
    if (state.route_type && ['WORKABLE', 'GREENHOUSE', 'LEVER', 'COMPANY_WEBSITE', 'LINKEDIN'].includes(state.route_type)) return { label: 'Open Application Page', action: 'review', disabled: false };
    return { label: 'Continue Application', action: 'review', disabled: false };
  }
  if (state.package_id) return state.package_ready
    ? { label: 'Review Application', action: 'review', disabled: false }
    : { label: 'Continue Preparation', action: 'continue_preparation', disabled: false };
  if (state.application_id) return { label: 'Continue Preparation', action: 'continue_preparation', disabled: false };
  if (state.tailoring_session_id && !['failed', 'verified'].includes(state.tailoring_status ?? '')) return { label: 'Continue Tailoring', action: 'continue_tailoring', disabled: false };
  if (state.tailored_resume_verified) return { label: 'Prepare Application', action: 'prepare', disabled: false };
  if (state.match_exists) return { label: 'Tailor CV', action: 'tailor', disabled: false };
  return { label: 'Analyze Match', action: 'analyze', disabled: false };
}
