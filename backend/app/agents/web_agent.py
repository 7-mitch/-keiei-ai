"""
#95 Playwright Web収集エージェント
金融ニュース・市場情報・競合情報を自動収集する
"""
import asyncio
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

async def scrape_page(url: str, selector: str) -> list[dict]:
    results = []
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless = True,
                args     = ["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page()
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
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
        print(f" スクレイピングエラー ({url}): {e}")
    return results


async def save_to_db(url: str, status: str, data_type: str, content: str) -> None:
    try:
        async with get_conn() as conn:
            await conn.execute("""
                INSERT INTO web_collection_logs
                    (url, status, data_type, raw_content)
                VALUES ($1, $2, $3, $4)
            """, url, status, data_type, content)
    except Exception as e:
        print(f" DB保存エラー: {e}")


async def collect_news() -> list[dict]:
    all_results = []
    for source in NEWS_SOURCES:
        print(f" 収集開始: {source['name']}")
        articles = await scrape_page(source["url"], source["selector"])
        if articles:
            import json
            await save_to_db(
                url       = source["url"],
                status    = "success",
                data_type = source["type"],
                content   = json.dumps(articles, ensure_ascii=False),
            )
            print(f" {source['name']}: {len(articles)}件収集")
            all_results.extend([
                {**a, "source": source["name"], "type": source["type"]}
                for a in articles
            ])
        else:
            await save_to_db(
                url       = source["url"],
                status    = "failed",
                data_type = source["type"],
                content   = "",
            )
    return all_results


async def collect_url(url: str) -> dict:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless = True,
                args     = ["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page    = await browser.new_page()
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
            await save_to_db(url=url, status="success", data_type="custom_url", content=content)
            return {"title": title, "content": content, "url": url, "status": "success"}
    except Exception as e:
        return {"title": "", "content": f"収集エラー: {str(e)}", "url": url, "status": "failed"}


async def run_web_agent(question: str, session_id: str) -> str:
    q = question.lower()
    if "http" in q:
        import re
        urls = re.findall(r'https?://[^\s]+', question)
        if urls:
            result = await collect_url(urls[0])
            return f"【{result['title']}】\n{result['content'][:500]}..."
    print(f" Web収集エージェント起動: {question}")
    articles = await collect_news()
    if not articles:
        return "現在ニュースを収集できませんでした。"
    lines = [f"【{a['source']}】{a['title']}" for a in articles[:5]]
    return "最新ニュース:\n" + "\n".join(lines)
