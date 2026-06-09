# 🌙 《世界下班以后》晚间电台 · 部署清单

复用你已有的早间电台基础设施(VPS、Claude Code、Python venv、ffmpeg、Telegram bot),
只需要 **15 分钟** 就能加上这第二个电台。

---

## 配置决策(默认值)

- 🎙️ **音色**: `XiaomengNeural` 晓梦(温柔知性,深夜电台气质)
- 🎵 **BGM**: 推荐 Kevin MacLeod "Carefree" 或 "Cherry Blossom"(轻钢琴/竖琴)
- 🎚️ **BGM 音量**: 25%(晚上更柔和)
- 🐢 **语速**: -5%(夜晚节奏放慢)
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

### ② 创建脚本

```bash
cd ~/yt-agent
source venv/bin/activate
nano night_radio.py
```

把 `night_radio.py` 完整内容粘贴进去 → `Ctrl+O` → `Enter` → `Ctrl+X` 保存。

验证:
```bash
head -5 night_radio.py
```
应看到 `#!/usr/bin/env python3 -u` 和 `《世界下班以后》` 字样。

---

### ③ 手动测试

```bash
source secrets.env
nohup python3 night_radio.py > night_radio.log 2>&1 &
tail -f night_radio.log
```

⏱️ 预计 6-10 分钟(没有 RSS 抓取,比早间电台快)。

预期进度:
```
→ Fetching weather for Detroit…
  XX°C, ..., sunset 20:42
→ Writing evening broadcast with claude -p (sonnet)…
  script saved: ~7000 chars
→ Writing caption…
→ Synthesizing voice MP3 with Edge TTS…
  voice saved: ~11 MB
→ Mixing with BGM at 25% volume…
  mixed: ~28 MB
→ Sending to Telegram…
✓ Done.
```

收到 Telegram MP3 后听一下,主要看:
1. 主题选得有不有意思
2. 30 分钟节奏会不会太长/太短
3. 晓梦的声音是不是你喜欢的"晚间档"气质
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

最终 `crontab -l` 应该有两行:
```cron
45 06 * * * cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/news_radio_cc.py >> /root/yt-agent/radio.log 2>&1
30 17 * * 1-5 cd /root/yt-agent && . /root/yt-agent/secrets.env && /root/yt-agent/venv/bin/python /root/yt-agent/night_radio.py >> /root/yt-agent/night_radio.log 2>&1
```

---

## 后续可调

晚间电台跑稳之后,可能想微调,改 `night_radio.py` 顶部即可:

| 想改的 | 改哪行 |
|---|---|
| 换音色 | `EDGE_VOICE = "zh-CN-XiaomengNeural"` |
| 调语速 | `EDGE_RATE = "-5%"`(`-10%` 更慢,`+0%` 正常) |
| 改时长 | `TARGET_MINUTES = 30` |
| 改 BGM 响度 | `BGM_VOLUME = 0.25` |
| 换 BGM 曲子 | 替换 `~/yt-agent/bgm/night.mp3` 文件即可 |

---

## 文件位置

```
/root/yt-agent/
├── news_radio_cc.py          ← 早间(你)
├── night_radio.py            ← 晚间(《世界下班以后》)新加
├── secrets.env               ← 共用密钥
├── radio.log                 ← 早间日志
├── night_radio.log           ← 晚间日志(新)
├── venv/                     ← Python 环境(共用)
├── bgm/
│   ├── bossa.mp3             ← 早间 BGM
│   └── night.mp3             ← 晚间 BGM(新)
└── radio_night/              ← 晚间产出目录(新)
    ├── script_night_YYYYMMDD.txt
    ├── voice_night_YYYYMMDD.mp3
    └── night_YYYYMMDD.mp3
```

注意:两个电台**输出目录分开**,文件名也分开(`radio_` vs `night_`),不会混淆。

---

## 关于额度

两个电台 + Claude Code 写代码 + 你日常聊天,都共享同一个 Pro 订阅 5 小时滚动窗口。

每天:
- 早间电台 ≈ 6000-10000 字写稿(约 15000 token)
- 晚间电台 ≈ 7000 字写稿(约 10000 token)
- 合计:约 1 次 5 小时窗口的 25-30%

很安全,正常用不会超额。
