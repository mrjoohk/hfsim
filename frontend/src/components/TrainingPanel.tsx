import { useState, useEffect } from 'react';
import {
  LineChart, Line, CartesianGrid, XAxis, YAxis,
  Tooltip, ResponsiveContainer,
} from 'recharts';
import useWebSocket from '../hooks/useWebSocket';
import { startTraining, stopTraining, fetchTrainingStatus } from '../api/client';
import type { MetricRow } from '../api/types';

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function StatCard({ label, value, color = '#e2e8f0' }: { label: string; value: string; color?: string }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      <span style={{ color: '#64748b', fontSize: 10, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      <span style={{ color, fontSize: 18, fontWeight: 700, fontFamily: 'monospace' }}>{value}</span>
    </div>
  );
}

function ConnDot({ connected }: { connected: boolean }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
      <div style={{
        width: 8, height: 8, borderRadius: '50%',
        background: connected ? '#22c55e' : '#ef4444',
        boxShadow: connected ? '0 0 6px #22c55e' : 'none',
      }} />
      <span style={{ color: '#64748b', fontSize: 11 }}>
        {connected ? 'WS connected' : 'WS disconnected'}
      </span>
    </div>
  );
}

function ChartCard({
  title, data, dataKey, color,
}: {
  title: string;
  data: MetricRow[];
  dataKey: keyof MetricRow;
  color: string;
}) {
  return (
    <div style={{ background: '#1e293b', borderRadius: 6, padding: 12, border: '1px solid #1e3a5f' }}>
      <p style={{ color: '#94a3b8', fontSize: 12, marginBottom: 6 }}>{title}</p>
      <ResponsiveContainer width="100%" height={160}>
        <LineChart data={data} margin={{ top: 2, right: 8, left: -18, bottom: 0 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
          <XAxis
            dataKey="episode"
            stroke="#334155"
            tick={{ fill: '#64748b', fontSize: 10 }}
          />
          <YAxis stroke="#334155" tick={{ fill: '#64748b', fontSize: 10 }} />
          <Tooltip
            contentStyle={{
              background: '#0f172a', border: '1px solid #334155',
              color: '#e2e8f0', fontSize: 11, borderRadius: 4,
            }}
          />
          <Line
            type="monotone"
            dataKey={dataKey as string}
            stroke={color}
            dot={false}
            strokeWidth={2}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const BTN = (active: boolean, color: string): React.CSSProperties => ({
  padding: '6px 14px', borderRadius: 4, border: 'none',
  background: active ? color : '#334155',
  color: active ? '#fff' : '#64748b',
  fontSize: 13, cursor: active ? 'pointer' : 'not-allowed',
});

export default function TrainingPanel() {
  const { messages, connected } = useWebSocket<MetricRow>('/api/training/stream');
  const [running, setRunning] = useState(false);
  const [startErr, setStartErr] = useState('');
  const [jobId, setJobId] = useState<string | null>(null);

  const last = messages[messages.length - 1] ?? null;

  // Poll /api/training/status every 5 s to sync job_id (Ray mode) and state
  useEffect(() => {
    const id = setInterval(async () => {
      try {
        const s = await fetchTrainingStatus();
        if (s.job_id) setJobId(s.job_id);
        if (s.state === 'STOPPED' || s.state === 'FAILED') setRunning(false);
      } catch { /* server not yet up */ }
    }, 5000);
    return () => clearInterval(id);
  }, []);

  const handleStart = async () => {
    setStartErr('');
    try {
      const res = await startTraining();
      if (res.ok) {
        setRunning(true);
        if (res.job_id) setJobId(res.job_id);
      } else {
        setStartErr(res.detail ?? 'Failed to start training.');
      }
    } catch (e) {
      setStartErr(String(e));
    }
  };

  const handleStop = async () => {
    await stopTraining();
    setRunning(false);
  };

  // Sync running state with live status from WS
  const wsStatus = last?.status;
  const displayRunning = running || wsStatus === 'TRAINING';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>

      {/* Status card */}
      <div style={{ background: '#1e293b', borderRadius: 6, padding: 14, border: '1px solid #1e3a5f' }}>
        <div style={{ display: 'flex', alignItems: 'center', flexWrap: 'wrap', gap: 20, marginBottom: last ? 14 : 0 }}>
          <ConnDot connected={connected} />
          {last ? (
            <>
              <StatCard
                label="Status"
                value={last.status}
                color={last.status === 'TRAINING' ? '#22c55e' : '#94a3b8'}
              />
              <StatCard label="Episode"   value={String(last.episode)} />
              <StatCard label="Steps"     value={last.step_count.toLocaleString()} />
              <StatCard label="Return"    value={last.mean_return.toFixed(4)} color="#38bdf8" />
              <StatCard label="Length"    value={last.mean_length.toFixed(1)} />
              <StatCard
                label="RSSM Loss"
                value={Number.isFinite(last.rssm_loss) ? last.rssm_loss.toFixed(4) : '—'}
                color="#a78bfa"
              />
              {jobId && (
                <StatCard
                  label="Ray Job"
                  value={jobId.length > 14 ? jobId.slice(0, 14) + '…' : jobId}
                  color="#f59e0b"
                />
              )}
            </>
          ) : (
            <span style={{ color: '#475569', fontSize: 13 }}>
              No training data yet. Click <b>Start Training</b> to begin.
            </span>
          )}

          <div style={{ marginLeft: 'auto', display: 'flex', gap: 8 }}>
            <button
              disabled={displayRunning}
              onClick={handleStart}
              style={BTN(!displayRunning, '#16a34a')}
            >
              ▶ Start Training
            </button>
            <button
              disabled={!displayRunning}
              onClick={handleStop}
              style={BTN(displayRunning, '#dc2626')}
            >
              ⏹ Stop
            </button>
          </div>
        </div>

        {startErr && (
          <p style={{ color: '#f43f5e', fontSize: 12, marginTop: 6 }}>❌ {startErr}</p>
        )}

        {last?.anomaly && (
          <div style={{
            marginTop: 8, padding: '6px 10px',
            background: '#7f1d1d', borderRadius: 4,
            fontSize: 12, color: '#fca5a5',
          }}>
            ⚠️ Anomaly detected: <b>{last.anomaly}</b>
          </div>
        )}

        <p style={{ color: '#475569', fontSize: 11, marginTop: 8 }}>
          Experiment history and hyperparameters: &nbsp;
          <a href="http://localhost:5000" target="_blank" rel="noreferrer" style={{ color: '#0ea5e9' }}>
            MLflow UI ↗
          </a>
        </p>
      </div>

      {/* Live charts */}
      {messages.length > 1 && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
          <ChartCard title="Episode Return"         data={messages} dataKey="mean_return"  color="#38bdf8" />
          <ChartCard title="Episode Length (steps)" data={messages} dataKey="mean_length"  color="#22c55e" />
        </div>
      )}

      {messages.length > 1 && Number.isFinite(last?.rssm_loss) && (
        <ChartCard title="RSSM Loss" data={messages} dataKey="rssm_loss" color="#a78bfa" />
      )}
    </div>
  );
}
