# life.ai

A personal AI observer that automatically records your daily life and enables reflection and pattern discovery.

## Vision

**"Record your life, reflect on it, and see the patterns."**

Two core values:

1. **Externalized memory** — Instantly answer "what was I doing then?" Your day is recorded automatically, no journaling required.
2. **Productivity visibility** — See "how focused was I today?" and "where did my time go?" in concrete numbers.

## Features

### Capture & Sensing

- **30-second interval capture** — Webcam + PC screen + audio recorded automatically
- **Change detection** — Extra screenshots/camera frames captured when significant visual changes occur between intervals
- **Foreground window tracking** — Persistent PowerShell monitor detects app focus changes every 500ms via Win32 API, recording precise per-app usage time
- **Presence detection** — Face detection + motion analysis to classify presence state (present / absent / sleep)
- **Audio transcription** — Recorded audio is transcribed via LLM for speech-aware analysis
- **Live feed** — MJPEG real-time video stream at ~30fps

### AI Analysis

- **Frame analysis** — Each frame (camera + screen + audio + active window) is analyzed by Gemini or Claude
- **Activity classification** — Auto-categorizes into canonical activities (programming, browsing, gaming, sleep, etc.)
- **Multi-scale summaries** — Hierarchical summaries generated automatically: 10min → 30min → 1h → 6h → 12h → 24h
- **Daily reports** — Auto-generated end-of-day diary with focus metrics, delivered via webhook
- **Context awareness** — User profile (`data/context.md`) and recent frame history are included in every LLM prompt

### Web UI

- **Timeline** — Scrollable frame timeline with activity color-coding and click-to-expand detail
- **Detail panel** — Frame images, screen captures, audio player, transcription, active window info, metadata
- **Dashboard** — Focus score, category breakdown (pie chart), activity list, app usage (bar chart), weekly chart, session timeline
- **Search** — Full-text search across frame descriptions, transcriptions, activities, window titles, and summaries (FTS5 trigram)
- **Activity heatmap** — Visual distribution of activities across hours
- **Live feed** — Real-time camera stream in browser
- **Summary panel** — Browse multi-scale summaries with timeline range highlighting

### Notifications

- **Discord** — Daily reports delivered via webhook embed
- **LINE Notify** — Daily reports via LINE API
- Test with `life notify-test`

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

## Setup

### Requirements

- Python 3.12+
- Node.js 22+
- WSL2 (uses powershell.exe for screen capture and window tracking)
- Gemini API key or Claude API key

### Installation

```bash
# Python
uv sync  # or pip install -e .

# Web UI
cd web && npm install
```

### Configuration

```bash
# Set API key in .env
echo "GEMINI_API_KEY=your-key-here" > .env

# Configure in life.toml
cat > life.toml << 'EOF'
[llm]
provider = "gemini"
gemini_model = "gemini-2.5-flash"

[capture]
interval_sec = 30

[presence]
enabled = true

[notify]
provider = "discord"
webhook_url = "https://discord.com/api/webhooks/..."
enabled = false
EOF
```

Add user context to `data/context.md` so the AI can reference your name, environment, and habits in its analysis.

### Running

```bash
# Start daemon
life start       # foreground
life start -d    # background

# Start web UI
cd web && npm run dev    # development
cd web && npm start      # production (serves from dist/)
```

- Web UI: http://localhost:3001
- Live feed: http://localhost:3002

### Docker

```bash
docker compose up
```

For environments with camera/audio devices, configure device mounts in `docker-compose.override.yml`.

## CLI Commands

| Command | Description |
|---------|-------------|
| `life start [-d]` | Start the observer daemon (`-d` for background) |
| `life stop` | Stop the running daemon |
| `life status` | Show status (frame count, summaries, disk usage) |
| `life capture` | Capture a single test frame |
| `life look` | Capture and analyze a frame immediately |
| `life recent [-n 5]` | Show recent frame analyses |
| `life today [DATE]` | Show timeline for the day |
| `life stats [DATE]` | Show daily statistics |
| `life summaries [DATE] [--scale 1h]` | Show summaries (10m/30m/1h/6h/12h/24h) |
| `life events [DATE]` | List detected events |
| `life report [DATE]` | Generate daily diary report |
| `life review [DATE] [--json]` | Generate review package |
| `life notify-test` | Test webhook notification |

## Configuration

All options in `life.toml`:

```toml
data_dir = "data"

[capture]
device = 0              # camera device ID
interval_sec = 30       # capture interval (seconds)
width = 640
height = 480
jpeg_quality = 85
audio_device = ""       # ALSA device (empty = auto-detect)
audio_sample_rate = 44100

[analysis]
motion_threshold = 0.02
brightness_dark = 40.0
brightness_bright = 180.0

[llm]
provider = "gemini"              # "gemini" or "claude"
claude_model = "haiku"
gemini_model = "gemini-2.5-flash"

[presence]
enabled = true
absent_threshold_ticks = 3       # ticks before absent state
sleep_start_hour = 23
sleep_end_hour = 8

[notify]
provider = "discord"             # "discord" or "line"
webhook_url = ""
enabled = false
```

## Web API

| Endpoint | Description |
|----------|-------------|
| `GET /api/frames?date=YYYY-MM-DD` | List frames for a date |
| `GET /api/frames/latest` | Get latest frame |
| `GET /api/frames/:id` | Get frame by ID |
| `GET /api/summaries?date=...&scale=...` | List summaries |
| `GET /api/events?date=...` | List events |
| `GET /api/stats?date=...` | Daily statistics |
| `GET /api/stats/activities?date=...` | Activity breakdown with duration |
| `GET /api/stats/apps?date=...` | App usage tracking (from window events) |
| `GET /api/stats/dates` | List dates with data |
| `GET /api/stats/range?from=...&to=...` | Per-day stats for date range |
| `GET /api/sessions?date=...` | Activity sessions (consecutive grouping) |
| `GET /api/reports?date=...` | Get daily report |
| `GET /api/reports` | List recent reports |
| `GET /api/activities` | List activity categories |
| `GET /api/search?q=...&from=...&to=...` | Full-text search |
| `GET /api/live/stream` | MJPEG stream proxy |
| `GET /media/{path}` | Serve image/audio files |

## Database Schema

### frames
Core capture data: timestamp, camera path, screen path, audio path, transcription, brightness, motion score, scene type, LLM description, activity category, foreground window.

### window_events
Focus change events recorded by the window monitor: timestamp, process name, window title. Used for precise app usage duration calculation via `LEAD()` window function.

### summaries
Multi-scale summaries (10m to 24h) with timestamp, scale, content, and frame count.

### events
Detected events: scene changes, motion spikes, presence state changes.

### reports
Daily auto-generated reports with content, frame count, and focus percentage.

### FTS indexes
`frames_fts` (trigram) over description, transcription, activity, foreground_window. `summaries_fts` (trigram) over content.

## Tech Stack

- **Backend**: Python 3.12 / Click / OpenCV / SQLite (WAL mode)
- **LLM**: Google Gemini / Anthropic Claude (abstracted provider layer)
- **Window tracking**: PowerShell / Win32 P/Invoke (GetForegroundWindow)
- **Frontend**: React 19 / TypeScript / Vite
- **Web Server**: Hono + better-sqlite3
- **Infra**: Docker Compose / WSL2
