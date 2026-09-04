import { useEffect, useState } from 'react';

import Icon from '@/components/ui/Icon';
import { useSettings, useUpdateSettings, useLLMProviders } from '@/hooks/useSettings';
import { getTelegramStatus, getTelegramLinkToken, disconnectTelegram, testTelegramNotification } from '@/services/telegram';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { useAppStore } from '@/store/useAppStore';
import type { Settings } from '@/types/settings';

const card: React.CSSProperties = {
  background: 'var(--surface)', border: '1px solid var(--border)', borderRadius: 'var(--r-lg)', boxShadow: 'var(--shadow-1)', padding: 18,
};
const buttonStyle = (bg: string, color: string, border: string): React.CSSProperties => ({
  background: bg, color, border, padding: '6px 12px', borderRadius: 'var(--r-md)', font: '600 12.5px/1 var(--font)', cursor: 'pointer'
});

function TelegramSettings() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ['telegramStatus'], queryFn: getTelegramStatus });
  const [tokenData, setTokenData] = useState<{token: string, bot_url: string} | null>(null);

  const getLink = async () => {
    try {
      const res = await getTelegramLinkToken();
      setTokenData(res);
    } catch(e) {
      console.error("Failed to get Telegram token:", e);
    }
  };

  const disconnect = async () => {
    try {
      await disconnectTelegram();
      qc.invalidateQueries({ queryKey: ['telegramStatus'] });
    } catch(e) {}
  };

  const testNotif = async () => {
    try { await testTelegramNotification(); } catch(e) {}
  };

  if (isLoading) return <div style={{...card, marginBottom: 14}}><p>Loading Telegram status...</p></div>;

  return (
    <section style={{ ...card, marginBottom: 14 }}>
      <SectionTitle icon="smartphone" title="Telegram Integration" sub="Get mobile notifications and send jobs to AutoApply." />
      <div style={{ marginTop: 14, display: 'flex', flexDirection: 'column', gap: 12 }}>
        <p style={{ margin: 0, font: '500 13px/1.4 var(--font)', color: 'var(--text-1)' }}>
          Status: <strong style={{ color: data?.status === 'CONNECTED' ? 'var(--primary)' : 'var(--text-3)' }}>{data?.status}</strong>
        </p>
        
        {data?.status === 'CONNECTED' ? (
          <div style={{ display: 'flex', gap: 10 }}>
            <button onClick={testNotif} style={buttonStyle('var(--surface)', 'var(--text-1)', '1px solid var(--border)')}>Test Notification</button>
            <button onClick={disconnect} style={buttonStyle('var(--failed-bg)', 'var(--failed)', 'none')}>Disconnect</button>
          </div>
        ) : (
          <div>
            {!tokenData ? (
              <button onClick={getLink} style={buttonStyle('var(--primary)', 'white', 'none')}>Connect Telegram</button>
            ) : (
              <a href={tokenData.bot_url} target="_blank" rel="noreferrer" style={{ ...buttonStyle('var(--primary)', 'white', 'none'), display: 'inline-block', textDecoration: 'none' }}>Open Telegram Bot</a>
            )}
            {tokenData && (
              <p style={{ margin: '8px 0 0 0', font: '400 12px/1.4 var(--font)', color: 'var(--text-2)' }}>
                Click the button above to open Telegram and start the bot to complete linking.
              </p>
            )}
          </div>
        )}
      </div>
    </section>
  );
}

const PLATFORMS = ['linkedin', 'indeed', 'glassdoor', 'exa'];
const controlStyle: React.CSSProperties = {
  height: 36, padding: '0 11px', borderRadius: 'var(--r-md)', background: 'var(--surface-3)',
  border: '1px solid var(--border)', color: 'var(--text)', font: '500 12.5px/1 var(--font)', outline: 'none',
};

