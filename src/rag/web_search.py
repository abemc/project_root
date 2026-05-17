import os

# Web検索用ライブラリ
try:
    from ddgs.ddgs import DDGS
except ImportError:
    DDGS = None

try:
    from tavily import TavilyClient
except ImportError:
    TavilyClient = None

import requests
from bs4 import BeautifulSoup
import urllib.parse as urlparse

def search_web_tool(query, max_results=3):
    """
    Web検索ツール。
    優先順位: Tavily -> DuckDuckGo
    """
    errors = []
    
    # Strategy 1: Tavily Search
    def search_tavily():
        tavily_api_key = os.environ.get("TAVILY_API_KEY")
        if not tavily_api_key or not TavilyClient:
            return None
        
        try:
            client = TavilyClient(api_key=tavily_api_key)
            # If client supports API key validation, call it to fail fast on invalid keys
            if hasattr(client, 'validate_api_key'):
                try:
                    valid = client.validate_api_key()
                    if not valid:
                        errors.append("Tavily: API key validation failed")
                        return None
                except Exception as e:
                    errors.append(f"Tavily validation error: {e}")
                    return None
            response = client.search(query, search_depth="advanced", max_results=max_results)
            results = []
            # response may have different shapes; normalize safely
            candidates = response.get("results") or response.get("items") or []
            for i, r in enumerate(candidates[:max_results]):
                # flexible field extraction
                title = r.get('title') or r.get('headline') or r.get('name') or ''
                url = r.get('url') or r.get('link') or r.get('href') or ''
                # try nested link
                if not url and isinstance(r.get('meta'), dict):
                    url = r['meta'].get('url') or r['meta'].get('source') or ''
                # snippet/body
                snippet = r.get('content') or r.get('snippet') or r.get('summary') or r.get('excerpt') or ''
                score = r.get('score') if isinstance(r.get('score'), (int, float)) else 1.0

                # normalize URL (if ddg redirected uddg link present, keep as-is)
                if url and url.startswith('/'):
                    # leave relative-looking urls returned by DDG proxy
                    norm_url = url
                else:
                    norm_url = urlparse.unquote(url) if url else ''

                text_parts = []
                if title:
                    text_parts.append(f"Title: {title}")
                if norm_url:
                    text_parts.append(f"URL: {norm_url}")
                if snippet:
                    text_parts.append(f"Body: {snippet}")

                text_content = "\n".join(text_parts) if text_parts else str(r)

                results.append({
                    "id": f"web_{i+1}",
                    "text": text_content,
                    "score": score,
                    "source": "web",
                    "meta": {"source": norm_url}
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

    # Strategy 3: DuckDuckGo HTML scrape fallback (use requests + BeautifulSoup)
    def search_ddg_scrape():
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; RAGAgent/1.0; +https://example.com)"
            }
            # Use DuckDuckGo's HTML endpoint
            resp = requests.get("https://duckduckgo.com/html/", params={"q": query, "kl": "jp-jp"}, headers=headers, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "html.parser")
            results = []
            # DuckDuckGo HTML results often place results in 'a.result__a' or 'a' within 'div.result'
            items = soup.select("div.result")
            if not items:
                items = soup.select("a.result__a") or soup.select("a")
            for i, it in enumerate(items[:max_results]):
                # attempt to find link and snippet
                link = None
                title = ""
                snippet = ""
                a = it.find("a") if getattr(it, 'find', None) else None
                if a and a.get("href"):
                    link = a.get("href")
                    title = a.get_text(strip=True)
                else:
                    # if 'it' is an <a> element already
                    try:
                        link = it.get("href")
                        title = it.get_text(strip=True)
                    except Exception:
                        pass

                # snippet: look for descendant with class 'result__snippet' or 'c-abstract'
                sn = it.select_one("a > .result__snippet, .result__snippet, .c-abstract, .snippet")
                if sn:
                    snippet = sn.get_text(strip=True)
                else:
                    # fallback: get nearby text
                    snippet = it.get_text(separator=' ', strip=True)[:300]

                if not link:
                    continue

                text_content = f"Title: {title}\nURL: {link}\nBody: {snippet}"
                results.append({
                    "id": f"web_{i+1}",
                    "text": text_content,
                    "score": 1.0,
                    "source": "web",
                    "meta": {"source": link}
                })
            return results
        except Exception as e:
            errors.append(f"DDG-scrape: {e}")
            return None
    
    res = search_tavily()
    if res is not None:
        return res

    res = search_ddg()
    if res is not None:
        return res

    # try html-scrape fallback
    res = search_ddg_scrape()
    if res is not None:
        return res

    return [{
        "id": "web_error",
        "text": f"Web検索でエラーが発生しました。詳細:\n" + "\n".join(errors),
        "score": 0.0,
        "source": "system"
    }]