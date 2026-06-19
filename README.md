# AI Personal Radio Station

A self-hosted AI radio station that generates personalized Chinese-language audio programs every day — scripted by Claude, voiced by Microsoft Edge TTS, mixed with background music, and delivered over Telegram.

## Programs

| Program | Description | Target | Length |
|---|---|---|---|
| **晨间播报** (`news_radio_cc.py`) | Tech/AI/science + auto industry news digest + US stock market | Listener 1 | ~50 min |
| **第二听众晨间** (`news_radio_wife.py`) | Morning news — international tax / transfer pricing focus | Listener 2 | ~30 min |
| **第二听众午间** (`news_radio_wife_noon.py`) | Global politics / geopolitics / finance | Listener 2 | ~30 min |
| **世界下班以后** (`night_radio.py`) | Evening culture radio — world cities, history, slow life | Both | ~30 min |
| **今晚慢慢睡** (`sleep_radio.py`) | Bedtime relaxation — stories, health tips, cultural imagery | Both | ~20 min |

## How it works

```
RSS feeds / weather / stock APIs
         ↓
   Claude (claude -p)   ← generates ~7000–15000 char Chinese script
         ↓
   Edge TTS             ← synthesizes MP3 voice track
         ↓
   FFmpeg               ← mixes voice with looping BGM + fade
         ↓
   Telegram Bot API     ← sends final MP3 to personal channel
```

## Prerequisites

- Python 3.11+
- [Claude Code CLI](https://claude.ai/code) installed and authenticated (`claude` in PATH)
- `ffmpeg` and `ffprobe` in PATH
- A Telegram Bot token and chat ID for each channel

## Setup

### 1. Clone and create virtual environment

```bash
git clone https://github.com/jackhan1026/yt-agent.git
cd yt-agent
python3 -m venv venv
source venv/bin/activate
pip install feedparser requests edge-tts
```

### 2. Configure secrets

```bash
cp secrets.env.example secrets.env
# Edit secrets.env and fill in your Telegram bot tokens and chat IDs
```

### 3. Add background music

```bash
mkdir -p bgm
# Morning BGM (bossa nova)
curl -L -o bgm/bossa.mp3 "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Bossa%20Antigua.mp3"
# Evening / sleep BGM (gentle piano)
curl -L -o bgm/night.mp3 "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cherry%20Blossom.mp3"
```

### 4. Run manually

```bash
source secrets.env
source venv/bin/activate
python news_radio_cc.py
```

### 5. Schedule with cron

```cron
45 06 * * *     cd /root/yt-agent && . ./secrets.env && venv/bin/python news_radio_cc.py        >> radio.log 2>&1
00 07 * * *     cd /root/yt-agent && . ./secrets.env && venv/bin/python news_radio_wife.py      >> wife_radio.log 2>&1
00 12 * * *     cd /root/yt-agent && . ./secrets.env && venv/bin/python news_radio_wife_noon.py >> wife_noon_radio.log 2>&1
30 17 * * 1-5   cd /root/yt-agent && . ./secrets.env && venv/bin/python night_radio.py          >> night_radio.log 2>&1
00 23 * * *     cd /root/yt-agent && . ./secrets.env && venv/bin/python sleep_radio.py          >> sleep_radio.log 2>&1
```

## Configuration

Each script has a small constants block at the top. Common knobs:

| Constant | What it controls |
|---|---|
| `TARGET_MINUTES` | Program target length |
| `CLAUDE_MODEL` | `"sonnet"` for scripts, `"haiku"` for captions |
| `EDGE_VOICE` | TTS voice (default: `zh-CN-XiaoxiaoNeural`) |
| `EDGE_RATE` | TTS speed (`+0%` to `-18%`) |
| `BGM_VOLUME` | Background music level (0.0–1.0) |
| `CITY_FOR_WEATHER` | City for weather fetch |

## Night radio topic calendar

`topics_calendar.py` assigns every episode's topics deterministically by day-of-year — zero token cost, no LLM calls, no log file reads.

| Dimension | Pool size | Repeat gap |
|---|---|---|
| World / Chinese cities | 73 | every 73 days (~2.4 months) |
| Historical figures | 71 | every 71 days (~2.3 months) |
| Culture themes | 61 | every 61 days (~2 months) |
| Health topics | 59 | every 59 days (~2 months) |

The four list lengths are co-prime → the exact combination of all four topics never repeats within a human lifetime.

To add or reorder topics, edit the four lists in `topics_calendar.py`. The calendar is shared by both `night_radio.py` and is imported at script start — no other changes needed.

**Chinese small cities in rotation (23):** 苏州、杭州、平遥、丽江、凤凰、绍兴、歙县、松阳、大理、阆中、同里、西塘、碛口、景德镇、乌镇、南浔、宏村、婺源、建水、束河、稻城、镇远、泸沽湖

**Historical figures in rotation (71):** 50 ancient Chinese (陶渊明、王维、李清照、欧阳修、范仲淹 … 苏东坡、唐寅、郑板桥、石涛 …) + 21 world pre-modern (马可·波罗、达·芬奇、维米尔、莫奈、巴赫、托尔斯泰、卡夫卡 …)

## Extending & customising

### Delivery schedule
Change the cron time to whatever fits your routine.

### News sources & topics
Each news script has a `FEEDS` dict near the top listing RSS sources by category. Add, remove, or replace feed URLs freely.

### Program format & content
The Claude prompt inside `write_broadcast()` (or `write_evening_broadcast()`, `write_sleep_script()`) is plain text — edit it to change sections, tone, language, or target audience.

### Night radio topics
Edit the four lists in `topics_calendar.py` to change the city/figure/culture/health pools. Each list entry is a plain Chinese string. Keep list lengths co-prime for best non-repeat behaviour.

### Sleep radio scenes
The bedtime story scene list is a `/`-separated string in `write_sleep_script()` inside `sleep_radio.py`. Current pool has 17 scenes including 7 characteristic Chinese small-city settings (平遥、凤凰、景德镇、松阳、绍兴、歙县、大理).

### Delivery channel
The final step is an HTTP POST with an MP3. Swap `send_audio()` to deliver via email, a local folder, or any other channel.

### Multiple listeners
Each script reads `LISTENER_NAME` and `WIFE_NAME` from `secrets.env`. To add a third listener, duplicate a script, point it at a new `TG_BOT_TOKEN` / `TG_CHAT_ID`, and add one cron line.

### Personal worklog
`worklog.py` + `worklog_bot.py` provide a lightweight SQLite task log with CLI and Telegram bot interfaces.

## Project structure

```
yt-agent/
├── news_radio_cc.py          # Morning news — CC edition
├── news_radio_wife.py        # Morning news — wife edition (timeout=900s)
├── news_radio_wife_noon.py   # Noon radio — wife edition
├── night_radio.py            # Evening culture radio
├── sleep_radio.py            # Bedtime radio
├── topics_calendar.py        # 365-day topic lookup table for night_radio
├── radio_utils.py            # Shared: Claude, TTS, FFmpeg, weather
├── secrets.env.example       # Template — copy to secrets.env
├── bgm/                      # Background music (not in git)
├── radio/                    # Output: morning (not in git)
├── radio_night/              # Output: evening (not in git)
├── radio_noon/               # Output: noon wife (not in git)
└── radio_sleep/              # Output: sleep (not in git)
```

## TTS calibration note

`zh-CN-XiaoxiaoNeural` at `+0%` rate runs at approximately **287 characters/minute**. Script length targets are set as `TARGET_MINUTES × 300` chars in prompts. Section time annotations in the Claude prompt are the primary lever for controlling episode length.

## License

MIT
