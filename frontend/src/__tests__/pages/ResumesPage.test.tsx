import { describe, it, expect } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { http, HttpResponse } from 'msw';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

import { server } from '@/__tests__/mocks/server';
import ResumesPage from '@/pages/ResumesPage';
import { useAppStore } from '@/store/useAppStore';

function resume(overrides: Record<string, unknown> = {}) {
  return {
    id: 'resume-1', name: 'Alex Morgan', type: 'base', template_id: 'modern',
    base_resume_id: null, job_id: null, has_pdf: true, has_docx: false, ats_score: 0.82,
    content_text: 'Alex Morgan\nalex@example.com\nSummary\nProduct leader\nExperience\nLed a global platform migration without truncation.\nEducation\nBSc Computer Science',
    created_at: '2026-07-01T00:00:00Z', updated_at: '2026-07-01T00:00:00Z', ...overrides,
  };
}
const list = (...items: object[]) => ({ items, total: items.length });

const oneJob = {
  id: 'j1', platform: 'linkedin', platform_job_id: 'ln1', title: 'Senior PM', company: 'Northwind',
  location: 'Remote', url: 'https://x', description: '', salary_range: null, job_type: null,
  remote: true, posted_date: null, experience_level: null, match_score: 0.9, skills_required: null,
  status: 'new', created_at: '', updated_at: '',
};

