import { useLocation } from 'react-router-dom';

import Icon from '@/components/ui/Icon';
import { useUiStore } from '@/store/useUiStore';
import { useDashboardStats } from '@/hooks/useAnalytics';
import { useTranslation } from 'react-i18next';
import { BRAND } from '@/lib/brand';

const CRUMB: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/jobs': 'Opportunities',
  '/applications': 'Applications',
  '/resumes': 'Résumés',
  '/analytics': 'Insights',
  '/settings': 'Settings',
  '/profile': 'Candidate Profile',
  '/workflow': 'Import Opportunity',
  '/admin': 'System Health',
};

export default function Header() {
  const { t, i18n } = useTranslation();
  const { pathname } = useLocation();
  const toggleSidebar = useUiStore((s) => s.toggleSidebar);
  const setPaletteOpen = useUiStore((s) => s.setPaletteOpen);
  const { data: stats } = useDashboardStats();
  const current = CRUMB[pathname] ?? BRAND.name;
  const isMac = /Mac|iP(hone|ad|od)/.test(navigator.platform ?? '');

  const switchLang = (lang: string) => {
    i18n.changeLanguage(lang);
    useUiStore.getState().setLanguage(lang);
  };

  return (
    <header
      style={{
        flex: '0 0 auto', height: 56, display: 'flex', alignItems: 'center', gap: 12, padding: '0 20px',
        borderBottom: '1px solid var(--border)', background: 'color-mix(in srgb,var(--bg) 82%,transparent)',
        backdropFilter: 'blur(10px)', position: 'relative', zIndex: 15,
      }}
    >
      {/* Sidebar toggle */}
      <button
        onClick={toggleSidebar}
        aria-label="Toggle sidebar"
        style={{
          flex: '0 0 auto', width: 32, height: 32, borderRadius: 'var(--r-md)', background: 'transparent',
          border: '1px solid transparent', color: 'var(--text-3)', cursor: 'pointer', display: 'grid', placeItems: 'center',
        }}
      >
        <Icon name="panel" size={18} />
      </button>

      {/* Breadcrumb */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: '0 0 auto' }}>
        <span style={{ font: '600 12px/1 var(--font)', color: 'var(--text-3)', whiteSpace: 'nowrap' }}>{t('workspace')}</span>
        <span style={{ color: 'var(--text-4)', display: 'grid', placeItems: 'center' }}><Icon name="chevR" size={13} /></span>
        <span style={{ font: '700 13.5px/1 var(--font)', color: 'var(--text)', whiteSpace: 'nowrap', letterSpacing: '-.015em' }}>{current}</span>
      </div>

      <div style={{ flex: '1 1 auto' }} />

      {/* Command palette trigger */}
      <button
        onClick={() => setPaletteOpen(true)}
        aria-label="Open command palette"
        style={{
          flex: '0 1 260px', minWidth: 110, display: 'flex', alignItems: 'center', gap: 9, height: 34,
          padding: '0 10px 0 11px', borderRadius: 'var(--r-md)', background: 'var(--surface-3)',
          border: '1px solid var(--border)', color: 'var(--text-3)', cursor: 'pointer', textAlign: 'start',
        }}
      >
        <span style={{ flex: '0 0 auto', display: 'grid', placeItems: 'center' }}><Icon name="search" size={15} /></span>
        <span style={{ flex: '1 1 auto', font: '500 12px/1 var(--font)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}>
          Search jobs, applications…
        </span>
        <span style={{ flex: '0 0 auto', display: 'flex', gap: 2 }}>
          <kbd style={{ font: '600 10px/16px var(--mono)', color: 'var(--text-3)', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, padding: '0 4px', minWidth: 16, textAlign: 'center' }}>{isMac ? '⌘' : 'Ctrl'}</kbd>
          <kbd style={{ font: '600 10px/16px var(--mono)', color: 'var(--text-3)', background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 4, padding: '0 5px' }}>K</kbd>
        </span>
      </button>

      {/* Language switcher — inline styles, no Tailwind */}
      <div style={{ display: 'flex', alignItems: 'center', borderRadius: 'var(--r-sm)', overflow: 'hidden', border: '1px solid var(--border)' }}>
        <button
          onClick={() => switchLang('ar')}
          aria-label="Switch to Arabic"
          style={{
            padding: '5px 10px', cursor: 'pointer', font: '600 12px/1 var(--font)',
            background: i18n.language === 'ar' ? 'var(--accent)' : 'transparent',
            color: i18n.language === 'ar' ? 'var(--accent-ink)' : 'var(--text-3)',
            border: 'none',
          }}
        >
          عربي
        </button>
        <button
          onClick={() => switchLang('en')}
          aria-label="Switch to English"
          style={{
            padding: '5px 10px', cursor: 'pointer', font: '600 12px/1 var(--font)',
            background: i18n.language === 'en' ? 'var(--accent)' : 'transparent',
            color: i18n.language === 'en' ? 'var(--accent-ink)' : 'var(--text-3)',
            border: 'none',
          }}
        >
          EN
        </button>
      </div>

      {/* LLM cost pill */}
      {stats && (
        <div
          title="Month-to-date LLM cost"
          style={{ flex: '0 0 auto', display: 'flex', alignItems: 'center', gap: 7, height: 34, padding: '0 11px', borderRadius: 'var(--r-md)', background: 'var(--surface-3)', border: '1px solid var(--border)' }}
        >
          <span style={{ color: 'var(--accent)', display: 'grid', placeItems: 'center' }}><Icon name="dollar" size={14} /></span>
          <span style={{ font: '700 12px/1 var(--mono)', color: 'var(--text)' }}>${stats.total_llm_cost_usd.toFixed(2)}</span>
        </div>
      )}
    </header>
  );
}
