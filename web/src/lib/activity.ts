/**
 * Shared activity module — single source of truth for meta-category colors,
 * labels, and dynamic activity→meta_category mapping from the API.
 */

export const META_COLORS: Record<string, string> = {
  focus: '#60a860',
  communication: '#6088d0',
  entertainment: '#d06060',
  browsing: '#d0a840',
  break: '#888888',
  idle: '#444466',
  other: '#a060b0',
};

export const META_LABELS: Record<string, string> = {
  focus: 'Focus',
  communication: 'Communication',
  entertainment: 'Entertainment',
  browsing: 'Browsing',
  break: 'Break',
  idle: 'Idle',
  other: 'Other',
};

// Dynamic mappings fetched from API
let _mappings: Record<string, string> | null = null;

export async function loadActivityMappings(): Promise<void> {
  try {
    const res = await fetch('/api/activities/mappings');
    if (res.ok) {
      _mappings = await res.json();
    }
  } catch {
    // Silently fail — will use 'other' as fallback
  }
}

export function getMetaCategory(activity: string): string {
  if (!activity) return 'other';
  if (_mappings && activity in _mappings) return _mappings[activity];
  return 'other';
}

export function activityColor(activity: string): string {
  return META_COLORS[getMetaCategory(activity)] || META_COLORS.other;
}
