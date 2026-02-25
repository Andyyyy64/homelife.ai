# life.ai

パーソナルライフオブザーバー — カメラ・画面キャプチャ・音声からAIが日常を記録・分析するシステム。

## 機能

- **30秒間隔キャプチャ** — ウェブカメラ + PC画面 + 音声を自動記録
- **バーストスクリーンキャプチャ** — 30秒間に3枚（0s, 10s, 20s）の画面を撮影し、時系列で変化を把握
- **AI分析** — Gemini / Claude が各フレームを分析し、活動内容を日本語で記述
- **アクティビティ分類** — 「プログラミング」「YouTube視聴」「ブラウジング」等のカテゴリを自動付与
- **マルチスケールサマリー** — 10分〜24時間の階層的な活動要約を自動生成
- **イベント検知** — シーン変化（明→暗）や大きな動きを自動検出
- **ライブフィード** — MJPEG 10fps リアルタイム映像配信
- **Web UI** — タイムライン表示、フレーム詳細、バーストスクリーン切替、サマリー閲覧

## セットアップ

### 必要環境

- Python 3.12+
- Node.js 22+
- WSL2 (画面キャプチャにpowershell.exeを使用)
- Gemini API キーまたは Claude API キー

### インストール

```bash
# Python
uv sync  # or pip install -e .

# Web UI
cd web && npm install
```

### 設定

```bash
# .env に API キーを設定
echo "GEMINI_API_KEY=your-key-here" > .env

# life.toml でプロバイダーを選択（省略時はデフォルト値）
cat > life.toml << 'EOF'
[llm]
provider = "gemini"           # "gemini" or "claude"
gemini_model = "gemini-2.5-flash"

[capture]
interval_sec = 30
screen_burst_count = 3        # バーストスクリーン枚数
EOF
```

`data/context.md` にユーザーの背景情報を書くと、AIが名前や環境を踏まえた分析をします。

### 起動

```bash
# デーモン起動（バックグラウンド）
life start -d

# Web UI 起動
cd web && npm run dev
```

- Web UI: http://localhost:5173
- API: http://localhost:3001
- ライブフィード: http://localhost:3002

## CLI コマンド

| コマンド | 説明 |
|---------|------|
| `life start [-d]` | デーモン起動（`-d` でバックグラウンド） |
| `life stop` | デーモン停止 |
| `life status` | 状態表示（フレーム数、サマリー数、ディスク使用量） |
| `life capture` | テストフレームを1枚撮影 |
| `life look` | 撮影してAIに即分析させる |
| `life recent [-n 5]` | 直近のフレーム分析を表示 |
| `life today [DATE]` | タイムライン表示 |
| `life stats [DATE]` | 日別統計 |
| `life summaries [DATE] [--scale 1h]` | サマリー表示（10m/30m/1h/6h/12h/24h） |
| `life events [DATE]` | イベント一覧 |
| `life review [DATE] [--json]` | レビューパッケージ生成 |

## 設定オプション

`life.toml` で以下を設定可能:

```toml
data_dir = "data"

[capture]
device = 0              # カメラデバイスID
interval_sec = 30       # キャプチャ間隔（秒）
width = 640
height = 480
jpeg_quality = 85
screen_burst_count = 3  # バーストスクリーン枚数

[analysis]
motion_threshold = 0.02
brightness_dark = 40.0
brightness_bright = 180.0

[llm]
provider = "gemini"              # "gemini" or "claude"
claude_model = "haiku"
gemini_model = "gemini-2.5-flash"
```

## Web API

| エンドポイント | 説明 |
|--------------|------|
| `GET /api/frames?date=YYYY-MM-DD` | フレーム一覧 |
| `GET /api/frames/latest` | 最新フレーム |
| `GET /api/frames/:id` | フレーム詳細 |
| `GET /api/summaries?date=...&scale=...` | サマリー一覧 |
| `GET /api/events?date=...` | イベント一覧 |
| `GET /api/stats?date=...` | 日別統計 |
| `GET /api/stats/activities?date=...` | アクティビティ別統計 |
| `GET /api/stats/dates` | データのある日付一覧 |
| `GET /media/{path}` | 画像・音声ファイル配信 |

## 技術スタック

- **Backend**: Python 3.12 / Click / OpenCV / SQLite
- **LLM**: Google Gemini / Anthropic Claude（抽象化プロバイダー層）
- **Frontend**: React 19 / TypeScript / Vite
- **Web Server**: Hono + better-sqlite3
- **Infra**: WSL2 + powershell.exe（画面キャプチャ）
