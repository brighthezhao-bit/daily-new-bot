import openai
import requests
import os
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


def get_daily_news():
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""今天是 {today}。

你是一位顶尖的全球商业资讯编辑。你的读者是一位中国自媒体博主，他的定位是"抹平全球商业的信息差"。

请你联网搜索今天全球各地最新的商业新闻，然后完成以下工作：

1. 搜索范围要覆盖：北美、欧洲、中国、东亚（日韩）、东南亚、南亚（印度）、澳大利亚、中东、非洲、拉美。

2. 筛选标准（只挑真正有价值的）：
   - 各国重大经济政策变动（关税、监管、利率等）
   - 新兴市场的商业机会
   - 全球巨头的重要动作（收购、扩张、裁员、新业务）
   - 跨境电商 / 出海相关动态
   - 科技商业化的重大突破
   - 消费趋势变化
   - 中文互联网很少报道但其实很重要的事

3. 严格按以下格式输出：

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

💡 AI点评
[一段话总结今天全球商业的整体风向，指出值得持续关注的趋势]

4. 重要规则：
   - 只报道过去24小时内的新闻，严禁使用超过1天的旧闻，如果无法确认是24小时内的，宁可不报道
   - 如果某个地区今天没有值得报道的新闻，直接跳过该地区
   - 全部用中文
   - 简洁有力，不要废话套话
   - 保持客观中立
   - 每条新闻都必须标注来源媒体名称（如：路透社、彭博社、Financial Times等），不能只放链接，必须写出媒体名
   - 来源不明或无法确认的新闻不要使用"""

    try:
        print("正在通过 Poe API 调用 Web-Search...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}])
        print("AI 日报整理完成！")
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


def rewrite_for_wechat(daily_news):
    beijing_tz = timezone(timedelta(hours=8))
    today = datetime.now(beijing_tz).strftime("%Y年%m月%d日")

    prompt = f"""你是微信公众号「奇怪地球咨询社」的写手，口头禅是"抹平全球市场的信息差！"

请根据以下全球商业日报素材，改写为一篇适合公众号发布的推文。

## 今日日报素材（基于此改写，不要自己编造新闻）：
{daily_news}

## 最重要的规则：保持和日报完全一致的结构
- 保留「今日最值得关注的3件事」
- 保留「分区速览」的各地区板块（日报有哪些地区你就保留哪些）
- 保留「AI点评」
- 不要重新组织结构、不要合并板块、不要改成01｜02｜03的文章体

## 你要做的改动（只改风格和深度，不改结构）：

1. 加一个有冲击力的标题（问句或感叹句，有信息量但不低俗）

2. 开头加一段个人化的引入（1-3句话），用第一人称，像博主跟读者打招呼
   - 例如"今早被推送炸醒的""刷了十分钟新闻人都麻了"这种生活场景感

3. 每条新闻在保留原有信息的基础上，加入：
   - **中国视角**：跟中国人有什么关系？对A股/人民币/大宗商品/出海企业有什么影响？中国的机遇在哪？
   - **个人点评**：用一两句口语化的话说出你的判断，比如"说白了就是…""懂的都懂""这个信号很值得注意"
   - 敏感实体用模糊化处理（如"波斯方面""巴铁""美方""以方"等）

4. AI点评部分改写为「我的判断」，用第一人称，更主观、更有态度，但不偏激

5. 结尾加上：
   - 一句个人感悟
   - "关注「奇怪地球咨询社」，抹平全球市场的信息差！"
   - "⚠️ 以上内容基于公开信息和个人研判，不构成投资建议。"

## 语言风格（贯穿全文）
- 像跟朋友聊天，口语化，不要书面腔
- 绝对不能读起来像AI写的——避免工整排比、避免空洞形容词堆砌
- 可以用："说白了""懂的都懂""说句大实话""各位自己想吧""不用我多说吧"
- 长短句交替，关键判断加粗，偶尔用emoji但别满屏都是
- 段落要短，适合手机阅读，一段最多4-5行
- 信源/数据要保留，但表达方式要轻松"""

    try:
        print("正在生成公众号推文版本...")
        result = call_poe("Web-Search", [{"role": "user", "content": prompt}])
        print("公众号推文生成完成！")
        return result
    except Exception as e:
        print(f"公众号推文生成失败: {e}")
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

    # 第一步：生成详细日报
    daily_news = get_daily_news()

    if daily_news:
        # 发送第一条：完整日报
        print("发送第一条：完整日报...")
        send_telegram(daily_news)

        # 第二步：基于日报生成公众号推文
        time.sleep(5)
        wechat_post = rewrite_for_wechat(daily_news)

        if wechat_post:
            # 发送第二条：公众号推文版
            print("发送第二条：公众号推文版...")
            header = "✍️ 以下是公众号「奇怪地球咨询社」推文版本：\n\n"
            send_telegram(header + wechat_post)
            print("两条消息全部发送完成！")
        else:
            send_telegram("⚠️ 公众号推文版本生成失败")
    else:
        send_telegram("⚠️ 今天新闻获取失败，请检查 Poe API。")
        print("任务失败")


if __name__ == "__main__":
    main()
