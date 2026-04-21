import { useEffect, useRef, useMemo, useState } from 'react';
import * as Plotly from 'plotly.js-dist-min';
import type { Entry } from '../api/types';

// ---------------------------------------------------------------------------
// Geometry helpers
// ---------------------------------------------------------------------------

function norm(v: number[]): number {
  return Math.sqrt(v.reduce((s, x) => s + x * x, 0));
}

function trajectoryScale(points: [number, number, number][]): number {
  if (points.length < 2) return 100;
  const [x0, y0, z0] = points[0];
  let max = 0;
  for (const [x, y, z] of points.slice(1)) {
    max = Math.max(max, Math.sqrt((x - x0) ** 2 + (y - y0) ** 2 + (z - z0) ** 2));
  }
  return Math.max(20, Math.min(max * 0.15, 500));
}

function sphereWire(
  center: [number, number, number],
  radius: number,
  color: string,
  opacity: number,
): Plotly.Data {
  const x: (number | null)[] = [], y: (number | null)[] = [], z: (number | null)[] = [];
  const N = 36;
  for (let i = 0; i <= 6; i++) {
    const lat = -Math.PI / 2 + (i / 6) * Math.PI;
    const r2  = radius * Math.cos(lat);
    for (let j = 0; j < N; j++) {
      const t = (j / (N - 1)) * 2 * Math.PI;
      x.push(center[0] + r2 * Math.cos(t));
      y.push(center[1] + r2 * Math.sin(t));
      z.push(center[2] + radius * Math.sin(lat));
    }
    x.push(null); y.push(null); z.push(null);
  }
  for (let i = 0; i < 12; i++) {
    const lon = (i / 12) * 2 * Math.PI;
    for (let j = 0; j < N; j++) {
      const t = -Math.PI / 2 + (j / (N - 1)) * Math.PI;
      x.push(center[0] + radius * Math.cos(t) * Math.cos(lon));
      y.push(center[1] + radius * Math.cos(t) * Math.sin(lon));
      z.push(center[2] + radius * Math.sin(t));
    }
    x.push(null); y.push(null); z.push(null);
  }
  return { type: 'scatter3d', x, y, z, mode: 'lines', line: { color, width: 1 }, opacity, name: '', showlegend: false } as Plotly.Data;
}

function buildFigure(entry: Entry, branch: Entry[], scale: number): { data: Plotly.Data[]; layout: Plotly.Layout } {
  const traces: Plotly.Data[] = [];
  const pos  = entry.ownship.position_m;
  const vel  = entry.ownship.velocity_mps;
  const pts  = branch.map(e => e.ownship.position_m);

  // Trajectory
  if (pts.length > 0) {
    traces.push({
      type: 'scatter3d',
      x: pts.map(p => p[0]), y: pts.map(p => p[1]), z: pts.map(p => p[2]),
      mode: 'lines+markers',
      line: { color: '#0ea5e9', width: 3 },
      marker: { size: 2, color: '#38bdf8' },
      opacity: 0.5, name: 'Trajectory', showlegend: false,
    } as Plotly.Data);
  }

  // Aircraft marker
  traces.push({
    type: 'scatter3d',
    x: [pos[0]], y: [pos[1]], z: [pos[2]],
    mode: 'markers',
    marker: { size: 10, color: '#f97316', symbol: 'diamond' },
    name: 'Aircraft', showlegend: false,
  } as Plotly.Data);

  // Velocity arrow
  const spd = Math.max(norm(vel), 1);
  const vd  = vel.map(v => v / spd);
  const tip = pos.map((p, i) => p + vd[i] * scale * 1.2) as [number, number, number];
  traces.push({
    type: 'scatter3d',
    x: [pos[0], tip[0]], y: [pos[1], tip[1]], z: [pos[2], tip[2]],
    mode: 'lines', line: { color: '#fbbf24', width: 4 },
    name: 'Velocity', showlegend: false,
  } as Plotly.Data);

  // Terrain strip
  const tRef = entry.environment?.terrain_reference ?? [];
  if (tRef.length > 0) {
    const ox = pts[0]?.[0] ?? pos[0];
    const oy = pts[0]?.[1] ?? pos[1];
    const xs  = tRef.map((_, i) => i * 120 + ox - 120);
    traces.push({
      type: 'surface',
      x: xs, y: [oy - 600, oy + 600],
      z: [[...tRef], [...tRef]] as number[][],
      colorscale: [[0, '#6b4226'], [1, '#a0785a']],
      opacity: 0.72, showscale: false, name: 'Terrain', showlegend: false,
    } as unknown as Plotly.Data);
  }

  // Radar detection sphere
  const quality = entry.sensor?.quality ?? 0.5;
  traces.push(sphereWire(pos, 6000 * (0.5 + 0.5 * quality), '#38bdf8', 0.12));

  // Threats
  for (const t of entry.threats ?? []) {
    const tp = t.position_m;
    traces.push({
      type: 'scatter3d', x: [tp[0]], y: [tp[1]], z: [tp[2]],
      mode: 'markers', marker: { size: 10, color: '#e11d48', symbol: 'diamond' },
      name: 'Threat', showlegend: false,
    } as Plotly.Data);
    traces.push(sphereWire(tp, 1500, '#f43f5e', 0.06));
  }

  // Wind arrow
  const wind = entry.atmosphere?.wind_vector_mps ?? [0, 0, 0];
  const wn   = norm(wind);
  if (wn > 1e-9) {
    const wd = wind.map(w => w / wn);
    const ws = [pos[0], pos[1], pos[2] + scale * 1.4] as [number, number, number];
    const wt = ws.map((p, i) => p + wd[i] * scale * 1.2) as [number, number, number];
    traces.push({
      type: 'scatter3d', x: [ws[0], wt[0]], y: [ws[1], wt[1]], z: [ws[2], wt[2]],
      mode: 'lines', line: { color: '#22c55e', width: 3 },
      name: 'Wind', showlegend: false,
    } as Plotly.Data);
  }

  const axis = (title: string) => ({
    backgroundcolor: '#1e293b', gridcolor: '#334155',
    showbackground: true, title,
  });

  const layout: Plotly.Layout = {
    paper_bgcolor: '#0f172a',
    margin: { l: 0, r: 0, t: 0, b: 0 },
    uirevision: 'keep_camera',
    scene: {
      bgcolor: '#0f172a',
      xaxis: axis('X (m)'),
      yaxis: axis('Y (m)'),
      zaxis: axis('Z Alt (m)'),
      camera: { center: { x: 0, y: 0, z: 0 }, eye: { x: 1.4, y: 1.4, z: 0.9 } },
      aspectmode: 'data',
    },
  };

  return { data: traces, layout };
}

