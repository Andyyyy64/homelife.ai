import { Hono } from 'hono';
import { getDb } from '../db.js';

// Cached mappings from DB with TTL
let _mappingsCache: Record<string, string> | null = null;
let _cacheTime = 0;
const CACHE_TTL_MS = 60_000; // 60 seconds

function loadMappingsFromDb(): Record<string, string> {
  const db = getDb();
  const rows = db
    .prepare('SELECT activity, meta_category FROM activity_mappings')
    .all() as { activity: string; meta_category: string }[];
  const map: Record<string, string> = {};
  for (const r of rows) {
    map[r.activity] = r.meta_category;
  }
  return map;
}

function getMappings(): Record<string, string> {
  const now = Date.now();
  if (_mappingsCache && now - _cacheTime < CACHE_TTL_MS) {
    return _mappingsCache;
  }
  _mappingsCache = loadMappingsFromDb();
  _cacheTime = now;
  return _mappingsCache;
}

function getMetaCategory(activity: string): string {
  const mappings = getMappings();
  return mappings[activity] || 'other';
}

const app = new Hono();

// GET /api/activities — list all activity categories with meta-categories
app.get('/', (c) => {
  const db = getDb();
  const rows = db
    .prepare(
      `SELECT activity, COUNT(*) as frame_count
       FROM frames WHERE activity != ''
       GROUP BY activity ORDER BY frame_count DESC`,
    )
    .all() as { activity: string; frame_count: number }[];

  const mappings = getMappings();
  const activities = rows.map((r) => ({
    activity: r.activity,
    metaCategory: mappings[r.activity] || 'other',
    frameCount: r.frame_count,
  }));

  return c.json(activities);
});

// GET /api/activities/mappings — full mapping table for frontend
app.get('/mappings', (c) => {
  const mappings = getMappings();
  return c.json(mappings);
});

export default app;
export { getMetaCategory };
