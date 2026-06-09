#!/usr/bin/env python3 -u
"""
《今晚慢慢睡》— 睡前电台
每天晚上生成一期约 20 分钟的中文睡前放松节目。

Cron（每晚 23:00）:
  00 23 * * * cd /root/yt-agent && . /root/yt-agent/secrets.env && \
    /root/yt-agent/venv/bin/python /root/yt-agent/sleep_radio.py \
    >> /root/yt-agent/sleep_radio.log 2>&1
"""

import os
import re
import requests
from datetime import datetime, timedelta
from radio_utils import call_claude, get_audio_duration
from radio_utils import mix_with_bgm as _mix_bgm
from radio_utils import synthesize_mp3 as _synth

TG_BOT_TOKEN      = os.environ["TG_BOT_TOKEN"]
TG_CHAT_ID        = os.environ["TG_CHAT_ID"]
TG_BOT_TOKEN_WIFE = os.environ["TG_BOT_TOKEN_WIFE"]
TG_CHAT_ID_WIFE   = os.environ["TG_CHAT_ID_WIFE"]

TARGET_MINUTES = 20
CLAUDE_MODEL   = "sonnet"

EDGE_VOICE = "zh-CN-XiaoxiaoNeural"
EDGE_RATE  = "-18%"
EDGE_PITCH = "-2Hz"

BGM_PATH     = os.path.expanduser("~/yt-agent/bgm/night.mp3")
BGM_VOLUME   = 0.14
BGM_FADE_IN  = 6
BGM_FADE_OUT = 8

OUT_DIR = os.path.expanduser("~/yt-agent/radio_sleep")
os.makedirs(OUT_DIR, exist_ok=True)

HEALTHY_LIFE_TOPICS = [
    "早餐的重要性与营养搭配",
    "蔬菜推荐：菠菜的营养价值与食用方法",
    "蔬菜推荐：西兰花与抗氧化健康",
    "蔬菜推荐：胡萝卜与护眼健康",
    "每天饮水量与身体代谢",
    "减少精制糖的实用方法",
    "地中海饮食入门与日常实践",
    "益生菌食品与肠道健康",
    "坚果与健康脂肪的选择",
    "健康零食替代方案",
    "减少久坐的小习惯",
    "每日步行与心血管健康",
    "正念饮食：慢下来吃饭",
    "减少加工食品的实用策略",
    "植物性蛋白质来源推荐",
    "优质睡眠与饮食的关系",
    "补充维生素D的天然方式",
    "发酵食品：泡菜/酸奶/味噌的好处",
    "深色蔬菜叶菜类每周摄入建议",
    "减少晚餐分量与消化健康",
    "豆类食品的营养与烹饪方法",
    "蓝莓等浆果类水果的抗氧化作用",
    "健康烹饪方式：蒸煮vs油炸",
    "橄榄油与健康用油指南",
    "海鲜与Omega-3脂肪酸的好处",
]


def synthesize_mp3(script, out_path):
    script_for_tts = script.replace("[停顿]", "。。。")
    _synth(script_for_tts, out_path, EDGE_VOICE, EDGE_RATE, EDGE_PITCH)

def mix_with_bgm(voice_path, bgm_path, output_path, bgm_volume=BGM_VOLUME):
    _mix_bgm(voice_path, bgm_path, output_path, bgm_volume, BGM_FADE_IN, BGM_FADE_OUT)


# ---------- 健康话题日志 ----------
def get_yesterday_section2_topic() -> str:
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    log_path  = os.path.join(OUT_DIR, f"sleep_topic_{yesterday}.txt")
    if not os.path.exists(log_path):
        print("  [topic] No yesterday topic log found.")
        return ""
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            topic = f.read().strip()
        print(f"  [topic] Yesterday's section 2 topic: {topic}")
        return topic
    except Exception as e:
        print(f"  [topic] Failed to read yesterday log: {e}")
        return ""


def save_section2_topic(topic: str):
    today    = datetime.now().strftime("%Y%m%d")
    log_path = os.path.join(OUT_DIR, f"sleep_topic_{today}.txt")
    with open(log_path, "w", encoding="utf-8") as f:
        f.write(topic)
    print(f"  [topic] Today's section 2 topic saved: {topic} → {log_path}")