// ---------------------------------------------------------------------------
// Info panel
// ---------------------------------------------------------------------------

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8, padding: '1px 0' }}>
      <span style={{ color: '#64748b' }}>{label}</span>
      <span style={{ color: '#e2e8f0' }}>{value}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div style={{ marginBottom: 8 }}>
      <div style={{ color: '#0ea5e9', fontSize: 10, marginBottom: 2, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{title}</div>
      {children}
    </div>
  );
}

function InfoPanel({ entry, step, total }: { entry: Entry; step: number; total: number }) {
  const o   = entry.ownship;
  const c   = entry.control;
  const s   = entry.sensor;
  const atm = entry.atmosphere;
  const rad = entry.radar;
  const dm  = entry.derived_metrics;
  return (
    <div style={{
      width: 230, flexShrink: 0, background: '#1e293b', borderRadius: 6,
      padding: 10, border: '1px solid #1e3a5f',
      overflowY: 'auto', fontSize: 11, fontFamily: 'monospace',
    }}>
      <Section title="Playback">
        <Row label="Step"   value={`${step} / ${total}`} />
        <Row label="Time"   value={`${entry.sim_time_s.toFixed(2)} s`} />
      </Section>
      <Section title="Ownship">
        <Row label="Pos (m)"  value={o.position_m.map(v => v.toFixed(0)).join(', ')} />
        <Row label="Speed"    value={`${o.speed_mps.toFixed(1)} m/s`} />
        <Row label="Alt"      value={`${o.altitude_m.toFixed(0)} m`} />
        <Row label="Roll"     value={`${o.roll_deg.toFixed(1)}°`} />
        <Row label="Pitch"    value={`${o.pitch_deg.toFixed(1)}°`} />
        <Row label="Heading"  value={`${o.heading_deg.toFixed(1)}°`} />
      </Section>
      <Section title="Control">
        <Row label="Throttle"    value={`${(c.throttle * 100).toFixed(0)}%`} />
        <Row label="Load factor" value={`${c.load_factor_cmd.toFixed(2)} g`} />
      </Section>
      <Section title="Sensor / Env">
        <Row label="Sensor quality" value={`${(s.quality * 100).toFixed(0)}%`} />
        <Row label="Contacts"       value={String(s.contact_count)} />
        <Row label="Radar tracks"   value={String(rad.track_count)} />
        <Row label="Wind"           value={`${atm.wind_speed_mps.toFixed(1)} m/s`} />
        <Row label="Turbulence"     value={atm.turbulence_level.toFixed(2)} />
        <Row label="Threats"        value={String(entry.threats.length)} />
        {entry.threats.length > 0 && (
          <Row label="Nearest threat" value={`${dm.nearest_threat_distance_m.toFixed(0)} m`} />
        )}
      </Section>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

const BTN: React.CSSProperties = {
  background: '#1e293b', color: '#e2e8f0',
  border: '1px solid #334155', borderRadius: 4,
  padding: '4px 10px', fontSize: 13,
};

interface Props { entries: Entry[] }

export default function ReplayViewer({ entries }: Props) {
  const plotRef = useRef<HTMLDivElement>(null);
  const [branch,  setBranch]  = useState('');
  const [step,    setStep]    = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed,   setSpeed]   = useState(1);

  const branches = useMemo(() => {
    const seen = new Set<string>(), out: string[] = [];
    for (const e of entries) if (!seen.has(e.branch_id)) { seen.add(e.branch_id); out.push(e.branch_id); }
    return out;
  }, [entries]);

  const branchEntries = useMemo(
    () => entries.filter(e => e.branch_id === branch),
    [entries, branch],
  );

  const maxStep = Math.max(0, branchEntries.length - 1);
  const entry   = branchEntries[Math.min(step, maxStep)] ?? null;

  // Sync branch when entries change
  useEffect(() => {
    if (branches.length > 0) setBranch(branches[0]);
    setStep(0); setPlaying(false);
  }, [entries]); // eslint-disable-line react-hooks/exhaustive-deps

  // Reset step on branch switch
  useEffect(() => { setStep(0); }, [branch]);

  // Auto-play ticker
  useEffect(() => {
    if (!playing || branchEntries.length === 0) return;
    const ms = Math.max(50, Math.round(150 / speed));
    const id = setInterval(() => {
      setStep(s => {
        if (s >= maxStep) { setPlaying(false); return s; }
        return s + 1;
      });
    }, ms);
    return () => clearInterval(id);
  }, [playing, speed, maxStep, branchEntries.length]);

  // Draw / update Plotly
  useEffect(() => {
    if (!plotRef.current || !entry) return;
    const scale = trajectoryScale(branchEntries.map(e => e.ownship.position_m));
    const { data, layout } = buildFigure(entry, branchEntries, scale);
    Plotly.react(plotRef.current, data, layout, {
      displayModeBar: true, scrollZoom: true, responsive: true,
    });
  }, [entry, branchEntries]);

  if (entries.length === 0) {
    return (
      <div style={{ background: '#1e293b', borderRadius: 6, border: '1px solid #1e3a5f', padding: 40, textAlign: 'center' }}>
        <p style={{ color: '#475569' }}>No log loaded — select a file below and click <b>Load</b>.</p>
      </div>
    );
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {/* 3D scene + info panel */}
      <div style={{ display: 'flex', gap: 8 }}>
        <div ref={plotRef} style={{ flex: 1, background: '#0f172a', borderRadius: 6, minHeight: 480 }} />
        {entry && <InfoPanel entry={entry} step={step} total={maxStep} />}
      </div>

      {/* Controls */}
      <div style={{
        background: '#1e293b', borderRadius: 6, padding: '8px 12px',
        border: '1px solid #1e3a5f', display: 'flex', alignItems: 'center',
        gap: 10, flexWrap: 'wrap',
      }}>
        <button onClick={() => setStep(s => Math.max(0, s - 1))} style={BTN}>|◀</button>

        <button
          onClick={() => setPlaying(p => !p)}
          style={{ ...BTN, background: playing ? '#7f1d1d' : '#14532d', minWidth: 90 }}
        >
          {playing ? '⏸  Pause' : '▶  Play'}
        </button>

        <button onClick={() => setStep(s => Math.min(maxStep, s + 1))} style={BTN}>▶|</button>

        <input
          type="range" min={0} max={maxStep} value={step}
          onChange={e => { setPlaying(false); setStep(Number(e.target.value)); }}
          style={{ flex: 1, accentColor: '#0ea5e9', minWidth: 100 }}
        />

        <span style={{ color: '#64748b', fontSize: 12, whiteSpace: 'nowrap' }}>
          {step} / {maxStep}
        </span>

        <label style={{ color: '#94a3b8', fontSize: 12 }}>
          Speed:&nbsp;
          <select
            value={speed}
            onChange={e => setSpeed(Number(e.target.value))}
            style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 4, padding: '2px 4px' }}
          >
            {[0.25, 0.5, 1, 2, 4, 8].map(v => <option key={v} value={v}>{v}×</option>)}
          </select>
        </label>

        {branches.length > 1 && (
          <label style={{ color: '#94a3b8', fontSize: 12 }}>
            Branch:&nbsp;
            <select
              value={branch}
              onChange={e => setBranch(e.target.value)}
              style={{ background: '#0f172a', color: '#e2e8f0', border: '1px solid #334155', borderRadius: 4, padding: '2px 4px' }}
            >
              {branches.map(b => <option key={b} value={b}>{b}</option>)}
            </select>
          </label>
        )}
      </div>
    </div>
  );
}
