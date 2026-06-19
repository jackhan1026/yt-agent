#!/usr/bin/env python3 -u
"""
《世界下班以后》— 晚间电台
- 话题由 topics_calendar.py 静态日历决定,零 token 消耗,365 天不重复
- 生成后提取并保存今日话题 log（供人工回顾）
"""

import os
import re
import json
from datetime import datetime, timedelta
from topics_calendar import get_topics_for_day
from radio_utils import call_claude, fetch_weather, get_audio_duration, send_telegram_audio
from radio_utils import mix_with_bgm as _mix_bgm
from radio_utils import synthesize_mp3 as _synth

TG_BOT_TOKEN      = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID        = os.environ["TG_CHAT_ID"]
TG_BOT_TOKEN_WIFE = os.environ["TG_BOT_TOKEN_WIFE"]
TG_CHAT_ID_WIFE   = os.environ["TG_CHAT_ID_WIFE"]

TARGET_MINUTES   = 30
CLAUDE_MODEL     = "sonnet"        # creative content needs quality
LISTENER_NAME    = os.environ.get("LISTENER_NAME", "听众")
OWNER_PROFILE    = os.environ.get("OWNER_PROFILE", "")
CITY_FOR_WEATHER = os.environ["CITY_FOR_WEATHER"]

EDGE_VOICE = "zh-CN-XiaoxiaoNeural"
EDGE_RATE  = "-10%"
EDGE_PITCH = "-1Hz"

BGM_PATH     = os.path.expanduser("~/yt-agent/bgm/night.mp3")
BGM_VOLUME   = 0.25
BGM_FADE_IN  = 4
BGM_FADE_OUT = 6

OUT_DIR = os.path.expanduser("~/yt-agent/radio_night")
os.makedirs(OUT_DIR, exist_ok=True)


def synthesize_mp3(script, out_path):
    script_for_tts = script.replace("[停顿]", "。。。")
    _synth(script_for_tts, out_path, EDGE_VOICE, EDGE_RATE, EDGE_PITCH)

def mix_with_bgm(voice_path, bgm_path, output_path, bgm_volume=BGM_VOLUME):
    _mix_bgm(voice_path, bgm_path, output_path, bgm_volume, BGM_FADE_IN, BGM_FADE_OUT)


# ---------- Topic log (archive only, not used for topic selection) ----------


def extract_and_save_topics(script: str):
    today = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(OUT_DIR, f"topics_night_{today}.json")
    prompt = (
        "从以下晚间电台节目文字稿中提取各节的核心主题，严格以JSON格式返回，不加任何其他文字：\n"
        '{"city": "第2节世界城市漫游中的城市名", '
        '"history": "第3节历史故事的主角或主题（10字以内）", '
        '"culture": "第4节文化细节的主题（10字以内）", '
        '"health": "第5节健康养生的主题（10字以内）"}\n\n'
        f"文字稿（前4000字）:\n{script[:4000]}"
    )
    raw = call_claude(prompt, model="haiku")
    try:
        m = re.search(r'\{[^}]+\}', raw, re.DOTALL)
        if m:
            topics = json.loads(m.group())
            with open(log_path, "w", encoding="utf-8") as f:
                json.dump(topics, f, ensure_ascii=False, indent=2)
            print(f"  [topics] Today's topics saved → {log_path}")
            return topics
    except Exception as e:
        print(f"  [topics] Failed to extract/save topics: {e}")
    return None


