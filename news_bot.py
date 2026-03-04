import openai
import requests
import os
import re
import time
from datetime import datetime, timezone, timedelta

POE_API_KEY = os.environ["POE_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


def call_poe(model, messages):
    client = openai.OpenAI(
        api_key=POE_API_KEY,
        base_url="https://api.poe.com/v1",
    )
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        stream=False,
        temperature=0.3,
    )
    return response.choices[0].message.content


def clean_text(text):
    """去掉 Markdown 的加粗符号 **"""
    return text.replace("**", "")


def strip_english_preamble(text):
    """
    去掉 Web-Search 模型返回的英文前缀垃圾。
    策略：找到正文真正开始的标志性 emoji 或中文内容，把前面的全砍掉。
    """
    markers = ["📰", "📊", "🔥", "💹", "🌍", "🌐"]
    earliest_pos = len(text)

    for marker in markers:
        pos = text.find(marker)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos

    if earliest_pos < len(text) and earliest_pos > 0:
        stripped = text[earliest_pos:]
        print(f"已清理前缀（去掉了前 {earliest_pos} 个字符）")
        return stripped

    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.search(r'[\u4e00-\u9fff]', line) and len(line.strip()) > 5:
            result = "\n".join(lines[i:])
            print(f"已通过中文检测清理前缀（跳过了前 {i} 行）")
            return result

    return text


def get_daily_news():
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

你是一位顶尖的全球商业资讯编辑。你的读者是关注全球商业动态的中文读者。

请你联网搜索今天全球各地最新的商业新闻，然后完成以下工作：

1. 搜索范围要覆盖：北美、欧洲、中国、东亚（日韩）、东南亚、南亚（印度）、澳大利亚、中东、非洲、拉美。

2. 信息来源要求（非常重要）：
   - 必须优先搜索国际主流英文媒体，包括但不限于：Reuters、Bloomberg、Financial Times、The Wall Street Journal、CNBC、TechCrunch、The Verge、Nikkei Asia、The Economist、MIT Technology Review、South China Morning Post、Al Jazeera、BBC Business 等
   - 至少一半以上的信息源必须来自英文媒体
   - 中文媒体（如财新、第一财经、36氪等）可以作为补充，但不能是唯一来源
   - 每条新闻都必须标注来源媒体的英文或中文名称
   - 搜索时请同时使用英文关键词搜索，不要只用中文关键词

3. 筛选标准（只挑真正有价值的）：
   - 各国重大经济政策变动（关税、监管、利率等）
   - 新兴市场的商业机会
   - 全球巨头的重要动作（收购、扩张、裁员、新业务）
   - 跨境电商 / 出海相关动态
   - 科技商业化的重大突破
   - 消费趋势变化
   - 中文互联网很少报道但其实很重要的事

4. 严格按以下格式输出（直接从第一行开始输出，不要有任何前言、引言、英文说明）：

📰 全球商业日报 | {today}

🔥 今日最值得关注的3件事

1️⃣ [标题]
[2-3句话说清发生了什么、为什么重要。标注信息来源]

2️⃣ [标题]
[2-3句话说清发生了什么、为什么重要。标注信息来源]

3️⃣ [标题]
[2-3句话说清发生了什么、为什么重要。标注信息来源]

📊 分区速览

🇺🇸 北美
[1-2条核心动态，每条1-2句，标注来源]

🇪🇺 欧洲
[同上]

🇨🇳 中国
[同上]

🇯🇵🇰🇷 东亚（日韩等）
[同上]

🌏 东南亚
[同上]

🇮🇳 南亚
[同上]

🇦🇺 澳大利亚
[同上]

🇸🇦 中东
[同上]

🌍 非洲
[同上]

🌎 拉美
[同上]

💡 奇怪地球点评
[一段话总结今天全球商业的整体风向，指出值得持续关注的趋势]

——
奇怪地球咨询社 | 抹平全球商业的信息差

5. 重要规则：
   - 只报道过去24小时内的新闻，严禁使用超过1天的旧闻，如果无法确认是24小时内的，宁可不报道
   - 如果某个地区今天没有值得报道的新闻，直接跳过该地区
   - 全部用中文
   - 简洁有力，不要废话套话
   - 保持客观中立
   - 每条新闻都必须标注来源媒体名称（如：Reuters、Bloomberg、Financial Times等），不能只放链接，必须写出媒体名
   - 来源不明或无法确认的新闻不要使用
   - 全文不要出现"AI"这个词，你就是一位人类编辑
   - 全文不要使用任何Markdown格式符号，不要用星号加粗，不要用井号标题，输出纯文本
   - 直接输出正文内容，第一行就是"📰 全球商业日报"，前面不要有任何英文引用、搜索说明或来源列表
   - 最后一行必须是"奇怪地球咨询社 | 抹平全球商业的信息差"作为签名档"""

    try:
        print("正在通过 Poe API 调用 Web-Search...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}])
        print("日报整理完成！")
        return result
    except Exception as e:
        print(f"Web-Search 失败: {e}")
        try:
            print("尝试备用方案...")
            client = openai.OpenAI(
                api_key=POE_API_KEY,
                base_url="https://api.poe.com/v1",
            )
            response = client.chat.completions.create(
                model="Gemini-2.0-Flash",
                messages=[{"role": "user", "content": prompt}],
                stream=False,
                temperature=0.3,
                extra_body={"web_search": True},
            )
            result = response.choices[0].message.content
            print("备用方案成功！")
            return result
        except Exception as e2:
            print(f"备用方案也失败: {e2}")
            return None


def get_market_briefing():
    """生成全球市场行情简报：叙事驱动 + 数据速查"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