export default function SettingsPage() {
  const notify = useAppStore((s) => s.showNotification);
  const { data, isError, refetch } = useSettings();
  const { data: providers } = useLLMProviders();
  const update = useUpdateSettings();
  const [draft, setDraft] = useState<Settings | null>(null);

  useEffect(() => {
    if (data) setDraft(data);
  }, [data]);

  if (isError && !draft) {
    return (
      <div style={{ ...card, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 12, padding: '40px 20px', textAlign: 'center' }}>
        <span style={{ color: 'var(--failed)', display: 'grid', placeItems: 'center' }}><Icon name="alert" size={18} /></span>
        <span style={{ font: '600 13px/1.4 var(--font)', color: 'var(--text-2)' }}>Couldn't load your settings.</span>
        <button
          onClick={() => void refetch()}
          style={{ display: 'inline-flex', alignItems: 'center', gap: 7, height: 34, padding: '0 16px', borderRadius: 'var(--r-md)', background: 'var(--surface-2)', border: '1px solid var(--border)', color: 'var(--text)', font: '700 12.5px/1 var(--font)', cursor: 'pointer' }}
        >
          Retry
        </button>
      </div>
    );
  }

  if (!draft) {
    return <div style={{ ...card, height: 120, background: 'linear-gradient(90deg,var(--surface-2),var(--hover),var(--surface-2))', backgroundSize: '200% 100%', animation: 'aaShimmer 1.3s linear infinite' }} />;
  }

  const set = <K extends keyof Settings>(key: K, value: Settings[K]) => setDraft({ ...draft, [key]: value });
  const togglePlatform = (p: string) => {
    const on = draft.platforms_enabled.includes(p);
    set('platforms_enabled', on ? draft.platforms_enabled.filter((x) => x !== p) : [...draft.platforms_enabled, p]);
  };
  const save = () =>
    update.mutate(draft, {
      onSuccess: () => notify('Settings saved', 'success'),
      onError: () => notify('Could not save settings', 'error'),
    });

  return (
    <div style={{ animation: 'aaUp .4s var(--ease) both', maxWidth: 760 }}>
      <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', gap: 16, marginBottom: 18 }}>
        <div>
          <h1 style={{ margin: 0, font: '800 24px/1.1 var(--font)', letterSpacing: '-.03em' }}>Settings</h1>
          <p style={{ margin: '6px 0 0', font: '500 13px/1.4 var(--font)', color: 'var(--text-3)' }}>Tune how the agent applies, which platforms it searches, and your AI keys.</p>
        </div>
        <button onClick={save} disabled={update.isPending} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, height: 38, padding: '0 16px', borderRadius: 'var(--r-md)', background: 'var(--accent)', border: '1px solid var(--accent)', color: 'var(--accent-ink)', font: '700 12.5px/1 var(--font)', cursor: 'pointer' }}>
          <Icon name="check" size={14} sw={2.2} /> {update.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>

      {/* Apply preferences */}
      <section style={{ ...card, marginBottom: 14 }}>
        <SectionTitle icon="cpu" title="Apply preferences" sub="Control the autonomy of the apply agent." />
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(200px,1fr))', gap: 14, marginTop: 14 }}>
          <Field label="Apply mode">
            <select aria-label="Apply mode" value={draft.apply_mode} onChange={(e) => set('apply_mode', e.target.value)} style={controlStyle}>
              <option value="review">Review each</option>
              <option value="autonomous">Autonomous</option>
              <option value="batch">Batch approve</option>
            </select>
          </Field>
          <Field label={`Min ATS score · ${Math.round(draft.min_ats_score * 100)}`}>
            <input type="range" min={0} max={100} value={Math.round(draft.min_ats_score * 100)} onChange={(e) => set('min_ats_score', Number(e.target.value) / 100)} aria-label="Minimum ATS score" style={{ accentColor: 'var(--accent)', width: '100%' }} />
          </Field>
          <Field label="Max parallel runs">
            <input type="number" min={1} max={10} value={draft.max_parallel} onChange={(e) => set('max_parallel', Number(e.target.value))} aria-label="Max parallel" style={controlStyle} />
          </Field>
        </div>
      </section>

        <TelegramSettings />
        {/* Platforms */}
      <section style={{ ...card, marginBottom: 14 }}>
        <SectionTitle icon="briefcase" title="Platforms" sub="Where the agent searches for roles." />
        <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
          {PLATFORMS.map((p) => {
            const on = draft.platforms_enabled.includes(p);
            return (
              <button key={p} aria-pressed={on} onClick={() => togglePlatform(p)} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, height: 32, padding: '0 13px', borderRadius: 999, cursor: 'pointer', font: '600 12px/1 var(--font)', textTransform: 'capitalize', border: `1px solid ${on ? 'var(--accent-line)' : 'var(--border)'}`, background: on ? 'var(--accent-soft)' : 'var(--surface-2)', color: on ? 'var(--accent)' : 'var(--text-3)' }}>
                {on && <Icon name="check" size={12} sw={2.4} />} {p}
              </button>
            );
          })}
        </div>
      </section>

      {/* AI providers */}
      <section style={card}>
        <SectionTitle icon="key" title="AI providers" sub="Bring your own key. The agent uses your preferred provider first." />
        <div style={{ display: 'flex', flexDirection: 'column', gap: 8, marginTop: 14 }}>
          {(providers ?? []).length === 0 ? (
            <p style={{ margin: 0, font: '500 12.5px/1.4 var(--font)', color: 'var(--text-3)' }}>No providers configured yet.</p>
          ) : (
            (providers ?? []).map((p) => (
              <div key={p.provider} style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '11px 13px', borderRadius: 'var(--r-md)', background: 'var(--surface-2)', border: '1px solid var(--border)' }}>
                <span style={{ display: 'grid', placeItems: 'center', width: 30, height: 30, borderRadius: 8, background: p.configured ? 'var(--applied-soft)' : 'var(--surface-3)', color: p.configured ? 'var(--applied)' : 'var(--text-4)' }}><Icon name={p.configured ? 'check' : 'key'} size={15} /></span>
                <span style={{ flex: '1 1 auto', minWidth: 0 }}>
                  <span style={{ display: 'block', font: '700 12.5px/1.2 var(--font)', textTransform: 'capitalize' }}>{p.provider}</span>
                  <span style={{ display: 'block', font: '500 11px/1.2 var(--mono)', color: 'var(--text-3)', marginTop: 2 }}>{p.model}</span>
                </span>
                {p.is_primary && <span style={{ height: 20, padding: '0 8px', display: 'inline-flex', alignItems: 'center', borderRadius: 5, background: 'var(--accent-soft)', color: 'var(--accent)', font: '700 9.5px/1 var(--mono)', letterSpacing: '.05em' }}>PRIMARY</span>}
                <span style={{ font: '600 10.5px/1 var(--mono)', color: p.configured ? 'var(--applied)' : 'var(--text-4)' }}>{p.configured ? 'CONFIGURED' : 'NOT SET'}</span>
              </div>
            ))
          )}
        </div>
      </section>
    </div>
  );
}

function SectionTitle({ icon, title, sub }: { icon: 'cpu' | 'briefcase' | 'key' | 'smartphone'; title: string; sub: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 11 }}>
      <span style={{ display: 'grid', placeItems: 'center', width: 32, height: 32, borderRadius: 9, background: 'var(--accent-soft)', color: 'var(--accent)' }}><Icon name={icon} size={16} /></span>
      <span>
        <span style={{ display: 'block', font: '700 14px/1.2 var(--font)', letterSpacing: '-.01em' }}>{title}</span>
        <span style={{ display: 'block', font: '500 11.5px/1.3 var(--font)', color: 'var(--text-3)', marginTop: 2 }}>{sub}</span>
      </span>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label style={{ display: 'flex', flexDirection: 'column', gap: 7 }}>
      <span style={{ font: '600 11px/1 var(--font)', color: 'var(--text-3)', textTransform: 'uppercase', letterSpacing: '.05em' }}>{label}</span>
      {children}
    </label>
  );
}


