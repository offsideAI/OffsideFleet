/** Format micro-USD as dollars, keeping sub-cent precision visible. */
export function formatCost(microusd: number): string {
	const usd = microusd / 1_000_000;
	if (usd === 0) return '$0';
	if (usd < 0.01) return `$${usd.toFixed(6)}`;
	return `$${usd.toFixed(4)}`;
}

export function formatDuration(ms: number): string {
	if (ms < 1000) return `${ms}ms`;
	return `${(ms / 1000).toFixed(1)}s`;
}

export function formatTokens(tokensIn: number, tokensOut: number): string {
	return `${tokensIn}→${tokensOut}`;
}
