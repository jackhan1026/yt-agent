# AI Personal Radio Station

A self-hosted AI radio station that generates personalized Chinese-language audio programs every day — scripted by Claude, voiced by Microsoft Edge TTS, mixed with background music, and delivered over Telegram.

## Programs

| Program | Description | Target | Length |
|---|---|---|---|
| **晨间播报** (`news_radio_cc.py`) | Tech/AI/science + auto industry news digest + US stock market | CC (韩卿) | ~50 min |
| **妻子晨间** (`news_radio_wife.py`) | Morning news for wife | 曾霓 | ~30 min |
| **妻子午间** (`news_radio_wife_noon.py`) | Global politics / geopolitics / finance | 曾霓 | ~30 min |
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

## Project structure

```
yt-agent/
├── news_radio_cc.py          # Morning news — CC edition
├── news_radio_wife.py        # Morning news — wife edition
├── news_radio_wife_noon.py   # Noon radio — wife edition
├── night_radio.py            # Evening culture radio
├── sleep_radio.py            # Bedtime radio
├── radio_utils.py            # Shared: Claude, TTS, FFmpeg, weather
├── secrets.env.example       # Template — copy to secrets.env
├── bgm/                      # Background music (not in git)
├── radio/                    # Output: morning CC (not in git)
├── radio_night/              # Output: evening (not in git)
├── radio_noon/               # Output: noon wife (not in git)
└── radio_sleep/              # Output: sleep (not in git)
```

## TTS calibration note

`zh-CN-XiaoxiaoNeural` at `+0%` rate runs at approximately **287 characters/minute**. Script length targets are set as `TARGET_MINUTES × 300` chars in prompts. Section time annotations in the Claude prompt are the primary lever for controlling episode length.

## License

MIT
