import openai
import requests
import os
import re
import time
import json
from datetime import datetime, timezone, timedelta

# 从环境变量获取 API Key 和 Telegram 配置
POE_API_KEY = os.environ.get("POE_API_KEY", "你的POE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "你的TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "你的CHAT_ID")


def validate_env():
    """启动前检查关键配置，避免拿占位符去调用接口"""
    missing = []
    if not POE_API_KEY or POE_API_KEY == "你的POE_API_KEY":
        missing.append("POE_API_KEY")
    if not TELEGRAM_TOKEN or TELEGRAM_TOKEN == "你的TG_TOKEN":
        missing.append("TELEGRAM_TOKEN")
    if not CHAT_ID or CHAT_ID == "你的CHAT_ID":
        missing.append("CHAT_ID")

    if missing:
        raise ValueError(f"缺少必要环境变量配置: {', '.join(missing)}")


def call_poe(model, messages, temperature=0.5, max_retries=2):
    """调用 Poe API 的通用函数，增加简单重试"""
    last_error = None
    for attempt in range(max_retries + 1):
        try:
            client = openai.OpenAI(
                api_key=POE_API_KEY,
                base_url="https://api.poe.com/v1",
            )
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                stream=False,
                temperature=temperature,
            )
            return response.choices[0].message.content
        except Exception as e:
            last_error = e
            print(f"[call_poe] 第 {attempt + 1} 次调用失败: {e}")
            if attempt < max_retries:
                time.sleep(2)
    raise last_error


def clean_markdown(text):
    """
    清理 Markdown 符号，使文本适合 Telegram/微信群/纯文本阅读。
    由于新版简报本来就要求极简，这里只做温和清洗，避免误伤正文。
    """
    # 去掉粗体/斜体星号
    text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)

    # 去掉 Markdown 标题符号
    text = re.sub(r'^\s*#{1,6}\s*', '', text, flags=re.MULTILINE)

    # 去掉无意义项目符号，但保留箭头
    text = re.sub(r'^\s*[-•]\s+', '', text, flags=re.MULTILINE)

    # 压缩多余空行
    text = re.sub(r'\n{3,}', '\n\n', text)

    return text.strip()


def strip_report_preamble(text):
    """清理模型可能加的说明性前缀，只保留从正式标题开始的内容"""
    markers = [
        "🌍 今日全球情绪",
        "今日全球情绪",
        "🌍 全球情绪早报",
        "全球情绪早报",
    ]
    earliest_pos = len(text)
    for marker in markers:
        pos = text.find(marker)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos

    if earliest_pos < len(text) and earliest_pos > 0:
        return text[earliest_pos:].strip()

    return text.strip()


