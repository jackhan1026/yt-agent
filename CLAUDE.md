# yt-agent — AI Radio Station

## Project overview
A personal AI radio station that generates daily Chinese-language audio programs using Claude (via `claude -p`) for scripting, Microsoft Edge TTS for voice synthesis, FFmpeg for BGM mixing, and Telegram Bot API for delivery.

## Scripts
| Script | Audience | Schedule | Length |
|---|---|---|---|
| `news_radio_cc.py` | CC (韩卿) | 06:45 daily | ~50 min |
| `news_radio_wife.py` | Wife (曾霓) | 07:00 daily | ~30 min |
| `news_radio_wife_noon.py` | Wife | 12:00 daily | ~30 min |
| `night_radio.py` | Both | 17:30 weekdays | ~30 min |
| `sleep_radio.py` | Both | 23:00 daily | ~20 min |

## Shared utilities (`radio_utils.py`)
- `call_claude(prompt, model, retries, timeout)` — runs `claude -p` subprocess; never uses `ANTHROPIC_API_KEY` directly
- `fetch_weather(city)` — wttr.in JSON API
- `get_audio_duration(path)` — ffprobe
- `mix_with_bgm(...)` — FFmpeg amix with loop + fade
- `synthesize_mp3(text, out_path, voice, rate, pitch)` — edge-tts async

## Running a script
```bash
. ./secrets.env
python news_radio_cc.py
```
All four env vars must be set; scripts crash immediately otherwise.

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
radio/          ← morning CC
radio_night/    ← evening "世界下班以后"
radio_noon/     ← wife noon
radio_sleep/    ← sleep "今晚慢慢睡"
```

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
