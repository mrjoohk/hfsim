import { useState } from 'react';
import LogBrowser from './components/LogBrowser';
import ReplayViewer from './components/ReplayViewer';
import TrainingPanel from './components/TrainingPanel';
import SweepUI from './components/SweepUI';
import type { Entry } from './api/types';

type Tab = 'replay' | 'training' | 'sweep';

function TabBtn({ label, active, onClick }: { label: string; active: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      style={{
        padding: '6px 14px',
        borderRadius: 4,
        border: 'none',
        background: active ? '#0284c7' : 'transparent',
        color: active ? '#fff' : '#94a3b8',
        fontSize: 13,
        cursor: 'pointer',
        fontWeight: active ? 600 : 400,
      }}
    >
      {label}
    </button>
  );
}

export default function App() {
  const [tab,     setTab]     = useState<Tab>('replay');
  const [entries, setEntries] = useState<Entry[]>([]);
  const [logName, setLogName] = useState('');

  const handleLoad = (loaded: Entry[], name: string) => {
    setEntries(loaded);
    setLogName(name);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', color: '#e2e8f0' }}>

      {/* Header */}
      <header style={{
        background: '#1e293b',
        borderBottom: '1px solid #334155',
        padding: '0 16px',
        height: 50,
        display: 'flex',
        alignItems: 'center',
        gap: 12,
      }}>
        <span style={{ fontWeight: 700, color: '#0ea5e9', fontSize: 17, marginRight: 8 }}>
          HF_Sim Dashboard
        </span>

        <TabBtn label="🎥  Replay Viewer"   active={tab === 'replay'}   onClick={() => setTab('replay')} />
        <TabBtn label="📊  Training Monitor" active={tab === 'training'} onClick={() => setTab('training')} />
        <TabBtn label="⚗️  HP Sweep"         active={tab === 'sweep'}    onClick={() => setTab('sweep')} />

        {logName && tab === 'replay' && (
          <span style={{ color: '#475569', fontSize: 11, marginLeft: 8 }}>
            {logName} · {entries.length} steps
          </span>
        )}

        <div style={{ marginLeft: 'auto', display: 'flex', gap: 12, alignItems: 'center' }}>
          <a
            href="/api/profiler/traces"
            target="_blank"
            rel="noreferrer"
            style={{ color: '#64748b', fontSize: 12, textDecoration: 'none' }}
          >
            Profiler ↗
          </a>
          <a
            href="http://localhost:5000"
            target="_blank"
            rel="noreferrer"
            style={{ color: '#64748b', fontSize: 12, textDecoration: 'none' }}
          >
            MLflow ↗
          </a>
          <a
            href="http://localhost:8000/docs"
            target="_blank"
            rel="noreferrer"
            style={{ color: '#64748b', fontSize: 12, textDecoration: 'none' }}
          >
            API Docs ↗
          </a>
        </div>
      </header>

      {/* Main */}
      <main style={{ padding: 12, maxWidth: 1600, margin: '0 auto' }}>
        {tab === 'replay' && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            <ReplayViewer entries={entries} />
            <LogBrowser onLoad={handleLoad} />
          </div>
        )}
        {tab === 'training' && <TrainingPanel />}
        {tab === 'sweep'    && <SweepUI />}
      </main>
    </div>
  );
}