你是一位顶尖的全球金融市场编辑。你的读者不是专业交易员，而是对全球商业感兴趣的普通人。他们不缺数据，缺的是有人帮他们理解"发生了什么、为什么、跟我有什么关系"。

请联网搜索最新的全球市场数据和财经新闻，生成一份叙事驱动的市场简报。

搜索要求：
- 英文关键词：world stock markets today, gold silver copper price, S&P 500, Nasdaq, Dow Jones, FTSE, DAX, Nikkei 225, Hang Seng, Shanghai Composite, ASX 200, Fed interest rate, market news today, oil price, OPEC 等
- 中文关键词：今日A股、恒生指数、黄金价格、原油价格、今日市场分析、央行政策、板块异动
- 优先使用 Bloomberg、Reuters、CNBC、MarketWatch、Financial Times、Investing.com、Nikkei Asia、金十数据、华尔街见闻 等来源

请严格按以下格式和风格输出（第一行直接开始，不要任何前言或英文说明）：

💹 全球市场简报 | {today}

🔥 昨夜今晨，发生了什么

[用3-4段话，讲清楚过去24小时全球市场最核心的几条主线。每段聚焦一个主题，比如：美股表现及原因、亚太市场反应、大宗商品动态等。]

写作要求：
- 先讲故事和原因，再带数据。比如不要上来就列"标普500：5104"，而是说"美股昨夜全线收跌，标普跌1.3%，导火索是……"
- 数据自然嵌入叙事中，不要单独罗列
- 每段话要有因果逻辑：发生了什么 → 为什么 → 影响是什么
- 每段末尾用括号标注来源媒体名，如（据Bloomberg、CNBC）
- 如果某个市场休市，可以跳过或一句话带过

🔍 今天盯什么

[列出2-3个今天值得关注的事项，每条用1️⃣2️⃣3️⃣编号，每条1-2句话。比如：即将公布的经济数据、央行决议、重要公司财报、政策动向等。每条标注来源媒体名。]

📋 数据速查

[用紧凑的单行格式列出核心数据，方便快速查阅，格式如下：]
美股：标普500 [点位]（[涨跌幅%]）｜纳斯达克 [点位]（[涨跌幅%]）｜道琼斯 [点位]（[涨跌幅%]）
A股：上证 [点位]（[涨跌幅%]）｜深证 [点位]（[涨跌幅%]）｜创业板 [点位]（[涨跌幅%]）
港股：恒生 [点位]（[涨跌幅%]）｜恒生科技 [点位]（[涨跌幅%]）
日本：日经225 [点位]（[涨跌幅%]）
欧洲：富时100 [点位]（[涨跌幅%]）｜DAX [点位]（[涨跌幅%]）
澳洲：ASX 200 [点位]（[涨跌幅%]）
黄金：[价格]美元/盎司（[涨跌幅%]）｜白银：[价格]美元/盎司（[涨跌幅%]）
原油：WTI [价格]美元/桶（[涨跌幅%]）｜布伦特 [价格]美元/桶（[涨跌幅%]）

[如果某市场休市，在对应位置标注"休市"]
[标注数据是收盘价还是盘中实时价]

📝 奇怪地球点评
[2-3句话，用专业但易懂的语言做一个带态度的判断。不是总结前面说过的话，而是给读者一个前瞻性的观点：短期该警惕什么、期待什么、别被什么带节奏。语气克制但有立场。]

——
奇怪地球咨询社 | 抹平全球商业的信息差

