"""
web_agent.py — Web収集エージェント（業界別法令・ニュース自動収集 + RAG自動追加）
機能:
  - 業界別法令サイト自動巡回（厚労省・国交省・経産省等）
  - 金融ニュース・市場情報収集
  - SNSインサイト収集（Reddit・Zenn・Qiita）
  - LLM要約生成
  - RAGへの自動追加
  - 定期実行対応
  - Tavily API連携（優先検索）
"""
import asyncio
import json
import os
import re
from datetime import datetime
from playwright.async_api import async_playwright
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.llm_factory import get_llm
from app.agents.base_prompt import get_agent_prompt
from app.db.connection import get_conn

# ===== LLM =====
llm = get_llm()


# ===== 業界別法令サイト =====
REGULATORY_SOURCES = {
    "介護": [
        {
            "name":     "厚生労働省（介護保険）",
            "url":      "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/kaigo_koureisha/index.html",
            "selector": "div.m-listLink a",
            "type":     "regulatory_care",
        },
        {
            "name":     "厚生労働省（介護報酬）",
            "url":      "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/hukushi_kaigo/kaigo_koureisha/housyu/index.html",
            "selector": "div.m-listLink a",
            "type":     "regulatory_care",
        },
    ],
    "医療": [
        {
            "name":     "厚生労働省（医療）",
            "url":      "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/index.html",
            "selector": "div.m-listLink a",
            "type":     "regulatory_medical",
        },
        {
            "name":     "厚生労働省（診療報酬）",
            "url":      "https://www.mhlw.go.jp/stf/seisakunitsuite/bunya/kenkou_iryou/iryou/hourei/index.html",
            "selector": "div.m-listLink a",
            "type":     "regulatory_medical",
        },
    ],
    "建設": [
        {
            "name":     "国土交通省（建設業）",
            "url":      "https://www.mlit.go.jp/totikensangyo/const/index.html",
            "selector": "div.content-area a",
            "type":     "regulatory_construction",
        },
        {
            "name":     "国土交通省（建築基準法）",
            "url":      "https://www.mlit.go.jp/jutakukentiku/build/index.html",
            "selector": "div.content-area a",
            "type":     "regulatory_construction",
        },
    ],
    "製造": [
        {
            "name":     "経済産業省（製造業）",
            "url":      "https://www.meti.go.jp/policy/mono_info_service/mono/index.html",
            "selector": "div.contents-body a",
            "type":     "regulatory_manufacturing",
        },
        {
            "name":     "経済産業省（カーボンニュートラル）",
            "url":      "https://www.meti.go.jp/policy/energy_environment/global_warming/index.html",
            "selector": "div.contents-body a",
            "type":     "regulatory_manufacturing",
        },
    ],
    "法律": [
        {
            "name":     "e-Gov法令検索",
            "url":      "https://laws.e-gov.go.jp/",
            "selector": "a.law-title",
            "type":     "regulatory_legal",
        },
    ],
    "経理": [
        {
            "name":     "国税庁（インボイス）",
            "url":      "https://www.nta.go.jp/taxes/shiraberu/zeimokubetsu/shohi/keigenzeiritsu/invoice.htm",
            "selector": "div.content-area a",
            "type":     "regulatory_accounting",
        },
        {
            "name":     "国税庁（電帳法）",
            "url":      "https://www.nta.go.jp/law/joho-zeikaishaku/sonota/jirei/index.htm",
            "selector": "div.content-area a",
            "type":     "regulatory_accounting",
        },
    ],
}

# ===== 金融ニュース =====
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