def extract_section2_topic(script: str) -> str:
    prompt = (
        "从以下睡前节目文字稿的第二部分（健康生活话题）中，"
        "用不超过15字的中文概括今晚讲的健康主题。"
        "只返回主题名称本身，不加任何其他文字。\n\n"
        f"文字稿（前3000字）:\n{script[:3000]}"
    )
    return call_claude(prompt, model="haiku").strip()


# ---------- 文字稿生成 ----------
def write_sleep_script(yesterday_topic: str = "") -> str:
    today      = datetime.now().strftime("%Y年%m月%d日")
    weekday_cn = ["星期一","星期二","星期三","星期四","星期五","星期六","星期日"][
        datetime.now().weekday()
    ]
    target_chars = TARGET_MINUTES * 240

    topic_avoid_note = (
        f"\n**昨天第二部分讲的是「{yesterday_topic}」，今天必须选不同的健康话题。**\n"
        if yesterday_topic else ""
    )

    topics_list = "\n".join(f"- {t}" for t in HEALTHY_LIFE_TOPICS)

    prompt = f"""你是《今晚慢慢睡》的文字创作者。今天是 {today} {weekday_cn}。

节目：每晚20分钟的睡前放松电台，温柔陪伴，无新闻无励志，不刺激大脑。
气质：温柔/安静/慢/有呼吸感/有中国意境（茶/瓷/月/灯/雨/书/院落）。
禁止：励志说教/新闻工作/悬疑恐怖/强烈情绪冲突/死亡疾病灾难政治。
语言：全中文，短句，段落间空行，停顿处用[停顿]不用省略号，不用markdown/列表/emoji/标题符号，只返回正文。
总字数不少于 {target_chars} 字（约20分钟），每节都要写够，偏短是最大失败。
{topic_avoid_note}
节目结构（五节，全部写完整，各部分间空行分隔，不要写"第X部分"等字样）：

睡前开场（最少400字）
轻轻欢迎。让听众感受：今天已经结束了，不需要再解决任何问题，可以慢慢把注意力从外面的世界收回来。语气温柔，像一个懂你的朋友低声说话。

健康生活小知识（最少800字）
{topic_avoid_note}从以下话题中选一个（每天轮换，不选昨天的）：
{topics_list}

风格：像关心你的朋友在睡前轻声分享一个小知识，不是课程不是医嘱，内容实用，节奏缓慢，多用[停顿]。

安静的小故事（最少1400字）
从以下场景中选一个（每天轮换）：
一家夜晚关门的旧书店 / 雨夜里的京都小巷 / 景德镇窑火慢慢暗下去的傍晚 / 一个老茶馆准备打烊的夜晚 / 博物馆夜里安静的展厅 / 一列慢慢行驶的夜行火车 / 一个旅人住进海边小旅馆 / 一个古城里慢慢熄灯的院子 / 苏州园林夜里的月光与水面 / 一位修复古画的老师傅在安静的午后 / 一个卖茶的老人关门前的最后一泡茶

无强冲突/悬疑/惊吓/悲伤/过度搞笑，只需安静/画面感/温度/细节/慢慢展开，要写够7分钟。

睡前文化意象（最少800字）
从以下选一个（每天轮换）：
一盏茶 / 一只白瓷杯 / 一页旧书 / 一幅山水画 / 一扇窗 / 一盏灯 / 一场小雨 / 一条夜里的河 / 月光落在桌面上 / 茶烟慢慢散开 / 旧木桌上的砚台 / 瓷器上的青色釉面

重点是安静的感受和意境，带一点中国审美（留白/清供/茶烟/瓷色），写够不要用几段带过。

睡前收尾（最少600字）
慢慢结束，语气越来越轻、越来越慢。让听众感觉：今天已经够了，可以休息了，明天再说。多用[停顿]，结尾如"晚安。""灯可以暗一点。呼吸可以慢一点。""我们明天再见。"
"""

    script = call_claude(prompt)

    if script.startswith("```"):
        script = re.sub(r"^```\w*\n?|\n?```$", "", script).strip()
    script = re.sub(
        r"^(?:好的[，,][^\n]*\n+|以下是[^\n]*\n+|下面是[^\n]*\n+|当然[，,][^\n]*\n+)+",
        "", script,
    ).strip()
    script = re.sub(r"^#{1,3}\s+.*$", "", script, flags=re.MULTILINE)
    script = re.sub(r"^[-•·]\s+", "", script, flags=re.MULTILINE)
    script = re.sub(r"\n{3,}", "\n\n", script).strip()

    return script