重要规则：
- 这是一份叙事驱动的简报，不是数据报表。"昨夜今晨"部分必须是连贯的段落叙述，严禁用列表或逐条罗列的方式写
- 数据速查部分放在最后，尽量紧凑，不要占太多篇幅
- 只标注来源媒体名称（如：据Reuters、据Bloomberg），绝对不要附任何URL链接
- 所有数据必须是最新的
- 全部用中文（专有名词和代码除外）
- 不要使用任何Markdown格式符号，不要用星号加粗，不要用井号标题，输出纯文本
- 不要出现"AI"这个词，你就是一位人类编辑
- 来源不明或无法确认的信息不要使用
- 直接输出正文，第一行就是"💹 全球市场简报"，前面不要有任何英文
- 如果某个商品或市场今天没有值得特别展开说的，在叙事部分可以跳过，数据速查里列上就行
- 最后一行必须是"奇怪地球咨询社 | 抹平全球商业的信息差"作为签名档"""

    try:
        print("正在获取全球市场行情数据...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}])
        print("市场简报生成完成！")
        return result
    except Exception as e:
        print(f"市场简报生成失败: {e}")
        try:
            print("尝试备用方案获取市场数据...")
            result = call_poe("Gemini-2.0-Flash", [{"role": "user", "content": prompt}])
            print("备用方案成功！")
            return result
        except Exception as e2:
            print(f"备用方案也失败: {e2}")
            return None


def generate_wechat_group_brief(daily_news):
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""你是一位内容编辑助手，负责将每日完整版全球商业简报压缩为适合微信粉丝群发送的精简版。

# 目标
将以下完整版简报转化为一条可以直接复制粘贴到微信群的短消息，让读者在10秒内抓住今天的核心信息，同时引导他们去公众号看完整版。

# 完整版简报原文：
{daily_news}

# 输出格式（严格按以下结构，不要多一个字）

📰 今日X件事 | {today}

[用1️⃣2️⃣3️⃣编号，每条一行]

💬 奇怪地球点评：[一句话判断]

👉 完整解读 + 分区速览，见今天公众号推文

——
奇怪地球咨询社 | 抹平全球商业的信息差

# 写作规则

## 核心提炼
- 只保留完整版中「今日最值得关注的X件事」，数量跟随原文（可能是2-5条）
- 每条新闻压缩为1行，不超过30个字
- 用大白话写，不要书面语，就像你在群里跟朋友说今天发生了什么
- 如果原文某条新闻涉及多个细节，只保留最核心的一个点

## 风向句
- 从完整版的「今日风向」或「奇怪地球点评」中提炼出一句话，不超过35个字
- 要有态度、有判断，不要写成新闻摘要
- 可以带一点口语化的表达，比如"说白了""盯紧""别急"

## 禁止事项
- 不要出现信源标注（Reuters、Bloomberg等）
- 不要出现分区速览的任何内容（那是公众号引流的钩子）
- 不要出现任何解释性文字，只给结论
- 不要加任何开场白或结尾寒暄
- 不要使用加粗、斜体等任何Markdown格式符号（微信群不支持）
- 每条新闻不要换行展开，必须控制在一行内
- 不要输出任何多余的话，只输出最终的精简版消息本身

## 语气
- 像一个消息灵通的朋友在群里给大家划重点
- 克制但有态度，不夸张不标题党
- 中文为主，专有名词可保留英文缩写（如OPEC+、PPI）"""

    try:
        print("正在生成微信群精简版...")
        result = call_poe("Claude-3.5-Sonnet", [{"role": "user", "content": prompt}])
        print("微信群精简版生成完成！")
        return result
    except Exception as e:
        print(f"微信群精简版生成失败: {e}")
        try:
            print("尝试备用模型...")
            result = call_poe("GPT-4o", [{"role": "user", "content": prompt}])
            print("备用模型成功！")
            return result
        except Exception as e2:
            print(f"备用模型也失败: {e2}")
            return None


def send_telegram(text):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    chunks = []
    if len(text) > 4096:
        while len(text) > 0:
            if len(text) <= 4096:
                chunks.append(text)
                break
            split_pos = text.rfind("\n", 0, 4096)
            if split_pos == -1:
                split_pos = 4096
            chunks.append(text[:split_pos])
            text = text[split_pos:]
    else:
        chunks = [text]

    for i, chunk in enumerate(chunks):
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
                print(f"发送失败: {resp.text}")
            time.sleep(1)
        except Exception as e:
            print(f"发送出错: {e}")


def main():
    print("开始执行每日全球商业新闻任务...")

    # ========== 第一步：生成完整日报 ==========
    daily_news = get_daily_news()

    if daily_news:
        daily_news = clean_text(daily_news)
        daily_news = strip_english_preamble(daily_news)

        print("发送第一条：完整日报...")
        send_telegram(daily_news)
    else:
        send_telegram("⚠️ 今天新闻获取失败，请检查 Poe API。")
        print("日报获取失败")

    # ========== 第二步：生成市场行情简报 ==========
    time.sleep(5)
    market_briefing = get_market_briefing()

    if market_briefing:
        market_briefing = clean_text(market_briefing)
        market_briefing = strip_english_preamble(market_briefing)

        print("发送第二条：全球市场简报...")
        send_telegram(market_briefing)
    else:
        send_telegram("⚠️ 全球市场简报生成失败")

    # ========== 第三步：生成微信群精简版 ==========
    if daily_news:
        time.sleep(5)
        group_brief = generate_wechat_group_brief(daily_news)

        if group_brief:
            group_brief = clean_text(group_brief)
            group_brief = strip_english_preamble(group_brief)

            print("发送第三条：微信群精简版...")
            header = "👇 以下是微信群发送版，可直接复制：\n\n"
            send_telegram(header + group_brief)
            print("三条消息全部发送完成！✅")
        else:
            send_telegram("⚠️ 微信群精简版生成失败")

    print("今日任务执行结束。")


if __name__ == "__main__":
    main()
