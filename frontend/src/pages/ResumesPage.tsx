import { useState } from 'react';
import { useNavigate } from 'react-router-dom';

import Icon from '@/components/ui/Icon';
import ResumeCard from '@/components/resumes/ResumeCard';
import { useResumes, useUploadResume, useOptimizeResume, useGenerateResume, useArchiveResume } from '@/hooks/useResumes';
import { useJobs } from '@/hooks/useJobs';
import { downloadResumeFile } from '@/services/resumeService';
import { useAppStore } from '@/store/useAppStore';
import type { Resume } from '@/types/resume';
import { atsColor, atsPercent, relativeTime } from '@/lib/status';
import { parseResumeContent } from '@/lib/tailoringPreview';
import { tailoringService } from '@/services/tailoringService';

const card: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-1)',
};
const notice: React.CSSProperties = {
  display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 10,
  padding: '30px 20px', color: 'var(--text-3)', font: '500 12.5px/1.4 var(--font)', textAlign: 'center',
};

// ── TYPE META ──────────────────────────────────────────────────────────────
const TYPE_META = {
  base: { label: 'Base', color: 'var(--text-3)', soft: 'var(--surface-2)' },
  tailored: { label: 'Tailored', color: 'var(--interview)', soft: 'var(--interview-soft)' },
  optimized: { label: 'Optimized', color: 'var(--offer)', soft: 'var(--offer-soft)' },
};

