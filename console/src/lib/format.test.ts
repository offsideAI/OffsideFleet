import { describe, expect, it } from 'vitest';

import { formatCost, formatDuration, formatTokens } from './format';

describe('formatCost', () => {
	it('renders zero plainly', () => {
		expect(formatCost(0)).toBe('$0');
	});
	it('keeps sub-cent LLM costs visible (never rounds to $0.00)', () => {
		expect(formatCost(6460)).toBe('$0.006460'); // 812 in + 96 out on opus-5
	});
	it('renders cent-scale costs at 4 places', () => {
		expect(formatCost(12_500)).toBe('$0.0125');
	});
});

describe('formatDuration', () => {
	it('uses ms under a second', () => {
		expect(formatDuration(900)).toBe('900ms');
	});
	it('uses seconds above', () => {
		expect(formatDuration(2400)).toBe('2.4s');
	});
});

describe('formatTokens', () => {
	it('renders in→out', () => {
		expect(formatTokens(812, 96)).toBe('812→96');
	});
});
