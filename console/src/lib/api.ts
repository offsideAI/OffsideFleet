const API_BASE = import.meta.env.VITE_FLEET_API ?? 'http://localhost:8000';

export interface Run {
	id: string;
	state: 'queued' | 'running' | 'succeeded' | 'failed' | 'killed' | 'budget_stopped';
	trigger_kind: string;
	input_text: string;
	error: Record<string, unknown> | null;
	cost_microusd_total: number;
	tokens_in_total: number;
	tokens_out_total: number;
	created_at: string;
	started_at: string | null;
	ended_at: string | null;
}

export interface RunStep {
	step_index: number;
	kind: string;
	provider: string;
	tokens_in: number;
	tokens_out: number;
	cost_microusd: number;
	price_table_version: string;
	duration_ms: number;
	created_at: string;
	request_payload?: unknown;
	response_payload?: unknown;
	rng_seed?: number | null;
	clock_reads?: string[];
}

async function get<T>(path: string): Promise<T> {
	const resp = await fetch(`${API_BASE}${path}`);
	if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} for ${path}`);
	return (await resp.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
	const resp = await fetch(`${API_BASE}${path}`, {
		method: 'POST',
		headers: { 'content-type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body)
	});
	if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText} for ${path}`);
	return (await resp.json()) as T;
}

export const api = {
	listRuns: () => get<{ runs: Run[] }>('/api/v1/runs'),
	getRun: (id: string) => get<Run>(`/api/v1/runs/${id}`),
	getSteps: (id: string) =>
		get<{ run: Run; steps: RunStep[] }>(`/api/v1/runs/${id}/steps?include=payloads`),
	createRun: (input: string) => post<Run>('/api/v1/runs', { input }),
	killRun: (id: string) =>
		post<{ state: string; killed_in_ms: number | null }>(`/api/v1/runs/${id}/kill`)
};
