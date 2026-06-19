# 🌙 《世界下班以后》晚间电台 · 部署清单

复用你已有的早间电台基础设施(VPS、Claude Code、Python venv、ffmpeg、Telegram bot),
只需要 **15 分钟** 就能加上这第二个电台。

---

## 配置决策(默认值)

- 🎙️ **音色**: `XiaoxiaoNeural` 晓晓(温柔知性,深夜电台气质)
- 🎵 **BGM**: 推荐 Kevin MacLeod "Carefree" 或 "Cherry Blossom"(轻钢琴/竖琴)
- 🎚️ **BGM 音量**: 25%(晚上更柔和)
- 🐢 **语速**: -10%(夜晚节奏放慢)
- ⏰ **触发时间**: 17:30(17:45 送达,适合 18:00 下班)
- ⏱️ **时长**: 30 分钟

听完不喜欢,vi 改脚本顶部 4-5 个常量即可。

---

## 部署步骤

### ① 下载夜晚专用背景音乐

```bash
mkdir -p ~/yt-agent/bgm
cd ~/yt-agent/bgm

# 选项 1: Kevin MacLeod "Cherry Blossom" — 轻柔钢琴,日本风
curl -L -o night.mp3 "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Cherry%20Blossom.mp3"

ls -la night.mp3
```

**备选**(如果上面下不动):
```bash
# 选项 2: "Carefree" — 轻柔木管 + 钢琴
curl -L -o night.mp3 "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Carefree.mp3"

# 选项 3: "Quiet Reflection" — 极简钢琴
curl -L -o night.mp3 "https://incompetech.com/music/royalty-free/mp3-royaltyfree/Quiet%20Reflection.mp3"
```

下载完应该是 3-8 MB。

---

### ② 确认两个核心文件都在位

晚间电台需要两个脚本文件:

| 文件 | 作用 |
|---|---|
| `night_radio.py` | 主程序：生成脚本、合成语音、发送 Telegram |
| `topics_calendar.py` | 365 天话题日历：决定每天播什么城市、历史故事、文化主题、健康话题 |

```bash
ls ~/yt-agent/night_radio.py ~/yt-agent/topics_calendar.py
```

两个文件都应该存在。`topics_calendar.py` 是纯 Python 静态数据,不需要任何配置。

---

### ③ 手动测试

```bash
cd ~/yt-agent
source secrets.env
nohup venv/bin/python night_radio.py > night_radio.log 2>&1 &
tail -f night_radio.log
```

⏱️ 预计 6-10 分钟(没有 RSS 抓取,比早间电台快)。

预期进度:
```
→ Fetching weather for Detroit…
  21°C, Partly cloudy, sunset 21:12
→ Today's topics (day 169): city=马德里, history=李煜, culture=印度手工纺织文化, health=高血压饮食调控
→ Writing evening broadcast (sonnet)…
  script saved: ~9000 chars → radio_night/script_night_YYYYMMDD.txt
→ Extracting & saving today's topics…
  [topics] Today's topics saved → radio_night/topics_night_YYYYMMDD.json
→ Writing caption…
→ Synthesizing voice MP3…
  voice: ~11 MB
→ Mixing with BGM…
  mixed: ~28 MB
→ Sending to Telegram…
✓ Done.
```

收到 Telegram MP3 后听一下,主要看:
1. 话题选得有没有意思(由日历决定,每天不同)
2. 30 分钟节奏会不会太长/太短
3. 声音和 BGM 是否喜欢
4. BGM 25% 是不是太轻/太响

---

### ④ 加 cron(早间电台后再加一行)

```bash
crontab -e
```

加这一行(已有早间那行不要动):

```cron
30 17 * * 1-5 cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/night_radio.py >> /root/yt-agent/night_radio.log 2>&1
```

**关键细节**:
- `30 17` = 17:30 触发
- `* * 1-5` = 周一到周五(周末不下班就不推送)
  - 想周末也推送:改成 `* * *`
- 路径完全用绝对路径(cron 必需)

保存退出。

最终 `crontab -l` 应该包含:
```cron
45 06 * * *   cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/news_radio_cc.py >> /root/yt-agent/radio.log 2>&1
00 07 * * *   cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/news_radio_wife.py >> /root/yt-agent/wife_radio.log 2>&1
00 12 * * *   cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/news_radio_wife_noon.py >> /root/yt-agent/wife_noon_radio.log 2>&1
30 17 * * 1-5 cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/night_radio.py >> /root/yt-agent/night_radio.log 2>&1
00 23 * * *   cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/sleep_radio.py >> /root/yt-agent/sleep_radio.log 2>&1
```

---

## 话题日历 `topics_calendar.py`

晚间电台的每节话题由 `topics_calendar.py` 静态决定,**不消耗任何 token**。

### 工作原理

```python
from topics_calendar import get_topics_for_day
topics = get_topics_for_day(169)
# → {"city": "马德里", "history": "李煜", "culture": "印度手工纺织文化", "health": "高血压饮食调控"}
```

脚本用 `datetime.now().timetuple().tm_yday`(当年第几天)查表,直接告诉 Claude 今天讲什么。

### 话题池规模

