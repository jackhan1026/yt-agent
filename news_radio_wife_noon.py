#!/usr/bin/env python3
"""
Noon Radio — Second listener edition
主题: 全球时政 / 地缘政治 / 财经知识 / Podcast推荐
目标约 30 分钟 · 午间版 · BGM + edge-tts

TTS 速率校准 (XiaoxiaoNeural +5%): 约 290 字/分钟
→ 30 分钟需要至少 8700 字，设硬性下限 8500 字

Cron（每天 12:00）:
  00 12 * * * cd /root/yt-agent && . /root/yt-agent/secrets.env && \
    /root/yt-agent/venv/bin/python /root/yt-agent/news_radio_wife_noon.py \
    >> /root/yt-agent/wife_noon_radio.log 2>&1
"""

import os
import re
import json
import time
import requests
import feedparser
from datetime import datetime, timezone, timedelta
from radio_utils import call_claude, fetch_weather, get_audio_duration
from radio_utils import mix_with_bgm as _mix_bgm
from radio_utils import synthesize_mp3 as _synth

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN_WIFE"]
TG_CHAT_ID   = os.environ["TG_CHAT_ID_WIFE"]

WIFE_NAME        = os.environ.get("WIFE_NAME", "听众")
CITY_FOR_WEATHER = "Detroit"      # change to your city
TARGET_MINUTES = 30
TARGET_CHARS   = 9000
MIN_CHARS      = 8500

CLAUDE_MODEL   = "sonnet"  # haiku refuses long content generation in Claude Code context

EDGE_VOICE = "zh-CN-XiaoxiaoNeural"   # 女声，午间清爽感
EDGE_RATE  = "+5%"
EDGE_PITCH = "+0Hz"

BGM_PATH     = os.path.expanduser("~/yt-agent/bgm/bossa.mp3")
BGM_VOLUME   = 0.30
BGM_FADE_IN  = 2
BGM_FADE_OUT = 4

OUT_DIR     = os.path.expanduser("~/yt-agent/radio_noon")
FILE_PREFIX = "wife_noon_"
os.makedirs(OUT_DIR, exist_ok=True)

LOOKBACK_HOURS = 24

FEEDS = {
    "global_politics": [
        ("BBC World",
         "https://feeds.bbci.co.uk/news/world/rss.xml", "en"),
        ("Al Jazeera",
         "https://www.aljazeera.com/xml/rss/all.xml", "en"),
        ("NYT World",
         "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en"),
        ("Reuters World",
         "https://feeds.reuters.com/Reuters/worldNews", "en"),
        ("新华网国际",
         "http://www.xinhuanet.com/world/news_world.xml", "zh"),
    ],
    "geopolitics": [
        ("US-China Relations",
         "https://news.google.com/rss/search?q=%22US-China%22+OR+%22China+US%22+geopolitics+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Russia Ukraine",
         "https://news.google.com/rss/search?q=Russia+Ukraine+war+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Middle East",
         "https://news.google.com/rss/search?q=%22Middle+East%22+Israel+Gaza+when:1d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Indo-Pacific Taiwan",
         "https://news.google.com/rss/search?q=%22Indo-Pacific%22+OR+Taiwan+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
    ],
    "finance_economy": [
        ("Federal Reserve & Rates",
         "https://news.google.com/rss/search?q=%22Federal+Reserve%22+OR+%22interest+rate%22+OR+%22inflation%22+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("GDP & Economy",
         "https://news.google.com/rss/search?q=%22GDP%22+OR+%22economic+growth%22+OR+%22recession%22+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Yahoo Finance",
         "https://finance.yahoo.com/news/rssindex", "en"),
        ("BBC Business",
         "https://feeds.bbci.co.uk/news/business/rss.xml", "en"),
    ],
    "podcasts": [
        ("ChinaTalk",
         "https://chinatalk.media/feed/", "en"),
        ("Ezra Klein Show",
         "https://feeds.simplecast.com/82FI35Px", "en"),
        ("Prof G Pod",
         "https://feeds.megaphone.fm/GLT1412515089", "en"),
    ],
}

PODCAST_STATIC = {
    "ChinaTalk": "分析美中关系、中国科技政策与经济动态的深度播客（chinatalk.media）",
    "Ezra Klein Show": "《纽约时报》Ezra Klein的政治政策深度访谈（nytimes.com/column/ezra-klein-podcast）",
    "Prof G Pod with Scott Galloway": "Scott Galloway教授分析科技巨头、商业趋势与未来（Apple Podcasts ID: 1498802610）",
}


def synthesize_mp3(script, out_path):
    _synth(script, out_path, EDGE_VOICE, EDGE_RATE, EDGE_PITCH)

def mix_with_bgm(voice_path, bgm_path, output_path, bgm_volume=BGM_VOLUME):
    _mix_bgm(voice_path, bgm_path, output_path, bgm_volume, BGM_FADE_IN, BGM_FADE_OUT)


# ---------- RSS Feeds ----------
def fetch_feeds():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    podcast_cutoff = datetime.now(timezone.utc) - timedelta(days=7)
    bucket_items = {k: [] for k in FEEDS}
    for bucket, sources in FEEDS.items():
        for name, url, lang in sources:
            try:
                fp = feedparser.parse(url, request_headers={
                    "User-Agent": "Mozilla/5.0 (NewsRadio/1.0)"
                })
                is_podcast = (bucket == "podcasts")
                limit = 8 if is_podcast else 8
                this_cutoff = podcast_cutoff if is_podcast else cutoff
                for e in fp.entries[:limit]:
                    pub = e.get("published_parsed") or e.get("updated_parsed")
                    if pub:
                        pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                        if pub_dt < this_cutoff:
                            continue
                    else:
                        pub_dt = None
                    summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:150]
                    bucket_items[bucket].append({
                        "source":  name,
                        "lang":    lang,
                        "title":   e.title,
                        "summary": summary,
                        "url":     getattr(e, "link", ""),
                        "pub":     pub_dt.isoformat() if pub_dt else "unknown",
                    })
            except Exception as ex:
                print(f"[warn] {name}: {ex}")
                time.sleep(0.3)
    for k, v in bucket_items.items():
        print(f"  {k}: {len(v)} items")
    return bucket_items


