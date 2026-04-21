import { useEffect, useState } from 'react';
import { fetchLogs, fetchEntries } from '../api/client';
import type { Entry, LogFile } from '../api/types';

interface Props {
  onLoad: (entries: Entry[], fileName: string) => void;
}

const S = {
  card: {
    background: '#1e293b',
    borderRadius: 6,
    padding: 12,
    border: '1px solid #1e3a5f',
  } as React.CSSProperties,
  label: { color: '#94a3b8', fontSize: 12 } as React.CSSProperties,
  btn: (enabled: boolean): React.CSSProperties => ({
    width: '100%',
    padding: '7px 0',
    marginBottom: 8,
    borderRadius: 4,
    border: 'none',
    background: enabled ? '#0284c7' : '#1e3a5f',
    color: enabled ? '#e2e8f0' : '#475569',
    fontSize: 13,
    cursor: enabled ? 'pointer' : 'not-allowed',
  }),
  row: (selected: boolean): React.CSSProperties => ({
    padding: '6px 10px',
    cursor: 'pointer',
    fontSize: 12,
    background: selected ? '#0c4a6e' : 'transparent',
    color: selected ? '#e2e8f0' : '#94a3b8',
    borderBottom: '1px solid #0f172a',
    userSelect: 'none',
  }),
};

export default function LogBrowser({ onLoad }: Props) {
  const [files,    setFiles]    = useState<LogFile[]>([]);
  const [selected, setSelected] = useState('');
  const [loading,  setLoading]  = useState(false);
  const [status,   setStatus]   = useState('');

  useEffect(() => {
    fetchLogs()
      .then(setFiles)
      .catch(e => setStatus(`Cannot reach API: ${e}`));
  }, []);

  const handleLoad = async () => {
    if (!selected || loading) return;
    setLoading(true);
    setStatus('Loading…');
    try {
      const entries = await fetchEntries(selected);
      onLoad(entries, selected);
      setStatus(`✅ ${entries.length} steps from ${selected}`);
    } catch (e) {
      setStatus(`❌ ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const statusColor =
    status.startsWith('✅') ? '#22c55e' :
    status.startsWith('❌') ? '#f43f5e' : '#94a3b8';

  return (
    <div style={S.card}>
      <p style={S.label}>Select Replay Log (.jsonl / .parquet)</p>
      {status && (
        <p style={{ margin: '6px 0 0', fontSize: 11, color: statusColor }}>{status}</p>
      )}
      <button
        onClick={handleLoad}
        disabled={!selected || loading}
        style={{ ...S.btn(!!selected && !loading), marginTop: 8 }}
      >
        {loading ? 'Loading…' : '⬆  Load Selected File'}
      </button>
      <div style={{ maxHeight: 180, overflowY: 'auto', border: '1px solid #334155', borderRadius: 4 }}>
        {files.length === 0 ? (
          <p style={{ color: '#475569', padding: 10, fontSize: 12 }}>
            No log files found in <code>reports/</code> — run{' '}
            <code>python src/make_log.py</code> first.
          </p>
        ) : (
          files.map(f => (
            <div
              key={f.path}
              onClick={() => setSelected(f.path)}
              style={S.row(selected === f.path)}
            >
              {f.name}{' '}
              <span style={{ color: '#475569' }}>
                ({(f.size_bytes / 1024).toFixed(1)} KB)
              </span>
            </div>
          ))
        )}
      </div>
      <p style={{ ...S.label, marginTop: 6 }}>
        3D controls: drag to rotate · scroll to zoom · shift+drag to pan
      </p>
    </div>
  );
}
