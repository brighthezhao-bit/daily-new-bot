import openai
import requests
import os
import re
import time
from datetime import datetime, timezone, timedelta

# 从环境变量获取 API Key 和 Telegram 配置
POE_API_KEY = os.environ.get("POE_API_KEY", "你的POE_API_KEY")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "你的TG_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID", "你的CHAT_ID")


def call_poe(model, messages, temperature=0.5):
    """调用 Poe API 的通用函数"""
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


def clean_markdown(text):
    """
    清理 Markdown 符号，使文本干干净净，适合微信群/纯文本阅读。
    同时将标题符号转换为纯文本的排版符号，保留层次感。
    """
    # 1. 去除加粗和斜体的星号 **文字** 或 *文字* -> 文字
    text = re.sub(r'\*{1,2}(.*?)\*{1,2}', r'\1', text)
    
    # 2. 将三级标题 ### 替换为 【】 括号 (用于7大区域的标题)
    text = re.sub(r'^###\s+(.*)', r'【\1】', text, flags=re.MULTILINE)
    
    # 3. 将二级标题 ## 替换为 ■ 符号
    text = re.sub(r'^##\s+(.*)', r'■ \1', text, flags=re.MULTILINE)
    
    # 4. 去除一级标题 # 
    text = re.sub(r'^#\s+(.*)', r'\1', text, flags=re.MULTILINE)
    
    # 5. 清理多余的空行（将3个以上的连续换行替换为2个）
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def strip_english_preamble(text):
    """清理大模型可能带有的废话前缀，直接保留正文主体"""
    markers = ["🌍 全球情绪早报", "全球情绪早报", "过滤全球商业噪音"]
    earliest_pos = len(text)
    for marker in markers:
        pos = text.find(marker)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos
            
    if earliest_pos < len(text) and earliest_pos > 0:
        # 如果前面有废话，从标记处截断
        stripped = text[earliest_pos:]
        return stripped
        
    return text


# ==============================================================
#  第一道：Web-Search 定向搜索海外主流媒体 (按7大区域)
# ==============================================================

