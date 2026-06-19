#!/usr/bin/env python3
"""
Daily News Radio — Second listener edition
专注: 国际税 / Transfer Pricing / Tariff / Pillar Two / M&A / 美股 / 财报 / 大公司动态
约 30 分钟 · BGM + edge-tts
"""

import os
import re
import json
import time
import feedparser
from datetime import datetime, timezone, timedelta
from radio_utils import call_claude, fetch_weather, get_audio_duration, send_telegram_audio
from radio_utils import mix_with_bgm as _mix_bgm
from radio_utils import synthesize_mp3 as _synth

TG_BOT_TOKEN = os.environ["TG_BOT_TOKEN_WIFE"]
TG_CHAT_ID   = os.environ["TG_CHAT_ID_WIFE"]

WIFE_NAME      = os.environ.get("WIFE_NAME", "听众")
WIFE_PROFILE   = os.environ.get("WIFE_PROFILE", "")
TARGET_MINUTES = 30
CLAUDE_MODEL   = "sonnet"    # sonnet required — haiku refuses content generation in CC context
FILE_PREFIX    = "wife_"

CITY_FOR_WEATHER = os.environ["CITY_FOR_WEATHER"]

EDGE_VOICE = "zh-CN-YunyangNeural"   # 男声，沉稳主播风
EDGE_RATE  = "+0%"
EDGE_PITCH = "+0Hz"

BGM_PATH     = os.path.expanduser("~/yt-agent/bgm/bossa.mp3")
BGM_VOLUME   = 0.38
BGM_FADE_IN  = 2
BGM_FADE_OUT = 4

OUT_DIR = os.path.expanduser("~/yt-agent/radio")
os.makedirs(OUT_DIR, exist_ok=True)

LOOKBACK_HOURS = 30
SENT_LOG_PATH  = os.path.join(OUT_DIR, "wife_sent_log.json")
DEDUP_DAYS     = 7

FEEDS = {
    "intl_tax": [
        ("International Tax & TP",
         "https://news.google.com/rss/search?q=%22international+tax%22+OR+%22transfer+pricing%22+when:3d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Pillar Two Global Min Tax",
         "https://news.google.com/rss/search?q=%22Pillar+Two%22+OR+%22global+minimum+tax%22+OR+%22OECD+tax%22+when:7d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Tax Foundation",
         "https://taxfoundation.org/feed/", "en"),
    ],
    "tariff_macro": [
        ("Tariff Trade Policy",
         "https://news.google.com/rss/search?q=tariff+%22trade+policy%22+OR+%22trade+war%22+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Reuters Business",
         "https://feeds.reuters.com/reuters/businessNews", "en"),
    ],
    "ma_company": [
        ("M&A Deals",
         "https://news.google.com/rss/search?q=%22merger%22+OR+%22acquisition%22+%22billion%22+deal+when:3d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Big Tech M&A",
         "https://news.google.com/rss/search?q=(Apple+OR+Amazon+OR+Microsoft+OR+Google+OR+Nvidia+OR+Meta)+%22acquisition%22+OR+%22deal%22+OR+%22revenue%22+when:3d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Auto Industry Finance",
         "https://news.google.com/rss/search?q=(%22General+Motors%22+OR+%22Ford+Motor%22+OR+Stellantis)+%22earnings%22+OR+%22revenue%22+OR+%22tariff%22+when:3d&hl=en-US&gl=US&ceid=US:en", "en"),
    ],
    "stocks_earnings": [
        ("US Earnings Reports",
         "https://news.google.com/rss/search?q=%22earnings+report%22+OR+%22quarterly+results%22+%22EPS%22+when:3d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Growth Stocks",
         "https://news.google.com/rss/search?q=%22growth+stock%22+OR+%22high+growth%22+%22revenue+growth%22+when:2d&hl=en-US&gl=US&ceid=US:en", "en"),
        ("Yahoo Finance",
         "https://finance.yahoo.com/news/rssindex", "en"),
    ],
}


def synthesize_mp3(script, out_path):
    _synth(script, out_path, EDGE_VOICE, EDGE_RATE, EDGE_PITCH)

def mix_with_bgm(voice_path, bgm_path, output_path, bgm_volume=BGM_VOLUME):
    _mix_bgm(voice_path, bgm_path, output_path, bgm_volume, BGM_FADE_IN, BGM_FADE_OUT)


