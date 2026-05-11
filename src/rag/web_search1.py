import os
from pathlib import Path

# Web検索用ライブラリ
try:
    from ddgs.ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

def search_web_tool(query, max_results=3):
    """
    Web検索ツール。
    優先順位: Tavily -> DuckDuckGo
    """
    # Entry debug
    try:
        entry_path = Path(__file__).resolve().parent.parent / 'logs' / 'web_search_entry.log'
        entry_path.parent.mkdir(parents=True, exist_ok=True)
        with open(entry_path, 'a', encoding='utf-8') as ef:
            ef.write(f"called search_web_tool with query={query}\n")
    except Exception:
        pass

    errors = []
    
    # Strategy 1: Tavily Search
    def search_tavily():
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_api_key or not TavilyClient:
            return None
        
        try:
            client = TavilyClient(api_key=tavily_api_key)
            response = client.search(query, search_depth="advanced", max_results=max_results)
            results = []
            for i, r in enumerate(response.get("results", [])):
                text_content = f"Title: {r.get('title')}\nURL: {r.get('url')}\nBody: {r.get('content')}"
                results.append({
                    "id": f"web_{i+1}",
                    "text": text_content,
                    "score": r.get("score", 1.0),
                    "source": "web",
                    "meta": {"source": r.get("url")}
                })
            return results
        except Exception as e:
            errors.append(f"Tavily: {e}")
            return None

    # Strategy 2: DuckDuckGo Search
    def search_ddg():
        if DDGS is None:
            return None

        try:
            results = []
            with DDGS() as ddgs:
                ddgs_gen = ddgs.text(keywords=query, region='jp-jp', max_results=max_results)
                for i, r in enumerate(ddgs_gen):
                    text_content = f"Title: {r['title']}\nURL: {r['href']}\nBody: {r['body']}"
                    results.append({
                        "id": f"web_{i+1}",
                        "text": text_content,
                        "score": 1.0,
                        "source": "web",
                        "meta": {"source": r["href"]}
                    })
            return results
        except Exception as e:
            errors.append(f"DuckDuckGo: {e}")
            return None
    
    res = search_tavily()
    if res is not None:
        return res

    res = search_ddg()
    if res is not None:
        return res

    return [{
        "id": "web_error",
        "text": f"Web検索でエラーが発生しました。詳細:\n" + "\n".join(errors),
        "score": 0.0,
        "source": "system"
    }]