import { tailoringService } from '../services/tailoringService';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import Icon from '@/components/ui/Icon';
import JobDrawer from '@/components/jobs/JobDrawer';
import { useJobs, useSearchJobs, useAnalyzeJob } from '@/hooks/useJobs';
import { useApplications, useCreateApplication } from '@/hooks/useApplications';
import { useResumes } from '@/hooks/useResumes';
import { useAppStore } from '@/store/useAppStore';
import { atsColor, atsPercent, relativeTime } from '@/lib/status';
import { resolveOpportunityCta } from '@/lib/opportunityCta';
import type { Job } from '@/types/job';
import type { Application } from '@/types/application';

// ── Shared card style ─────────────────────────────────────────────────────
const card: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-1)',
};

const PLATFORMS: { key: string; label: string; color: string }[] = [
  { key: 'linkedin', label: 'LinkedIn', color: 'var(--approved)' },
  { key: 'indeed', label: 'Indeed', color: 'var(--interview)' },
  { key: 'glassdoor', label: 'Glassdoor', color: 'var(--applied)' },
  { key: 'exa', label: 'Exa', color: 'var(--accent)' },
  { key: 'bayt', label: 'Bayt', color: 'var(--review)' },
  { key: 'telegram', label: 'Telegram', color: 'var(--accent-3)' },
  { key: 'url', label: 'URL', color: 'var(--text-3)' },
  { key: 'paste', label: 'Paste', color: 'var(--text-3)' },
];

