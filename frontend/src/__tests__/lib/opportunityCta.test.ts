import { describe, expect, it } from 'vitest';
import { resolveOpportunityCta } from '@/lib/opportunityCta';
import type { Job, OpportunityOperationalState } from '@/types/job';

const state = (overrides: Partial<OpportunityOperationalState> = {}): OpportunityOperationalState => ({
  match_exists: false, tailoring_session_id: null, tailoring_status: null,
  tailored_resume_id: null, tailored_resume_verified: false,
  application_id: null, application_status: null, package_id: null,
  package_version: null, package_ready: false, package_approved: false,
  route_type: null, route_url: null, ...overrides,
});

const job = (overrides: Partial<Job> = {}): Job => ({
  id: 'job-1', platform: 'linkedin', platform_job_id: 'p1', title: 'Engineer',
  company: 'ACME', location: 'Remote', url: 'https://example.com', description: '',
  salary_range: null, job_type: null, remote: true, posted_date: null,
  experience_level: null, match_score: null, skills_required: null, status: 'ready',
  created_at: '', updated_at: '', operational_state: state(), ...overrides,
});

describe('resolveOpportunityCta operational lifecycle', () => {
  it.each([
    [job({ status: 'processing', operational_state: state({ match_exists: true, tailored_resume_verified: true }) }), 'Processing…', true],
    [job({ status: 'failed' }), 'Retry', false],
    [job(), 'Analyze Match', false],
    [job({ operational_state: state({ match_exists: true }) }), 'Tailor CV', false],
    [job({ operational_state: state({ match_exists: true, tailoring_session_id: 's1', tailoring_status: 'reviewing' }) }), 'Continue Tailoring', false],
    [job({ operational_state: state({ match_exists: true, tailoring_session_id: 's1', tailoring_status: 'reviewing', tailored_resume_verified: true }) }), 'Continue Tailoring', false],
    [job({ operational_state: state({ match_exists: true, tailored_resume_id: 'r1', tailored_resume_verified: true }) }), 'Prepare Application', false],
    [job({ operational_state: state({ application_id: 'a1', application_status: 'preparing' }) }), 'Continue Preparation', false],
    [job({ operational_state: state({ application_id: 'a1', package_id: 'p1', package_ready: true }) }), 'Review Application', false],
    [job({ operational_state: state({ application_id: 'a1', package_id: 'p1', package_ready: true, package_approved: true, route_type: 'EMAIL' }) }), 'Review Email', false],
    [job({ operational_state: state({ application_id: 'a1', package_id: 'p1', package_ready: true, package_approved: true, route_type: 'GREENHOUSE' }) }), 'Open Application Page', false],
    [job({ operational_state: state({ application_id: 'a1', application_status: 'applied' }) }), 'View Application', false],
  ])('maps backend state to one primary action', (record, label, disabled) => {
    expect(resolveOpportunityCta(record)).toEqual(expect.objectContaining({ label, disabled }));
  });

  it('never exposes a future Prepare action next to Tailor CV', () => {
    const cta = resolveOpportunityCta(job({ operational_state: state({ match_exists: true }) }));
    expect(cta.label).toBe('Tailor CV');
    expect(Object.keys(cta)).not.toContain('secondary');
  });
});
