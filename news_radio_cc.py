#!/usr/bin/env python3
"""Daily News Radio — morning edition · BGM + stock market summary."""

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

TG_BOT_TOKEN  = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID    = os.environ["TG_CHAT_ID"]

LOOKBACK_HOURS = 36
TARGET_MINUTES = 50
CLAUDE_MODEL   = "sonnet"         # sonnet required — haiku refuses content generation in CC context

LISTENER_NAME    = os.environ.get("LISTENER_NAME", "听众")
CITY_FOR_WEATHER = "Detroit"      # change to your city

EDGE_VOICE = "zh-CN-XiaoxiaoNeural"
EDGE_RATE  = "+0%"
EDGE_PITCH = "+0Hz"

BGM_PATH     = os.path.expanduser("~/yt-agent/bgm/bossa.mp3")
BGM_VOLUME   = 0.38
BGM_FADE_IN  = 2
BGM_FADE_OUT = 4

OUT_DIR = os.path.expanduser("~/yt-agent/radio")
os.makedirs(OUT_DIR, exist_ok=True)

FEEDS = {
    "ai_tech": [
        ("BBC Technology",   "https://feeds.bbci.co.uk/news/technology/rss.xml", "en"),
        ("MIT Tech Review",  "https://www.technologyreview.com/feed/",           "en"),
        ("OpenAI Blog",      "https://openai.com/blog/rss.xml",                  "en"),
        ("Anthropic News",   "https://www.anthropic.com/news/rss.xml",           "en"),
        ("Ars Technica",     "https://feeds.arstechnica.com/arstechnica/technology-lab", "en"),
        ("Wired",            "https://www.wired.com/feed/rss",                   "en"),
        ("Science Daily",    "https://www.sciencedaily.com/rss/top.xml",         "en"),
        ("Nature",           "https://www.nature.com/nature.rss",                "en"),
        ("机器之心",          "https://www.jiqizhixin.com/rss",                    "zh"),
        ("36Kr AI",          "https://36kr.com/feed",                            "zh"),
    ],
    "auto": [
        ("Detroit Three",
         "https://news.google.com/rss/search?q=(%22General+Motors%22+OR+%22Ford+Motor%22+OR+Stellantis)+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Tesla News",
         "https://news.google.com/rss/search?q=Tesla+Elon+Musk+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("BYD News",
         "https://news.google.com/rss/search?q=BYD+%E6%AF%94%E4%BA%9A%E8%BF%AA+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Hyundai Kia News",
         "https://news.google.com/rss/search?q=(Hyundai+OR+Kia)+electric+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Toyota News",
         "https://news.google.com/rss/search?q=Toyota+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("European Auto News",
         "https://news.google.com/rss/search?q=(Volkswagen+OR+BMW+OR+Mercedes)+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("36Kr 汽车",        "https://36kr.com/feed",                            "zh"),
    ],
}


def synthesize_mp3(script, out_path):
    _synth(script, out_path, EDGE_VOICE, EDGE_RATE, EDGE_PITCH)

def mix_with_bgm(voice_path, bgm_path, output_path, bgm_volume=BGM_VOLUME):
    _mix_bgm(voice_path, bgm_path, output_path, bgm_volume, BGM_FADE_IN, BGM_FADE_OUT)


# ---------- US Stock Market ----------
def fetch_market_data():
    weekday = datetime.now().weekday()   # 0=Mon … 6=Sun
    if weekday in (0, 6):               # Mon or Sun — no trading yesterday
        print("  [market] Skipped (Sunday/Monday — markets were closed yesterday)")
        return None

    symbols = [("^GSPC", "标普500"), ("^DJI", "道琼斯"), ("^IXIC", "纳斯达克")]
    results = []
    for symbol, name in symbols:
        try:
            url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
                   f"?range=5d&interval=1d")
            r = requests.get(url, headers={
                "User-Agent": "Mozilla/5.0",
                "Accept": "application/json",
            }, timeout=15)
            r.raise_for_status()
            data = r.json()
            result = data["chart"]["result"][0]
            closes     = result["indicators"]["quote"][0]["close"]
            timestamps = result["timestamp"]
            valid = [(t, c) for t, c in zip(timestamps, closes) if c is not None]
            if len(valid) >= 2:
                prev_c = valid[-2][1]
                last_c = valid[-1][1]
                change = last_c - prev_c
                pct    = change / prev_c * 100
                direction = "上涨" if change > 0 else "下跌"
                results.append({
                    "name": name, "symbol": symbol,
                    "close": round(last_c, 2),
                    "change": round(change, 2),
                    "pct": round(abs(pct), 2),
                    "direction": direction,
                })
                print(f"  {name}: {last_c:,.2f} ({direction} {abs(pct):.2f}%)")
        except Exception as e:
            print(f"[warn] market {symbol}: {e}")
    return results if results else None


