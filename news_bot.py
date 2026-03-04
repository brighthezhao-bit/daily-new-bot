import openai
import requests
import os
import re
import time
from datetime import datetime, timezone, timedelta

POE_API_KEY = os.environ["POE_API_KEY"]
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]


def call_poe(model, messages, temperature=0.3):
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


def clean_text(text):
    """去掉 Markdown 格式符号"""
    text = text.replace("**", "")
    text = re.sub(r'^#{1,3}\s+', '', text, flags=re.MULTILINE)
    return text


def strip_english_preamble(text):
    markers = ["📰", "📊", "🔥", "💹", "🌍", "🌐", "☀️", "📋"]
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


# ==============================================================
#  语言风格指南（第1条和第2条共用）
# ==============================================================

STYLE_GUIDE = """
你的语言风格指南（非常重要，必须严格遵守）：

称呼规则（每次提到这些地方都必须用昵称，不要用正式名称）：
- 美国 → 老美
- 中国 → 东大
- 日本 → 脚盆鸡 或 小日子
- 澳大利亚 → 土澳
- 欧洲 → 欧洲老钱
- 中东国家 → 中东土豪
- 韩国 → 思密达
- 印度 → 三哥

语气和风格：
- 像一个消息灵通又幽默的朋友在群里跟大家聊昨晚发生了啥
- 适当用互联网用语，比如"整活""上大分""绷不住""属于是""格局打开""闷声发大财""拿捏了"
- 可以用歇后语或俏皮比喻来点睛
- 数据要准确，但表达要口语化，不要书面腔
- 开头要抓人，先讲结论或最劲爆的点
- 保持克制——重要的地方正经说，轻松的地方皮一下，不要每句都加梗
- 绝对不要用"小伙伴们""家人们""宝子们"这类油腻称呼
- 不要用"震惊""重磅""突发"这类标题党词汇

示例句子（感受一下调性，不要照抄）：
- "老美昨晚又整活了，标普跌了1.3%，导火索是非农数据炸了锅。"
- "东大这边稳得一批，上证微涨0.2%，新能源板块继续上大分。"
- "脚盆鸡的日经225跟着吃瓜跌了0.8%，日元又软了。"
- "土澳矿老板们今天心情不太好，铁矿石价格又往下走了。"
- "说白了，现在全球就是在等老美那边利率到底降不降，其他都是噪音。"
- "思密达那边三星又放大招了，这次是真有东西还是PPT先行，再看看。"
- "东大这波闷声干大事，等欧洲老钱反应过来黄花菜都凉了。"
"""


# ==============================================================
#  第一道：Web-Search 搜索原始素材（两个函数，各搜各的）
# ==============================================================

