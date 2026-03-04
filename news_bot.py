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
    # 尝试找到内容的真正起始点（各种可能的开头标志）
    markers = ["📰", "📊", "🔥", "💹", "🌍", "🌐"]
    earliest_pos = len(text)

    for marker in markers:
        pos = text.find(marker)
        if pos != -1 and pos < earliest_pos:
            earliest_pos = pos

    # 如果找到了标志性 emoji，把前面的都砍掉
    if earliest_pos < len(text) and earliest_pos > 0:
        stripped = text[earliest_pos:]
        print(f"已清理前缀（去掉了前 {earliest_pos} 个字符）")
        return stripped

    # 如果没找到 emoji 标志，尝试用正则：找到第一行包含中文的内容
    lines = text.split("\n")
    for i, line in enumerate(lines):
        if re.search(r'[\u4e00-\u9fff]', line) and len(line.strip()) > 5:
            result = "\n".join(lines[i:])
            print(f"已通过中文检测清理前缀（跳过了前 {i} 行）")
            return result

    # 实在找不到就原样返回
    return text


def get_daily_news():
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

你是一位顶尖的全球商业资讯编辑。你的读者是一位中国自媒体博主，他的定位是"抹平全球商业的信息差"。

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

💡 今日风向
[一段话总结今天全球商业的整体风向，指出值得持续关注的趋势]

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
   - 直接输出正文内容，第一行就是"📰 全球商业日报"，前面不要有任何英文引用、搜索说明或来源列表"""

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




def generate_wechat_group_brief(daily_news):
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""你是"奇怪地球咨询社"的内容编辑助手，负责将每日完整版全球商业简报压缩为适合微信粉丝群发送的精简版。

# 目标
将以下完整版简报转化为一条可以直接复制粘贴到微信群的短消息，让读者在10秒内抓住今天的核心信息，同时引导他们去公众号看完整版。

# 完整版简报原文：
{daily_news}

# 输出格式（严格按以下结构，不要多一个字）

📰 今日X件事 | {today}

[用1️⃣2️⃣3️⃣编号，每条一行]

💬 今日风向：[一句话判断]

👉 完整解读 + 分区速览，见今天公众号推文

# 写作规则

## 核心提炼
- 只保留完整版中「今日最值得关注的X件事」，数量跟随原文（可能是2-5条）
- 每条新闻压缩为1行，不超过30个字
- 用大白话写，不要书面语，就像你在群里跟朋友说今天发生了什么
- 如果原文某条新闻涉及多个细节，只保留最核心的一个点

## 风向句
- 从完整版的「今日风向」中提炼出一句话，不超过35个字
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

def get_market_briefing():
    """生成全球市场行情简报：股市 + 贵金属 + 稀土 + 新闻点评"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

你是一位专业的全球金融市场编辑。请联网搜索最新的全球市场数据和相关财经新闻，然后生成一份既有数据又有洞察的行情简报。

搜索要求：
- 搜索关键词包括：world stock markets today, gold silver copper price, rare earth prices, S&P 500, Nasdaq, Dow Jones, FTSE, DAX, Nikkei 225, Hang Seng, Shanghai Composite, ASX 200 等
- 同时搜索：今日A股、恒生指数、黄金价格、白银价格、铜价、稀土价格
- 还要搜索：market news today, Fed interest rate, stock market analysis, 今日市场分析、央行政策、板块异动 等
- 优先使用 Bloomberg、Reuters、CNBC、MarketWatch、Investing.com、Financial Times、金十数据、华尔街见闻 等金融数据源和财经媒体

请严格按以下格式输出（第一行直接开始，不要任何前言或英文说明）：

💹 全球市场简报 | {today}

📈 全球股市

🇺🇸 美股
标普500：[点位] [涨跌幅%]
纳斯达克：[点位] [涨跌幅%]
道琼斯：[点位] [涨跌幅%]
[1-2句话点评美股今日表现的驱动因素，如哪些板块领涨领跌、受什么消息影响。标注来源媒体名]

🇨🇳 A股
上证综指：[点位] [涨跌幅%]
深证成指：[点位] [涨跌幅%]
创业板指：[点位] [涨跌幅%]
[1-2句话点评A股今日走势，如主力资金流向、板块热点、政策影响等。标注来源媒体名]

🇭🇰 港股
恒生指数：[点位] [涨跌幅%]
恒生科技：[点位] [涨跌幅%]
[1-2句话点评港股表现及驱动因素。标注来源媒体名]

🇯🇵 日本
日经225：[点位] [涨跌幅%]
[1句话点评。标注来源媒体名]

🇬🇧🇪🇺 欧洲
富时100：[点位] [涨跌幅%]
德国DAX：[点位] [涨跌幅%]
法国CAC40：[点位] [涨跌幅%]
[1-2句话点评欧洲市场表现。标注来源媒体名]

🇦🇺 澳洲
ASX 200：[点位] [涨跌幅%]
[1句话点评。标注来源媒体名]

🪙 贵金属 & 大宗商品

黄金（XAUUSD）：[价格] 美元/盎司 [涨跌幅%]
白银（XAGUSD）：[价格] 美元/盎司 [涨跌幅%]
铜（COMEX）：[价格] 美元/磅 [涨跌幅%]
原油（WTI）：[价格] 美元/桶 [涨跌幅%]
原油（布伦特）：[价格] 美元/桶 [涨跌幅%]
[1-2句话分析今日大宗商品价格波动的原因，如地缘政治、供需变化、美元走势等。标注来源媒体名]

🔋 稀土 & 关键矿产

[列出主要稀土品种的最新价格动态，如氧化镨钕、氧化镝、氧化铽等。如果搜不到实时价格，说明最近的价格趋势即可]
[1句话点评稀土市场近期走势及影响因素。标注来源媒体名]

🔍 今日值得关注

[列出2-3个今天市场参与者应该重点关注的事项，比如：即将公布的经济数据、央行会议、大公司财报、政策动向等。每条1句话，标注来源媒体名]

📝 编辑点评
[2-3句话，用专业但易懂的语言概括今天全球市场的整体情绪、核心驱动因素，以及短期需要警惕或期待的信号]

重要规则：
- 所有数据必须是最新的，标注是收盘价还是盘中价
- 涨用 📗 或 +，跌用 📕 或 -（或直接用正负号）
- 如果某个市场当天未开盘或休市，注明"休市"
- 全部用中文（专有名词和代码除外）
- 不要使用任何Markdown格式符号，不要用星号加粗，不要用井号标题，输出纯文本
- 不要出现"AI"这个词
- 每条点评和新闻后面只需标注来源媒体名称（如：据Reuters、据Bloomberg、据CNBC），绝对不要附任何URL链接
- 来源不明或无法确认的信息不要使用
- 直接输出正文，第一行就是"💹 全球市场简报"，前面不要有任何英文"""

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