# ---------- RSS Feeds ----------
def fetch_feeds():
    cutoff = datetime.now(timezone.utc) - timedelta(hours=LOOKBACK_HOURS)
    bucket_items = {k: [] for k in FEEDS}
    for bucket, sources in FEEDS.items():
        for name, url, lang in sources:
            try:
                fp = feedparser.parse(url, request_headers={
                    "User-Agent": "Mozilla/5.0 (NewsRadio/1.0)"
                })
                for e in fp.entries[:8]:
                    pub = e.get("published_parsed") or e.get("updated_parsed")
                    if not pub:
                        continue
                    pub_dt = datetime(*pub[:6], tzinfo=timezone.utc)
                    if pub_dt < cutoff:
                        continue
                    summary = re.sub(r"<[^>]+>", "", e.get("summary", ""))[:150]
                    weekday_en = ["Monday","Tuesday","Wednesday","Thursday",
                                  "Friday","Saturday","Sunday"][pub_dt.weekday()]
                    bucket_items[bucket].append({
                        "source": name, "lang": lang,
                        "title": e.title, "summary": summary,
                        "url": e.link, "pub": pub_dt.isoformat(),
                        "pub_weekday": weekday_en,
                    })
            except Exception as ex:
                print(f"[warn] {name}: {ex}")
                time.sleep(0.5)
    for k, v in bucket_items.items():
        print(f"  {k}: {len(v)} items")
    return bucket_items


# ---------- Broadcast script ----------
def write_broadcast(bucket_items, weather, market_data=None):
    today = datetime.now().strftime("%Y年%m月%d日")
    weekday_cn = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][
        datetime.now().weekday()]
    target_chars = TARGET_MINUTES * 300

    weather_block = (
        f"{CITY_FOR_WEATHER}今日天气:\n"
        f"- 当前 {weather['temp_c']}°C/{weather['temp_f']}°F,体感 {weather['feels_like_c']}°C\n"
        f"- {weather['desc']},高/低 {weather['max_c']}°C/{weather['min_c']}°C\n"
        f"- 湿度 {weather['humidity']}%,风速 {weather['wind_kmh']} km/h\n"
        f"- 日出 {weather['sunrise']},日落 {weather['sunset']}"
        if weather else "(天气获取失败,请简短跳过)"
    )

    if market_data:
        market_lines = "\n".join(
            f"- {m['name']}({m['symbol']}): 收盘 {m['close']:,.2f}，{m['direction']} {m['pct']}%"
            for m in market_data
        )
        market_section = f"""

第四部分 昨日美股市场概况(约 4 分钟)
昨日美国三大股指收盘:
{market_lines}
每个指数一句话:名称+收盘点数+涨跌幅,一句话点评整体市场情绪,结尾加"以上数据仅供参考,不构成任何投资建议。"
"""
    else:
        market_section = ""

    compact = json.dumps(bucket_items, ensure_ascii=False)[:48000]

    prompt = f"""你是温暖的双语女主播,为听众"{LISTENER_NAME}"录制专属早间新闻播报。
风格: 温暖家人型,亲切自然。今天是 {today} {weekday_cn}。
总长度约 {TARGET_MINUTES} 分钟,约 {target_chars} 字(硬性要求,不够时把每条新闻讲得更深入、更有背景和分析)。

称呼: 第一句用"{LISTENER_NAME}"(仅此一次): "{LISTENER_NAME},早上好,新的一天开始啦",之后全部用"亲爱的"。

结构(严格按序):

第一部分 开场问候(约2分钟)
开场问候,报日期星期,播报{CITY_FOR_WEATHER}天气(摄氏度为主),给一句具体建议,过渡到新闻。

第二部分 科技/AI/科学新闻(8条,约20分钟)
选最值得听的AI、高科技、科学突破新闻,每条标明来源和时间,每条约2.5分钟:来源+是什么+为什么重要+对普通人或社会的影响。涵盖AI前沿、芯片/硬件、科学发现等多角度。

第三部分 汽车产业新闻(8条,约24分钟)
涵盖通用/福特/Stellantis(至少一条)、特斯拉(一条)、比亚迪(一条)、现代/起亚(一条,韩国车企)、丰田(一条,日本车企)、大众/宝马/奔驰任一(一条,欧洲车企),每条约3分钟:标明来源+核心动态+行业影响+对消费者的意义+与竞争对手的横向比较。{market_section}

第{"五" if market_data else "四"}部分 暖心结尾(约2分钟)
称呼用"亲爱的",提醒中午按时吃饭、多走走、休息眼睛,一句温暖鼓励(每天换说法)。
结束语: "我是您的AI主播,今天播报到这里,明天同一时间再见,亲爱的,加油!"

文体: 数字读全称,每条必须有来源如"据BBC周一报道",英文专有名词保留原文,不用markdown/列表/emoji,段落间空行,只返回正文。

天气: {weather_block}

新闻(JSON,请利用source和pub_weekday字段):
{compact}
"""
    script = call_claude(prompt, model=CLAUDE_MODEL, timeout=900)
    if script.startswith("```"):
        script = re.sub(r"^```\w*\n?|\n?```$", "", script).strip()
    return script


