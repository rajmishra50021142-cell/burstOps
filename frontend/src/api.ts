import { DemoStatusResponse, RunDetail } from './types';

export async function fetchDemoStatus(): Promise<DemoStatusResponse> {
  const resp = await fetch('/api/demo/status');
  if (!resp.ok) {
    throw new Error(`Failed to fetch status: HTTP ${resp.status}`);
  }
  return resp.json();
}

export async function triggerBurst(): Promise<{ run_id: string; status: string; message: string }> {
  const resp = await fetch('/api/demo/burst', { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Burst trigger failed' }));
    throw new Error(err.detail || `Error ${resp.status}`);
  }
  return resp.json();
}

export async function triggerRecovery(): Promise<{ run_id: string; status: string; message: string }> {
  const resp = await fetch('/api/demo/recover', { method: 'POST' });
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: 'Recovery trigger failed' }));
    throw new Error(err.detail || `Error ${resp.status}`);
  }
  return resp.json();
}

export async function fetchRunDetail(runId: string): Promise<RunDetail> {
  const resp = await fetch(`/api/demo/runs/${runId}`);
  if (!resp.ok) {
    throw new Error(`Failed to fetch run details: HTTP ${resp.status}`);
  }
  return resp.json();
}
