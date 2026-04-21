import { useState, useEffect, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface SweepStatus {
  state: string;
  n_trials: number;
  n_done: number;
  best_value: number | null;
  best_params: Record<string, number | string> | null;
}

interface TrialRecord {
  number: number;
  params: Record<string, number | string>;
  value: number | null;
  state: string;
}

// ---------------------------------------------------------------------------
// API helpers
// ---------------------------------------------------------------------------

async function apiPost(path: string, body: unknown = {}): Promise<unknown> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  return r.json();
}

async function apiGet<T>(path: string): Promise<T> {
  const r = await fetch(path);
  return r.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Card({ children, style }: { children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <div style={{
      background: '#1e293b', borderRadius: 6, padding: 14,
      border: '1px solid #1e3a5f', ...style,
    }}>
      {children}
    </div>
  );
}

function StatItem({ label, value, color = '#e2e8f0' }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ color: '#64748b', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
        {label}
      </span>
      <span style={{ color, fontSize: 16, fontWeight: 700, fontFamily: 'monospace' }}>{value}</span>
    </div>
  );
}

function ProgressBar({ done, total }: { done: number; total: number }) {
  const pct = total > 0 ? Math.round((done / total) * 100) : 0;
  return (
    <div style={{ marginTop: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 11, color: '#64748b', marginBottom: 4 }}>
        <span>Progress</span>
        <span>{done} / {total} trials ({pct}%)</span>
      </div>
      <div style={{ height: 6, background: '#0f172a', borderRadius: 3, overflow: 'hidden' }}>
        <div style={{
          height: '100%',
          width: `${pct}%`,
          background: pct === 100 ? '#22c55e' : '#0284c7',
          transition: 'width 0.4s ease',
          borderRadius: 3,
        }} />
      </div>
    </div>
  );
}

const STATE_COLOR: Record<string, string> = {
  COMPLETE: '#22c55e',
  RUNNING:  '#0ea5e9',
  FAILED:   '#ef4444',
  PRUNED:   '#f59e0b',
};

