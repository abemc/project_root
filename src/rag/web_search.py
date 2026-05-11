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
    戻り値: list of result dicts with keys id,text,score,source,meta
    """
    errors = []
    # quick trace to /tmp to verify function entry
    try:
        with open('/tmp/ws_entry.log','a',encoding='utf-8') as tf:
            tf.write(f'entered search_web_tool query={query}\n')
    except Exception:
        pass

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
                    "score": float(r.get("score", 1.0)),
                    "source": "web",
                    "meta": {"source": r.get("url")}
                })
            return results
        except Exception as e:
            errors.append(f"Tavily: {e}")
            return None

    # Strategy 2: DuckDuckGo Search using ddgs
    def search_ddg():
        if DDGS is None:
            return None
        results = []
        # target project log
        proj_log = Path(__file__).resolve().parent.parent.parent / 'logs' / 'web_search_debug.log'
        try:
            proj_log.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        try:
            with DDGS() as ddgs:
                # debug info
                try:
                    import inspect
                    with open(proj_log, 'a', encoding='utf-8') as lf:
                        lf.write('--- DDGS call debug ---\n')
                        lf.write(f'DDGS instance type: {type(ddgs)}\n')
                        lf.write(f'ddgs.text repr: {repr(getattr(ddgs, "text", None))}\n')
                        try:
                            lf.write(f'signature: {inspect.signature(ddgs.text)}\n')
                        except Exception:
                            lf.write('signature: <unavailable>\n')
                except Exception:
                    pass

                # call with positional query arg (ddgs.text(self, query, **kwargs))
                ddgs_result = ddgs.text(query, region='jp-jp', max_results=max_results)
                # ddgs.text may return a list
                for i, r in enumerate(ddgs_result):
                    title = r.get('title') or r.get('text') or ''
                    href = r.get('href') or r.get('url') or r.get('link') or ''
                    body = r.get('body') or r.get('snippet') or r.get('text') or ''
                    text_content = f"Title: {title}\nURL: {href}\nBody: {body}"
                    results.append({
                        "id": f"web_{i+1}",
                        "text": text_content,
                        "score": float(r.get('score', 1.0)),
                        "source": "web",
                        "meta": {"source": href}
                    })
            return results
        except Exception as e:
            import traceback
            tb = traceback.format_exc()
            errors.append(f"DuckDuckGo: {e}\n" + tb)
            try:
                with open(proj_log, 'a', encoding='utf-8') as lf:
                    lf.write('--- exception in search_ddg ---\n')
                    lf.write(tb + '\n')
            except Exception:
                pass
            return None

    # Try Tavily first
    res = search_tavily()
    if res:
        return res

    # Then DuckDuckGo
    res = search_ddg()
    if res:
        return res

    # If all failed, return error payload
    return [{
        "id": "web_error",
        "text": "Web検索でエラーが発生しました。詳細:\n" + "\n".join(errors),
        "score": 0.0,
        "source": "system"
    }]
