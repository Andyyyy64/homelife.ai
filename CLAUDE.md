# life.ai

A personal AI observer that automatically records daily life and enables reflection and pattern discovery.

## Project Direction

Two core values:

1. **Externalized memory** — Answer "what was I doing then?" Searchable, auto-generated diary.
2. **Productivity visibility** — Show "how focused was I?" and "where did my time go?" in numbers.

Improvement priorities:
1. Improved activity classification accuracy
2. Mobile support / notification integration
3. Long-term trend analysis (weekly/monthly patterns)

## Architecture

```
daemon (Python)          web (Node.js/Hono)        frontend (React)
  ├─ Camera capture        ├─ REST API               ├─ Timeline view
  ├─ Screen capture        ├─ SQLite read-only       ├─ Frame detail
  ├─ Audio capture         ├─ Media serving          ├─ Summary panel
  ├─ Window monitor        ├─ MJPEG proxy            ├─ Live feed
  ├─ Presence detection    └─ Static file serving    ├─ Dashboard
  ├─ LLM analysis                                    ├─ Search
  ├─ Summary generation                              └─ Activity heatmap
  ├─ Report generation
  ├─ SQLite write
  └─ MJPEG live server (port 3002)
```

- Daemon writes to SQLite, web reads it (WAL mode for concurrency)
- Window monitor runs a persistent PowerShell process with its own SQLite connection
- Shared `data/` directory: frames/, screens/, audio/, life.db
- LLM provider is abstracted: Gemini or Claude, configured in life.toml

## Key Paths

- `daemon/` — Python package (daemon, capture, analysis, LLM, storage)
- `daemon/cli.py` — CLI entry point
- `daemon/daemon.py` — Main observer loop
- `daemon/config.py` — Config loading from life.toml
- `daemon/analyzer.py` — Frame analysis and summary generation
- `daemon/report.py` — Daily report generation
- `daemon/llm/` — LLM provider abstraction (base, gemini, claude)
- `daemon/capture/` — Camera, screen (PowerShell/WSL2), audio (ALSA), window (Win32 P/Invoke)
- `daemon/analysis/` — Motion, scene, change detection, presence, transcription
- `daemon/storage/database.py` — SQLite schema, migrations, queries
- `daemon/storage/models.py` — Frame, Event, Summary, Report dataclasses
- `daemon/notify.py` — Discord/LINE webhook notifications
- `web/server/` — Hono API server + routes
- `web/server/db.ts` — SQLite connection (better-sqlite3, read-only)
- `web/server/routes/stats.ts` — Stats, activities, app usage, date range endpoints
- `web/src/` — React frontend
- `web/src/components/Dashboard.tsx` — Dashboard with focus score, pie chart, app usage, sessions
- `web/src/components/DetailPanel.tsx` — Frame detail with images, audio, window info, metadata
- `life.toml` — Runtime config
- `.env` — API keys (GEMINI_API_KEY)
- `data/` — Runtime data (DB, frames, screens, audio)
- `docker-compose.yml` — Container orchestration

## Database Tables

- `frames` — Core capture data (path, screen, audio, transcription, analysis, activity, foreground_window)
- `window_events` — Focus change events (timestamp, process_name, window_title) for precise app duration tracking
- `summaries` — Multi-scale summaries (10m, 30m, 1h, 6h, 12h, 24h)
- `events` — Scene changes, motion spikes, presence state changes
- `reports` — Daily auto-generated reports
- `frames_fts` / `summaries_fts` — FTS5 trigram indexes for full-text search

## Conventions

- Python: dataclasses, type hints, logging module
- TypeScript: strict mode, Hono for API, Vite for build
- Database: SQLite with WAL mode, relative paths for media files
- Config: TOML for app config, .env for secrets
- Git commit prefixes: feat, fix, docs, refactor
- Do not git commit unless explicitly instructed by the user