function TrialTable({ trials }: { trials: TrialRecord[] }) {
  if (trials.length === 0) return null;

  const paramKeys = trials.length > 0 ? Object.keys(trials[0].params) : [];
  const bestVal = Math.max(...trials.filter(t => t.value !== null).map(t => t.value!));

  return (
    <div style={{ overflowX: 'auto' }}>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ borderBottom: '1px solid #334155' }}>
            <th style={TH}>#</th>
            {paramKeys.map(k => <th key={k} style={TH}>{k}</th>)}
            <th style={TH}>return</th>
            <th style={TH}>state</th>
          </tr>
        </thead>
        <tbody>
          {[...trials].reverse().map(t => {
            const isBest = t.value !== null && t.value === bestVal;
            return (
              <tr key={t.number} style={{
                borderBottom: '1px solid #1e3a5f',
                background: isBest ? 'rgba(34,197,94,0.06)' : 'transparent',
              }}>
                <td style={TD}>{isBest ? '★ ' : ''}{t.number}</td>
                {paramKeys.map(k => <td key={k} style={TD}>{t.params[k]}</td>)}
                <td style={{ ...TD, color: '#38bdf8', fontFamily: 'monospace' }}>
                  {t.value !== null ? t.value.toFixed(4) : '—'}
                </td>
                <td style={{ ...TD, color: STATE_COLOR[t.state] ?? '#94a3b8' }}>
                  {t.state}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const TH: React.CSSProperties = { padding: '6px 10px', textAlign: 'left', color: '#64748b', fontWeight: 600 };
const TD: React.CSSProperties = { padding: '5px 10px', color: '#e2e8f0' };

const BTN = (active: boolean, color: string): React.CSSProperties => ({
  padding: '6px 14px', borderRadius: 4, border: 'none',
  background: active ? color : '#334155',
  color: active ? '#fff' : '#64748b',
  fontSize: 13, cursor: active ? 'pointer' : 'not-allowed',
});

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function SweepUI() {
  const [status, setStatus]   = useState<SweepStatus | null>(null);
  const [trials, setTrials]   = useState<TrialRecord[]>([]);
  const [nTrials, setNTrials] = useState(10);
  const [nEps,    setNEps]    = useState(50);
  const [err,     setErr]     = useState('');

  const refresh = useCallback(async () => {
    try {
      const [s, t] = await Promise.all([
        apiGet<SweepStatus>('/api/sweep/status'),
        apiGet<TrialRecord[]>('/api/sweep/trials'),
      ]);
      setStatus(s);
      setTrials(t);
    } catch { /* server not ready */ }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, 3000);
    return () => clearInterval(id);
  }, [refresh]);

  const handleStart = async () => {
    setErr('');
    const res = await apiPost('/api/sweep/start', {
      n_trials:             nTrials,
      n_episodes_per_trial: nEps,
    }) as { ok: boolean; detail?: string };
    if (!res.ok) setErr(res.detail ?? 'Failed to start sweep.');
    else refresh();
  };

  const handleStop = async () => {
    await apiPost('/api/sweep/stop');
    refresh();
  };

  const running = status?.state === 'RUNNING';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Config + controls */}
      <Card>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 20, marginBottom: 12 }}>
          <span style={{ fontWeight: 600, color: '#e2e8f0', fontSize: 14 }}>
            Hyperparameter Sweep
          </span>
          {status && (
            <>
              <StatItem
                label="State"
                value={status.state}
                color={status.state === 'RUNNING' ? '#0ea5e9' : status.state === 'STOPPED' ? '#22c55e' : '#94a3b8'}
              />
              {status.best_value !== null && (
                <StatItem label="Best Return" value={status.best_value.toFixed(4)} color="#38bdf8" />
              )}
            </>
          )}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button disabled={running} onClick={handleStart} style={BTN(!running, '#16a34a')}>
              ▶ Start Sweep
            </button>
            <button disabled={!running} onClick={handleStop} style={BTN(running, '#dc2626')}>
              ⏹ Stop
            </button>
          </div>
        </div>

        {/* Config inputs */}
        <div style={{ display: 'flex', gap: 20, alignItems: 'center', flexWrap: 'wrap' }}>
          <label style={{ color: '#94a3b8', fontSize: 12 }}>
            Trials&nbsp;
            <input
              type="number" min={1} max={200} value={nTrials}
              disabled={running}
              onChange={e => setNTrials(Number(e.target.value))}
              style={INPUT}
            />
          </label>
          <label style={{ color: '#94a3b8', fontSize: 12 }}>
            Episodes/trial&nbsp;
            <input
              type="number" min={5} max={500} value={nEps}
              disabled={running}
              onChange={e => setNEps(Number(e.target.value))}
              style={INPUT}
            />
          </label>
          <span style={{ color: '#475569', fontSize: 11 }}>
            Search space: train_steps · batch_size · seq_len · collect_per_iter
          </span>
        </div>

        {err && <p style={{ color: '#f43f5e', fontSize: 12, marginTop: 8 }}>❌ {err}</p>}

        {status && (status.n_done > 0 || running) && (
          <ProgressBar done={status.n_done} total={status.n_trials} />
        )}
      </Card>

      {/* Best params */}
      {status?.best_params && (
        <Card>
          <p style={{ color: '#64748b', fontSize: 11, marginBottom: 8 }}>Best Parameters</p>
          <div style={{ display: 'flex', gap: 20, flexWrap: 'wrap' }}>
            {Object.entries(status.best_params).map(([k, v]) => (
              <StatItem key={k} label={k} value={String(v)} color="#a78bfa" />
            ))}
          </div>
        </Card>
      )}

      {/* Trial table */}
      {trials.length > 0 && (
        <Card>
          <p style={{ color: '#64748b', fontSize: 11, marginBottom: 8 }}>
            All Trials ({trials.length})
          </p>
          <TrialTable trials={trials} />
        </Card>
      )}

      {/* Optuna note */}
      <p style={{ color: '#334155', fontSize: 11 }}>
        Uses Optuna (TPE sampler) if installed, otherwise random search.
        Install: <code style={{ color: '#475569' }}>pip install optuna</code>
      </p>
    </div>
  );
}

const INPUT: React.CSSProperties = {
  width: 70, padding: '3px 6px', borderRadius: 4,
  border: '1px solid #334155', background: '#0f172a',
  color: '#e2e8f0', fontSize: 12, marginLeft: 4,
};