# ---------- Dedup log ----------
def load_sent_urls() -> set:
    if not os.path.exists(SENT_LOG_PATH):
        return set()
    try:
        with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
            log = json.load(f)
    except Exception as e:
        print(f"[warn] could not read sent log: {e}")
        return set()
    cutoff = datetime.now() - timedelta(days=DEDUP_DAYS)
    seen = set()
    for day_key, urls in log.items():
        try:
            if datetime.strptime(day_key, "%Y%m%d") >= cutoff:
                seen.update(urls)
        except ValueError:
            pass
    return seen


def save_sent_urls(today_key: str, urls: list):
    log = {}
    if os.path.exists(SENT_LOG_PATH):
        try:
            with open(SENT_LOG_PATH, "r", encoding="utf-8") as f:
                log = json.load(f)
        except Exception:
            log = {}
    cutoff = datetime.now() - timedelta(days=DEDUP_DAYS)
    log = {k: v for k, v in log.items()
           if _parse_day_key(k) and _parse_day_key(k) >= cutoff}
    existing = log.get(today_key, [])
    merged = list(dict.fromkeys(existing + urls))
    log[today_key] = merged
    with open(SENT_LOG_PATH, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)
    print(f"  sent-log updated: {len(merged)} URLs logged for {today_key}")


def _parse_day_key(key: str):
    try:
        return datetime.strptime(key, "%Y%m%d")
    except ValueError:
        return None


def filter_new_items(bucket_items: dict, sent_urls: set) -> dict:
    filtered = {}
    total_removed = 0
    for bucket, items in bucket_items.items():
        fresh = [it for it in items if it.get("url") not in sent_urls]
        removed = len(items) - len(fresh)
        if removed:
            print(f"  [{bucket}] removed {removed} already-sent articles")
        total_removed += removed
        filtered[bucket] = fresh
    if total_removed:
        print(f"  total deduped: {total_removed} articles skipped")
    return filtered


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
def write_broadcast(bucket_items, weather):
    today       = datetime.now().strftime("%Y年%m月%d日")
    weekday_cn  = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][
        datetime.now().weekday()]
    target_chars = TARGET_MINUTES * 300

    weather_block = (
        f"{CITY_FOR_WEATHER}今日天气:\n"
        f"- 当前 {weather['temp_c']}°C/{weather['temp_f']}°F,体感 {weather['feels_like_c']}°C\n"
        f"- {weather['desc']},高/低 {weather['max_c']}°C/{weather['min_c']}°C\n"
        f"- 日出 {weather['sunrise']},日落 {weather['sunset']}"
        if weather else "(天气获取失败,请简短跳过)"
    )

    compact = json.dumps(bucket_items, ensure_ascii=False)[:32000]

    prompt = f"""你是一位沉稳专业的双语男主播,正在为"{WIFE_NAME}"录制专属晨间财税播报。

听众: {WIFE_NAME}{(' ' + WIFE_PROFILE) if WIFE_PROFILE else ''}。
风格: 专业沉稳有深度,像懂她专业的同行在播报最新资讯。今天是 {today} {weekday_cn}。
总长度约 {TARGET_MINUTES} 分钟,约 {target_chars} 字(硬性要求,每条讲深讲透,必须达到字数)。

称呼: 第一句仅用一次"{WIFE_NAME}": "{WIFE_NAME},早上好,今天财税资讯来了",之后全部用"亲爱的"。

结构(严格按序,共约30分钟):

第一部分 开场问候(约90秒)
开场,报日期星期,播报{CITY_FOR_WEATHER}天气,一句专业激励,过渡到正文。

第二部分 国际税与转让定价(3-4条,约8分钟)
主题:国际税合规/TP/BEPS/各国税局新动态。每条标明来源和时间,格式:来源+核心+对国际税从业者的实务影响。

第三部分 Pillar Two与全球最低税(2-3条,约6分钟)
主题:OECD Pillar Two/15%全球最低税/各国实施进展。每条标明来源,重点:新实施法规/豁免更新/对汽车制造业具体影响。

第四部分 关税与贸易政策(3条,约6分钟)
主题:美中贸易关税/汽车行业关税/供应链税务风险。每条标明来源,结合Tier 1供应商视角分析实际影响。

第五部分 并购与大公司动态(3-4条,约6分钟)
主题:重大M&A/大公司财务/汽车行业并购。每条标明来源,可涉及交易结构/税务考量/行业格局影响。

第六部分 美股精选与财报(2-3条,约4分钟)
主题:美股潜力股/重要财报/机构观点。每条标明来源(Bloomberg/Reuters/Yahoo Finance等)。
结尾加:"以上仅供参考,不构成任何投资建议,请自行判断。"

第七部分 暖心结尾(约60秒)
称呼"亲爱的",给一句真诚鼓励(针对兼顾专业与家庭的职场女性,每天换说法)。
提醒:中午按时吃饭,下午给自己留5分钟喘息。
结束语:"我是您的AI专属主播,今天播报到这里,明天早上同一时间再见,亲爱的,加油!"

文体: 数字读全称,每条必须有来源,英文术语保留原文(TP/Pillar Two/M&A/EPS/EBITDA),不用markdown/列表/emoji,段落间空行,只返回正文。

天气: {weather_block}

素材(JSON):
{compact}
"""
    script = call_claude(prompt, model=CLAUDE_MODEL, timeout=900)
    if script.startswith("```"):
        script = re.sub(r"^```\w*\n?|\n?```$", "", script).strip()
    return script