def write_summary(script):
    prompt = (
        "用中文写不超过 500 字的播报概要,分两段(科技AI科学 / 汽车产业),"
        "每段 3-4 个要点,用 • 符号。不要标题,不要问候和结尾。\n\n"
        f"播报稿:\n{script[:12000]}"
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
                "title":     f"AI 晨间播报 · {today}",
                "performer": "早间电台",
            },
            files={"audio": ("morning_radio.mp3", f, "audio/mpeg")},
            timeout=300,
        )
    r.raise_for_status()


# ---------- Main ----------
def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY is set — will be unset for claude -p")

    print(f"→ Fetching weather for {CITY_FOR_WEATHER}…")
    weather = fetch_weather(CITY_FOR_WEATHER)
    if weather:
        print(f"  {weather['temp_c']}°C, {weather['desc']}, "
              f"high {weather['max_c']}°C / low {weather['min_c']}°C")

    print("→ Fetching US stock market data…")
    market_data = fetch_market_data()

    print("→ Fetching RSS feeds…")
    items = fetch_feeds()
    total = sum(len(v) for v in items.values())
    if total < 5:
        print(f"[abort] only {total} fresh items, skipping today")
        return

    print(f"→ Writing broadcast script ({CLAUDE_MODEL})…")
    script = write_broadcast(items, weather, market_data)
    today  = datetime.now().strftime("%Y%m%d")
    script_path = os.path.join(OUT_DIR, f"script_{today}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  script saved: {len(script)} chars → {script_path}")

    print("→ Writing Telegram caption…")
    caption = write_summary(script)

    print("→ Synthesizing voice MP3…")
    voice_path = os.path.join(OUT_DIR, f"voice_{today}.mp3")
    synthesize_mp3(script, voice_path)
    print(f"  voice: {os.path.getsize(voice_path)/1024/1024:.1f} MB")

    print(f"→ Mixing with BGM…")
    final_path = os.path.join(OUT_DIR, f"radio_{today}.mp3")
    if os.path.exists(BGM_PATH):
        mix_with_bgm(voice_path, BGM_PATH, final_path, BGM_VOLUME)
        print(f"  mixed: {os.path.getsize(final_path)/1024/1024:.1f} MB")
    else:
        print(f"  [warn] BGM not found at {BGM_PATH}, sending voice only")
        final_path = voice_path

    print("→ Sending to Telegram…")
    send_audio(final_path, caption)
    print("✓ Done.")


if __name__ == "__main__":
    main()