// ── STRUCTURED PREVIEW PANEL ───────────────────────────────────────────────
function ResumeContentPreview({ resume }: { resume: Resume }) {
  const t = TYPE_META[resume.type as keyof typeof TYPE_META] ?? TYPE_META.base;
  const structured = parseResumeContent(resume.content_text ?? null);

  const sectionHead: React.CSSProperties = {
    margin: '0 0 8px 0', font: '600 10px/1 var(--mono)', textTransform: 'uppercase',
    letterSpacing: '.1em', color: 'var(--text-4)', borderBottom: '1px solid var(--border)', paddingBottom: 6,
  };

  return (
    <div style={{ position: 'sticky', top: 0, background: 'var(--surface-2)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-1)', overflow: 'hidden', display: 'flex', flexDirection: 'column', height: 'calc(100vh - 120px)', minHeight: 640 }}>
      {/* Panel header */}
      <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', flex: '0 0 auto' }}>
        <span style={{ font: '700 13px/1 var(--font)' }}>Preview</span>
        <span style={{ padding: '3px 8px', borderRadius: 6, background: t.soft, color: t.color, font: '700 9px/1 var(--mono)', letterSpacing: '.04em', textTransform: 'uppercase' }}>{t.label}</span>
      </div>

      {/* Document content */}
      <div aria-label={`Full résumé preview for ${resume.name}`} style={{ flex: '1 1 auto', overflowY: 'auto', margin: 14, padding: '36px 40px', background: '#fff', color: '#18202a', boxShadow: '0 2px 12px rgba(0,0,0,.12)', aspectRatio: '210 / 297', minHeight: 700, font: '400 12.5px/1.65 var(--font)' }}>
        {structured ? (
          <>
            {/* Identity */}
            <div style={{ textAlign: 'center', marginBottom: 18 }}>
              {structured.name && <div style={{ font: '700 18px/1.2 var(--font)', marginBottom: 4 }}>{structured.name}</div>}
              <div style={{ font: '500 11px/1.4 var(--font)', color: 'var(--text-3)', display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '3px 12px' }}>
                {structured.email && <span>{structured.email}</span>}
                {structured.phone && <span>{structured.phone}</span>}
                {structured.location && <span>{structured.location}</span>}
              </div>
            </div>

            {structured.summary && (
              <div style={{ marginBottom: 14 }}>
                <div style={sectionHead}>Summary</div>
                <p style={{ margin: 0, font: '400 12px/1.55 var(--font)' }}>{structured.summary}</p>
              </div>
            )}

            {structured.skills && structured.skills.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <div style={sectionHead}>Skills</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px 8px' }}>
                  {structured.skills.map((s, i) => (
                    <span key={i} style={{ padding: '2px 7px', borderRadius: 4, background: 'var(--surface-2)', border: '1px solid var(--border)', font: '600 10.5px/1 var(--font)', color: 'var(--text-2)' }}>{s}</span>
                  ))}
                </div>
              </div>
            )}

            {structured.experience && structured.experience.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <div style={sectionHead}>Experience</div>
                {structured.experience.map((exp, i) => (
                  <div key={i} style={{ marginBottom: 12 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', marginBottom: 2 }}>
                      <span style={{ font: '700 12px/1 var(--font)' }}>{exp.title}</span>
                      <span style={{ font: '500 10px/1 var(--font)', color: 'var(--text-4)' }}>{exp.duration}</span>
                    </div>
                    {exp.company && <div style={{ font: '600 11px/1 var(--font)', color: 'var(--text-3)', marginBottom: 4 }}>{exp.company}</div>}
                    {exp.description && (
                      <p style={{ margin: 0, font: '400 11.5px/1.5 var(--font)', color: '#344054', whiteSpace: 'pre-wrap' }}>
                        {String(exp.description)}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            )}

            {structured.education && structured.education.length > 0 && (
              <div style={{ marginBottom: 12 }}>
                <div style={sectionHead}>Education</div>
                {structured.education.map((edu, i) => (
                  <div key={i} style={{ marginBottom: 8 }}>
                    <div style={{ font: '700 12px/1.2 var(--font)' }}>{edu.degree}</div>
                    {edu.institution && <div style={{ font: '500 11px/1 var(--font)', color: 'var(--text-3)' }}>{edu.institution}</div>}
                  </div>
                ))}
              </div>
            )}
            {structured.projects && structured.projects.length > 0 && (
              <div style={{ marginBottom: 14 }}>
                <div style={sectionHead}>Projects</div>
                {structured.projects.map((project, i) => <div key={i} style={{ marginBottom: 9 }}><strong>{project.name}</strong>{project.description && <div style={{ whiteSpace: 'pre-wrap' }}>{project.description}</div>}{project.tech && <div style={{ color: '#667085' }}>{project.tech}</div>}</div>)}
              </div>
            )}
            {structured.certifications && structured.certifications.length > 0 && (
              <div style={{ marginBottom: 14 }}><div style={sectionHead}>Certifications</div>{structured.certifications.map((item, i) => <div key={i}>{item}</div>)}</div>
            )}
            {structured.raw_text && <pre style={{ margin: 0, font: '400 11px/1.6 var(--font)', whiteSpace: 'pre-wrap', wordBreak: 'break-word' }}>{structured.raw_text}</pre>}
          </>
        ) : resume.content_text ? (
          // Plain text fallback
          <pre style={{ margin: 0, font: '400 11px/1.6 var(--mono)', whiteSpace: 'pre-wrap', wordBreak: 'break-word', color: 'var(--text-2)' }}>
            {resume.content_text}
          </pre>
        ) : (
          // No content available
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 10, padding: '30px 0', color: 'var(--text-4)' }}>
            <Icon name="file" size={28} />
            <span style={{ font: '500 12px/1.4 var(--font)', textAlign: 'center' }}>
              No preview available.<br />Download to view the full résumé.
            </span>
          </div>
        )}
      </div>

      {/* Panel footer: ATS + downloads */}
      <div style={{ flex: '0 0 auto', padding: '12px 16px', borderTop: '1px solid var(--border)', background: 'var(--surface-2)', display: 'flex', flexDirection: 'column', gap: 8 }}>
        {resume.ats_score != null && (
          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            <span style={{ font: '700 13px/1 var(--mono)', color: atsColor(atsPercent(resume.ats_score)) }}>{atsPercent(resume.ats_score)}</span>
            <span style={{ font: '600 10px/1 var(--mono)', color: 'var(--text-4)' }}>ATS SCORE</span>
          </div>
        )}
        <div style={{ font: '500 11px/1 var(--font)', color: 'var(--text-4)' }}>
          Created {relativeTime(resume.created_at)}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          {resume.has_pdf && (
            <button
              onClick={() => downloadResumeFile(resume.id, 'pdf', resume.name)}
              style={{ flex: '1 1 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, height: 33, borderRadius: 'var(--r-md)', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-2)', font: '700 11px/1 var(--font)', cursor: 'pointer' }}
            >
              <Icon name="download" size={12} /> PDF
            </button>
          )}
          {resume.has_docx && (
            <button
              onClick={() => downloadResumeFile(resume.id, 'docx', resume.name)}
              style={{ flex: '1 1 auto', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 5, height: 33, borderRadius: 'var(--r-md)', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-2)', font: '700 11px/1 var(--font)', cursor: 'pointer' }}
            >
              <Icon name="download" size={12} /> DOCX
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

// ── MAIN PAGE ──────────────────────────────────────────────────────────────
export default function ResumesPage() {
  const navigate = useNavigate();
  const notify = useAppStore((s) => s.showNotification);
  const { data, isLoading, isError } = useResumes();
  const { data: jobData } = useJobs(1, 50);
  const upload = useUploadResume();
  const optimize = useOptimizeResume();
  const generate = useGenerateResume();
  const archive = useArchiveResume();

  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [targetJobId, setTargetJobId] = useState('');

  const resumes = data?.items ?? [];
  const jobs = jobData?.items ?? [];
  const selected = resumes.find((r) => r.id === selectedId) ?? resumes[0] ?? null;
  const baseResumeId = resumes.find((r) => r.type === 'base')?.id ?? resumes[0]?.id ?? null;

  const onUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    upload.mutate(file, {
      onSuccess: () => notify(`Uploaded · ${file.name}`, 'success'),
      onError: () => notify('Upload failed — supported: PDF, DOCX', 'error'),
    });
    e.target.value = '';
  };

  const onOptimize = (r: Resume) =>
    optimize.mutate(r.id, {
      onSuccess: () => notify(`Optimized · ${r.name}`, 'success'),
      onError: () => notify('Could not optimize this résumé', 'error'),
    });

  const onDownload = async (r: Resume, format: 'pdf' | 'docx') => {
    try {
      await downloadResumeFile(r.id, format, r.name);
    } catch {
      notify('Could not download the résumé', 'error');
    }
  };

  const canGenerate = Boolean(baseResumeId) && Boolean(targetJobId) && !generate.isPending;

  const onGenerate = () => {
    if (!baseResumeId || !targetJobId) { notify('Pick a target job first', 'warning'); return; }
    if (!canGenerate) return;
    generate.mutate(
      { base_resume_id: baseResumeId, job_id: targetJobId },
      {
        onSuccess: () => notify('Tailored résumé generated', 'success'),
        onError: () => notify('Could not generate the résumé', 'error'),
      },
    );
  };

  return (
    <div style={{ animation: 'aaUp .4s var(--ease) both' }}>
      {/* Page header */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 20 }}>
        <div>
          <h1 style={{ margin: 0, font: '800 24px/1.1 var(--font)', letterSpacing: '-.03em' }}>Résumés</h1>
          <p style={{ margin: '6px 0 0', font: '500 13px/1.4 var(--font)', color: 'var(--text-3)' }}>
            Your base résumé plus every tailored and optimized variant.
          </p>
        </div>
        {/* Generate tailored — requires base + target job */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
          <select
            aria-label="Target job for generation"
            value={targetJobId}
            onChange={(e) => setTargetJobId(e.target.value)}
            style={{ height: 36, padding: '0 10px', borderRadius: 'var(--r-md)', background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)', font: '600 12px/1 var(--font)', cursor: 'pointer' }}
          >
            <option value="">Select job for tailoring…</option>
            {jobs.map((j) => <option key={j.id} value={j.id}>{j.title} · {j.company}</option>)}
          </select>
          <button
            onClick={onGenerate}
            disabled={!canGenerate}
            title={!baseResumeId ? 'Upload a base résumé first' : !targetJobId ? 'Select a target job' : undefined}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 36, padding: '0 14px', borderRadius: 'var(--r-md)', background: canGenerate ? 'var(--accent)' : 'var(--surface-2)', border: canGenerate ? '1px solid var(--accent)' : '1px solid var(--border)', color: canGenerate ? 'var(--accent-ink)' : 'var(--text-4)', font: '700 12.5px/1 var(--font)', cursor: canGenerate ? 'pointer' : 'not-allowed' }}
          >
            <Icon name="sparkle" size={13} /> {generate.isPending ? 'Generating…' : 'Generate Tailored'}
          </button>
        </div>
      </div>

      {isError ? (
        <div style={{ ...card, ...notice }}>
          <span style={{ color: 'var(--failed)' }}><Icon name="alert" size={16} /></span> Couldn't load your résumés.
        </div>
      ) : isLoading ? (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(206px,1fr))', gap: 14 }}>
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} style={{ ...card, height: 200, background: 'linear-gradient(90deg,var(--surface-2),var(--hover),var(--surface-2))', backgroundSize: '200% 100%', animation: 'aaShimmer 1.3s linear infinite' }} />
          ))}
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: 'minmax(360px,.85fr) minmax(520px,1.15fr)', gap: 18, alignItems: 'start' }}>
          {/* Left: Upload + Grid */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 16, minWidth: 0 }}>
            {/* Upload dropzone */}
            <label style={{ ...card, border: '1px dashed var(--border-2)', padding: 22, display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: 11, cursor: 'pointer' }}>
              <span style={{ width: 46, height: 46, borderRadius: 12, background: 'var(--accent-soft)', border: '1px solid var(--accent-line)', display: 'grid', placeItems: 'center', color: 'var(--accent)' }}><Icon name="upload" size={20} /></span>
              <span>
                <span style={{ display: 'block', font: '700 13.5px/1.2 var(--font)', color: 'var(--text)' }}>Drag &amp; drop a résumé</span>
                <span style={{ display: 'block', font: '500 12px/1.4 var(--font)', color: 'var(--text-3)', marginTop: 4 }}>PDF or DOCX — we parse skills and sections automatically</span>
              </span>
              <span style={{ height: 34, padding: '0 16px', display: 'inline-flex', alignItems: 'center', borderRadius: 'var(--r-md)', background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)', font: '700 12px/1 var(--font)' }}>
                {upload.isPending ? 'Uploading…' : 'Browse files'}
              </span>
              <input type="file" accept=".pdf,.docx,.doc" aria-label="Upload résumé" onChange={onUpload} style={{ position: 'absolute', width: 1, height: 1, opacity: 0 }} />
            </label>

            {resumes.length === 0 ? (
              <div style={{ ...card, ...notice, flexDirection: 'column', gap: 8, padding: '40px 20px' }}>
                <div style={{ display: 'grid', placeItems: 'center', width: 44, height: 44, borderRadius: 12, background: 'var(--accent-soft)', color: 'var(--accent)' }}><Icon name="file" size={20} /></div>
                <div style={{ font: '700 14px/1.2 var(--font)', color: 'var(--text)' }}>No résumés yet</div>
                <span>Upload a PDF or DOCX to get started.</span>
              </div>
            ) : (
              <>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                  <span style={{ font: '700 13px/1 var(--font)' }}>Your résumés</span>
                  <span style={{ font: '600 11px/1 var(--mono)', color: 'var(--text-4)' }}>{resumes.length} {resumes.length === 1 ? 'VARIANT' : 'VARIANTS'}</span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill,minmax(220px,1fr))', gap: 13 }}>
                  {resumes.map((r) => (
                    <ResumeCard
                      key={r.id}
                      resume={r}
                      jobLabel={jobs.find((j) => j.id === r.job_id)?.title}
                      selected={selected?.id === r.id}
                      onSelect={() => setSelectedId(r.id)}
                      onOptimize={() => onOptimize(r)}
                      onDownload={() => onDownload(r, r.has_pdf ? 'pdf' : 'docx')}
                      onRevise={() => {
                        void tailoringService.openRevisionSession(r.id).then((session) => navigate(`/cv-tailoring/${session.id}`)).catch(() => notify('Could not open the revision workbench.', 'error'));
                      }}
                      onArchive={() => {
                        archive.mutate(r.id, {
                          onSuccess: () => { if (selectedId === r.id) setSelectedId(null); notify(`Archived · ${r.name}`, 'success'); },
                          onError: () => notify('Could not archive this résumé', 'error'),
                        });
                      }}
                      optimizing={optimize.isPending}
                    />
                  ))}
                </div>
              </>
            )}
          </div>

          {/* Right: Structured preview panel */}
          {selected && <ResumeContentPreview resume={selected} />}
        </div>
      )}
    </div>
  );
}
