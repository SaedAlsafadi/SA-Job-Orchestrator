import React, { useEffect, useMemo, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { tailoringService, type CVTailoringSession } from '../services/tailoringService';
import { getJob } from '../services/jobService';
import { getResume } from '../services/resumeService';
import { createApplication, listApplications } from '../services/applicationService';
import type { Job } from '../types/job';
import type { Resume } from '../types/resume';
import { ChangeCard } from '../components/tailoring/ChangeCard';
import Icon from '@/components/ui/Icon';
import { MatchIntelligenceView } from '@/components/matching/MatchIntelligenceView';
import { parseResumeContent, mergeTailoringChanges, type StructuredResume } from '@/lib/tailoringPreview';

// ── Panel layout helpers ──────────────────────────────────────────────────
const panel: React.CSSProperties = { display: 'flex', flexDirection: 'column', background: 'var(--surface)', minHeight: 0 };
const pHead: React.CSSProperties = { padding: '14px 18px', borderBottom: '1px solid var(--border)', flex: '0 0 auto' };
const pBody: React.CSSProperties = { flex: '1 1 auto', overflowY: 'auto', padding: '18px' };

// ── Live Draft Preview ─────────────────────────────────────────────────────
/**
 * Renders a structured resume document with change-highlighting.
 * When mode='draft', shows the merged result of accepted changes.
 * When mode='base', shows the original with highlights.
 */
function StructuredResumeDoc({
  data,
  changes,
  mode,
}: {
  data: StructuredResume;
  changes: CVTailoringSession['changes'];
  mode: 'base' | 'draft';
}) {
  const getFieldStyle = (path: string): React.CSSProperties => {
    if (mode === 'draft') return {}; // Draft shows merged result — no highlight needed

    const related = changes.filter((c) => c.target_reference.startsWith(path));
    if (related.length === 0) return {};
    if (related.some((c) => c.user_decision === 'pending'))
      return { background: 'var(--review-soft)', borderInlineStart: '3px solid var(--review)', paddingInlineStart: 10 };
    if (related.some((c) => c.user_decision === 'accepted'))
      return { background: 'var(--applied-soft)', borderInlineStart: '3px solid var(--applied)', paddingInlineStart: 10 };
    if (related.some((c) => c.user_decision === 'rejected'))
      return { background: 'var(--rejected-soft)', borderInlineStart: '3px solid var(--rejected)', paddingInlineStart: 10, opacity: 0.5 };
    return {};
  };

  const sectionHead: React.CSSProperties = {
    margin: '0 0 10px 0', font: '700 11px/1 var(--mono)', textTransform: 'uppercase',
    letterSpacing: '.08em', color: 'var(--text-3)', borderBottom: '1px solid var(--border)', paddingBottom: 8,
  };

  const isStructured = !!(data.summary || data.skills?.length || data.experience?.length || data.projects?.length || data.education?.length || data.certifications?.length);

  if (!isStructured && data.raw_text) {
    return (
      <div style={{ font: '400 13px/1.65 var(--font)', color: 'var(--text)', whiteSpace: 'pre-wrap', fontFamily: 'monospace' }}>
        {data.raw_text}
      </div>
    );
  }

  return (
    <div style={{ font: '400 13.5px/1.65 var(--font)', color: 'var(--text)' }}>
      {/* Identity */}
      <div style={{ textAlign: 'center', marginBottom: 22, ...getFieldStyle('name') }}>
        <h1 style={{ margin: '0 0 6px 0', font: '800 22px/1.2 var(--font)' }}>{data.name || '—'}</h1>
        <div style={{ font: '500 12px/1.4 var(--font)', color: 'var(--text-3)', display: 'flex', justifyContent: 'center', gap: 14, flexWrap: 'wrap' }}>
          {data.email && <span>{data.email}</span>}
          {data.phone && <span>{data.phone}</span>}
          {data.location && <span>{data.location}</span>}
          {data.linkedin && <span>{data.linkedin}</span>}
        </div>
      </div>

      {/* Summary */}
      {data.summary && (
        <div style={{ marginBottom: 20, ...getFieldStyle('summary') }}>
          <h2 style={sectionHead}>Summary</h2>
          <p style={{ margin: 0 }}>{data.summary}</p>
        </div>
      )}

      {/* Skills */}
      {data.skills && data.skills.length > 0 && (
        <div style={{ marginBottom: 20, ...getFieldStyle('skills') }}>
          <h2 style={sectionHead}>Skills</h2>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: '5px 10px' }}>
            {data.skills.map((s, i) => (
              <span key={i} style={{ padding: '3px 8px', borderRadius: 5, background: 'var(--surface-2)', border: '1px solid var(--border)', font: '600 11.5px/1 var(--font)', color: 'var(--text-2)' }}>{s}</span>
            ))}
          </div>
        </div>
      )}

      {/* Experience */}
      {data.experience && data.experience.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h2 style={sectionHead}>Experience</h2>
          {data.experience.map((exp, idx) => (
            <div key={idx} style={{ marginBottom: 16, ...getFieldStyle(`experience[${idx}]`) }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 3 }}>
                <h3 style={{ margin: 0, font: '700 14px/1.2 var(--font)' }}>{exp.title}</h3>
                <span style={{ font: '600 11px/1 var(--font)', color: 'var(--text-3)' }}>{exp.duration}</span>
              </div>
              {exp.company && <div style={{ font: '600 13px/1.4 var(--font)', color: 'var(--text-2)', marginBottom: 6 }}>{exp.company}</div>}
              {exp.description && (
                <ul style={{ margin: 0, paddingInlineStart: 18 }}>
                  {String(exp.description).split('\n').filter(Boolean).map((bullet, i) => (
                    <li key={i} style={{ marginBottom: 3 }}>{bullet.replace(/^[-•*]\s*/, '')}</li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Projects */}
      {data.projects && data.projects.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h2 style={sectionHead}>Projects</h2>
          {data.projects.map((proj, idx) => (
            <div key={idx} style={{ marginBottom: 12, ...getFieldStyle(`projects[${idx}]`) }}>
              <div style={{ font: '700 13px/1.2 var(--font)', marginBottom: 3 }}>{proj.name}</div>
              {proj.tech && <div style={{ font: '600 11px/1 var(--mono)', color: 'var(--text-3)', marginBottom: 4 }}>{proj.tech}</div>}
              {proj.description && <p style={{ margin: 0, font: '400 13px/1.5 var(--font)' }}>{String(proj.description)}</p>}
            </div>
          ))}
        </div>
      )}

      {/* Education */}
      {data.education && data.education.length > 0 && (
        <div style={{ marginBottom: 20 }}>
          <h2 style={sectionHead}>Education</h2>
          {data.education.map((edu, idx) => (
            <div key={idx} style={{ marginBottom: 10, ...getFieldStyle(`education[${idx}]`) }}>
              <div style={{ font: '700 13px/1.2 var(--font)' }}>{edu.degree}</div>
              {edu.institution && <div style={{ font: '500 12px/1.3 var(--font)', color: 'var(--text-3)' }}>{edu.institution} {edu.year ? `· ${edu.year}` : ''}</div>}
            </div>
          ))}
        </div>
      )}

      {/* Certifications */}
      {data.certifications && data.certifications.length > 0 && (
        <div style={{ marginBottom: 12, ...getFieldStyle('certifications') }}>
          <h2 style={sectionHead}>Certifications</h2>
          <ul style={{ margin: 0, paddingInlineStart: 18 }}>
            {data.certifications.map((cert, i) => (
              <li key={i} style={{ marginBottom: 4 }}>{cert}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}

// ── Main Workbench ─────────────────────────────────────────────────────────
export const CVTailoringWorkbench: React.FC = () => {
  const { sessionId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();

  const [session, setSession] = useState<CVTailoringSession | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [baseResume, setBaseResume] = useState<Resume | null>(null);
  const [finalResume, setFinalResume] = useState<Resume | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<'ALL' | 'ADDED' | 'MODIFIED' | 'REMOVED' | 'WARNING' | 'BLOCKED'>('ALL');
  const [verifying, setVerifying] = useState(false);
  const [preparing, setPreparing] = useState(false);
  // Draft vs base toggle for the center panel
  const [previewMode, setPreviewMode] = useState<'draft' | 'base'>('draft');

  useEffect(() => {
    if (sessionId) loadData(sessionId);
  }, [sessionId]);

  const loadData = async (id: string) => {
    try {
      setLoading(true);
      const s = await tailoringService.getSession(id);
      setSession(s);
      const [j, r, completedResume] = await Promise.all([
        getJob(s.job_id),
        getResume(s.base_resume_id),
        s.final_resume_id ? getResume(s.final_resume_id) : Promise.resolve(null),
      ]);
      setJob(j);
      setBaseResume(r);
      setFinalResume(completedResume);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load tailoring session');
    } finally {
      setLoading(false);
    }
  };

  /**
   * Live draft preview: deterministically merges accepted changes onto the base resume
   * WITHOUT any backend call or PDF generation. Updates immediately on each decision.
   */
  const draftData = useMemo<StructuredResume | null>(() => {
    if (!baseResume?.content_text) return null;
    const base = parseResumeContent(baseResume.content_text);
    if (!base) return null;
    if (!session) return base;
    return mergeTailoringChanges(base, session.changes);
  }, [baseResume?.content_text, session?.changes]);

  const baseData = useMemo<StructuredResume | null>(() => {
    if (!baseResume?.content_text) return null;
    return parseResumeContent(baseResume.content_text);
  }, [baseResume?.content_text]);

  const handleDecision = async (changeId: string, decision: 'accepted' | 'rejected') => {
    if (!session) return;
    try {
      const updated = await tailoringService.submitDecisions(session.id, { [changeId]: decision });
      setSession(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit decision');
    }
  };

  const handleBulkAccept = async () => {
    if (!session) return;
    const decisions: Record<string, 'accepted'> = {};
    session.changes.forEach((c) => {
      if (c.user_decision === 'pending' && c.review_severity === 'safe') {
        decisions[c.change_id] = 'accepted';
      }
    });
    if (Object.keys(decisions).length === 0) return;
    try {
      const updated = await tailoringService.submitDecisions(session.id, decisions);
      setSession(updated);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to submit bulk decisions');
    }
  };

  const handleRevise = async (changeId: string, instruction: string) => {
    if (!session) return;
    try {
      await tailoringService.reviseChange(session.id, changeId, instruction);
      await loadData(session.id);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Revision failed');
    }
  };

  const handleFinalize = async () => {
    if (!session) return;
    try {
      setVerifying(true);
      const newResume = await tailoringService.finalizeSession(session.id);
      setFinalResume(newResume);
      setSession({ ...session, status: 'verified' });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to finalize résumé');
    } finally {
      setVerifying(false);
    }
  };

  const handlePrepareApplication = async () => {
    if (!session || !finalResume) return;
    setPreparing(true);
    setError(null);
    try {
      const application = await createApplication({
        job_id: session.job_id,
        resume_id: finalResume.id,
        apply_mode: 'review',
      });
      navigate(`/applications/${application.id}`);
    } catch (err: any) {
      try {
        const existing = await listApplications(1, 50);
        const application = existing.items.find((item) => item.job_id === session.job_id);
        if (application) {
          navigate(`/applications/${application.id}`);
          return;
        }
      } catch {
        // fall through
      }
      setError(err.response?.data?.detail || err.message || 'Failed to prepare application');
    } finally {
      setPreparing(false);
    }
  };

  // ── Loading / Error states ────────────────────────────────────────────────
  if (loading) {
    return (
      <div style={{ display: 'grid', placeItems: 'center', height: 'calc(100vh - 56px)', color: 'var(--text-3)' }}>
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 14 }}>
          <div style={{ width: 40, height: 40, borderRadius: '50%', border: '3px solid var(--border)', borderTopColor: 'var(--accent)', animation: 'aaSpin .8s linear infinite' }} />
          <span style={{ font: '600 14px/1 var(--font)' }}>Analyzing CV against this job…</span>
        </div>
      </div>
    );
  }

  if (error && !session) {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: 'calc(100vh - 56px)', gap: 16 }}>
        <span style={{ color: 'var(--failed)' }}><Icon name="alert" size={32} /></span>
        <h2 style={{ font: '700 18px/1 var(--font)', color: 'var(--failed)', margin: 0 }}>Failed to load</h2>
        <p style={{ color: 'var(--text-2)', margin: 0 }}>{error}</p>
        <button onClick={() => navigate(-1)} style={{ padding: '9px 18px', background: 'var(--accent)', color: 'var(--accent-ink)', border: 'none', borderRadius: 'var(--r-md)', cursor: 'pointer', font: '700 13px/1 var(--font)' }}>Go Back</button>
      </div>
    );
  }

  if (!session || !job || !baseResume) return null;

  const filteredChanges = session.changes.filter((c) => {
    if (filter === 'ALL') return true;
    if (filter === 'ADDED') return c.change_type === 'add';
    if (filter === 'MODIFIED') return c.change_type === 'modify';
    if (filter === 'REMOVED') return c.change_type === 'remove';
    if (filter === 'WARNING') return c.review_severity === 'warning';
    if (filter === 'BLOCKED') return c.review_severity === 'blocked';
    return true;
  });

  const pendingCount = session.changes.filter((c) => c.user_decision === 'pending').length;
  const acceptedCount = session.changes.filter((c) => c.user_decision === 'accepted').length;
  const rejectedCount = session.changes.filter((c) => c.user_decision === 'rejected').length;
  const canFinalize = pendingCount === 0 && session.changes.every((c) => !(c.user_decision === 'accepted' && c.review_severity === 'blocked'));

  const displayData = previewMode === 'draft' ? draftData : baseData;

  return (
    <div style={{ display: 'flex', height: 'calc(100vh - 56px)', background: 'var(--bg)', overflow: 'hidden', animation: 'aaUp .3s var(--ease) both' }}>

      {/* ── LEFT: Job context + match intelligence ────────────────────────── */}
      <div style={{ ...panel, width: 260, flex: '0 0 260px', borderInlineEnd: '1px solid var(--border)' }}>
        <div style={pHead}>
          <button
            onClick={() => navigate(-1)}
            style={{ background: 'none', border: 'none', color: 'var(--text-3)', cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, font: '600 12px/1 var(--font)', padding: 0, marginBottom: 14 }}
          >
            <Icon name="chevL" size={13} /> Back
          </button>
          <h2 style={{ margin: '0 0 4px 0', font: '700 15px/1.3 var(--font)', overflow: 'hidden', display: '-webkit-box', WebkitLineClamp: 2, WebkitBoxOrient: 'vertical' } as React.CSSProperties}>
            {job.title}
          </h2>
          <p style={{ margin: 0, font: '500 12px/1 var(--font)', color: 'var(--text-3)' }}>{job.company} · {job.location}</p>
        </div>
        <div style={pBody}>
          <div style={{ font: '600 10px/1 var(--mono)', textTransform: 'uppercase', letterSpacing: '.1em', color: 'var(--text-4)', marginBottom: 12 }}>Match Intelligence</div>
          {job.raw_data?.match_result ? (
            <MatchIntelligenceView result={job.raw_data.match_result} />
          ) : (
            <p style={{ font: '500 12px/1.5 var(--font)', color: 'var(--text-3)', margin: 0 }}>
              Run Analyze Match from the Opportunities page to see detailed match intelligence here.
            </p>
          )}
        </div>
      </div>

      {/* ── CENTER: Live draft CV preview ─────────────────────────────────── */}
      <div style={{ ...panel, flex: '1 1 auto', minWidth: 0, background: 'var(--bg-2)', borderInlineEnd: '1px solid var(--border)' }}>
        {/* Preview header with mode toggle */}
        <div style={{ ...pHead, display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'var(--surface)', gap: 12 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <h2 style={{ margin: 0, font: '700 14px/1 var(--font)' }}>CV Preview</h2>
            {session.status === 'verified' ? (
              <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, padding: '3px 9px', borderRadius: 999, background: 'var(--applied-soft)', border: '1px solid var(--applied)', color: 'var(--applied)', font: '700 10px/1 var(--mono)' }}>
                <Icon name="check" size={11} sw={2.5} /> VERIFIED FINAL
              </span>
            ) : (
              <span style={{ padding: '3px 9px', borderRadius: 999, background: 'var(--review-soft)', border: '1px solid var(--review-line)', color: 'var(--review)', font: '700 10px/1 var(--mono)' }}>
                DRAFT
              </span>
            )}
          </div>

          {/* Base vs Draft toggle */}
          <div style={{ display: 'flex', alignItems: 'center', borderRadius: 'var(--r-sm)', overflow: 'hidden', border: '1px solid var(--border)' }}>
            <button
              onClick={() => setPreviewMode('draft')}
              style={{
                padding: '5px 12px', cursor: 'pointer', font: '600 11px/1 var(--font)', border: 'none',
                background: previewMode === 'draft' ? 'var(--accent)' : 'transparent',
                color: previewMode === 'draft' ? 'var(--accent-ink)' : 'var(--text-3)',
              }}
            >
              Draft ({acceptedCount} changes)
            </button>
            <button
              onClick={() => setPreviewMode('base')}
              style={{
                padding: '5px 12px', cursor: 'pointer', font: '600 11px/1 var(--font)', border: 'none',
                background: previewMode === 'base' ? 'var(--accent)' : 'transparent',
                color: previewMode === 'base' ? 'var(--accent-ink)' : 'var(--text-3)',
              }}
            >
              Original
            </button>
          </div>
        </div>

        {/* Document area */}
        <div style={{ ...pBody, padding: '28px 32px' }}>
          <div style={{ background: 'var(--surface)', boxShadow: 'var(--shadow-2)', borderRadius: 'var(--r-lg)', padding: '36px 40px', maxWidth: 760, margin: '0 auto' }}>
            {displayData ? (
              <StructuredResumeDoc
                data={displayData}
                changes={session.changes}
                mode={previewMode}
              />
            ) : (
              <div style={{ color: 'var(--text-3)', font: '500 13px/1.5 var(--font)', textAlign: 'center', padding: '40px 0' }}>
                No structured resume data available. The base résumé may be in an unsupported format.
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ── RIGHT: Changes panel ──────────────────────────────────────────── */}
      <div style={{ ...panel, width: 300, flex: '0 0 300px' }}>
        {/* Changes header */}
        <div style={pHead}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 10 }}>
            <h2 style={{ margin: 0, font: '700 14px/1 var(--font)' }}>{session.changes.length} Changes</h2>
            <button
              onClick={handleBulkAccept}
              style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', font: '600 11px/1 var(--font)', textDecoration: 'underline', padding: 0 }}
            >
              Accept All Safe
            </button>
          </div>
          {/* Filter chips */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
            {(['ALL', 'ADDED', 'MODIFIED', 'REMOVED', 'WARNING', 'BLOCKED'] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFilter(f)}
                style={{
                  padding: '4px 9px', borderRadius: 'var(--r-sm)', font: '600 10px/1 var(--font)', cursor: 'pointer',
                  border: `1px solid ${filter === f ? 'var(--accent)' : 'var(--border)'}`,
                  background: filter === f ? 'var(--accent)' : 'var(--surface-2)',
                  color: filter === f ? 'var(--accent-ink)' : 'var(--text-3)',
                }}
              >
                {f}
              </button>
            ))}
          </div>
        </div>

        {/* Changes list */}
        <div style={pBody}>
          {filteredChanges.map((change) => (
            <ChangeCard
              key={change.change_id}
              change={change}
              onAccept={() => handleDecision(change.change_id, 'accepted')}
              onReject={() => handleDecision(change.change_id, 'rejected')}
              onRevise={(instr) => handleRevise(change.change_id, instr)}
            />
          ))}
          {session.changes.length === 0 ? (
            <p style={{ textAlign: 'center', color: 'var(--text-4)', font: '500 12px/1.4 var(--font)', marginTop: 24 }}>
              No tailoring suggestions have been generated yet.
            </p>
          ) : filteredChanges.length === 0 ? (
            <p style={{ textAlign: 'center', color: 'var(--text-4)', font: '500 12px/1.4 var(--font)', marginTop: 24 }}>
              No changes match the selected filter.
            </p>
          ) : null}
        </div>

        {/* Footer: stats + finalize */}
        <div style={{ padding: '14px 18px', borderTop: '1px solid var(--border)', background: 'var(--surface-2)' }}>
          {/* Stats bar */}
          <div style={{ display: 'flex', gap: 10, marginBottom: 12, font: '600 11px/1 var(--mono)' }}>
            <span style={{ color: 'var(--applied)' }}>✓ {acceptedCount}</span>
            <span style={{ color: 'var(--rejected)' }}>✗ {rejectedCount}</span>
            <span style={{ color: 'var(--review)' }}>⏳ {pendingCount}</span>
          </div>

          {/* Error notice */}
          {error && (
            <div style={{ padding: '8px 10px', borderRadius: 'var(--r-sm)', background: 'var(--failed-soft)', border: '1px solid var(--failed)', color: 'var(--failed)', font: '600 11px/1.4 var(--font)', marginBottom: 10 }}>
              {error}
            </div>
          )}

          {session.status === 'verified' ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <button
                onClick={() => finalResume && window.open(`/api/v1/resumes/${finalResume.id}/download?format=pdf`, '_blank')}
                disabled={!finalResume}
                style={{ width: '100%', height: 36, borderRadius: 'var(--r-md)', background: 'var(--surface-3)', border: '1px solid var(--border)', color: 'var(--text)', font: '700 12px/1 var(--font)', cursor: 'pointer' }}
              >
                <Icon name="download" size={13} /> Download PDF
              </button>
              <button
                disabled={!finalResume || preparing}
                style={{ width: '100%', height: 36, borderRadius: 'var(--r-md)', background: 'var(--accent)', border: '1px solid var(--accent)', color: 'var(--accent-ink)', font: '700 12px/1 var(--font)', cursor: 'pointer', opacity: (!finalResume || preparing) ? 0.55 : 1 }}
                onClick={handlePrepareApplication}
              >
                {preparing ? 'Preparing…' : 'Prepare Application →'}
              </button>
            </div>
          ) : (
            <>
              {pendingCount > 0 && (
                <p style={{ margin: '0 0 8px', font: '600 11px/1.3 var(--font)', color: 'var(--review)' }}>
                  {pendingCount} change{pendingCount !== 1 ? 's' : ''} still pending — resolve all to finalize.
                </p>
              )}
              <button
                disabled={!canFinalize || verifying}
                onClick={handleFinalize}
                style={{ width: '100%', height: 36, borderRadius: 'var(--r-md)', background: 'var(--accent)', border: '1px solid var(--accent)', color: 'var(--accent-ink)', font: '700 12px/1 var(--font)', cursor: 'pointer', opacity: (!canFinalize || verifying) ? 0.55 : 1 }}
              >
                {verifying ? 'Finalizing…' : 'Finalize CV'}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
