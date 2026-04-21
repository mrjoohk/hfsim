import type { Entry, LogFile, TrainingStatus } from './types';

async function get<T>(path: string): Promise<T> {
  const r = await fetch(path);
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${path}`);
  return r.json() as Promise<T>;
}

async function post<T>(path: string, body: unknown = {}): Promise<T> {
  const r = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${r.statusText} — ${path}`);
  return r.json() as Promise<T>;
}

export const fetchLogs = (): Promise<LogFile[]> =>
  get<LogFile[]>('/api/logs');

export const fetchEntries = (
  path: string,
  opts: { branch?: string; stepFrom?: number; stepTo?: number } = {},
): Promise<Entry[]> => {
  const params = new URLSearchParams();
  if (opts.branch)                 params.set('branch',    opts.branch);
  if (opts.stepFrom !== undefined) params.set('step_from', String(opts.stepFrom));
  if (opts.stepTo   !== undefined) params.set('step_to',   String(opts.stepTo));
  const qs = params.toString();
  return get<Entry[]>(`/api/logs/${encodeURIComponent(path)}/entries${qs ? `?${qs}` : ''}`);
};

export const fetchBranches = (path: string): Promise<string[]> =>
  get<string[]>(`/api/logs/${encodeURIComponent(path)}/branches`);

export const startTraining = (config: Record<string, unknown> = {}): Promise<{ ok: boolean; pid?: number; job_id?: string | null; detail?: string }> =>
  post('/api/training/start', { config });

export const stopTraining = (): Promise<{ ok: boolean }> =>
  post('/api/training/stop');

export const fetchTrainingStatus = (): Promise<TrainingStatus> =>
  get<TrainingStatus>('/api/training/status');
