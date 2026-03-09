import { describe, it, expect } from 'vitest';
import ja from '../locales/ja.json';
import en from '../locales/en.json';

/** Recursively collect all leaf keys with dot-separated paths. */
function collectKeys(obj: Record<string, unknown>, prefix = ''): string[] {
  const keys: string[] = [];
  for (const [k, v] of Object.entries(obj)) {
    const path = prefix ? `${prefix}.${k}` : k;
    if (typeof v === 'object' && v !== null && !Array.isArray(v)) {
      keys.push(...collectKeys(v as Record<string, unknown>, path));
    } else {
      keys.push(path);
    }
  }
  return keys.sort();
}

describe('i18n translations', () => {
  it('ja and en have the same top-level keys', () => {
    const jaKeys = Object.keys(ja).sort();
    const enKeys = Object.keys(en).sort();
    expect(jaKeys).toEqual(enKeys);
  });

  it('ja and en have the same full key set', () => {
    const jaKeys = collectKeys(ja as Record<string, unknown>);
    const enKeys = collectKeys(en as Record<string, unknown>);
    expect(jaKeys).toEqual(enKeys);
  });

  it('no translation values are empty strings (ja)', () => {
    const leaves = collectKeys(ja as Record<string, unknown>);
    for (const path of leaves) {
      const value = path.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], ja);
      expect(value, `ja key "${path}" is empty`).not.toBe('');
    }
  });

  it('no translation values are empty strings (en)', () => {
    const leaves = collectKeys(en as Record<string, unknown>);
    for (const path of leaves) {
      const value = path.split('.').reduce<unknown>((o, k) => (o as Record<string, unknown>)[k], en);
      expect(value, `en key "${path}" is empty`).not.toBe('');
    }
  });
});
