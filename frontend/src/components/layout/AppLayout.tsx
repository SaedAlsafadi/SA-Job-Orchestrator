import { useEffect } from 'react';
import { Outlet } from 'react-router-dom';

import Sidebar from './Sidebar';
import Header from './Header';
import CommandPalette from '@/components/ui/CommandPalette';
import InterventionModal from '@/components/applications/InterventionModal';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useApplicationEvents } from '@/hooks/useApplicationEvents';
import { useAppStore } from '@/store/useAppStore';
import { useUiStore } from '@/store/useUiStore';

/**
 * App shell — collapsible sidebar + header + scrollable content.
 *
 * LAYOUT FIX: The content area uses flex to correctly fill the remaining viewport
 * after the sidebar. There is NO inner max-width/margin-auto wrapper that would
 * create a double-centering effect and leave blank space on the right.
 *
 * Pages that need a max-width constraint should apply it internally.
 */
export default function AppLayout() {
  const { connected, lastMessage } = useWebSocket('/ws');
  const setWsConnected = useAppStore((s) => s.setWsConnected);
  const setPaletteOpen = useUiStore((s) => s.setPaletteOpen);

  useApplicationEvents(lastMessage);

  useEffect(() => {
    setWsConnected(connected);
  }, [connected, setWsConnected]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
        e.preventDefault();
        setPaletteOpen(true);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [setPaletteOpen]);

  return (
    <div
      style={{
        display: 'flex',
        height: '100vh',
        overflow: 'hidden',
        background: 'var(--bg)',
        color: 'var(--text)',
        fontFamily: 'var(--font)',
        letterSpacing: '-.01em',
      }}
    >
      <Sidebar />
      {/* Main content area — fills all remaining space after the sidebar */}
      <div style={{ flex: '1 1 auto', minWidth: 0, display: 'flex', flexDirection: 'column', height: '100vh' }}>
        <Header />
        {/*
          Scrollable content area. Padding is applied here — NOT inside a nested max-width wrapper.
          This ensures content uses the full available width without double-centering.
        */}
        <main style={{ flex: '1 1 auto', minHeight: 0, overflowY: 'auto', position: 'relative' }}>
          <div style={{ padding: '26px 28px 60px', minHeight: '100%' }}>
            <Outlet />
          </div>
        </main>
      </div>
      <CommandPalette />
      <InterventionModal />
    </div>
  );
}
