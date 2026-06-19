# yt-agent — AI Radio Station

## Project overview
A personal AI radio station that generates daily Chinese-language audio programs using Claude (via `claude -p`) for scripting, Microsoft Edge TTS for voice synthesis, FFmpeg for BGM mixing, and Telegram Bot API for delivery.

## Scripts
| Script | Audience | Schedule | Length |
|---|---|---|---|
| `news_radio_cc.py` | Listener 1 | 06:45 daily | ~50 min |
| `news_radio_wife.py` | Listener 2 | 07:00 daily | ~30 min |
| `news_radio_wife_noon.py` | Listener 2 | 12:00 daily | ~30 min |
| `night_radio.py` | Both | 17:30 weekdays | ~30 min |
| `sleep_radio.py` | Both | 23:00 daily | ~20 min |

## Key module: `topics_calendar.py`
Static 365-day topic lookup table for `night_radio.py`. No LLM calls, no file I/O — pure Python dict lookup by `day_of_year`.

| List | Size | Min repeat gap |
|---|---|---|
| `CITIES` (world + Chinese small cities) | 73 | 73 days |
| `HISTORY` (ancient Chinese + world pre-modern) | 71 | 71 days |
| `CULTURE` | 61 | 61 days |
| `HEALTH` | 59 | 59 days |

All four lengths are co-prime; the same combination never recurs within a human lifetime. `night_radio.py` imports `get_topics_for_day(doy)` and uses it to build a `directed_block` that tells Claude exactly which city, figure, culture theme, and health topic to cover — more reliable than negative "avoid" instructions.

## Shared utilities (`radio_utils.py`)
- `call_claude(prompt, model, retries, timeout)` — runs `claude -p` subprocess; default `timeout=300s`; **use `timeout=900` for long-form scripts**
- `fetch_weather(city)` — wttr.in JSON API
- `get_audio_duration(path)` — ffprobe
- `mix_with_bgm(...)` — FFmpeg amix with loop + fade
- `synthesize_mp3(text, out_path, voice, rate, pitch)` — edge-tts async

## Running a script
```bash
. ./secrets.env
venv/bin/python news_radio_cc.py
```
All required env vars must be set; scripts crash immediately otherwise.

## Timeout requirements
Long-form scripts that generate 7000+ chars need `timeout=900` in the `call_claude()` call. The default 300s is only sufficient for short caption/summary calls (haiku model). Current assignments:
- `news_radio_cc.py` → `timeout=900` ✓
- `news_radio_wife.py` → `timeout=900` ✓ (fixed 2026-06-18; was 300s causing daily failures)
- `night_radio.py` → `timeout=900` ✓
- All caption/summary helpers → default 300s (haiku, fast)

## TTS calibration
`zh-CN-XiaoxiaoNeural` at +0% rate ≈ 287 chars/min. Target length in prompts is set as `TARGET_MINUTES * 300` chars. Section time annotations in Claude prompts are the primary signal for length control.

## Claude model selection
- `sonnet` — all scripting tasks (creative, long-form, multi-section)
- `haiku` — caption / summary / topic-extraction helpers only

## BGM
- Morning: `bgm/bossa.mp3` at 38% volume
- Evening/Sleep: `bgm/night.mp3` at 14–25% volume
- Files are gitignored (download separately; see README)

## Output directories (gitignored)
```
radio/          ← morning CC + wife morning scripts/MP3s
radio_night/    ← evening "世界下班以后"
radio_noon/     ← wife noon
radio_sleep/    ← sleep "今晚慢慢睡"
```

## Night radio topic design
- `night_radio.py` Section 2 (city): 73-city pool across 50 world cities + 23 Chinese small cities
- `night_radio.py` Section 3 (history): 71-figure pool — 50 ancient Chinese (陶渊明 … 李煜、苏东坡、郑板桥 …) + 21 world pre-modern (达·芬奇、莫奈、托尔斯泰 …); never defaults to 苏轼 alone
- `sleep_radio.py` story scenes: 17-entry pool including 7 Chinese small city scenes (平遥、凤凰、景德镇、松阳、绍兴、歙县、大理)

## Secrets
Copy `secrets.env.example` → `secrets.env` and fill in real Telegram tokens. Never commit `secrets.env`.

## Cron layout (on the VPS)
```
45 06 * * *     news_radio_cc.py        >> radio.log
00 07 * * *     news_radio_wife.py      >> wife_radio.log
00 12 * * *     news_radio_wife_noon.py >> wife_noon_radio.log
30 17 * * 1-5   night_radio.py          >> night_radio.log
00 23 * * *     sleep_radio.py          >> sleep_radio.log
```