# ---------- Broadcast script ----------
def write_evening_broadcast(weather, today_topics: dict):
    today       = datetime.now().strftime("%Y年%m月%d日")
    weekday_cn  = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][
        datetime.now().weekday()]
    target_chars = TARGET_MINUTES * 300

    if weather:
        weather_block = (
            f"今晚{CITY_FOR_WEATHER}天气(可融入开场氛围,不要照念数据):\n"
            f"- 当前 {weather['temp_c']}°C,{weather['desc']},体感 {weather['feels_like_c']}°C\n"
            f"- 今日最高 {weather['max_c']}°C / 最低 {weather['min_c']}°C\n"
            f"- 日落约 {weather['sunset']}"
        )
    else:
        weather_block = "(天气信息缺失,用通用傍晚氛围描写)"

    directed_block = (
        f"\n**今天各节的指定话题（必须严格按照，不要更改）：**\n"
        f"- 第2节 城市漫游：今天讲「{today_topics['city']}」\n"
        f"- 第3节 历史故事：今天主角是「{today_topics['history']}」\n"
        f"- 第4节 文化细节：今天聊「{today_topics['culture']}」\n"
        f"- 第5节 健康养生：今天聊「{today_topics['health']}」\n"
    )

    prompt = f"""你是我的私人晚间电台主持人，每天下班后为我录制一期《世界下班以后》。

关于我：{OWNER_PROFILE}

节目名：《世界下班以后》。今天是 {today} {weekday_cn}。
{directed_block}
目标约 {TARGET_MINUTES} 分钟，总字数不少于 {target_chars} 字（硬性要求，节目偏短是最大失败）。

文体：全中文，短段落，有呼吸感，适合TTS，可加[停顿]，不用markdown/列表/emoji，氛围感和画面感优先，不确定细节用"据说…"，只返回正文。

节目结构（七节都必须写完整）：

第1节 开场（最少500字）
**第一句必须原文照用**："{LISTENER_NAME}，下班了，辛苦了，欢迎收听为你个人定制的晚间节目。"
然后融入今晚天气、季节感、傍晚空气、开车回家的感觉。
{weather_block}

第2节 世界城市漫游（最少1800字）
今天讲「{today_topics['city']}」。像傍晚在这座城市慢慢散步，写小街道、光线、气味、咖啡馆、市场、建筑、夜色。足够慢、足够细。

第3节 历史小故事（最少1800字）
独立一节，不与第2节合并。今天讲「{today_topics['history']}」的故事。轻松有趣，重点是"人"不是年代列表。要有细节、有转折、有情感，真正讲够7分钟。

第4节 文化与生活细节（最少1200字）
独立一节。今天聊「{today_topics['culture']}」，充分展开，聊出深度和温度。

第5节 健康、身体与养生（最少900字）
独立一节，非常重要，不要省略。今天聊「{today_topics['health']}」。风格温柔，像真正关心听众的朋友。

第6节 轻松笑话与奇闻（最少400字）
温和幽默，世界奇闻或历史趣事，要真正有趣，写够两分钟。

第7节 结尾（最少700字）
慢慢结束，情绪安静，感觉世界很大，生活有很多温柔小事。最后一句如："开车慢一点。今晚早点休息。"

总字数不少于 {target_chars} 字，七节都必须写完整。
"""
    script = call_claude(prompt, timeout=900)
    if script.startswith("```"):
        script = re.sub(r"^```\w*\n?|\n?```$", "", script).strip()
    script = re.sub(
        r"^(?:好的[，,][^\n]*\n+|以下是[^\n]*\n+|下面是[^\n]*\n+)+",
        "", script,
    ).strip()
    return script


def write_caption(script):
    prompt = (
        "用中文写不超过 180 字的今晚电台节目预告,温柔口吻,"
        "提一下今晚城市和历史故事,不用列表,不用标题,直接写。结尾一句温柔的话。\n\n"
        f"节目稿:\n{script[:2000]}"
    )
    return call_claude(prompt, model="haiku")


# ---------- Telegram ----------
def _send_audio_to(bot_token, chat_id, mp3_path, caption):
    today = datetime.now().strftime("%Y-%m-%d")
    send_telegram_audio(
        mp3_path, bot_token, chat_id,
        caption=caption,
        title=f"《世界下班以后》· {today}",
        performer="晚间电台",
    )

def send_audio(mp3_path, caption):
    recipients = [
        (TG_BOT_TOKEN,      TG_CHAT_ID,      "main"),
        (TG_BOT_TOKEN_WIFE, TG_CHAT_ID_WIFE, "wife"),
    ]
    for bot_token, chat_id, label in recipients:
        print(f"  → sending to {label}…")
        _send_audio_to(bot_token, chat_id, mp3_path, caption)
        print(f"    ✓ sent to {label}")


# ---------- Main ----------
def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY is set — will be unset for claude -p")

    print(f"→ Fetching weather for {CITY_FOR_WEATHER}…")
    weather = fetch_weather(CITY_FOR_WEATHER)
    if weather:
        print(f"  {weather['temp_c']}°C, {weather['desc']}, sunset {weather['sunset']}")

    doy = datetime.now().timetuple().tm_yday
    today_topics = get_topics_for_day(doy)
    print(f"→ Today's topics (day {doy}): city={today_topics['city']}, "
          f"history={today_topics['history']}, "
          f"culture={today_topics['culture']}, health={today_topics['health']}")

    print(f"→ Writing evening broadcast ({CLAUDE_MODEL})…")
    script = write_evening_broadcast(weather, today_topics)
    today  = datetime.now().strftime("%Y%m%d")
    script_path = os.path.join(OUT_DIR, f"script_night_{today}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  script saved: {len(script)} chars → {script_path}")

    print("→ Extracting & saving today's topics…")
    extract_and_save_topics(script)

    print("→ Writing caption…")
    caption = write_caption(script)

    print("→ Synthesizing voice MP3…")
    voice_path = os.path.join(OUT_DIR, f"voice_night_{today}.mp3")
    synthesize_mp3(script, voice_path)
    print(f"  voice: {os.path.getsize(voice_path)/1024/1024:.1f} MB")

    final_path = os.path.join(OUT_DIR, f"night_{today}.mp3")
    if os.path.exists(BGM_PATH):
        print(f"→ Mixing with BGM…")
        mix_with_bgm(voice_path, BGM_PATH, final_path, BGM_VOLUME)
        print(f"  mixed: {os.path.getsize(final_path)/1024/1024:.1f} MB")
    else:
        print(f"  [warn] BGM not found, sending voice only")
        final_path = voice_path

    print("→ Sending to Telegram…")
    send_audio(final_path, caption)
    print("✓ Done.")


if __name__ == "__main__":
    main()