def fetch_overseas_intelligence():
    """第一道：仅限搜索海外主流英文媒体，提取7大区域核心商业情报"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

请你作为一个高级商业情报检索员，联网搜索过去24小时内全球最重要的商业与科技情报。

【严格搜索红线】
1. 仅限检索海外主流英文媒体（如 Bloomberg, WSJ, Financial Times, Reuters, CNBC, The Economist, TechCrunch 等）。
2. 严禁引用任何中国国内中文媒体的二手报道。
3. 严格聚焦商业模式创新、前沿科技、全球宏观经济政策、出海与全球贸易。
4. 过滤掉纯政治体制、意识形态攻击等敏感话题，只提取纯粹的商业和经济影响。

【定向检索任务】
请务必分别检索以下 **7个区域** 过去24小时的核心动态，并输出原始素材（需包含外媒来源、核心事实数据、当地市场情绪）：
1. 北美（美国、加拿大）
2. 欧洲（英国、法国、德国及欧盟核心国）
3. 日韩东南亚（日本、韩国、东盟国家）
4. 澳新（澳大利亚、新西兰）
5. 南美（巴西、阿根廷等）
6. 非洲中东（沙特、阿联酋、南非等）
7. 中亚和蒙古（哈萨克斯坦、蒙古国等）

注意：这只是给下一步分析的原始素材，请确保信息密度极高，客观准确，务必标注具体的外媒来源。"""

    try:
        print("第一道：正在定向检索海外主流媒体情报(7大区域)...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}], temperature=0.1)
        print("海外情报原始素材获取完成！")
        return result
    except Exception as e:
        print(f"海外情报搜索失败: {e}")
        return None


# ==============================================================
#  第二道：生成《全球情绪早报》（核心业务逻辑）
# ==============================================================

def generate_morning_report(raw_intelligence):
    """第二道：根据新要求，使用 opus-4.6 生成高质量早报"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""你现在是“奇怪地球咨询社”的首席商业情报分析师。你的任务是基于我提供的海外媒体原始情报，为国内高管和创业者生成一份高质量的《全球情绪早报》。

【语言风格与人设指南】
1. 称呼规则（必须使用）：美国→老美，中国→东大，日本→脚盆鸡/小日子，欧洲→欧洲老钱，韩国→思密达，印度→三哥。
2. 语气要求：犀利、专业的“老炮”口吻。要有反共识的商业判断，指出事件对“东大”出海者或创业者的实质影响。不要用“震惊/重磅”等标题党。

以下是今天检索到的海外原始情报：
===情报开始===
{raw_intelligence}
===情报结束===

请严格按照以下结构输出早报（大模型内部请使用Markdown辅助生成，后续代码会清理符号，请保持结构清晰）：

# 🌍 全球情绪早报
过滤全球商业噪音，同步海外核心视野。 —— {today}

（请严格按照以下7个区域输出，每个区域必须包含情绪、核心情报、奇怪地球意见三项，不要增加多余的废话。如果没有该区域的重大新闻，请用一句话概括其宏观现状。）

### 1. 🇺🇸 北美
🌡️ 情绪：[使用1个Emoji + 2个字的词语，例如：😰 焦虑 / 🤑 亢奋 / 🤔 观望]
📡 核心情报：[用极度精简的语言，主谓宾结构，列出1-2条核心事实，必须带上外媒信源，如“据WSJ报道...”]
💡 奇怪地球意见：[这是灵魂！用犀利老炮口吻，给出反共识的商业判断或对东大出海的实质影响]

### 2. 🇪🇺 欧洲
🌡️ 情绪：[Emoji + 2字]
📡 核心情报：[精简事实 + 外媒信源]
💡 奇怪地球意见：[犀利点评]

### 3. 🌏 日韩东南亚
🌡️ 情绪：[Emoji + 2字]
📡 核心情报：[精简事实 + 外媒信源]
💡 奇怪地球意见：[犀利点评]

### 4. 🦘 澳新
🌡️ 情绪：[Emoji + 2字]
📡 核心情报：[精简事实 + 外媒信源]
💡 奇怪地球意见：[犀利点评]

### 5. 💃 南美
🌡️ 情绪：[Emoji + 2字]
📡 核心情报：[精简事实 + 外媒信源]
💡 奇怪地球意见：[犀利点评]

### 6. 🐪 非洲中东
🌡️ 情绪：[Emoji + 2字]
📡 核心情报：[精简事实 + 外媒信源]
💡 奇怪地球意见：[犀利点评]

### 7. 🐎 中亚和蒙古
🌡️ 情绪：[Emoji + 2字]
📡 核心情报：[精简事实 + 外媒信源]
💡 奇怪地球意见：[犀利点评]
"""

    try:
        print("第二道：正在使用 opus-4.6 深度思考并生成《全球情绪早报》...")
        result = call_poe("opus-4.6", [{"role": "user", "content": prompt}], temperature=0.6)
        print("《全球情绪早报》生成完毕 ✅")
        return result
    except Exception as e:
        print(f"opus-4.6 失败，尝试备用模型 GPT-4o: {e}")
        try:
            result = call_poe("GPT-4o", [{"role": "user", "content": prompt}], temperature=0.6)
            return result
        except Exception as e2:
            print(f"全部失败: {e2}")
            return None


# ==============================================================
#  发送模块（针对微信防折叠优化）
# ==============================================================

def send_telegram(text):
    """
    发送消息到 Telegram。
    针对微信转发进行优化：将单条消息长度限制在 800 字左右，防止微信折叠。
    """
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    
    # 微信防折叠安全长度设定为 800 字符
    MAX_LENGTH = 800 
    chunks = []
    
    while len(text) > 0:
        if len(text) <= MAX_LENGTH:
            chunks.append(text)
            break
            
        # 寻找最近的段落分割点（双换行），避免把一句话切断
        split_pos = text.rfind("\n\n", 0, MAX_LENGTH)
        
        # 如果找不到双换行，退而求其次找单换行
        if split_pos == -1:
            split_pos = text.rfind("\n", 0, MAX_LENGTH)
            
        # 如果连换行都没有（极端情况），硬切
        if split_pos == -1:
            split_pos = MAX_LENGTH
            
        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].strip()

    for i, chunk in enumerate(chunks):
        if not chunk:
            continue
            
        payload = {
            "chat_id": CHAT_ID,
            "text": chunk,
            "disable_web_page_preview": True,
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            if resp.status_code == 200:
                print(f"Telegram 发送成功 ({i+1}/{len(chunks)})")
            else:
                print(f"Telegram 发送失败: {resp.text}")
            # 增加延迟，防止消息顺序错乱
            time.sleep(2)
        except Exception as e:
            print(f"发送出错: {e}")


# ==============================================================
#  主流程
# ==============================================================

def main():
    print("=" * 50)
    print("🌍 奇怪地球咨询社 · 首席情报系统启动")
    print("=" * 50)

    # 1. 抓取海外情报
    raw_intelligence = fetch_overseas_intelligence()
    
    if not raw_intelligence:
        send_telegram("⚠️ 今日海外情报获取失败，请检查网络或 Poe API 状态。")
        return

    time.sleep(3) 

    # 2. 生成最终早报 (使用 opus-4.6)
    final_report = generate_morning_report(raw_intelligence)

    if final_report:
        # 清理废话前缀
        final_report = strip_english_preamble(final_report)
        # 核心：清理 Markdown 符号，保证输出干干净净
        final_report = clean_markdown(final_report)
        
        print("\n--- 开始发送早报 ---")
        print(final_report) # 在本地打印预览一下干净的排版
        send_telegram(final_report)
    else:
        send_telegram("⚠️ 今日《全球情绪早报》生成失败。")

    print("\n" + "=" * 50)
    print("今日情报任务全部完成 ✅")
    print("=" * 50)


if __name__ == "__main__":
    main()
