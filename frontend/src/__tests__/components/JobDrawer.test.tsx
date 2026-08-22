import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import JobDrawer from '@/components/jobs/JobDrawer';
import type { Job, JobAnalysisResponse } from '@/types/job';

const job = (o: Partial<Job> = {}): Job => ({
  id: 'j1', platform: 'linkedin', platform_job_id: 'ln1', title: 'Senior Product Manager',
  company: 'Northwind Labs', location: 'Remote', url: 'https://example.com/job',
  description: 'Own the roadmap.\n\nDrive outcomes.', salary_range: null, job_type: 'Full-time',
  remote: true, posted_date: null, experience_level: null, match_score: 0.9, skills_required: null,
  status: 'new', created_at: '', updated_at: '', ...o,
});

const analysis: JobAnalysisResponse = {
  eligibility: { is_eligible: true, status: "PASS", reasons: [] },
  match_score: 88,
  feature_scores: { skills_score: 92, experience_score: 80, role_alignment_score: 90, location_work_model_score: 100, education_language_score: 100, ats_score: 85 },
  strengths: [{ evidence_id: "exp-1", description: "Good PM skills" }],
  gaps: ["GraphQL", "Kubernetes"],
  critical_gaps: [],
  recommendation: "apply",
  provenance: { candidate_profile_version: 1, matching_algorithm_version: "1.1", model_provider: "test", model_name: "test", generated_at: "2026", ats_method: "test" }
};

const noop = () => {};

describe('JobDrawer', () => {
  it('shows the job header and analysis breakdown', () => {
    render(<JobDrawer job={job()} analysis={analysis} analyzing={false} baseResumeId="r1" generating={false} onClose={noop} onGenerate={noop} />);
    expect(screen.getByRole('dialog', { name: /job details/i })).toBeInTheDocument();
    expect(screen.getByText('Senior Product Manager')).toBeInTheDocument();
    expect(screen.getByText('88')).toBeInTheDocument(); // match_score 0.88 â†’ 88 (0â€“1 scaled to percent)
    expect(screen.getByText('GraphQL')).toBeInTheDocument();
    expect(screen.getByText(/Good PM skills/)).toBeInTheDocument();
  });

  it('disables "Generate tailored rÃ©sumÃ©" when there is no base rÃ©sumÃ©', () => {
    render(<JobDrawer job={job()} analysis={analysis} analyzing={false} baseResumeId={null} generating={false} onClose={noop} onGenerate={noop} />);
    expect(screen.getByRole('button', { name: /generate tailored rÃ©sumÃ©/i })).toBeDisabled();
  });

  it('fires onGenerate when a base rÃ©sumÃ© exists', async () => {
    const onGenerate = vi.fn();
    render(<JobDrawer job={job()} analysis={analysis} analyzing={false} baseResumeId="r1" generating={false} onClose={noop} onGenerate={onGenerate} />);
    await userEvent.click(screen.getByRole('button', { name: /generate tailored rÃ©sumÃ©/i }));
    expect(onGenerate).toHaveBeenCalledOnce();
  });

  it('links "View posting" to the job url', () => {
    render(<JobDrawer job={job()} analysis={null} analyzing={false} baseResumeId="r1" generating={false} onClose={noop} onGenerate={noop} />);
    expect(screen.getByRole('link', { name: /view posting/i })).toHaveAttribute('href', 'https://example.com/job');
  });
});


