import type { ReactNode } from 'react';
import React from 'react';

import Icon from '@/components/ui/Icon';
import type { Job, JobAnalysisResponse, MatchVerdict } from '@/types/job';

const PLAT_COLOR: Record<string, string> = {
  linkedin: 'var(--approved)', indeed: 'var(--interview)', glassdoor: 'var(--applied)', exa: 'var(--accent)',
};

interface JobDrawerProps {
  job: Job;
  analysis: JobAnalysisResponse | null;
  analyzing: boolean;
  baseResumeId: string | null;
  generating: boolean;
  onClose: () => void;
  onGenerate: () => void;
}

const VERDICT_LABELS: Record<MatchVerdict, { label: string, color: string }> = {
  STRONG_MATCH: { label: 'STRONG MATCH', color: 'var(--approved)' },
  GOOD_MATCH: { label: 'GOOD MATCH', color: 'var(--accent)' },
  PARTIAL_MATCH: { label: 'PARTIAL MATCH', color: 'var(--interview)' },
  WEAK_MATCH: { label: 'WEAK MATCH', color: 'var(--rejected)' },
  INSUFFICIENT_DATA: { label: 'INSUFFICIENT DATA', color: 'var(--text-3)' },
};

function Tag({ children, onClick }: { children: ReactNode; onClick?: () => void }) {
  return (
    <span onClick={onClick} style={{ cursor: onClick ? 'pointer' : 'default', padding: '3px 8px', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--border)', font: '500 11px/1.2 var(--font)', color: 'var(--text-2)' }}>
      {children}
    </span>
  );
}

export default function JobDrawer({ job, analysis, analyzing, baseResumeId, generating, onClose, onGenerate }: JobDrawerProps) {
  const [showDetailed, setShowDetailed] = React.useState(false);
  const paras = job.description.split(/\n\n+/).map((p) => p.trim()).filter(Boolean);
  const canGenerate = Boolean(baseResumeId) && !generating;
  const generateHint = !baseResumeId ? 'Upload a resume first' : undefined;

  const scoreDisplay = analysis?.total_score != null ? `${analysis.total_score}%` : 'Not enough information';
  const verdictInfo = analysis ? VERDICT_LABELS[analysis.verdict] : null;

  return (
    <>
      <div onClick={onClose} role="presentation" style={{ position: 'fixed', inset: 0, zIndex: 70, background: 'rgba(4,7,9,.5)', backdropFilter: 'blur(3px)', animation: 'aaPop .16s var(--ease)' }} />
      <aside role="dialog" aria-label="Job details" style={{ position: 'fixed', top: 0, right: 0, bottom: 0, width: 'min(94vw,540px)', zIndex: 71, background: 'var(--surface)', borderLeft: '1px solid var(--border-2)', boxShadow: 'var(--shadow-pop)', display: 'flex', flexDirection: 'column', fontFamily: 'var(--font)', color: 'var(--text)', animation: 'aaDrawer .28s var(--ease)' }}>
        <div style={{ display: 'flex', alignItems: 'flex-start', gap: 12, padding: '20px 22px', borderBottom: '1px solid var(--border)' }}>
          <div style={{ flex: '1 1 auto', minWidth: 0 }}>
            <div style={{ font: '800 18px/1.2 var(--font)', letterSpacing: '-.02em' }}>{job.title}</div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap', marginTop: 8, font: '500 12.5px/1 var(--font)', color: 'var(--text-3)' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5, color: 'var(--text-2)' }}><Icon name="building" size={13} /> {job.company}</span>
              <span style={{ color: 'var(--text-4)' }}>•</span>
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}><Icon name="mappin" size={13} /> {job.location || (job.remote ? 'Remote' : '—')}</span>
            </div>
            <div style={{ display: 'flex', gap: 7, flexWrap: 'wrap', marginTop: 10 }}>
              <span style={{ padding: '3px 8px', borderRadius: 6, background: 'var(--surface-2)', border: '1px solid var(--border)', font: '600 10.5px/1 var(--mono)', color: PLAT_COLOR[job.platform] ?? 'var(--text-3)' }}>{job.platform}</span>
              {job.remote && <Tag>Remote</Tag>}
              {job.job_type && <Tag>{job.job_type}</Tag>}
            </div>
          </div>
          <button onClick={onClose} aria-label="Close" style={{ flex: '0 0 auto', width: 32, height: 32, borderRadius: 'var(--r-md)', background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text-3)', cursor: 'pointer', display: 'grid', placeItems: 'center', font: '400 18px/1 var(--font)' }}>×</button>
        </div>

        <div style={{ flex: '1 1 auto', overflowY: 'auto', padding: '20px 22px', display: 'flex', flexDirection: 'column', gap: 20 }}>
          {analyzing ? (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-3)', font: '500 12.5px/1 var(--font)' }}>Analyzing match…</div>
          ) : analysis && verdictInfo ? (
            <>
              {analysis.blockers && analysis.blockers.length > 0 && (
                <div style={{ background: 'var(--rejected-soft)', border: '1px solid var(--rejected)', borderRadius: 'var(--r-lg)', padding: 16 }}>
                  <h4 style={{ margin: '0 0 8px 0', color: 'var(--rejected)', display: 'flex', gap: 8, alignItems: 'center' }}><Icon name="alert" size={16} /> Potential blockers</h4>
                  <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--text-2)', fontSize: '13px' }}>
                    {analysis.blockers.map((r: string, i: number) => <li key={i}>{r}</li>)}
                  </ul>
                </div>
              )}

              <div style={{ background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', padding: 20, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ margin: 0, fontSize: 18, color: verdictInfo.color }}>{verdictInfo.label}</h3>
                    <div style={{ fontSize: 24, fontWeight: 800, marginTop: 4 }}>{scoreDisplay}</div>
                  </div>
                  {analysis.data_quality !== 'HIGH' && (
                    <div style={{ textAlign: 'right', fontSize: 11, color: 'var(--text-3)', maxWidth: 150 }}>
                      <span style={{ fontWeight: 600 }}>Source quality: {analysis.data_quality}</span>
                      <div style={{ marginTop: 2 }}>{analysis.data_quality_explanation}</div>
                    </div>
                  )}
                </div>
                
                <div>
                  <h4 style={{ margin: '0 0 4px 0', fontSize: 13, color: 'var(--text-2)' }}>Why this is a {verdictInfo.label.toLowerCase()}</h4>
                  <p style={{ margin: 0, fontSize: 13, lineHeight: 1.5, color: 'var(--text-2)' }}>{analysis.explanation}</p>
                </div>
              </div>

              {analysis.strong_matches?.length > 0 && (
                <div>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: 14, color: 'var(--text-1)' }}>Strong matches</h4>
                  <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--text-2)', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {analysis.strong_matches.map((s, i) => <li key={i}>{s}</li>)}
                  </ul>
                </div>
              )}

              {(analysis.gaps?.length > 0 || analysis.critical_gaps?.length > 0) && (
                <div>
                  <h4 style={{ margin: '0 0 8px 0', fontSize: 14, color: 'var(--text-1)' }}>Gaps</h4>
                  <ul style={{ margin: 0, paddingLeft: 20, color: 'var(--text-2)', fontSize: '13px', display: 'flex', flexDirection: 'column', gap: 4 }}>
                    {analysis.critical_gaps?.map((g, i) => <li key={`c-${i}`} style={{color: 'var(--rejected)'}}><strong>Critical:</strong> {g}</li>)}
                    {analysis.gaps?.map((g, i) => <li key={`g-${i}`}>△ {g}</li>)}
                  </ul>
                </div>
              )}

              <div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
                  <h4 style={{ margin: 0, fontSize: 14, color: 'var(--text-1)' }}>Requirements</h4>
                  <button 
                    onClick={() => setShowDetailed(!showDetailed)}
                    style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12, padding: 0 }}
                  >
                    {showDetailed ? 'Hide detailed analysis' : 'View detailed analysis'}
                  </button>
                </div>
                
                <div style={{ fontSize: 13, color: 'var(--text-3)' }}>
                  {analysis.requirement_analysis.filter(r => r.status === 'MATCH').length} of {analysis.requirement_analysis.length} supported
                </div>

                {showDetailed && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 12 }}>
                    {analysis.requirement_analysis.map(req => (
                      <div key={req.requirement_id} style={{ padding: 12, borderRadius: 'var(--r-md)', background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                          <strong style={{ fontSize: 13, color: req.status === 'MATCH' ? 'var(--approved)' : req.status === 'PARTIAL' ? 'var(--interview)' : req.status === 'GAP' ? 'var(--rejected)' : 'var(--text-3)' }}>
                            {req.status === 'MATCH' ? '✓ ' : req.status === 'PARTIAL' ? '— ' : req.status === 'GAP' ? '△ ' : '? '}
                            {req.normalized_requirement}
                          </strong>
                          <span style={{ fontSize: 11, color: 'var(--text-4)' }}>{req.importance}</span>
                        </div>
                        <p style={{ margin: '4px 0', fontSize: 12, color: 'var(--text-2)' }}>{req.explanation}</p>
                        {req.evidence_ids?.length > 0 && (
                          <div style={{ fontSize: 11, color: 'var(--text-4)', marginTop: 4 }}>
                            <strong>Evidence:</strong> {req.evidence_ids.join(', ')}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            </>
          ) : (
            <div style={{ padding: 24, textAlign: 'center', color: 'var(--text-3)', font: '500 12.5px/1 var(--font)' }}>No match analysis yet.</div>
          )}

          <div>
            <h3 style={{ margin: '0 0 12px 0', font: '600 14.5px/1.2 var(--font)', color: 'var(--text-1)' }}>Description</h3>
            <div style={{ font: '400 13px/1.65 var(--font)', color: 'var(--text-2)' }}>
              {paras.map((p, i) => <p key={i} style={{ margin: '0 0 1em 0' }}>{p}</p>)}
            </div>
          </div>
        </div>

        <div style={{ flex: '0 0 auto', padding: '16px 22px', borderTop: '1px solid var(--border)', display: 'flex', gap: 12, background: 'var(--surface)' }}>
          <a href={job.url} target="_blank" rel="noreferrer" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '0 16px', height: 40, borderRadius: 'var(--r-md)', border: '1px solid var(--border)', background: 'var(--surface-2)', color: 'var(--text)', font: '500 13.5px/1 var(--font)', textDecoration: 'none' }}>
            <Icon name="ext" size={15} /> Original Post
          </a>
          {analysis && analysis.recommendation !== 'skip' && (
            <button
              onClick={onGenerate}
              disabled={!canGenerate}
              title={generateHint}
              style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, padding: '0 16px', height: 40, borderRadius: 'var(--r-md)', border: 'none', background: 'var(--accent)', color: '#fff', font: '600 13.5px/1 var(--font)', cursor: canGenerate ? 'pointer' : 'not-allowed', opacity: canGenerate ? 1 : 0.6 }}
            >
              {generating ? <span className="spin" style={{display: 'flex'}}><Icon name="spinner" size={16} /></span> : <Icon name="sparkle" size={16} />}
              {generating ? 'Tailoring...' : 'Tailor Resume'}
            </button>
          )}
        </div>
      </aside>
    </>
  );
}



