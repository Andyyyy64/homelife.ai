import { describe, it, expect } from 'vitest';
import { formatDate, todayStr } from '../lib/date';

describe('formatDate', () => {
  it('formats a date as YYYY-MM-DD', () => {
    const d = new Date(2025, 0, 5); // January 5, 2025
    expect(formatDate(d)).toBe('2025-01-05');
  });

  it('zero-pads single-digit months and days', () => {
    const d = new Date(2024, 2, 3); // March 3, 2024
    expect(formatDate(d)).toBe('2024-03-03');
  });

  it('handles double-digit months and days', () => {
    const d = new Date(2024, 11, 25); // December 25, 2024
    expect(formatDate(d)).toBe('2024-12-25');
  });
});

describe('todayStr', () => {
  it('returns a valid YYYY-MM-DD string', () => {
    const result = todayStr();
    expect(result).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it('matches today\'s date', () => {
    const now = new Date();
    const expected = formatDate(now);
    expect(todayStr()).toBe(expected);
  });
});