# ===== SNSインサイト =====
SNS_SOURCES = [
    {
        "name":     "Reddit - AI_Agents",
        "url":      "https://www.reddit.com/r/AI_Agents/top/?t=week",
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
                headless = True,
                args     = ["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = await browser.new_page(
                user_agent = (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                )
            )
            await page.goto(url, timeout=30000, wait_until="domcontentloaded")
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
        print(f"[WEB] スクレイピングエラー ({url}): {e}")

    return results


# ===== URL指定収集 =====
async def collect_url(url: str) -> dict:
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless = True,
                args     = ["--no-sandbox", "--disable-dev-shm-usage"],
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
                url       = url,
                status    = "success",
                data_type = "custom_url",
                content   = content,
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
    url:       str,
    status:    str,
    data_type: str,
    content:   str,
) -> None:
    try:
        async with get_conn() as conn:
            await conn.execute("""
                INSERT INTO web_collection_logs
                    (url, status, data_type, raw_content, processed_at)
                VALUES ($1, $2, $3, $4, NOW())
            """,
                url, status, data_type, content,
            )
    except Exception as e:
        print(f"[WEB] DB保存エラー: {e}")


# ===== RAGへの自動追加 =====
async def add_to_rag(
    content:  str,
    source:   str,
    industry: str | None = None,
) -> bool:
    try:
        from langchain_community.vectorstores import FAISS
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain.schema import Document

        cache_dir  = os.getenv("HF_CACHE_DIR", "/tmp/huggingface")
        embeddings = HuggingFaceEmbeddings(
            model_name    = "intfloat/multilingual-e5-small",
            cache_folder  = cache_dir,
            model_kwargs  = {"device": "cpu"},
            encode_kwargs = {"normalize_embeddings": True},
        )

        industry_dir_map = {
            "介護": "care", "医療": "medical", "建設": "construction",
            "製造": "manufacturing", "法律": "legal",
        }

        vector_dir = "vector_store"
        if industry and industry in industry_dir_map:
            vector_dir = f"vector_store/{industry_dir_map[industry]}"

        doc = Document(
            page_content = content[:1000],
            metadata     = {
                "source":    source,
                "industry":  industry or "general",
                "collected": datetime.now().isoformat(),
                "type":      "web_collected",
            },
        )

        if os.path.exists(vector_dir):
            store = FAISS.load_local(
                vector_dir,
                embeddings,
                allow_dangerous_deserialization = True,
            )
            store.add_documents([doc])
            store.save_local(vector_dir)
        else:
            store = FAISS.from_documents([doc], embeddings)
            os.makedirs(vector_dir, exist_ok=True)
            store.save_local(vector_dir)

        print(f"[WEB] RAG追加完了: {source} → {vector_dir}")
        return True

    except Exception as e:
        print(f"[WEB] RAG追加エラー: {e}")
        return False


# ===== LLM要約生成 =====
async def summarize_with_llm(
    articles: list[dict],
    context:  str = "経営者向け",
) -> str:
    if not articles:
        return "収集データがありません。"

    lines = [
        f"【{a.get('source', '不明')}】{a['title']}"
        for a in articles[:15]
    ]
    articles_text = "\n".join(lines)

    try:
        response = await llm.ainvoke([
            SystemMessage(content=get_agent_prompt("web", extra=f"【対象業界】{context}向けの情報を要約してください。")),
            HumanMessage(content=f"以下の記事を要約してください:\n\n{articles_text}"),
        ])

        if isinstance(response.content, list):
            return response.content[0].get("text", "") if response.content else ""
        return str(response.content)

    except Exception as e:
        print(f"[WEB] LLM要約エラー: {e}")
        return f"収集記事:\n{articles_text}"


# ===== 業界別法令収集 =====
async def collect_regulatory(industry: str) -> list[dict]:
    sources     = REGULATORY_SOURCES.get(industry, [])
    all_results = []

    for source in sources:
        print(f"[WEB] 法令収集: {source['name']}")
        articles = await scrape_page(source["url"], source["selector"])

        if articles:
            await save_to_db(
                url       = source["url"],
                status    = "success",
                data_type = source["type"],
                content   = json.dumps(articles, ensure_ascii=False),
            )
            await add_to_rag(
                content  = f"【{source['name']}】\n" + "\n".join(
                    [a["title"] for a in articles]
                ),
                source   = source["name"],
                industry = industry,
            )
            all_results.extend([
                {**a, "source": source["name"], "type": source["type"]}
                for a in articles
            ])
            print(f"[WEB] {source['name']}: {len(articles)}件収集・RAG追加")

    return all_results


# ===== 金融ニュース収集 =====
async def collect_news() -> list[dict]:
    all_results = []
    for source in NEWS_SOURCES:
        print(f"[WEB] ニュース収集: {source['name']}")
        articles = await scrape_page(source["url"], source["selector"])

        if articles:
            await save_to_db(
                url       = source["url"],
                status    = "success",
                data_type = source["type"],
                content   = json.dumps(articles, ensure_ascii=False),
            )
            all_results.extend([
                {**a, "source": source["name"], "type": source["type"]}
                for a in articles
            ])
            print(f"[WEB] {source['name']}: {len(articles)}件収集")

    return all_results


# ===== SNSインサイト収集 =====
async def collect_sns_insights() -> list[dict]:
    all_results = []
    for source in SNS_SOURCES:
        print(f"[WEB] SNS収集: {source['name']}")
        articles = await scrape_page(source["url"], source["selector"])

        if articles:
            await save_to_db(
                url       = source["url"],
                status    = "success",
                data_type = source["type"],
                content   = json.dumps(articles, ensure_ascii=False),
            )
            all_results.extend([
                {**a, "source": source["name"], "type": source["type"]}
                for a in articles
            ])

    return all_results


# ===== 定期実行（毎朝自動収集）=====
async def daily_collection() -> dict:
    """毎朝6時に実行: 0 6 * * *"""
    print(f"[WEB] 定期収集開始: {datetime.now()}")
    results = {}

    for industry in REGULATORY_SOURCES.keys():
        articles          = await collect_regulatory(industry)
        results[industry] = len(articles)
        print(f"[WEB] {industry}: {len(articles)}件")

    news                  = await collect_news()
    results["金融ニュース"] = len(news)

    print(f"[WEB] 定期収集完了: {results}")
    return results


# ===== メインエージェント =====
async def run_web_agent(question: str, session_id: str) -> str:
    q = question.lower()

    # ===== Tavily APIで検索（優先）=====
    tavily_key = os.getenv("TAVILY_API_KEY", "")
    if tavily_key:
        try:
            from tavily import TavilyClient
            client  = TavilyClient(api_key=tavily_key)
            results = client.search(
                query           = question,
                search_depth    = "basic",
                max_results     = 5,
                include_answer  = True,
                include_domains = [
                    "meti.go.jp", "chusho.meti.go.jp",
                    "mirasapo-plus.go.jp", "nikkei.com",
                    "boj.or.jp", "fsa.go.jp",
                    "mhlw.go.jp", "nta.go.jp",
                ],
            )

            if results.get("answer"):
                answer   = results["answer"]
                sources  = results.get("results", [])
                src_text = "\n".join([
                    f"- {r.get('title', '')}（{r.get('url', '')}）"
                    for r in sources[:3]
                ])
                return f"{answer}\n\n【参考情報】\n{src_text}"

            articles = [
                {
                    "title":  r.get("title", ""),
                    "source": r.get("url", ""),
                }
                for r in results.get("results", [])
            ]
            if articles:
                summary = await summarize_with_llm(articles, context="経営者向け")
                return f"【Web検索結果】\n{summary}"

        except Exception as e:
            print(f"[WEB] Tavily検索エラー: {e}")

    # ===== URL指定収集 =====
    if "http" in q:
        urls = re.findall(r'https?://[^\s]+', question)
        if urls:
            result = await collect_url(urls[0])
            if result["status"] == "success":
                await add_to_rag(
                    content = result["content"],
                    source  = result["url"],
                )
            return f"【{result['title']}】\n{result['content'][:500]}..."

    # ===== SNSインサイト収集 =====
    if any(kw in q for kw in ["sns", "insight", "インサイト", "トレンド", "reddit", "zenn", "qiita"]):
        articles = await collect_sns_insights()
        summary  = await summarize_with_llm(articles, context="AIエンジニア向け")
        return f"【AIトレンドインサイト】\n{summary}"

    # ===== 業界別法令収集 =====
    from app.agents.rag_agent import INDUSTRY_KEYWORDS
    for industry, keywords in INDUSTRY_KEYWORDS.items():
        if any(kw in q for kw in keywords):
            print(f"[WEB] 業界法令収集モード: {industry}")
            articles = await collect_regulatory(industry)
            summary  = await summarize_with_llm(
                articles,
                context = f"{industry}業界の経営者向け",
            )
            return f"【{industry}業界 最新法令・規制情報】\n{summary}"

    # ===== 通常の金融ニュース収集 =====
    articles = await collect_news()
    if not articles:
        return "現在ニュースを収集できませんでした。"

    summary = await summarize_with_llm(articles, context="経営者向け")
    return f"【最新経営情報】\n{summary}"


# ===== 単体テスト =====
if __name__ == "__main__":
    async def main():
        print("=== 介護法令収集テスト ===")
        result = await run_web_agent("介護報酬の最新情報を教えて", "test")
        print(result)

        print("\n=== 金融ニューステスト ===")
        result = await run_web_agent("最新の経済ニュースを教えて", "test")
        print(result)

    asyncio.run(main())


