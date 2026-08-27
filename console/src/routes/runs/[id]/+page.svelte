<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	import { page } from '$app/state';
	import { api, type Run, type RunStep } from '$lib/api';
	import { formatCost, formatDuration, formatTokens } from '$lib/format';

	let run: Run | null = $state(null);
	let steps: RunStep[] = $state([]);
	let expanded: Record<number, boolean> = $state({});
	let error = $state('');
	let killResult = $state('');
	let timer: ReturnType<typeof setInterval> | undefined;

	const runId = page.params.id ?? '';

	async function refresh() {
		try {
			const data = await api.getSteps(runId);
			run = data.run;
			steps = data.steps;
			error = '';
			if (run && ['succeeded', 'failed', 'killed', 'budget_stopped'].includes(run.state)) {
				clearInterval(timer);
			}
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	async function kill() {
		const result = await api.killRun(runId);
		killResult =
			result.killed_in_ms === null
				? `state: ${result.state}`
				: `killed in ${result.killed_in_ms}ms`;
		await refresh();
	}

	onMount(() => {
		void refresh();
		timer = setInterval(refresh, 1500);
	});
	onDestroy(() => clearInterval(timer));
</script>

{#if run}
	<div class="head">
		<h1 class="mono">run {run.id.slice(0, 8)}</h1>
		<span class={`badge ${run.state}`}>{run.state}</span>
		{#if !['succeeded', 'failed', 'killed', 'budget_stopped'].includes(run.state)}
			<button class="kill" onclick={() => void kill()}>KILL</button>
		{/if}
		{#if killResult}<span class="mono kill-note">{killResult}</span>{/if}
	</div>

	<p class="meta mono">
		total {formatCost(run.cost_microusd_total)} · tokens {formatTokens(
			run.tokens_in_total,
			run.tokens_out_total
		)} · trigger {run.trigger_kind}
	</p>

	{#if run.input_text}<p class="input">“{run.input_text}”</p>{/if}
	{#if run.error}<pre class="error mono">{JSON.stringify(run.error, null, 2)}</pre>{/if}

	<ol class="trace">
		{#each steps as step (step.step_index)}
			<li>
				<button
					class="step-row"
					onclick={() => (expanded[step.step_index] = !expanded[step.step_index])}
				>
					<span class="idx mono">{step.step_index}</span>
					<span class="kind mono">{step.kind}</span>
					<span class="provider mono">{step.provider || '—'}</span>
					<span class="tokens mono">{formatTokens(step.tokens_in, step.tokens_out)}</span>
					<span class="cost mono">{formatCost(step.cost_microusd)}</span>
					<span class="dur mono">{formatDuration(step.duration_ms)}</span>
				</button>
				{#if expanded[step.step_index]}
					<div class="payloads">
						{#if step.request_payload}
							<h3>request</h3>
							<pre class="mono">{JSON.stringify(step.request_payload, null, 2)}</pre>
						{/if}
						{#if step.response_payload}
							<h3>response</h3>
							<pre class="mono">{JSON.stringify(step.response_payload, null, 2)}</pre>
						{/if}
						{#if step.rng_seed != null}<p class="mono seed">rng_seed: {step.rng_seed}</p>{/if}
					</div>
				{/if}
			</li>
		{/each}
	</ol>
{:else if error}
	<p class="error mono">{error}</p>
{:else}
	<p class="mono">loading…</p>
{/if}

<style>
	.head {
		display: flex;
		align-items: center;
		gap: 14px;
	}
	.kill {
		background: var(--rust);
		color: var(--parchment);
		border: none;
		padding: 6px 16px;
		border-radius: 4px;
		font-family: var(--font-mono);
		font-weight: 600;
		letter-spacing: 0.08em;
		cursor: pointer;
	}
	.kill-note {
		color: var(--rust);
		font-size: 12px;
	}
	.meta {
		color: var(--parchment-dim);
	}
	.input {
		font-style: italic;
		color: var(--parchment-dim);
	}
	.trace {
		list-style: none;
		padding: 0;
		border: 1px solid var(--soot-3);
		border-radius: 6px;
		overflow: hidden;
	}
	.step-row {
		display: grid;
		grid-template-columns: 40px 140px 110px 90px 110px 70px;
		gap: 10px;
		width: 100%;
		text-align: left;
		background: var(--soot-2);
		border: none;
		border-bottom: 1px solid var(--soot-3);
		color: var(--parchment);
		padding: 9px 14px;
		cursor: pointer;
		font-size: 13px;
	}
	.step-row:hover {
		background: var(--soot-3);
	}
	.idx {
		color: var(--parchment-dim);
	}
	.kind {
		color: var(--emerald);
	}
	.cost {
		color: var(--parchment);
	}
	.dur,
	.provider,
	.tokens {
		color: var(--parchment-dim);
	}
	.payloads {
		padding: 10px 16px;
		background: var(--soot);
		border-bottom: 1px solid var(--soot-3);
	}
	.payloads h3 {
		font-size: 11px;
		text-transform: uppercase;
		letter-spacing: 0.08em;
		color: var(--parchment-dim);
		margin: 8px 0 4px;
	}
	.payloads pre {
		background: var(--soot-2);
		padding: 10px;
		border-radius: 4px;
		overflow-x: auto;
		font-size: 12px;
		max-height: 360px;
	}
	.seed {
		color: var(--parchment-dim);
		font-size: 12px;
	}
	.error {
		color: var(--rust);
	}
</style>