def save_text_file(prefix, content):
    """保存原始结果到本地，方便抽检和排查"""
    try:
        os.makedirs("logs", exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("logs", f"{prefix}_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[保存成功] {path}")
    except Exception as e:
        print(f"[保存失败] {e}")


# ==============================================================
#  第一道：Web-Search 定向搜索海外主流媒体（结构化候选池）
# ==============================================================

def fetch_overseas_intelligence():
    """
    第一阶段：
    用 Web-Search 扫描全球主流英文媒体，并尽量结构化输出候选新闻。
    目标不是直接写成品，而是拿到更可审查的原始候选池。
    """
    beijing_tz = timezone(timedelta(hours=8))
    utc_tz = timezone.utc
    beijing_now = datetime.now(beijing_tz)
    utc_now = datetime.now(utc_tz)

    today_cn = beijing_now.strftime("%Y年%m月%d日")
    today_iso = beijing_now.strftime("%Y.%m.%d")
    utc_now_str = utc_now.strftime("%Y-%m-%d %H:%M UTC")

    prompt = f"""今天是北京时间 {today_cn}，当前 UTC 时间约为 {utc_now_str}。

请你作为一个高级商业情报检索员，联网搜索过去24小时内全球最重要的商业、科技、能源、供应链、贸易与宏观经济动态，供后续生成一份【精简版全球情绪简报】。

【时间要求：必须严格执行】
1. 仅保留“过去24小时内发布或更新”的信息。
2. 如果某条新闻无法确认发布时间，请降低优先级；如果明显不是过去24小时，请不要收录。
3. 输出时必须尽量写明发布时间（原文时间或你能确认的时间表述）。

【媒体白名单：优先这些来源】
全球/财经/科技主媒体：
- Reuters
- Bloomberg
- The Wall Street Journal
- Financial Times
- CNBC
- The Economist
- TechCrunch

区域补充媒体：
- Nikkei Asia
- Al Jazeera
- The National
- Arab News
- The Japan Times
- The Korea Herald
- Straits Times
- Australian Financial Review
- Business Day

【严格搜索红线】
1. 严禁引用中国国内中文媒体二手报道。
2. 严格聚焦：商业模式创新、前沿科技、宏观政策、能源价格、全球贸易、物流航运、供应链、跨境投资、出海。
3. 过滤纯政治口水、意识形态攻击、无商业影响的外交新闻。

【扫描区域】
1. 🇺🇸 北美
2. 🇪🇺 欧洲
3. 🌏 亚太
4. 🦘 澳新
5. 💃 南美
6. 🐪 非洲中东
7. 🐎 中亚和蒙古

【输出目标】
请按区域输出“候选情报池”，每个区域最多保留 1-2 条最值得进入简报候选池的新闻。
如果某个区域没有足够重要的内容，就写：无足够重要动态

【每条候选必须尽量包含以下字段】
- 来源：
- 标题：
- 发布时间：
- 链接：
- 核心事实：
- 市场/区域情绪：
- 价值判断：

【格式必须严格如下】

【🇺🇸 北美】
1.
来源：
标题：
发布时间：
链接：
核心事实：
市场/区域情绪：
价值判断：

2.
来源：
标题：
发布时间：
链接：
核心事实：
市场/区域情绪：
价值判断：

【🇪🇺 欧洲】
...

如果无重要动态，写：
无足够重要动态

注意：
- 不要生成最终简报
- 不要写前言总结
- 只输出候选情报池
- 尽量使用明确媒体名，避免“据外媒报道”这种模糊说法
"""

    try:
        print("第一道：正在定向检索海外主流媒体情报（结构化候选池）...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}], temperature=0.1)
        print("海外情报候选池获取完成！")
        save_text_file("raw_candidates", result)
        return result
    except Exception as e:
        print(f"海外情报搜索失败: {e}")
        return None


# ==============================================================
#  第二道：筛选成【最多3个区域】的精简版简报
# ==============================================================

def generate_morning_report(raw_intelligence):
    """第二阶段：基于候选池生成精简版全球情绪简报"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y.%m.%d")

    prompt = f"""# 角色
你是「奇怪地球咨询社」的全球商业情绪简报助手。

# 任务
基于我提供的全球新闻/情报候选池，生成一份【精简版】全球情绪简报，供主理人直接转发到私域群。

# 核心原则
1. 每天只挑【最多3个】最值得说的区域，不是每天7个全覆盖。如果某个区域当天没有值得说的事，就不出现。出现即意味着今天这里有事。
2. 每个区域的情报压缩到【1条最核心】。不要堆砌。
3. 情绪标签要有区分度。如果多个区域情绪类似，只保留最典型的那个区域，其余砍掉。追求反差感——全球焦虑时，如果有一个区域是兴奋的，优先保留它。
4. 选择标准优先级如下：
   - 是否明确来自过去24小时的候选新闻
   - 是否来自更硬的媒体信源
   - 是否对全球商业/科技/能源/供应链/跨境贸易有现实影响
   - 是否对中国创业者、制造业、出海卖家、投资圈有现实意义
   - 是否一句话就能讲清楚
5. 「奇怪地球意见」部分要求：
   - 最多2-3句话
   - 必须说人话，像一个做过生意、去过现场的人在群里聊天，不是宏观分析师写报告
   - 优先使用以下句式风格：
     → "做XX生意的朋友注意，……"
     → "跟我在XX看到的一样，……"
     → "说白了就是……"
     → "别只盯着XX，真正的机会在……"
6. 禁止使用以下空话套话：
   ✗ "企业可以关注"
   ✗ "未雨绸缪"
   ✗ "多元化布局"
   ✗ "不可小觑"
   ✗ "长袖善舞"
   ✗ "如履薄冰"
   ✗ "捉襟见肘"
7. 整篇简报，群友30秒内能看完。

# 可选区域池
- 🇺🇸 北美
- 🇪🇺 欧洲
- 🌏 亚太
- 🦘 澳新
- 💃 南美
- 🐪 非洲中东
- 🐎 中亚和蒙古

# 情绪标签可选项
😰 焦虑 | 😓 压力 | 😨 紧张 | 🤔 观望 | 😐 平稳 | 🤑 兴奋 | 😎 乐观 | 🥶 冷淡 | 🔥 火热

以下是今天检索到的候选情报池：
===候选池开始===
{raw_intelligence}
===候选池结束===

# 输出格式（严格遵守）
🌍 今日全球情绪 | {today}

[区域emoji] [区域名] [情绪emoji] [情绪词]
[一句话核心情报，必须带明确外媒信源]
→ [奇怪地球意见，1-3句，说人话]

[区域emoji] [区域名] [情绪emoji] [情绪词]
[一句话核心情报，必须带明确外媒信源]
→ [奇怪地球意见，1-3句，说人话]

（如有第三个区域，同上格式；如果不够重要，只输出1-2个区域，不要凑数）

抹平全球市场信息差。大家发财。

# 严格限制
- 不要写前言、解释、备注
- 不要输出Markdown标题
- 不要使用项目符号
- 不要出现“以下是”
- 直接输出最终成稿
- 如果候选池里没有足够高价值的内容，宁可只写1个区域，也不要凑3个
"""

    try:
        print("第二道：正在使用 opus-4.6 生成《精简版全球情绪》...")
        result = call_poe("opus-4.6", [{"role": "user", "content": prompt}], temperature=0.6)
        print("《精简版全球情绪》生成完毕 ✅")
        save_text_file("final_report_raw", result)
        return result
    except Exception as e:
        print(f"opus-4.6 失败，尝试备用模型 GPT-4o: {e}")
        try:
            result = call_poe("GPT-4o", [{"role": "user", "content": prompt}], temperature=0.6)
            save_text_file("final_report_raw_fallback", result)
            return result
        except Exception as e2:
            print(f"全部失败: {e2}")
            return None


# ==============================================================
#  发送模块（针对 Telegram / 微信转发优化）
# ==============================================================

def split_text_safely(text, max_length=800):
    """
    将文本按相对自然的边界切分，避免一句话被切太碎。
    """
    chunks = []
    text = text.strip()

    while len(text) > 0:
        if len(text) <= max_length:
            chunks.append(text)
            break

        # 优先按双换行切
        split_pos = text.rfind("\n\n", 0, max_length)

        # 再按单换行切
        if split_pos == -1:
            split_pos = text.rfind("\n", 0, max_length)

        # 再按句号切
        if split_pos == -1:
            split_pos = text.rfind("。", 0, max_length)

        # 实在找不到就硬切
        if split_pos == -1 or split_pos < int(max_length * 0.5):
            split_pos = max_length

        chunk = text[:split_pos].strip()
        if chunk:
            chunks.append(chunk)

        text = text[split_pos:].strip()

    return chunks


def send_telegram(text):
    """
    发送消息到 Telegram。
    针对微信转发进行优化：将单条消息长度限制在 800 字左右，防止微信折叠。
    增加分段序号和简单重试。
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    chunks = split_text_safely(text, max_length=800)

    total = len(chunks)

    for i, chunk in enumerate(chunks, 1):
        if not chunk:
            continue

        # 如果分段超过 1 段，则添加序号
        display_text = chunk
        if total > 1:
            display_text = f"({i}/{total})\n{chunk}"

        payload = {
            "chat_id": CHAT_ID,
            "text": display_text,
            "disable_web_page_preview": True,
        }

        success = False
        for attempt in range(3):
            try:
                resp = requests.post(url, json=payload, timeout=30)
                if resp.status_code == 200:
                    print(f"Telegram 发送成功 ({i}/{total})")
                    success = True
                    break
                else:
                    print(f"Telegram 发送失败 ({i}/{total}) 第 {attempt + 1} 次: {resp.text}")
            except Exception as e:
                print(f"发送出错 ({i}/{total}) 第 {attempt + 1} 次: {e}")

            time.sleep(2)

        if not success:
            print(f"第 {i}/{total} 段最终发送失败。")

        # 控制顺序，避免消息乱序
        time.sleep(1.5)


# ==============================================================
#  主流程
# ==============================================================

def main():
    print("=" * 60)
    print("🌍 奇怪地球咨询社 · 精简版全球情绪系统启动")
    print("=" * 60)

    try:
        validate_env()
    except Exception as e:
        print(f"配置检查失败: {e}")
        return

    # 1. 抓取海外候选情报池
    raw_intelligence = fetch_overseas_intelligence()

    if not raw_intelligence:
        send_telegram("⚠️ 今日海外情报候选池获取失败，请检查网络或 Poe API 状态。")
        return

    time.sleep(3)

    # 2. 生成最终简报
    final_report = generate_morning_report(raw_intelligence)

    if final_report:
        final_report = strip_report_preamble(final_report)
        final_report = clean_markdown(final_report)

        print("\n--- 开始发送简报 ---")
        print(final_report)
        save_text_file("final_report_clean", final_report)
        send_telegram(final_report)
    else:
        send_telegram("⚠️ 今日《全球情绪简报》生成失败。")

    print("\n" + "=" * 60)
    print("今日情报任务全部完成 ✅")
    print("=" * 60)


if __name__ == "__main__":
    main()