| 维度 | 池大小 | 最短重复间隔 |
|---|---|---|
| 城市(世界 + 中国特色小城) | 73 | 73 天(约 2.4 个月) |
| 历史人物(古代中国 + 近现代世界) | 71 | 71 天(约 2.3 个月) |
| 文化主题 | 61 | 61 天(约 2 个月) |
| 健康话题 | 59 | 59 天(约 2 个月) |

四个数字互质 → 完全相同的话题组合要 **51,106 年**才会重复。

### 中国特色小城(23 座,在 73 城市中)
苏州、杭州、平遥、丽江、凤凰、绍兴、歙县、松阳、大理、阆中、同里、西塘、碛口、景德镇、乌镇、南浔、宏村、婺源、建水、束河、稻城、镇远、泸沽湖

### 历史人物(71 位)
- **古代中国(50 位)**: 陶渊明、王维、李清照、欧阳修、范仲淹、颜真卿、辛弃疾、陆游、米芾、柳宗元、白居易、郑板桥、石涛、徐霞客、李时珍、沈括、王阳明、纳兰性德、蒲松龄、袁枚、文征明、唐寅、赵孟頫、顾炎武、贺知章、温庭筠、李煜、苏东坡、黄庭坚、柳永、晏殊、张岱、归有光、李渔、黄公望、倪瓒、沈周、仇英、刘禹锡、杜牧、孟浩然、王昌龄、岑参、贾岛、韩愈、欧阳询、怀素、张旭、李格非、苏辙
- **世界历史名人(21 位)**: 马可·波罗、达·芬奇、维米尔、伦勃朗、莫奈、梵高、巴赫、莫扎特、贝多芬、舒伯特、蒙田、卢梭、赫尔曼·黑塞、安徒生、契诃夫、屠格涅夫、约翰·缪尔、托尔斯泰、狄更斯、雨果、卡夫卡

### 自定义话题
直接编辑 `topics_calendar.py` 中的四个列表(CITIES / HISTORY / CULTURE / HEALTH)。列表顺序决定轮换顺序;保持各列表长度互质效果最好。

---

## 后续可调

晚间电台跑稳之后,可能想微调:

| 想改的 | 怎么改 |
|---|---|
| 换音色 | 改 `night_radio.py` 顶部 `EDGE_VOICE` |
| 调语速 | 改 `EDGE_RATE`(`-10%` 更慢,`+0%` 正常) |
| 改时长 | 改 `TARGET_MINUTES = 30` |
| 改 BGM 响度 | 改 `BGM_VOLUME = 0.25` |
| 换 BGM 曲子 | 替换 `~/yt-agent/bgm/night.mp3` 文件 |
| 加/换城市 | 编辑 `topics_calendar.py` 中的 `CITIES` 列表 |
| 加/换历史人物 | 编辑 `topics_calendar.py` 中的 `HISTORY` 列表 |
| 加/换文化主题 | 编辑 `topics_calendar.py` 中的 `CULTURE` 列表 |
| 加/换健康话题 | 编辑 `topics_calendar.py` 中的 `HEALTH` 列表 |

---

## 文件位置

```
/root/yt-agent/
├── news_radio_cc.py          ← 早间(自己)
├── news_radio_wife.py        ← 早间(听众2,timeout=900s)
├── news_radio_wife_noon.py   ← 午间(听众2)
├── night_radio.py            ← 晚间《世界下班以后》
├── sleep_radio.py            ← 睡前《今晚慢慢睡》
├── topics_calendar.py        ← 365天话题日历(night_radio专用)
├── radio_utils.py            ← 公共工具(Claude/TTS/FFmpeg/天气)
├── secrets.env               ← 共用密钥
├── radio.log                 ← 早间日志
├── wife_radio.log            ← 听众2早间日志
├── wife_noon_radio.log       ← 听众2午间日志
├── night_radio.log           ← 晚间日志
├── sleep_radio.log           ← 睡前日志
├── venv/                     ← Python 环境(共用)
├── bgm/
│   ├── bossa.mp3             ← 早间 BGM
│   └── night.mp3             ← 晚间/睡前 BGM
├── radio/                    ← 早间产出(MP3 + 脚本)
├── radio_night/              ← 晚间产出 + 话题日志
│   ├── script_night_YYYYMMDD.txt
│   ├── voice_night_YYYYMMDD.mp3
│   ├── night_YYYYMMDD.mp3
│   └── topics_night_YYYYMMDD.json   ← 归档用,不用于话题选择
├── radio_noon/               ← 午间产出
└── radio_sleep/              ← 睡前产出
```

注意:两个电台**输出目录分开**,文件名也分开,不会混淆。

---

## 关于额度

五个电台 + Claude Code 日常使用,共享同一个 Pro 订阅。

每天 token 消耗估算:
- 早间(CC): 约 15,000 token(sonnet 写稿 + haiku 摘要)
- 早间(妻): 约 8,000 token(sonnet 写稿 + haiku 摘要)
- 午间(妻): 约 8,000 token
- 晚间: 约 10,000 token(sonnet 写稿) + **0 token 话题选择**(静态日历)
- 睡前: 约 7,000 token

合计约 5 万 token/天。话题选择已从 LLM 调用改为静态查表,每天节省 1-2 次 haiku 调用。