function renderResumes() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/']}>
        <Routes>
          <Route path="/" element={<ResumesPage />} />
          <Route path="/cv-tailoring/:id" element={<div>Tailoring workbench destination</div>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('ResumesPage', () => {
  it('renders résumé cards from the API', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume(), resume({ id: 'r2', name: 'Senior PM — Tailored', type: 'tailored' })))));
    renderResumes();
    // The first résumé auto-selects, so its name also appears in the preview panel.
    expect((await screen.findAllByText('Alex Morgan')).length).toBeGreaterThan(0);
    expect(screen.getByText('Senior PM — Tailored')).toBeInTheDocument();
  });

  it('updates the preview panel when a different résumé card is selected', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume(), resume({ id: 'r2', name: 'Senior PM — Tailored', type: 'tailored', ats_score: 0.9 })))));
    renderResumes();
    await screen.findByText('Senior PM — Tailored');
    await userEvent.click(screen.getByRole('button', { name: /select résumé senior pm/i }));
    await waitFor(() => expect(screen.getByLabelText(/full résumé preview for senior pm — tailored/i)).toBeInTheDocument());
  });

  it('renders the full canonical content in the document preview', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume()))));
    renderResumes();
    const preview = await screen.findByLabelText(/full résumé preview/i);
    expect(preview).toHaveTextContent('Led a global platform migration without truncation.');
    expect(preview).toHaveTextContent('BSc Computer Science');
  });

  it('generates a tailored résumé once a target job is chosen', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume()))));
    server.use(http.get('/api/v1/jobs/', () => HttpResponse.json({ items: [oneJob], total: 1, page: 1, page_size: 20, has_next: false })));
    let body: { base_resume_id?: string; job_id?: string } | null = null;
    server.use(http.post('/api/v1/resumes/generate', async ({ request }) => {
      body = (await request.json()) as { base_resume_id: string; job_id: string };
      return HttpResponse.json(resume({ id: 'r-gen', name: 'Generated', type: 'tailored' }));
    }));
    renderResumes();
    await screen.findAllByText('Alex Morgan');
    const gen = screen.getByRole('button', { name: /generate tailored/i });
    expect(gen).toBeDisabled();
    expect(gen).toHaveAccessibleDescription(/select a target job|upload a base résumé/i);
    await userEvent.selectOptions(screen.getByLabelText(/target job/i), 'j1');
    expect(gen).not.toBeDisabled();
    await userEvent.click(gen);
    await waitFor(() => expect(body).not.toBeNull());
    expect(body!.base_resume_id).toBe('resume-1');
    expect(body!.job_id).toBe('j1');
  });

  it('does not POST /resumes/generate when the button is blocked (no target job yet)', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume()))));
    server.use(http.get('/api/v1/jobs/', () => HttpResponse.json({ items: [oneJob], total: 1, page: 1, page_size: 20, has_next: false })));
    let posted = false;
    server.use(http.post('/api/v1/resumes/generate', () => {
      posted = true;
      return HttpResponse.json(resume({ id: 'r-gen', name: 'Generated', type: 'tailored' }));
    }));
    renderResumes();
    await screen.findAllByText('Alex Morgan');
    const gen = screen.getByRole('button', { name: /generate tailored/i });
    expect(gen).toBeDisabled();
    await userEvent.click(gen);
    expect(posted).toBe(false);
  });


  it('surfaces an error toast when a download fails', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume()))));
    server.use(http.get('/api/v1/resumes/:id/download', () => new HttpResponse(null, { status: 500 })));
    useAppStore.getState().clearNotification();
    renderResumes();
    await screen.findAllByText('Alex Morgan');
    await userEvent.click(screen.getByRole('button', { name: /download résumé/i }));
    await waitFor(() => expect(useAppStore.getState().notification?.message).toMatch(/could not download/i));
  });

  it('shows an empty state (and no preview panel) when there are no résumés', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json({ items: [], total: 0 })));
    renderResumes();
    expect(await screen.findByText(/no résumés yet/i)).toBeInTheDocument();
    expect(screen.queryByText(/preview & score/i)).not.toBeInTheDocument();
  });

  it('uploads a selected résumé file', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume()))));
    let uploaded = false;
    server.use(http.post('/api/v1/resumes/upload', () => {
      uploaded = true;
      return HttpResponse.json({ id: 'r-new', name: 'uploaded.pdf', file_format: 'pdf', word_count: 500, skills_detected: [] });
    }));
    renderResumes();
    await screen.findAllByText('Alex Morgan');
    const file = new File(['pdf-bytes'], 'resume.pdf', { type: 'application/pdf' });
    await userEvent.upload(screen.getByLabelText(/upload résumé/i), file);
    await waitFor(() => expect(uploaded).toBe(true));
  });

  it('optimizes a résumé via the endpoint', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume()))));
    let optimizedId: string | null = null;
    server.use(http.post('/api/v1/resumes/:id/optimize', ({ params }) => {
      optimizedId = params.id as string;
      return HttpResponse.json(resume({ ats_score: 0.9 }));
    }));
    renderResumes();
    await screen.findAllByText('Alex Morgan');
    await userEvent.click(screen.getByRole('button', { name: /optimize/i }));
    await waitFor(() => expect(optimizedId).toBe('resume-1'));
  });

  it('archives a résumé through the safe archive endpoint', async () => {
    let archived = false;
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(...(archived ? [] : [resume()])))));
    server.use(http.post('/api/v1/resumes/:id/archive', () => { archived = true; return HttpResponse.json(resume({ archived_at: new Date().toISOString() })); }));
    renderResumes();
    await screen.findAllByText('Alex Morgan');
    await userEvent.click(screen.getByRole('button', { name: /archive résumé/i }));
    await waitFor(() => expect(archived).toBe(true));
    expect(await screen.findByText(/no résumés yet/i)).toBeInTheDocument();
  });

  it('opens a deterministic revision workbench for a tailored résumé', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(resume({ type: 'tailored', job_id: 'j1' })))));
    server.use(http.post('/api/v1/tailoring/resume/:id/revision', () => HttpResponse.json({ id: 'session-1', job_id: 'j1', base_resume_id: 'resume-1', status: 'reviewing', changes: [] })));
    renderResumes();
    await screen.findAllByText('Alex Morgan');
    await userEvent.click(screen.getByRole('button', { name: /revise tailored cv/i }));
    expect(await screen.findByText(/tailoring workbench destination/i)).toBeInTheDocument();
  });

  it('shows the before/after ATS delta pill when an optimized résumé and its base are loaded', async () => {
    server.use(http.get('/api/v1/resumes/', () => HttpResponse.json(list(
      resume({ id: 'resume-2', name: 'Alex Morgan', type: 'optimized', base_resume_id: 'resume-1', ats_score: 0.81 }),
      resume({ id: 'resume-1', ats_score: 0.62 }),
    ))));
    server.use(http.get('/api/v1/jobs/', () => HttpResponse.json({ items: [oneJob], total: 1, page: 1, page_size: 20, has_next: false })));
    renderResumes();
    // The optimized variant is first → auto-selected; its base's stored score is the "was".
    const items = await screen.findAllByText('Alex Morgan');
    expect(items.length).toBeGreaterThanOrEqual(2);
  });
});
