import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';

import Icon, { type IconName } from '@/components/ui/Icon';
import { useDashboardStats } from '@/hooks/useAnalytics';
import { useApplications } from '@/hooks/useApplications';
import { useAuthStore } from '@/store/useAuthStore';
import { statusMeta, atsColor, atsPercent, relativeTime } from '@/lib/status';
import type { Application } from '@/types/application';
import { useDashboardDismissals, useDismissDashboardItem } from '@/hooks/useDashboardDismissals';
import { dashboardFingerprint } from '@/services/dashboardService';

function greeting(t: any): string {
  const h = new Date().getHours();
  if (h < 12) return t('good_morning');
  if (h < 18) return t('good_afternoon');
  return t('good_evening');
}

function firstName(name?: string | null, email?: string): string {
  if (name && name.trim()) return name.trim().split(/\s+/)[0] ?? name;
  return (email ?? 'there').split('@')[0] ?? 'there';
}

const card: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-1)',
};

const fmt = (n?: number) => (n == null ? '—' : new Intl.NumberFormat().format(n));

export default function DashboardPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const user = useAuthStore((s) => s.user);
  const { data: stats } = useDashboardStats();
  const { data: apps, isLoading } = useApplications(1, 20);
  const { data: dismissals = [] } = useDashboardDismissals();
  const dismiss = useDismissDashboardItem();

  const items = apps?.items ?? [];
  const live = items.find((a) => a.status === 'applying');
  const hidden = (a: Application, type: 'application' | 'activity') => dismissals.some((d) =>
    d.entity_type === type && d.entity_id === a.id && d.fingerprint === dashboardFingerprint(a.status, a.updated_at),
  );
  const needsAction = (a: Application) => ['pending_review', 'queued', 'failed', 'waiting_for_review', 'submission_blocked'].includes(a.status);
  const actionNeeded = items.filter((a) => needsAction(a) && !hidden(a, 'application'));
  const recentlyActive = items.filter((a) => !needsAction(a) && !hidden(a, 'activity'));

  const kpis: { label: string; value: string; icon: IconName; color: string }[] = [
    { label: 'Needs Review', value: fmt(stats?.applications_pending), icon: 'alert', color: 'var(--review)' },
    { label: 'Interviews', value: fmt(stats?.applications_interview), icon: 'activity', color: 'var(--interview)' },
    { label: 'Offers', value: fmt(stats?.applications_offer), icon: 'target', color: 'var(--offer)' },
    { label: 'Avg ATS', value: stats ? String(atsPercent(stats.avg_ats_score)) : '—', icon: 'gauge', color: 'var(--accent)' }
  ];

  const renderApplicationCard = (a: Application, feed: 'application' | 'activity') => {
    const sm = statusMeta(a.status);
    return (
      <div
        key={a.id}
        onClick={() => navigate(`/applications/${a.id}`)}
        style={{ ...card, padding: 16, cursor: 'pointer', display: 'flex', flexDirection: 'column', gap: 12, transition: 'transform 0.2s, box-shadow 0.2s' }}
        onMouseOver={e => e.currentTarget.style.borderColor = 'var(--accent)'}
        onMouseOut={e => e.currentTarget.style.borderColor = 'var(--border)'}
      >
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 12 }}>
          <div style={{ minWidth: 0 }}>
            <div style={{ font: '800 15px/1.2 var(--font)', color: 'var(--text)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{a.job_title ?? 'Untitled role'}</div>
            <div style={{ font: '600 13px/1.4 var(--font)', color: 'var(--text-2)', marginTop: 4 }}>{a.company ?? 'Unknown company'}</div>
          </div>
          <span style={{ flex: '0 0 auto', display: 'inline-flex', alignItems: 'center', gap: 6, height: 22, padding: '0 8px', borderRadius: 999, background: sm.soft, color: sm.color, font: '700 10px/1 var(--font)', textTransform: 'uppercase' }}>
            {sm.label}
          </span>
        </div>

        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto', paddingTop: 12, borderTop: '1px solid var(--border)' }}>
          <span style={{ font: '500 12px/1 var(--font)', color: 'var(--text-3)' }}>{relativeTime(a.updated_at || a.created_at)}</span>
          <button
            onClick={(event) => {
              event.stopPropagation();
              dismiss.mutate({ entity_type: feed, entity_id: a.id, fingerprint: dashboardFingerprint(a.status, a.updated_at) });
            }}
            disabled={dismiss.isPending}
            aria-label={`Dismiss ${a.job_title ?? 'application'} from dashboard`}
            style={{ marginInlineStart: 'auto', marginInlineEnd: 10, border: 0, background: 'none', color: 'var(--text-3)', cursor: 'pointer', font: '600 11px/1 var(--font)' }}
          >Dismiss</button>
          {a.ats_score != null && (
            <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
              <span style={{ font: '700 10px/1 var(--mono)', color: 'var(--text-3)' }}>ATS</span>
              <span style={{ font: '800 14px/1 var(--mono)', color: atsColor(atsPercent(a.ats_score)) }}>{atsPercent(a.ats_score)}</span>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div style={{ animation: 'aaUp .4s var(--ease) both' }}>
      {/* Greeting */}
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, flexWrap: 'wrap', marginBottom: 32 }}>
        <div>
          <h1 style={{ margin: 0, font: '800 28px/1.1 var(--font)', letterSpacing: '-.03em' }}>
            {greeting(t)}, {firstName(user?.full_name, user?.email)}
          </h1>
          <p style={{ margin: '8px 0 0', font: '500 14px/1.4 var(--font)', color: 'var(--text-3)' }}>
            Your agent applied to <span style={{ color: 'var(--applied)', fontWeight: 700 }}>{fmt(stats?.applications_applied)} {stats?.applications_applied === 1 ? 'role' : 'roles'}</span> and flagged{' '}
            <span style={{ color: 'var(--review)', fontWeight: 700 }}>{fmt(stats?.applications_pending)}</span> for review.
          </p>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <button
            onClick={() => navigate('/workflow')}
            style={{ display: 'flex', alignItems: 'center', gap: 8, height: 40, padding: '0 16px', borderRadius: 'var(--r-md)', background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-2)', font: '700 13px/1 var(--font)', cursor: 'pointer' }}
          >
            <span style={{ display: 'grid', placeItems: 'center', color: 'var(--text-3)' }}><Icon name="plus" size={16} /></span>
            Import Opportunity
          </button>
          <button
            onClick={() => navigate('/jobs')}
            style={{ display: 'flex', alignItems: 'center', gap: 8, height: 40, padding: '0 18px', borderRadius: 'var(--r-md)', background: 'var(--accent)', border: '1px solid var(--accent)', color: 'var(--accent-ink)', font: '700 13px/1 var(--font)', cursor: 'pointer', boxShadow: '0 0 0 1px var(--accent-line),0 6px 16px -8px var(--accent-glow)' }}
          >
            <span style={{ display: 'grid', placeItems: 'center' }}><Icon name="search" size={16} sw={2} /></span>
            Find Jobs
          </button>
        </div>
      </div>

      {/* Live now — an in-flight application (agent applying right now) */}
      {live && (
        <div
          onClick={() => navigate(`/applications/${live.id}`)}
          style={{ background: 'var(--surface)', border: '1px solid var(--accent-line)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-1),inset 0 0 40px -30px var(--accent-glow)', padding: 20, marginBottom: 24, display: 'flex', alignItems: 'center', gap: 16, cursor: 'pointer' }}
        >
          <span style={{ position: 'relative', width: 12, height: 12, flex: '0 0 auto' }}>
            <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--accent)', animation: 'aaPulse 1.6s infinite' }} />
            <span style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: 'var(--accent)', animation: 'aaRing 1.6s infinite' }} />
          </span>
          <div style={{ flex: '1 1 auto', minWidth: 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ font: '800 13px/1 var(--font)', color: 'var(--accent)', textTransform: 'uppercase', letterSpacing: '.04em' }}>Live now</span>
              <span style={{ font: '600 11px/1 var(--mono)', color: 'var(--text-4)' }}>agent applying</span>
            </div>
            <div style={{ font: '800 16px/1.3 var(--font)', marginTop: 8, whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>{live.job_title ?? 'Untitled role'}</div>
            <div style={{ font: '600 13px/1.3 var(--font)', color: 'var(--text-3)', marginTop: 4 }}>{live.company ?? '—'}</div>
          </div>
          {live.ats_score != null && (
            <div style={{ flex: '0 0 auto', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
              <span style={{ font: '800 24px/1 var(--mono)', color: atsColor(atsPercent(live.ats_score)) }}>{atsPercent(live.ats_score)}</span>
              <span style={{ font: '700 9px/1 var(--mono)', letterSpacing: '.1em', color: 'var(--text-4)' }}>ATS</span>
            </div>
          )}
        </div>
      )}

      {/* KPI row */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 16, marginBottom: 32 }}>
        {kpis.map((k, i) => (
          <div key={k.label} style={{ ...card, padding: '20px', overflow: 'hidden', animation: 'aaUp .5s var(--ease) both', animationDelay: `${i * 40}ms` }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
              <span style={{ font: '700 12px/1 var(--font)', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '.06em' }}>{k.label}</span>
              <span style={{ display: 'grid', placeItems: 'center', color: k.color }}><Icon name={k.icon} size={18} /></span>
            </div>
            <div style={{ font: '800 32px/1 var(--font)', letterSpacing: '-.03em', color: 'var(--text)', fontVariantNumeric: 'tabular-nums' }}>{k.value}</div>
          </div>
        ))}
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 32, alignItems: 'start' }}>
        {/* Action Needed */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={{ margin: 0, font: '800 18px/1 var(--font)', letterSpacing: '-.02em' }}>Action Needed</h2>
            {actionNeeded.length > 0 && <span style={{ background: 'var(--review-soft)', color: 'var(--review)', padding: '4px 8px', borderRadius: 999, font: '700 11px/1 var(--font)' }}>{actionNeeded.length}</span>}
          </div>
          {isLoading ? (
             <div style={{ padding: 8 }}>
             {Array.from({ length: 3 }).map((_, i) => (
               <div key={i} style={{ height: 100, margin: '0 0 16px', borderRadius: 'var(--r-md)', background: 'linear-gradient(90deg,var(--surface-2),var(--hover),var(--surface-2))', backgroundSize: '200% 100%', animation: 'aaShimmer 1.3s linear infinite' }} />
             ))}
           </div>
          ) : actionNeeded.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', background: 'var(--surface-2)', borderRadius: 'var(--r-lg)', border: '1px dashed var(--border-2)' }}>
              <div style={{ display: 'flex', justifyContent: 'center', color: 'var(--text-4)', marginBottom: 12 }}><Icon name="check" size={32} /></div>
              <div style={{ font: '700 15px/1.4 var(--font)', color: 'var(--text-2)' }}>You're caught up</div>
              <div style={{ font: '500 13px/1.4 var(--font)', color: 'var(--text-3)', marginTop: 4 }}>No opportunities currently need your attention.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {actionNeeded.map((a) => renderApplicationCard(a, 'application'))}
            </div>
          )}
        </div>

        {/* Recently Active */}
        <div>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 16 }}>
            <h2 style={{ margin: 0, font: '800 18px/1 var(--font)', letterSpacing: '-.02em' }}>Recently Active</h2>
            <div style={{ display: 'flex', gap: 10 }}>
              {recentlyActive.length > 0 && <button onClick={() => recentlyActive.forEach((a) => dismiss.mutate({ entity_type: 'activity', entity_id: a.id, fingerprint: dashboardFingerprint(a.status, a.updated_at) }))} style={{ background: 'none', border: 'none', color: 'var(--text-3)', font: '600 12px/1 var(--font)', cursor: 'pointer' }}>Clear recent activity</button>}
              <button onClick={() => navigate('/applications')} style={{ background: 'none', border: 'none', color: 'var(--text-3)', font: '600 13px/1 var(--font)', cursor: 'pointer' }}>View All &rarr;</button>
            </div>
          </div>
          {isLoading ? (
            <div style={{ padding: 8 }}>
             {Array.from({ length: 3 }).map((_, i) => (
               <div key={i} style={{ height: 100, margin: '0 0 16px', borderRadius: 'var(--r-md)', background: 'linear-gradient(90deg,var(--surface-2),var(--hover),var(--surface-2))', backgroundSize: '200% 100%', animation: 'aaShimmer 1.3s linear infinite' }} />
             ))}
           </div>
          ) : recentlyActive.length === 0 ? (
            <div style={{ textAlign: 'center', padding: '40px 20px', background: 'var(--surface-2)', borderRadius: 'var(--r-lg)', border: '1px dashed var(--border-2)' }}>
              <div style={{ font: '700 15px/1.4 var(--font)', color: 'var(--text-3)' }}>No recent activity yet.</div>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {recentlyActive.slice(0, 5).map((a) => renderApplicationCard(a, 'activity'))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// Notice component not needed inline anymore
