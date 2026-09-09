import { afterEach, describe, expect, it } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';

import { PackageReview } from '@/components/applications/PackageReview';
import { server } from '@/__tests__/mocks/server';
import type { ApplicationPackage, Readiness } from '@/services/packageService';

const HASH = 'a'.repeat(64);

function packageFixture(overrides: Partial<ApplicationPackage> = {}): ApplicationPackage {
  return {
    id: 'pkg-1',
    application_id: 'app-1',
    job_id: 'job-1',
    route_id: 'route-1',
    resume_id: 'resume-tailored',
    cover_letter_key: null,
    cover_letter_text: null,
    email_to: null,
    email_subject: null,
    email_body: null,
    attachment_keys: ['users/me/resumes/tailored.pdf'],
    answers: null,
    language: 'en',
    version: 1,
    content_hash: HASH,
    is_current: true,
    qa_verdict: null,
    qa_issues: null,
    approval_id: null,
    approved_at: null,
    send_state: null,
    sent_at: null,
    message_id: null,
    created_at: '2026-09-09T08:00:00Z',
    ...overrides,
  };
}

function readinessFor(pkg: ApplicationPackage): Readiness {
  const complete = Boolean(pkg.resume_id && pkg.cover_letter_text && pkg.email_to && pkg.email_subject && pkg.email_body);
  return {
    ready: complete,
    missing: complete ? [] : ['cover letter', 'application email'],
    warnings: ['work-authorization requirements unknown'],
    documents: [
      { name: 'Tailored CV', ok: Boolean(pkg.resume_id), detail: pkg.resume_id ? 'verified' : 'missing' },
      { name: 'Cover Letter', ok: Boolean(pkg.cover_letter_text), detail: pkg.cover_letter_text ? 'drafted' : 'not generated' },
      { name: 'Application Email', ok: Boolean(pkg.email_body), detail: pkg.email_body ? 'drafted' : 'not drafted' },
    ],
    route: 'EMAIL',
    posting_quality: { signal: 'likely_legitimate', reasons: [] },
    work_authorization: { status: 'UNKNOWN', requirements: [], evidence: [] },
    package_version: pkg.version,
    content_hash: pkg.content_hash,
    approved: Boolean(pkg.approval_id),
    send_state: pkg.send_state,
  };
}

function installPackageHandlers(initial: ApplicationPackage) {
  let current = initial;
  let sendCalls = 0;

  server.use(
    http.get('/api/v1/applications/:appId/package', () => HttpResponse.json(current)),
    http.get('/api/v1/applications/:appId/readiness', () => HttpResponse.json(readinessFor(current))),
    http.get('/api/v1/resumes/', () => HttpResponse.json({
      items: [{
        id: 'resume-tailored', name: 'Tailored CV — Senior Engineer', type: 'tailored',
        template_id: 'modern', base_resume_id: 'resume-base', job_id: 'job-1',
        has_pdf: true, has_docx: true, ats_score: 0.91,
        created_at: '2026-09-09T07:00:00Z', updated_at: '2026-09-09T07:00:00Z',
      }],
      total: 1,
    })),
    http.post('/api/v1/applications/:appId/package', async ({ request }) => {
      const update = await request.json() as Partial<ApplicationPackage>;
      current = {
        ...current,
        ...update,
        id: `pkg-${current.version + 1}`,
        version: current.version + 1,
        content_hash: String(current.version + 1).repeat(64).slice(0, 64),
        approval_id: null,
        approved_at: null,
        qa_verdict: null,
        qa_issues: null,
      };
      return HttpResponse.json(current);
    }),
    http.post('/api/v1/applications/:appId/package/approve', () => {
      current = { ...current, approval_id: 'approval-1', approved_at: '2026-09-09T09:00:00Z' };
      return HttpResponse.json(current);
    }),
    http.post('/api/v1/applications/:appId/package/send', () => {
      sendCalls += 1;
      return HttpResponse.json({ state: 'sent', message_id: 'unexpected' });
    }),
  );

  return { current: () => current, sendCalls: () => sendCalls };
}

afterEach(() => localStorage.removeItem('aa_mock_ai'));

describe('PackageReview', () => {
  it('shows every review block and completes the mocked review flow without AI or sending', async () => {
    localStorage.setItem('aa_mock_ai', '1');
    const state = installPackageHandlers(packageFixture());
    const user = userEvent.setup();

    render(
      <PackageReview
        applicationId="app-1"
        jobId="job-1"
        job={{ title: 'Senior Engineer', company: 'Example Co', location: 'Riyadh' }}
        matchSummary={{ score: 0.91 }}
      />,
    );

    expect(await screen.findByText('Senior Engineer')).toBeInTheDocument();
    expect(screen.getByText('91%')).toBeInTheDocument();
    expect(screen.getByText('Tailored CV — Senior Engineer')).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /application email/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /application answers/i })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: /qa findings/i })).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Generate cover letter' }));
    expect(await screen.findByText(/I am excited to apply for this role/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Generate email' }));
    await waitFor(() => expect(state.current().email_body).toContain('Please find attached'));

    await user.click(screen.getByRole('button', { name: 'Generate answers' }));
    expect(await screen.findByText('Years of relevant experience?')).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Run QA' }));
    expect(await screen.findByText(/Confirm work-authorization requirements/)).toBeInTheDocument();

    const approve = screen.getByRole('button', { name: 'Approve package' });
    await waitFor(() => expect(approve).toBeEnabled());
    await user.click(approve);
    expect(await screen.findByText(/Approved for version/)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /send email/i })).not.toBeInTheDocument();
    expect(screen.getByText(/sending is disabled/i)).toBeInTheDocument();
    expect(state.sendCalls()).toBe(0);
  });

  it('invalidates approval and QA when a package component creates a newer version', async () => {
    localStorage.setItem('aa_mock_ai', '1');
    installPackageHandlers(packageFixture({
      cover_letter_text: 'Existing letter',
      email_to: 'jobs@example.com',
      email_subject: 'Application',
      email_body: 'Existing email',
      answers: [],
      qa_verdict: 'pass',
      approval_id: 'approval-old',
      approved_at: '2026-09-09T08:30:00Z',
    }));
    const user = userEvent.setup();

    render(<PackageReview applicationId="app-1" jobId="job-1" />);
    expect(await screen.findByText(/Approved for version 1/)).toBeInTheDocument();

    await user.click(screen.getByRole('button', { name: 'Regenerate email' }));
    expect(await screen.findByText(/Awaiting approval for version 2/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Approve package' })).toBeDisabled();
    await waitFor(() => expect(screen.getByRole('button', { name: 'Regenerate email' })).toBeEnabled());
  });
});
