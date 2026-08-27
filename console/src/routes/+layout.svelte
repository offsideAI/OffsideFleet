<script lang="ts">
	import '../app.css';
	let { children } = $props();
</script>

<header>
	<a href="/" class="wordmark">OffsideFleet</a>
	<span class="tag mono">runtime spine · M1</span>
</header>

<main>
	{@render children()}
</main>

<style>
	header {
		display: flex;
		align-items: baseline;
		gap: 14px;
		padding: 14px 24px;
		border-bottom: 1px solid var(--soot-3);
	}
	.wordmark {
		font-family: var(--font-display);
		font-size: 20px;
		color: var(--parchment);
	}
	.tag {
		color: var(--parchment-dim);
		font-size: 12px;
	}
	main {
		max-width: 1000px;
		margin: 0 auto;
		padding: 24px;
	}
</style>
