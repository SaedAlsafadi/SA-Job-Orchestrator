import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';


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
  total_score: 88,
  dimensions: { skills: { status: 'VALID_SCORE', score: 92, explanation: null }, experience: { status: 'VALID_SCORE', score: 80, explanation: null }, role_alignment: { status: 'VALID_SCORE', score: 90, explanation: null } },
  verdict: 'STRONG_MATCH', confidence: 0.9, data_quality: 'HIGH', data_quality_explanation: null, explanation: 'Good fit', recommendation: 'apply', blockers: [], requirement_analysis: [],
  strong_matches: ["Good PM skills"],
  gaps: ["GraphQL", "Kubernetes"],
  critical_gaps: [],
  provenance: { candidate_profile_version: 1, matching_algorithm_version: "1.1", model_provider: "test", model_name: "test", generated_at: "2026", ats_method: "test" }
};

const noop = () => {};

describe('JobDrawer', () => {
  it('shows the job header and analysis breakdown', () => {
    render(<JobDrawer job={job()} analysis={analysis} analyzing={false} baseResumeId="r1" generating={false} onClose={noop} onGenerate={noop} />);
    expect(screen.getByRole('dialog', { name: /job details/i })).toBeInTheDocument();
    expect(screen.getByText('Senior Product Manager')).toBeInTheDocument();
    expect(screen.getByText('88%')).toBeInTheDocument();
  });
});

