import { describe, it, expect } from 'vitest';
import {
  META_COLORS,
  META_LABEL_KEYS,
  getMetaCategory,
  activityColor,
} from '../lib/activity';

const EXPECTED_CATEGORIES = [
  'focus',
  'communication',
  'entertainment',
  'browsing',
  'break',
  'idle',
  'other',
];

describe('META_COLORS', () => {
  it('has all expected meta-category keys', () => {
    for (const key of EXPECTED_CATEGORIES) {
      expect(META_COLORS).toHaveProperty(key);
    }
  });

  it('values are hex color strings', () => {
    for (const color of Object.values(META_COLORS)) {
      expect(color).toMatch(/^#[0-9a-fA-F]{6}$/);
    }
  });
});

describe('META_LABEL_KEYS', () => {
  it('has the same keys as META_COLORS', () => {
    const colorKeys = Object.keys(META_COLORS).sort();
    const labelKeys = Object.keys(META_LABEL_KEYS).sort();
    expect(labelKeys).toEqual(colorKeys);
  });

  it('values follow activity.* i18n key pattern', () => {
    for (const [key, value] of Object.entries(META_LABEL_KEYS)) {
      expect(value).toBe(`activity.${key}`);
    }
  });
});

describe('getMetaCategory', () => {
  it('returns "other" for unknown activity', () => {
    expect(getMetaCategory('something_unknown')).toBe('other');
  });

  it('returns "other" for empty string', () => {
    expect(getMetaCategory('')).toBe('other');
  });
});

describe('activityColor', () => {
  it('returns a hex color string for unknown activity', () => {
    const color = activityColor('unknown_activity');
    expect(color).toMatch(/^#[0-9a-fA-F]{6}$/);
  });

  it('returns the "other" color for unmapped activity', () => {
    expect(activityColor('unmapped')).toBe(META_COLORS.other);
  });
});