def write_summary(script):
    prompt = (
        "用中文写不超过 400 字的播报概要,分五段"
        "(国际税TP / Pillar Two / 关税贸易 / 并购动态 / 美股财报),"
        "每段 2-3 要点,用 • 符号。不要标题,不要问候结尾。\n\n"
        f"播报稿:\n{script[:3500]}"
    )
    return call_claude(prompt, model="haiku")


# ---------- Telegram ----------
def send_audio(mp3_path, caption):
    today = datetime.now().strftime("%Y-%m-%d")
    send_telegram_audio(
        mp3_path, TG_BOT_TOKEN, TG_CHAT_ID,
        caption=caption,
        title=f"AI 财税晨间播报 · {today}",
        performer=f"{WIFE_NAME}专属晨间电台",
    )


# ---------- Main ----------
def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY is set — will be unset for claude -p")

    print(f"→ Fetching weather for {CITY_FOR_WEATHER}…")
    weather = fetch_weather(CITY_FOR_WEATHER)
    if weather:
        print(f"  {weather['temp_c']}°C, {weather['desc']}, "
              f"high {weather['max_c']}°C / low {weather['min_c']}°C")

    print("→ Loading sent-URL log (dedup)…")
    sent_urls = load_sent_urls()
    print(f"  {len(sent_urls)} URLs already seen in last {DEDUP_DAYS} days")

    print("→ Fetching RSS feeds…")
    items = fetch_feeds()
    items = filter_new_items(items, sent_urls)
    total = sum(len(v) for v in items.values())
    if total < 5:
        print(f"[abort] only {total} fresh/new items after dedup, skipping today")
        return

    print(f"→ Writing broadcast script ({CLAUDE_MODEL})…")
    script = write_broadcast(items, weather)
    today  = datetime.now().strftime("%Y%m%d")
    script_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}script_{today}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  script saved: {len(script)} chars → {script_path}")

    print("→ Writing Telegram caption…")
    caption = write_summary(script)

    print("→ Synthesizing voice MP3…")
    voice_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}voice_{today}.mp3")
    synthesize_mp3(script, voice_path)
    print(f"  voice: {os.path.getsize(voice_path)/1024/1024:.1f} MB")

    final_path = os.path.join(OUT_DIR, f"{FILE_PREFIX}radio_{today}.mp3")
    if os.path.exists(BGM_PATH):
        mix_with_bgm(voice_path, BGM_PATH, final_path, BGM_VOLUME)
        print(f"  mixed: {os.path.getsize(final_path)/1024/1024:.1f} MB")
    else:
        print(f"  [warn] BGM not found, sending voice only")
        final_path = voice_path

    print("→ Sending to Telegram…")
    send_audio(final_path, caption)

    all_urls = [it["url"] for bucket in items.values() for it in bucket if it.get("url")]
    save_sent_urls(today, all_urls)

    print("✓ Done.")


if __name__ == "__main__":
    main()