def fetch_raw_market():
    """第一道：搜索全球市场数据，输出纯事实素材"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

请联网搜索过去24小时内全球金融市场的最新数据和重要新闻。

搜索关键词（英文和中文都要搜）：
英文：world stock markets today, S&P 500, Nasdaq, Dow Jones, FTSE 100, DAX, Nikkei 225, Hang Seng, Shanghai Composite, ASX 200, gold price today, silver price, oil price WTI Brent, Fed interest rate, ECB, market news today
中文：今日A股, 恒生指数, 黄金价格, 原油价格, 央行政策

优先来源：Bloomberg, Reuters, CNBC, MarketWatch, Financial Times, Investing.com, Nikkei Asia, 金十数据, 华尔街见闻

请输出一份纯事实的原始素材汇总，包含：

1. 各主要股票市场最新数据（标普500、纳斯达克、道琼斯、上证、深证、创业板、恒生、恒生科技、日经225、富时100、DAX、ASX 200）——写出具体点位和涨跌幅百分比

2. 大宗商品价格（黄金、白银、WTI原油、布伦特原油）——写出具体价格和涨跌幅

3. 过去24小时市场的重要事件和驱动因素（央行政策、经济数据、地缘政治、公司财报等），每条标注来源媒体

4. 今天即将发生的重要事项（数据公布、央行决议、重要会议等），标注来源

5. 如果某市场休市，注明

规则：
- 全部中文输出（专有名词除外）
- 每条信息标注来源媒体名称
- 数据要具体准确，不要模糊
- 不需要文学加工，纯事实数据罗列
- 不要使用Markdown格式
- 直接输出内容，不要英文前言"""

    try:
        print("第一道：正在搜索全球市场数据...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}])
        print("市场原始素材获取完成！")
        return result
    except Exception as e:
        print(f"市场数据搜索失败: {e}")
        return None


def fetch_raw_news():
    """第一道：搜索全球商业新闻，输出纯事实素材"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

请联网搜索过去24小时内全球各地最重要的商业新闻。

搜索范围：北美、欧洲、中国、日本、韩国、东南亚、印度、澳大利亚、中东、非洲、拉美。

搜索关键词（英文和中文都要搜）：
英文：business news today, tech news, trade policy, tariff, M&A, startup funding, global economy, OPEC, semiconductor, EV market, AI chips, cross-border ecommerce
中文：今日商业新闻, 科技动态, 跨境电商, 出海, 关税, 监管政策

优先来源：Reuters, Bloomberg, Financial Times, Wall Street Journal, CNBC, TechCrunch, The Verge, Nikkei Asia, South China Morning Post, Al Jazeera, BBC Business, 财新, 第一财经, 36氪

筛选标准：
- 各国重大经济政策变动（关税、监管、利率等）
- 新兴市场商业机会
- 全球巨头重要动作（收购、扩张、裁员、新业务）
- 跨境电商/出海动态
- 科技商业化重大突破
- 消费趋势变化
- 中文互联网很少报道但其实很重要的事

输出要求：
- 按地区分类列出所有搜集到的新闻
- 每条写清楚：发生了什么、涉及哪些公司/政策/人物、为什么重要
- 每条标注来源媒体名称
- 全部中文（专有名词除外）
- 纯事实罗列，不需要文学加工
- 不要使用Markdown格式
- 直接输出内容，不要英文前言
- 只报道过去24小时的新闻"""

    try:
        print("第一道：正在搜索全球商业新闻...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}])
        print("商业新闻原始素材获取完成！")
        return result
    except Exception as e:
        print(f"商业新闻搜索失败: {e}")
        return None


# ==============================================================
#  第二道：改写加工（四个函数，两个有人味，两个正经）
# ==============================================================

def rewrite_market_story(raw_market):
    """第二道·第1条：有人味的市场故事"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""你是「奇怪地球咨询社」的主编，每天早上给读者讲昨晚全球市场发生了什么。读者刚睡醒，你要用最快的方式让他们知道昨晚世界怎么了。

{STYLE_GUIDE}

以下是今天的市场原始数据和新闻素材（由搜索引擎采集，可能格式粗糙，你需要从中提取关键信息）：

===素材开始===
{raw_market}
===素材结束===

请基于以上素材，写一条早间市场速报。格式严格如下：

☀️ 早上好 市场速报 | {today}

[用2-3段话讲清楚昨晚到今早全球市场的核心故事。每段聚焦一个主题（比如老美那边、东大和亚太、大宗商品等）。先讲发生了什么和为什么，再自然带入涨跌数据。段落之间空一行。每段末尾括号标注来源。]

👀 今天盯这几个
1️⃣ [一句话，今天第一个值得关注的事]
2️⃣ [一句话，第二个]
3️⃣ [一句话，第三个（如果有的话）]

💬 奇怪地球点评：[1-2句话，带态度的前瞻判断，不是总结上面说过的，而是你的观点。口语化。]

——
奇怪地球咨询社 | 抹平全球商业的信息差

写作规则：
- 整条消息正文控制在250-350字，宁短勿长
- 来源用括号简单标注，如（据Bloomberg）
- 不要使用任何Markdown格式符号，纯文本
- 不要出现"AI"这个词
- 数据必须来自素材，不要编造
- 第一行直接输出"☀️"开头，前面不要有任何内容
- 某市场休市或没啥可说的就跳过
- 点评那句话要有自己的态度，可以皮一点"""

    try:
        print("第二道：正在改写市场故事（有人味版）...")
        result = call_poe("Claude-3.5-Sonnet", [{"role": "user", "content": prompt}], temperature=0.7)
        print("第1条 市场故事 ✅")
        return result
    except Exception as e:
        print(f"Claude失败，尝试GPT-4o: {e}")
        try:
            result = call_poe("GPT-4o", [{"role": "user", "content": prompt}], temperature=0.7)
            return result
        except Exception as e2:
            print(f"全部失败: {e2}")
            return None


def rewrite_business_highlights(raw_news):
    """第二道·第2条：有人味的商业重点事件"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""你是「奇怪地球咨询社」的主编，每天早上告诉读者今天最值得知道的几件商业大事。

{STYLE_GUIDE}

以下是今天搜集到的全球商业新闻原始素材（由搜索引擎采集，可能格式粗糙）：

===素材开始===
{raw_news}
===素材结束===

请从中挑出最重要的3件事（特别重大可以2件或4件，绝不超过4件），写一条早间商业快报。格式严格如下：

📰 今天商业圈这几件事 | {today}

1️⃣ [一个有意思的短标题，比如"老美又对东大出手了"而不是"美国对华关税政策调整"]
[2-3句话说清发生了什么、为什么重要。括号标注来源。语气口语化但信息准确。]

2️⃣ [短标题]
[2-3句话。标注来源。]

3️⃣ [短标题]
[2-3句话。标注来源。]

💬 奇怪地球点评：[1-2句话，带态度的总结判断。不是复述上面的内容，而是你对今天全球商业整体风向的一个判断。口语化，可以皮一点。]

——
奇怪地球咨询社 | 抹平全球商业的信息差

写作规则：
- 整条消息控制在300-450字
- 标题要有意思，要用昵称（老美、东大、脚盆鸡等）
- 每条新闻的展开要口语化但准确
- 来源括号简单标注
- 不要使用任何Markdown格式符号，纯文本
- 不要出现"AI"这个词
- 信息必须来自素材，不要编造
- 第一行直接输出"📰"开头"""

    try:
        print("第二道：正在改写商业重点（有人味版）...")
        result = call_poe("Claude-3.5-Sonnet", [{"role": "user", "content": prompt}], temperature=0.7)
        print("第2条 商业重点 ✅")
        return result
    except Exception as e:
        print(f"Claude失败，尝试GPT-4o: {e}")
        try:
            result = call_poe("GPT-4o", [{"role": "user", "content": prompt}], temperature=0.7)
            return result
        except Exception as e2:
            print(f"全部失败: {e2}")
            return None


def format_data_dashboard(raw_market):
    """第二道·第3条：正经的数据速查表"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""以下是今天的全球市场原始数据素材：

===素材开始===
{raw_market}
===素材结束===

请从中提取核心数据，整理为一份紧凑的数据速查表。格式严格如下：

📋 数据速查 | {today}

美股：标普500 [点位]（[涨跌幅%]）｜纳斯达克 [点位]（[涨跌幅%]）｜道琼斯 [点位]（[涨跌幅%]）
A股：上证 [点位]（[涨跌幅%]）｜深证 [点位]（[涨跌幅%]）｜创业板 [点位]（[涨跌幅%]）
港股：恒生 [点位]（[涨跌幅%]）｜恒生科技 [点位]（[涨跌幅%]）
日本：日经225 [点位]（[涨跌幅%]）
欧洲：富时100 [点位]（[涨跌幅%]）｜DAX [点位]（[涨跌幅%]）
澳洲：ASX 200 [点位]（[涨跌幅%]）
黄金：[价格]美元/盎司（[涨跌幅%]）｜白银：[价格]美元/盎司（[涨跌幅%]）
原油：WTI [价格]美元/桶（[涨跌幅%]）｜布伦特 [价格]美元/桶（[涨跌幅%]）

数据截至：[标注是昨日收盘还是今日盘中]

——
奇怪地球咨询社 | 抹平全球商业的信息差

规则：
- 只输出数据，不要任何叙事、评论或解读
- 某市场休市标注"休市"
- 素材中找不到的数据标注"暂无数据"，绝不编造
- 每类市场一行，格式紧凑
- 不要使用Markdown格式
- 第一行直接输出"📋"开头"""

    try:
        print("第二道：正在整理数据速查表（正经版）...")
        result = call_poe("Claude-3.5-Sonnet", [{"role": "user", "content": prompt}], temperature=0.1)
        print("第3条 数据速查 ✅")
        return result
    except Exception as e:
        print(f"Claude失败，尝试GPT-4o: {e}")
        try:
            result = call_poe("GPT-4o", [{"role": "user", "content": prompt}], temperature=0.1)
            return result
        except Exception as e2:
            print(f"全部失败: {e2}")
            return None


def format_regional_details(raw_news):
    """第二道·第4条：正经的分区速览"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""以下是今天搜集到的全球商业新闻原始素材：

===素材开始===
{raw_news}
===素材结束===

请按地区整理成一份分区商业速览。格式严格如下：

🌐 分区速览 | {today}

🇺🇸 北美
[1-2条核心动态，每条1-2句，标注来源媒体名]

🇪🇺 欧洲
[同上]

🇨🇳 中国
[同上]

🇯🇵🇰🇷 日韩
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

——
奇怪地球咨询社 | 抹平全球商业的信息差

规则：
- 正经、客观、简洁的语气，不需要口语化或昵称
- 每条标注来源媒体名称
- 如果某地区在素材中没有值得报道的新闻，直接跳过该地区，不要写"暂无"
- 信息必须来自素材，不要编造
- 不要使用Markdown格式
- 第一行直接输出"🌐"开头"""

    try:
        print("第二道：正在整理分区速览（正经版）...")
        result = call_poe("Claude-3.5-Sonnet", [{"role": "user", "content": prompt}], temperature=0.2)
        print("第4条 分区速览 ✅")
        return result
    except Exception as e:
        print(f"Claude失败，尝试GPT-4o: {e}")
        try:
            result = call_poe("GPT-4o", [{"role": "user", "content": prompt}], temperature=0.2)
            return result
        except Exception as e2:
            print(f"全部失败: {e2}")
            return None


# ==============================================================
#  微信群精简版（基于第1条+第2条生成）
# ==============================================================

def generate_wechat_brief(market_story, business_highlights):
    """基于已经改写好的第1条和第2条，生成微信群超短版"""
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""你是「奇怪地球咨询社」的编辑，需要把今天的速报压缩成一条微信群消息。读者10秒看完就行。

以下是今天已写好的两条速报：

【市场速报】
{market_story}

【商业速报】
{business_highlights}

压缩为以下格式（严格遵守，不要多一个字）：

☀️ 早报 | {today}

📈 [一句话总结昨晚市场，不超过25字]

📰 今天知道这几件事就够了：
1️⃣ [不超过20字]
2️⃣ [不超过20字]
3️⃣ [不超过20字]

💬 [一句话判断，不超过30字]

👉 完整版见今日公众号推文

——
奇怪地球咨询社 | 抹平全球商业的信息差

规则：
- 总字数150字以内
- 不要出现来源标注
- 语气口语化，像朋友划重点
- 不要Markdown格式
- 直接输出，不要多余的话
- 第一行直接输出"☀️"开头"""

    try:
        print("正在生成微信群精简版...")
        result = call_poe("Claude-3.5-Sonnet", [{"role": "user", "content": prompt}], temperature=0.5)
        print("微信群精简版 ✅")
        return result
    except Exception as e:
        print(f"微信群精简版失败: {e}")
        return None


# ==============================================================
#  发送
# ==============================================================

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


# ==============================================================
#  主流程
# ==============================================================

def main():
    print("=" * 50)
    print("奇怪地球咨询社 · 每日简报任务启动")
    print("流程：第一道搜索 → 第二道改写 → 发送4+1条")
    print("=" * 50)

    # ========== 第一道：搜索原始素材（2次API调用） ==========
    print("\n--- 第一道：搜索原始素材 ---")

    raw_market = fetch_raw_market()
    time.sleep(5)
    raw_news = fetch_raw_news()

    if not raw_market and not raw_news:
        send_telegram("⚠️ 今天数据获取全部失败，请检查 Poe API。")
        return

    # 清理原始素材
    if raw_market:
        raw_market = clean_text(strip_english_preamble(raw_market))
    if raw_news:
        raw_news = clean_text(strip_english_preamble(raw_news))

    # ========== 第二道：改写加工（4次API调用） ==========
    print("\n--- 第二道：改写加工 ---")

    msg1 = None  # 市场故事（有人味）→ 第1条发送
    msg2 = None  # 商业重点（有人味）→ 第2条发送
    msg3 = None  # 数据速查（正经）  → 第3条发送
    msg4 = None  # 分区速览（正经）  → 第4条发送

    if raw_market:
        msg1 = rewrite_market_story(raw_market)
        time.sleep(3)
        msg3 = format_data_dashboard(raw_market)
        time.sleep(3)

    if raw_news:
        msg2 = rewrite_business_highlights(raw_news)
        time.sleep(3)
        msg4 = format_regional_details(raw_news)
        time.sleep(3)

    # ========== 发送4条消息（浅→浅→深→深） ==========
    print("\n--- 开始发送 ---")

    if msg1:
        msg1 = clean_text(strip_english_preamble(msg1))
        print("发送第1条：☀️ 市场故事")
        send_telegram(msg1)
        time.sleep(2)
    else:
        send_telegram("⚠️ 今日市场速报生成失败")

    if msg2:
        msg2 = clean_text(strip_english_preamble(msg2))
        print("发送第2条：📰 商业重点")
        send_telegram(msg2)
        time.sleep(2)
    else:
        send_telegram("⚠️ 今日商业速报生成失败")

    if msg3:
        msg3 = clean_text(strip_english_preamble(msg3))
        print("发送第3条：📋 数据速查")
        send_telegram(msg3)
        time.sleep(2)
    else:
        send_telegram("⚠️ 数据速查生成失败")

    if msg4:
        msg4 = clean_text(strip_english_preamble(msg4))
        print("发送第4条：🌐 分区速览")
        send_telegram(msg4)
        time.sleep(2)
    else:
        send_telegram("⚠️ 分区速览生成失败")

    # ========== 第5条：微信群精简版 ==========
    if msg1 and msg2:
        time.sleep(3)
        wechat_brief = generate_wechat_brief(msg1, msg2)
        if wechat_brief:
            wechat_brief = clean_text(strip_english_preamble(wechat_brief))
            print("发送第5条：微信群精简版")
            header = "👇 以下是微信群发送版，可直接复制：\n\n"
            send_telegram(header + wechat_brief)

    print("\n" + "=" * 50)
    print("今日任务全部完成 ✅")
    print(f"共调用API：第一道2次搜索 + 第二道4次改写 + 1次微信版 = 7次")
    print("=" * 50)


if __name__ == "__main__":
    main()