# ---------- Telegram caption ----------
def write_caption(script: str) -> str:
    prompt = (
        "用中文写一段不超过 150 字的《今晚慢慢睡》节目介绍，"
        "语气温柔安静，提一下今晚故事的场景和文化意象，"
        "不用列表，不用标题，直接写。结尾一句轻柔的晚安祝语。\n\n"
        f"节目稿（前 2000 字）:\n{script[:2000]}"
    )
    return call_claude(prompt, model="haiku")


# ---------- Telegram ----------
def _send_audio_to(bot_token: str, chat_id: str, mp3_path: str, caption: str, label: str):
    today = datetime.now().strftime("%Y-%m-%d")
    with open(mp3_path, "rb") as f:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendAudio",
            data={
                "chat_id":   chat_id,
                "caption":   caption[:1020],
                "title":     f"《今晚慢慢睡》· {today}",
                "performer": "睡前电台",
            },
            files={"audio": (f"sleep_radio_{today}.mp3", f, "audio/mpeg")},
            timeout=300,
        )
    r.raise_for_status()
    print(f"    ✓ sent to {label} (chat_id={chat_id})")


def send_audio(mp3_path: str, caption: str):
    recipients = [
        (TG_BOT_TOKEN,      TG_CHAT_ID,      "main"),
        (TG_BOT_TOKEN_WIFE, TG_CHAT_ID_WIFE, "wife"),
    ]
    for bot_token, chat_id, label in recipients:
        print(f"  → sending to {label}…")
        try:
            _send_audio_to(bot_token, chat_id, mp3_path, caption, label)
        except Exception as e:
            print(f"  [warn] failed to send to {label}: {e}")


# ---------- 主流程 ----------
def main():
    if os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠️  ANTHROPIC_API_KEY is set — will be unset for claude -p")

    today = datetime.now().strftime("%Y%m%d")
    ts    = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] ▶ 《今晚慢慢睡》睡前电台开始生成…")

    print("→ 读取昨天健康话题 log…")
    yesterday_topic = get_yesterday_section2_topic()

    print(f"→ 用 claude -p ({CLAUDE_MODEL}) 创作睡前文字稿…")
    script = write_sleep_script(yesterday_topic)
    script_path = os.path.join(OUT_DIR, f"sleep_radio_{today}.txt")
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script)
    print(f"  文字稿已保存：{len(script)} 字 → {script_path}")

    print("→ 提取今天的健康话题…")
    section2_topic = extract_section2_topic(script)
    save_section2_topic(section2_topic)

    print("→ 生成节目简介（Telegram caption）…")
    caption = write_caption(script)

    print("→ Edge TTS 合成人声 MP3…")
    voice_path = os.path.join(OUT_DIR, f"sleep_voice_{today}.mp3")
    synthesize_mp3(script, voice_path)
    voice_size = os.path.getsize(voice_path) / 1024 / 1024
    voice_dur  = get_audio_duration(voice_path) / 60
    print(f"  人声已保存：{voice_size:.1f} MB，时长约 {voice_dur:.1f} 分钟 → {voice_path}")

    final_path = os.path.join(OUT_DIR, f"sleep_radio_{today}.mp3")
    if os.path.exists(BGM_PATH):
        print(f"→ 混入 BGM（音量 {int(BGM_VOLUME*100)}%）…")
        mix_with_bgm(voice_path, BGM_PATH, final_path, BGM_VOLUME)
        final_size = os.path.getsize(final_path) / 1024 / 1024
        print(f"  混音完成：{final_size:.1f} MB → {final_path}")
    else:
        print(f"  [warn] BGM 文件未找到：{BGM_PATH}，将直接发送人声版本")
        final_path = voice_path

    print("→ 发送到 Telegram…")
    send_audio(final_path, caption)

    ts_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts_end}] ✓ 《今晚慢慢睡》完成。晚安。")


if __name__ == "__main__":
    main()