# ---------- Broadcast script ----------
def write_broadcast(bucket_items, weather):
    today      = datetime.now().strftime("%Y年%m月%d日")
    weekday_cn = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][
        datetime.now().weekday()]

    weather_block = (
        f"{CITY_FOR_WEATHER}午间: {weather['temp_c']}°C/{weather['temp_f']}°F, "
        f"{weather['desc']}, 今日高/低 {weather['max_c']}°C/{weather['min_c']}°C"
        if weather else "(天气获取失败)"
    )

    podcast_items = bucket_items.get("podcasts", [])
    if podcast_items:
        podcast_data = json.dumps(podcast_items, ensure_ascii=False)[:3000]
        podcast_note = "以下是三个推荐播客的最新一期内容（来自RSS），请介绍最值得听的一集及理由："
    else:
        podcast_data = json.dumps(PODCAST_STATIC, ensure_ascii=False)
        podcast_note = "RSS未获取到，请根据你的知识介绍这三个播客最近值得听的内容："

    news_compact = json.dumps({
        k: v for k, v in bucket_items.items() if k != "podcasts"
    }, ensure_ascii=False)[:32000]

    prompt = f"""你是一位清爽专业的双语女主播，正在为"{WIFE_NAME}"录制专属午间新闻播报。

听众：{WIFE_NAME} 是CPA、国际税高级经理，就职于汽车Tier 1供应商。希望午休30分钟了解全球重大时事与财经动态，并获得优质播客推荐用于下班通勤收听。
风格：清晰简洁、信息密度高、有见地，语气比早间稍活泼，适合午间收听。
今天是 {today} {weekday_cn}，午间播报。

长度要求（严格遵守）：目标 {TARGET_CHARS} 字，整篇少于 {MIN_CHARS} 字视为失败。每节都必须写够规定字数，内容不足时把每条新闻讲得更深入，加入背景、历史脉络、影响分析。

称呼：开场仅用一次"{WIFE_NAME}"："{WIFE_NAME}，午安，今天世界发生了这些大事"，之后全部用"亲爱的"。

节目结构（严格遵守每节字数下限）：

第一部分：午间开场（最少400字）
"{WIFE_NAME}，午安，今天世界发生了这些大事"。今日 {weather_block}。活泼午间问候，用200-300字介绍今天节目亮点。

第二部分：全球时政（最少2500字，约9分钟）
今日最重要全球政治新闻，至少4条，每条600字：来源+是什么+背景+为什么重要+可能影响，涵盖美国/欧洲/亚洲，每条充分展开不要几句带过。

第三部分：地缘政治聚焦（最少2000字，约7分钟）
3-4条最值得关注的地缘事件，方向：美中关系/俄乌/中东/台海/印太，每条标明来源，分析对全球经济/供应链/汇率/贸易的影响，结合汽车Tier 1视角说明对制造业的意义。

第四部分：财经知识与市场（最少2000字，约7分钟）
3个有价值的财经动态或知识点，每个约650字：核心内容+背后逻辑+实际意义，可涉及宏观数据/央行政策/汇率/行业深度，每条标明来源，重点是让听众真正理解经济逻辑。

第五部分：播客推荐（最少1500字，约5分钟）
{podcast_note}
{podcast_data}

三个固定推荐播客：
1. ChinaTalk (chinatalk.media) — 美中关系、科技政策深度分析
2. Ezra Klein Show (NYT) — 政治政策深度访谈
3. The Prof G Pod with Scott Galloway — 科技商业趋势分析

每个播客约500字：2-3句介绍定位，本周/近期最值得听的一集（标题+嘉宾+核心议题+推荐理由），收听建议，与今日新闻的关联或独立价值。

第六部分：午间收尾（最少400字）
称呼"亲爱的"，一句鼓励（针对午间忙碌职场女性，每天换说法），提醒午饭后走一走/补充水分/下午重要事项，结束语："我是您的AI午间播报员，今天到这里，明天午间再见，亲爱的，加油！"

文体：数字一律读全称，每条必须有来源（"据BBC今日报道"等），英文专有名词保留原文（GDP/CPI/Fed/NATO等），不用markdown/标题符号/列表/emoji，段落间空行，不出现[音乐][停顿]，只返回正文。

新闻素材（JSON，请利用 source 字段标注来源）：
{news_compact}
"""

    script = call_claude(prompt, model=CLAUDE_MODEL, timeout=900)
    if script.startswith("```"):
        script = re.sub(r"^```\w*\n?|\n?```$", "", script).strip()
    script = re.sub(
        r"^(?:好的[，,][^\n]*\n+|以下是[^\n]*\n+|下面是[^\n]*\n+|当然[，,][^\n]*\n+)+",
        "", script,
    ).strip()
    return script


