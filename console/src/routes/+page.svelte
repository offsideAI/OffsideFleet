<script lang="ts">
	import { onDestroy, onMount } from 'svelte';

	import { api, type Run } from '$lib/api';
	import { formatCost } from '$lib/format';

	let runs: Run[] = $state([]);
	let input = $state('');
	let error = $state('');
	let timer: ReturnType<typeof setInterval> | undefined;

	async function refresh() {
		try {
			runs = (await api.listRuns()).runs;
			error = '';
		} catch (e) {
			error = e instanceof Error ? e.message : String(e);
		}
	}

	async function createRun() {
		await api.createRun(input);
		input = '';
		await refresh();
	}

	onMount(() => {
		void refresh();
		timer = setInterval(refresh, 2000);
	});
	onDestroy(() => clearInterval(timer));
</script>

<h1>Runs</h1>

<form
	onsubmit={(e) => {
		e.preventDefault();
		void createRun();
	}}
>
	<input bind:value={input} placeholder="Ask Pathfinder something…" aria-label="Run input" />
	<button type="submit">Run</button>
</form>

{#if error}
	<p class="error mono">{error}</p>
{/if}

<table>
	<thead>
		<tr><th>Run</th><th>State</th><th>Trigger</th><th>Cost</th><th>Created</th></tr>
	</thead>
	<tbody>
		{#each runs as run (run.id)}
			<tr>
				<td class="mono"><a href={`/runs/${run.id}`}>{run.id.slice(0, 8)}</a></td>
				<td><span class={`badge ${run.state}`}>{run.state}</span></td>
				<td>{run.trigger_kind}</td>
				<td class="mono">{formatCost(run.cost_microusd_total)}</td>
				<td class="mono">{new Date(run.created_at).toLocaleTimeString()}</td>
			</tr>
		{/each}
	</tbody>
</table>

<style>
	form {
		display: flex;
		gap: 8px;
		margin-bottom: 20px;
	}
	input {
		flex: 1;
		background: var(--soot-2);
		border: 1px solid var(--soot-3);
		color: var(--parchment);
		padding: 8px 12px;
		border-radius: 4px;
		font-family: var(--font-ui);
	}
	button {
		background: var(--emerald);
		color: var(--soot);
		border: none;
		padding: 8px 18px;
		border-radius: 4px;
		font-weight: 600;
		cursor: pointer;
	}
	table {
		width: 100%;
		border-collapse: collapse;
	}
	th {
		text-align: left;
		font-size: 12px;
		text-transform: uppercase;
		letter-spacing: 0.06em;
		color: var(--parchment-dim);
		padding: 6px 10px;
		border-bottom: 1px solid var(--soot-3);
	}
	td {
		padding: 8px 10px;
		border-bottom: 1px solid var(--soot-2);
	}
	.error {
		color: var(--rust);
	}
</style>
