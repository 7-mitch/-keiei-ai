"""
#95 Playwright Web収集エージェント（完全版）
金融ニュース・市場情報・競合情報・SNSインサイトを自動収集する
"""
import asyncio
import json
import re
from datetime import datetime
from playwright.async_api import async_playwright
from app.db.connection import get_conn

# ===== 収集対象サイト =====
NEWS_SOURCES = [
    {
        "name":     "日本銀行",
        "url":      "https://www.boj.or.jp/news/release/index.htm",
        "selector": "ul li a",
        "type":     "financial_news",
    },
    {
        "name":     "金融庁",
        "url":      "https://www.fsa.go.jp/news/",
        "selector": "div.news-list a",
        "type":     "regulatory_news",
    },
    {
        "name":     "日本経済新聞",
        "url":      "https://www.nikkei.com/news/category/markets/",
        "selector": "a.w-full",
        "type":     "market_news",
    },
]

# ===== SNS収集対象 =====
SNS_SOURCES = [
    {
        "name":     "Reddit - AI_Agents",
        "url":      "https://www.reddit.com/r/AI_Agents/top/?t=week",
        "selector": "a[data-click-id='body']",
        "type":     "sns_insight",
    },
    {
        "name":     "Reddit - MachineLearning",
        "url":      "https://www.reddit.com/r/MachineLearning/top/?t=week",
        "selector": "a[data-click-id='body']",
        "type":     "sns_insight",
    },
    {
        "name":     "Zenn - AI記事",
        "url":      "https://zenn.dev/topics/ai?order=trending",
        "selector": "a.ArticleList_link__",
        "type":     "tech_insight",
    },
    {
        "name":     "Qiita - LLM",
        "url":      "https://qiita.com/tags/llm",
        "selector": "a.css-truncated-text",
        "type":     "tech_insight",
    },
]


# ===== 汎用スクレイピング =====
async def scrape_page(url: str, selector: str) -> list[dict]:
    results = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            # 動的コンテンツ読み込み待機
            await page.wait_for_timeout(2000)
            elements = await page.query_selector_all(selector)
            for el in elements[:10]:
                text = await el.inner_text()
                href = await el.get_attribute("href")
                if text and text.strip():
                    results.append({
                        "title": text.strip()[:200],
                        "url":   href or "",
                    })
            await browser.close()
    except Exception as e:
        print(f"スクレイピングエラー ({url}): {e}")
    return results


# ===== URL指定収集 =====
async def collect_url(url: str) -> dict:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
            title   = await page.title()
            content = await page.evaluate("""
                () => {
                    const scripts = document.body.querySelectorAll('script, style');
                    scripts.forEach(s => s.remove());
                    return document.body.innerText.slice(0, 3000);
                }
            """)
            await browser.close()
            await save_to_db(
                url=url,
                status="success",
                data_type="custom_url",
                content=content,
            )
            return {
                "title":   title,
                "content": content,
                "url":     url,
                "status":  "success",
            }
    except Exception as e:
        return {
            "title":   "",
            "content": f"収集エラー: {str(e)}",
            "url":     url,
            "status":  "failed",
        }


# ===== DB保存 =====
async def save_to_db(
    url: str,
    status: str,
    data_type: str,
    content: str,
) -> None:
    try:
        async with get_conn() as conn:
            await conn.execute(
                """
                INSERT INTO web_collection_logs
                    (url, status, data_type, raw_content, collected_at)
                VALUES ($1, $2, $3, $4, $5)
                """,
                url,
                status,
                data_type,
                content,
                datetime.utcnow(),
            )
    except Exception as e:
        print(f"DB保存エラー: {e}")


# ===== 金融ニュース収集 =====
async def collect_news() -> list[dict]:
    all_results = []
    for source in NEWS_SOURCES:
        print(f"収集開始: {source['name']}")
        articles = await scrape_page(source["url"], source["selector"])
        if articles:
            await save_to_db(
                url=source["url"],
                status="success",
                data_type=source["type"],
                content=json.dumps(articles, ensure_ascii=False),
            )
            print(f"{source['name']}: {len(articles)}件収集")
            all_results.extend([
                {**a, "source": source["name"], "type": source["type"]}
                for a in articles
            ])
        else:
            await save_to_db(
                url=source["url"],
                status="failed",
                data_type=source["type"],
                content="",
            )
    return all_results


# ===== SNSインサイト収集 =====
async def collect_sns_insights() -> list[dict]:
    """
    RedditやZenn・Qiitaからトレンド記事を収集し
    AIエンジニア向けインサイトレポートの素材にする
    """
    all_results = []
    for source in SNS_SOURCES:
        print(f"SNS収集開始: {source['name']}")
        articles = await scrape_page(source["url"], source["selector"])
        if articles:
            await save_to_db(
                url=source["url"],
                status="success",
                data_type=source["type"],
                content=json.dumps(articles, ensure_ascii=False),
            )
            print(f"{source['name']}: {len(articles)}件収集")
            all_results.extend([
                {**a, "source": source["name"], "type": source["type"]}
                for a in articles
            ])
        else:
            await save_to_db(
                url=source["url"],
                status="failed",
                data_type=source["type"],
                content="",
            )
    return all_results


# ===== インサイトレポート生成 =====
async def generate_insight_report(articles: list[dict]) -> str:
    """
    収集したSNS記事からLLMでインサイトレポートを生成する
    （Gemini / OpenAI API と接続して使用）
    """
    if not articles:
        return "収集データがありません。"

    lines = [
        f"【{a['source']}】{a['title']}"
        for a in articles[:20]
    ]
    summary = "\n".join(lines)

    # TODO: ここにGemini / OpenAI API呼び出しを追加
    # 例: response = await gemini_client.generate(prompt=summary)
    # 現時点では収集データをそのまま返す
    return f"=== SNSインサイトレポート ===\n収集日時: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n{summary}"


# ===== メインエージェント =====
async def run_web_agent(question: str, session_id: str) -> str:
    q = question.lower()

    # URL指定収集
    if "http" in q:
        urls = re.findall(r'https?://[^\s]+', question)
        if urls:
            result = await collect_url(urls[0])
            return f"【{result['title']}】\n{result['content'][:500]}..."

    # SNSインサイト収集モード
    if any(kw in q for kw in ["sns", "insight", "インサイト", "トレンド", "reddit", "zenn", "qiita"]):
        print(f"SNSインサイト収集モード起動: {question}")
        articles = await collect_sns_insights()
        return await generate_insight_report(articles)

    # 通常の金融ニュース収集
    print(f"Web収集エージェント起動: {question}")
    articles = await collect_news()
    if not articles:
        return "現在ニュースを収集できませんでした。"

    lines = [f"【{a['source']}】{a['title']}" for a in articles[:5]]
    return "最新ニュース:\n" + "\n".join(lines)


# ===== 単体テスト用 =====
if __name__ == "__main__":
    async def main():
        # 金融ニュース収集テスト
        result = await run_web_agent("最新ニュースを教えて", "test_session")
        print(result)

        # SNSインサイト収集テスト
        result = await run_web_agent("redditのトレンドを収集して", "test_session")
        print(result)

    asyncio.run(main())