def write_summary(script):
    prompt = (
        "用中文写不超过 350 字的午间播报概要，分四段"
        "（全球时政 / 地缘政治 / 财经市场 / 播客推荐），"
        "每段 2-3 要点，用 • 符号。不要标题，不要问候结尾。\n\n"
        f"播报稿（前 3500 字）:\n{script[:3500]}"
    )
    return call_claude(prompt, model="haiku")


# ---------- Telegram ----------
def send_audio(mp3_path, caption):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(mp3_path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{TG_BOT_TOKEN}/sendAudio",
            data={
                "chat_id":   TG_CHAT_ID,
                "caption":   caption[:1020],
                "title":     f"AI 午间播报 · {today}",
                "performer": f"{WIFE_NAME}专属午间电台",
            },
            files={"audio": (f"wife_noon_radio_{today}.mp3", f, "audio/mpeg")},
            timeout=300,
        )
    r.raise_for_status()


# ---------- Main ----------
def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY is set — will be unset for claude -p")

    print("→ Fetching weather…")
    weather = fetch_weather(CITY_FOR_WEATHER)
    if weather:
        print(f"  {weather['temp_c']}°C, {weather['desc']}")

    print("→ Fetching RSS feeds…")
    items = fetch_feeds()
    total = sum(len(v) for v in items.values())
    if total < 5:
        print(f"[abort] only {total} fresh items, skipping today")
        return

    today = datetime.now().strftime("%Y%m%d")

    print(f"→ Writing noon broadcast ({CLAUDE_MODEL}, target {TARGET_CHARS} chars)…")
    script = write_broadcast(items, weather)

    if len(script) < MIN_CHARS:
        print(f"  ⚠️  Script too short ({len(script)} chars < {MIN_CHARS} minimum). Retrying…")
        script = write_broadcast(items, weather)

    char_count = len(script)
    estimated_min = round(char_count / 290)
    print(f"  script: {char_count} chars ≈ {estimated_min} min estimated")

    script_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}script_{today}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  saved → {script_path}")

    print("→ Writing Telegram caption…")
    caption = write_summary(script)

    print("→ Synthesizing voice MP3…")
    voice_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}voice_{today}.mp3")
    synthesize_mp3(script, voice_path)
    voice_mb  = os.path.getsize(voice_path) / 1024 / 1024
    voice_dur = get_audio_duration(voice_path) / 60
    print(f"  voice: {voice_mb:.1f} MB, {voice_dur:.1f} min")

    final_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}radio_{today}.mp3")
    if os.path.exists(BGM_PATH):
        mix_with_bgm(voice_path, BGM_PATH, final_path, BGM_VOLUME)
        final_dur = get_audio_duration(final_path) / 60
        print(f"  mixed: {os.path.getsize(final_path)/1024/1024:.1f} MB, {final_dur:.1f} min")
    else:
        print(f"  [warn] BGM not found, sending voice only")
        final_path = voice_path

    print("→ Sending to Telegram…")
    send_audio(final_path, caption)
    print("✓ Done.")


if __name__ == "__main__":
    main()