export default function JobSearchPage() {
  const navigate = useNavigate();
  const notify = useAppStore((s) => s.showNotification);
  const [query, setQuery] = useState('');
  const [location, setLocation] = useState('');
  const [platforms, setPlatforms] = useState<Set<string>>(new Set(PLATFORMS.slice(0, 4).map((p) => p.key)));
  const { data, isLoading, isError } = useJobs(1, 30);
  const { data: appsData } = useApplications(1, 100);
  const { data: resumeData } = useResumes();
  const search = useSearchJobs();
  const analyze = useAnalyzeJob();
  const createApp = useCreateApplication();
  const [startingSession, setStartingSession] = useState(false);
  const [drawerJob, setDrawerJob] = useState<Job | null>(null);
  const jobs = data?.items ?? [];
  const applications = appsData?.items ?? [];
  const resumes = resumeData?.items ?? [];
  const baseResumeId = resumes.find((r) => r.type === 'base')?.id ?? resumes[0]?.id ?? null;

  const openDrawer = (job: Job) => {
    setDrawerJob(job);
    if (job.raw_data?.match_result) {
      analyze.reset();
      return;
    }
    analyze.mutate(job.id, {
      onError: () => notify('Could not analyze this job', 'error'),
    });
  };

  const onGenerateTailored = async () => {
    if (!drawerJob || !baseResumeId) return;
    try {
      setStartingSession(true);
      const session = await tailoringService.startSession(drawerJob.id, baseResumeId);
      navigate('/cv-tailoring/' + session.id);
    } catch (err: any) {
      notify('Failed to start tailoring session: ' + (err.response?.data?.detail || err.message), 'error');
    } finally {
      setStartingSession(false);
    }
  };

  const togglePlatform = (key: string) =>
    setPlatforms((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });

  const runSearch = () => {
    if (!query.trim()) { notify('Enter a job title or keywords to search', 'warning'); return; }
    search.mutate(
      { query: query.trim(), location: location.trim() || undefined, platforms: [...platforms] },
      {
        onSuccess: (r) => notify(`Found ${r.total} matching roles`, 'success'),
        onError: () => notify('Search failed — try again', 'error'),
      },
    );
  };

  // CTA handlers
  const handleCta = (job: Job, app?: Application | null) => {
    const cta = resolveOpportunityCta(job, app);
    switch (cta.action) {
      case 'analyze':
        analyze.mutate(job.id, {
          onSuccess: () => notify(`Analysis complete`, 'success'),
          onError: () => notify('Could not analyze this job', 'error'),
        });
        break;
      case 'tailor':
        openDrawer(job);
        break;
      case 'continue_tailoring':
        if (job.operational_state?.tailoring_session_id) navigate(`/cv-tailoring/${job.operational_state.tailoring_session_id}`);
        break;
      case 'prepare':
        createApp.mutate(
          { job_id: job.id, apply_mode: 'review' },
          {
            onSuccess: (newApp) => {
              notify(`Ready to review — ${job.title}`, 'success');
              navigate(`/applications/${newApp.id}`);
            },
            onError: () => notify('Could not create the application', 'error'),
          },
        );
        break;
      case 'review':
      case 'view':
      case 'continue_preparation':
        if (job.operational_state?.application_id) navigate(`/applications/${job.operational_state.application_id}`);
        else if (app) navigate(`/applications/${app.id}`);
        break;
      case 'retry':
        if (app || job.operational_state?.application_id) navigate(`/applications/${app?.id ?? job.operational_state?.application_id}`);
        else openDrawer(job);
        break;
      default:
        openDrawer(job);
    }
  };

  return (
    <div style={{ animation: 'aaUp .4s var(--ease) both' }}>
      {/* Page header */}
      <div style={{ marginBottom: 18, display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16, flexWrap: 'wrap' }}>
        <div>
          <h1 style={{ margin: 0, font: '800 24px/1.1 var(--font)', letterSpacing: '-.03em' }}>Opportunities</h1>
          <p style={{ margin: '6px 0 0', font: '500 13px/1.4 var(--font)', color: 'var(--text-3)' }}>
            Search across platforms, import any job URL, or paste a description to analyze it.
          </p>
        </div>
        <button
          onClick={() => navigate('/workflow')}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 7, height: 36, padding: '0 16px', borderRadius: 'var(--r-md)', background: 'var(--accent)', border: '1px solid var(--accent)', color: 'var(--accent-ink)', font: '700 13px/1 var(--font)', cursor: 'pointer' }}
        >
          <Icon name="plus" size={14} /> Import Opportunity
        </button>
      </div>

      {/* Search bar */}
      <form
        onSubmit={(e) => { e.preventDefault(); runSearch(); }}
        style={{ ...card, display: 'flex', gap: 10, padding: 12, marginBottom: 14, flexWrap: 'wrap' }}
      >
        <div style={{ flex: '2 1 260px', display: 'flex', alignItems: 'center', gap: 9, height: 40, padding: '0 12px', borderRadius: 'var(--r-md)', background: 'var(--surface-3)', border: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--text-3)', display: 'grid', placeItems: 'center' }}><Icon name="search" size={16} /></span>
          <input
            aria-label="Job title or keywords"
            placeholder="Job title, skills, or company"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ flex: 1, background: 'transparent', border: 0, outline: 'none', color: 'var(--text)', font: '500 13px/1 var(--font)' }}
          />
        </div>
        <div style={{ flex: '1 1 180px', display: 'flex', alignItems: 'center', gap: 9, height: 40, padding: '0 12px', borderRadius: 'var(--r-md)', background: 'var(--surface-3)', border: '1px solid var(--border)' }}>
          <span style={{ color: 'var(--text-3)', display: 'grid', placeItems: 'center' }}><Icon name="mappin" size={16} /></span>
          <input
            aria-label="Location"
            placeholder="Location or Remote"
            value={location}
            onChange={(e) => setLocation(e.target.value)}
            style={{ flex: 1, background: 'transparent', border: 0, outline: 'none', color: 'var(--text)', font: '500 13px/1 var(--font)' }}
          />
        </div>
        <button
          type="submit"
          disabled={search.isPending}
          style={{ flex: '0 0 auto', display: 'inline-flex', alignItems: 'center', gap: 7, height: 40, padding: '0 18px', borderRadius: 'var(--r-md)', background: 'var(--accent)', border: '1px solid var(--accent)', color: 'var(--accent-ink)', font: '700 13px/1 var(--font)', cursor: 'pointer' }}
        >
          {search.isPending ? 'Searching…' : 'Search'}
        </button>
      </form>

      {/* Platform chips */}
      <div style={{ display: 'flex', gap: 8, marginBottom: 18, flexWrap: 'wrap' }}>
        {PLATFORMS.map((p) => {
          const on = platforms.has(p.key);
          return (
            <button
              key={p.key}
              aria-pressed={on}
              onClick={() => togglePlatform(p.key)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 7, height: 30, padding: '0 12px', borderRadius: 999, cursor: 'pointer', font: '600 12px/1 var(--font)', border: `1px solid ${on ? 'var(--accent-line)' : 'var(--border)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface-2)', color: on ? 'var(--accent)' : 'var(--text-3)' }}
            >
              <span style={{ width: 6, height: 6, borderRadius: '50%', background: on ? p.color : 'var(--text-4)' }} /> {p.label}
            </button>
          );
        })}
      </div>

      {/* Results */}
      {isError ? (
        <div style={{ ...card, ...noticeStyle }}>
          <span style={{ color: 'var(--failed)' }}><Icon name="alert" size={16} /></span> Couldn't load opportunities. Retry in a moment.
        </div>
      ) : isLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(290px,1fr))', gap: 14 }}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} style={{ ...card, height: 200, background: 'linear-gradient(90deg,var(--surface-2),var(--hover),var(--surface-2))', backgroundSize: '200% 100%', animation: 'aaShimmer 1.3s linear infinite' }} />
          ))}
        </div>
      ) : jobs.length === 0 ? (
        <div style={{ ...card, ...noticeStyle, flexDirection: 'column', gap: 8, padding: '46px 20px' }}>
          <div style={{ display: 'grid', placeItems: 'center', width: 44, height: 44, borderRadius: 12, background: 'var(--accent-soft)', color: 'var(--accent)' }}><Icon name="search" size={20} /></div>
          {search.isSuccess ? (
            <>
              <div style={{ font: '700 14px/1.2 var(--font)', color: 'var(--text)' }}>No matching roles</div>
              <span>Try broadening your keywords, changing location, or enabling more platforms.</span>
            </>
          ) : (
            <>
              <div style={{ font: '700 14px/1.2 var(--font)', color: 'var(--text)' }}>No opportunities yet</div>
              <span>Search above, or import a job from any URL.</span>
            </>
          )}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(290px,1fr))', gap: 14 }}>
          {jobs.map((j) => (
            <JobCardView
              key={j.id}
              job={j}
              app={applications.find((a) => a.job_id === j.id)}
              onOpen={() => openDrawer(j)}
              onCta={() => handleCta(j, applications.find(a => a.job_id === j.id))}
              analyzing={analyze.isPending && analyze.variables === j.id}
              applying={createApp.isPending}
            />
          ))}
        </div>
      )}

      {drawerJob && (
        <JobDrawer
          job={drawerJob}
          analysis={drawerJob.raw_data?.match_result ?? analyze.data ?? null}
          analyzing={!drawerJob.raw_data?.match_result && analyze.isPending}
          baseResumeId={baseResumeId}
          generating={startingSession}
          onClose={() => setDrawerJob(null)}
          onGenerate={onGenerateTailored}
        />
      )}
    </div>
  );
}

const noticeStyle: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
  padding: '30px 20px', color: 'var(--text-3)', font: '500 12.5px/1.4 var(--font)', textAlign: 'center',
};

// ── ScoreRing ──────────────────────────────────────────────────────────────
// job.match_score is 0–1 (float) — use atsPercent() to convert to 0–100.
function ScoreRing({ score }: { score: number | null }) {
  if (score == null) {
    return (
      <div style={{ width: 38, height: 38, borderRadius: '50%', background: 'var(--surface-2)', border: '1px solid var(--border)', display: 'grid', placeItems: 'center', color: 'var(--text-4)', fontSize: 10, fontWeight: 700 }} title="Not yet analyzed">
        ?
      </div>
    );
  }
  // score is 0–1 → multiply once to get 0–100 display value
  const pct = atsPercent(score);
  const r = 15.5;
  const c = 2 * Math.PI * r;
  const color = atsColor(pct);
  return (
    <div style={{ position: 'relative', width: 40, height: 40, flex: '0 0 auto' }}>
      <svg width={40} height={40} viewBox="0 0 40 40" style={{ transform: 'rotate(-90deg)' }}>
        <circle cx={20} cy={20} r={r} fill="none" stroke="var(--surface-2)" strokeWidth={3.5} />
        <circle cx={20} cy={20} r={r} fill="none" stroke={color} strokeWidth={3.5} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)} />
      </svg>
      <span style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', font: '700 11px/1 var(--mono)', color }}>
        {pct}
      </span>
    </div>
  );
}

// ── Consistent Opportunity Card ────────────────────────────────────────────
function JobCardView({
  job, app, onOpen, onCta, analyzing, applying,
}: {
  job: Job;
  app?: Application | null;
  onOpen: () => void;
  onCta: () => void;
  analyzing: boolean;
  applying: boolean;
}) {
  const plat = PLATFORMS.find((p) => p.key === job.platform);
  const cta = resolveOpportunityCta(job, app);
  const busy = (cta.action === 'analyze' && analyzing) || (cta.action === 'prepare' && applying);

  return (
    <div
      style={{
        ...card,
        padding: 16,
        display: 'flex',
        flexDirection: 'column',
        gap: 0,
        minHeight: 200,
      }}
    >
      {/* HEADER: source badge + score */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 22, padding: '0 9px', borderRadius: 999, background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-3)', font: '600 10.5px/1 var(--font)' }}>
          <span style={{ width: 6, height: 6, borderRadius: '50%', background: plat?.color ?? 'var(--text-4)' }} />
          {plat?.label ?? job.platform}
        </span>
        <ScoreRing score={job.match_score} />
      </div>

      {/* CONTENT: title + company */}
      <div style={{ flex: '1 1 auto' }}>
        <button
          onClick={onOpen}
          style={{ width: '100%', textAlign: 'start', padding: 0, margin: 0, background: 'none', border: 0, cursor: 'pointer', font: '700 14px/1.3 var(--font)', color: 'var(--text)', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' } as React.CSSProperties}
        >
          {job.title}
        </button>
        <div style={{ font: '500 12px/1.3 var(--font)', color: 'var(--text-3)', marginTop: 3, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          {job.company} · {job.location || (job.remote ? 'Remote' : '—')}
        </div>

        {/* Tags */}
        <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', marginTop: 8 }}>
          {job.remote && <Tag>Remote</Tag>}
          {job.job_type && <Tag>{job.job_type}</Tag>}
          {job.posted_date && <Tag>{relativeTime(job.posted_date)}</Tag>}
        </div>
      </div>

      {/* SPACER */}
      <div style={{ flex: '0 0 12px' }} />

      {/* FOOTER: one primary CTA anchored at bottom */}
      <div style={{ display: 'flex', gap: 8, paddingTop: 12, borderTop: '1px solid var(--border)' }}>
        <button
          onClick={onCta}
          disabled={cta.disabled || busy}
          title={cta.hint}
          style={{
            flex: '1 1 auto', display: 'inline-flex', alignItems: 'center', justifyContent: 'center', gap: 6,
            height: 34, padding: '0 12px', borderRadius: 'var(--r-md)', cursor: cta.disabled ? 'not-allowed' : 'pointer',
            font: '700 12px/1 var(--font)',
            background: 'var(--accent)', border: '1px solid var(--accent)', color: 'var(--accent-ink)',
            opacity: cta.disabled ? 0.5 : 1,
          }}
        >
          {busy ? '…' : cta.label}
        </button>
      </div>
    </div>
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span style={{ height: 22, padding: '0 8px', display: 'inline-flex', alignItems: 'center', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-3)', font: '600 10.5px/1 var(--font)' }}>
      {children}
    </span>
  );
}
