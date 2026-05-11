import sys
import pathlib
import importlib
import types
import streamlit as st
from datetime import date
import re
import requests
from bs4 import BeautifulSoup

# When Streamlit runs the script directly, relative imports inside
# the `analyzer` package can fail. Register a minimal package module
# for `analyzer` so submodule imports (e.g. `from .scanner import ...`)
# succeed.
THIS_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = THIS_DIR.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if 'analyzer' not in sys.modules:
    analyzer_pkg = types.ModuleType('analyzer')
    analyzer_pkg.__path__ = [str(THIS_DIR)]
    sys.modules['analyzer'] = analyzer_pkg

_cli_mod = importlib.import_module('analyzer.cli')
_llm_mod = importlib.import_module('analyzer.llm_client')

run_analyze = _cli_mod.run_analyze
MockLLMClient = _llm_mod.MockLLMClient
import json
import logging
import os


st.title("Project Analyzer — プロトタイプ")

root = st.text_input("Workspace path", value=".")

use_mock = st.checkbox("Use Mock LLM (no external API)", value=True)

if st.button("Run Analysis"):
    # If the user typed a date/time question into the input, answer locally without scanning
    q_low = (root or "").strip()
    # If the input looks like a real filesystem path (or is the default '.'), prefer scanning
    import os as _os
    looks_like_path = _os.path.isdir(q_low) or q_low in (".", "./")

    # Server-side shortcut: if user asks for today's Japanese date (only when input is NOT a path)
    if (not looks_like_path) and re.search(r"今日.?の?日付|今日は何月何日|今日は何日|何月何日|何曜日", q_low):
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
        except Exception:
            today = datetime.now().date()
        _weekdays = ["月曜日", "火曜日", "水曜日", "木曜日", "金曜日", "土曜日", "日曜日"]
        weekday = _weekdays[today.weekday()]
        resp = f"今日は{today.year}年{today.month}月{today.day}日（{weekday}）です。"
        # Build minimal result structure compatible with UI
        res = {
            "project_summary": {},
            "analysis_summary": resp,
            "files": [],
        }
    # Server-side shortcut: today's 日本ハム 試合結果
    elif (not looks_like_path) and re.search(r"日本ハム.*試合結果|今日.*日本ハム.*試合|今日の日本ハム", q_low):
        from datetime import datetime
        try:
            from zoneinfo import ZoneInfo
            today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
        except Exception:
            today = datetime.now().date()
        def _get_team_result(team_name: str, dt: date):
            # Try NPB first (may be blocked), then fallback to Fighters site
            date_str = dt.strftime('%Y%m%d')
            headers = {"User-Agent": "project-analyzer/1.0 (+https://example.com)"}
            # Try Fighters result pages directly (multiple possible game IDs)
            try:
                base = f"https://www.fighters.co.jp/gamelive/result/"
                for i in range(1, 8):
                    url = f"{base}{date_str}{i:02d}/"
                    try:
                        r = requests.get(url, timeout=6, headers=headers)
                        if r.status_code != 200:
                            continue
                        soup = BeautifulSoup(r.text, 'html.parser')
                        # get team names in header (order matters)
                        names = [d.get_text(strip=True) for d in soup.select('.c-game-detail__header-text')]
                        if not names:
                            # fallback: search for occurrence of team_name
                            if team_name not in r.text:
                                continue
                        # parse score table numbers
                        table = soup.find(class_='c-score-board-table')
                        if table:
                            nums = re.findall(r"\d+", table.get_text())
                            # look for pattern ... R H r1 h1 r2 h2
                            if len(nums) >= 4:
                                r1, h1, r2, h2 = nums[-4:]
                                r1 = int(r1); r2 = int(r2)
                                # if we have two team names, map them
                                if len(names) >= 2:
                                    t1 = names[0]; t2 = names[1]
                                else:
                                    # best-effort: extract team names by searching
                                    txt = r.text
                                    if '北海道' in txt and 'オリックス' in txt:
                                        t1 = '北海道日本ハム'; t2 = 'オリックス'
                                    else:
                                        t1 = team_name; t2 = '対戦相手'
                                if team_name in t1:
                                    opp = t2; team_score = r1; opp_score = r2
                                elif team_name in t2:
                                    opp = t1; team_score = r2; opp_score = r1
                                else:
                                    # not this page
                                    continue
                                return {'date': dt.isoformat(), 'team': team_name, 'opponent': opp, 'team_score': team_score, 'opponent_score': opp_score, 'source': url}
                    except Exception:
                        continue
            except Exception:
                pass
            # final fallback: try NPB index page (may return 403)
            try:
                url = f"https://npb.jp/scores/{dt.year}/{dt.strftime('%m%d')}/"
                r = requests.get(url, timeout=6, headers=headers)
                r.raise_for_status()
                soup = BeautifulSoup(r.text, 'html.parser')
                names = [d.get_text(strip=True) for d in soup.select('.c-game-detail__header-text')]
                table = soup.find(class_='c-score-board-table')
                if table:
                    nums = re.findall(r"\d+", table.get_text())
                    if len(nums) >= 4:
                        r1, h1, r2, h2 = nums[-4:]
                        r1 = int(r1); r2 = int(r2)
                        if len(names) >= 2:
                            t1 = names[0]; t2 = names[1]
                        else:
                            t1 = team_name; t2 = '対戦相手'
                        if team_name in t1:
                            opp = t2; team_score = r1; opp_score = r2
                        elif team_name in t2:
                            opp = t1; team_score = r2; opp_score = r1
                        else:
                            return None
                        return {'date': dt.isoformat(), 'team': team_name, 'opponent': opp, 'team_score': team_score, 'opponent_score': opp_score, 'source': url}
            except Exception:
                return None
            return None

        info = _get_team_result('北海道日本ハム', today)
        if info:
            resp = f"{info['date']} の試合結果 — {info['team']} {info['team_score']} - {info['opponent_score']} {info['opponent']}。 (出典: {info['source']})"
        else:
            resp = "申し訳ありません、外部サイトから試合結果を取得できませんでした。後ほど再試行してください。"
        res = {"project_summary": {}, "analysis_summary": resp, "files": []}
    else:
        # provide current date in Japanese format to the LLM client as default context
            from datetime import datetime
            try:
                from zoneinfo import ZoneInfo
                today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
            except Exception:
                today = datetime.now().date()
            date_str = f"{today.year}年{today.month}月{today.day}日"
            client = MockLLMClient(default_context=date_str) if use_mock else None
            # lightweight logging to file for debugging when run inside Streamlit
            try:
                logging.basicConfig(filename='/tmp/ui_run.log', level=logging.DEBUG)
                logging.debug('UI run: cwd=%s root=%s use_mock=%s', os.getcwd(), root, use_mock)
            except Exception:
                pass
            # If a precomputed analysis JSON exists for the project root, use it as a fast fallback
            # unless FORCE_RUN_ANALYZE=1 is set in the environment.
            fallback_path = os.path.join(PROJECT_ROOT, 'analysis_result.json')
            force_run = os.environ.get('FORCE_RUN_ANALYZE', '0') == '1'
            if root in ('.', './') and os.path.exists(fallback_path) and not force_run:
                try:
                    with open(fallback_path, 'r', encoding='utf-8') as f:
                        res = json.load(f)
                    logging.debug('Loaded fallback analysis_result.json with files=%d', len(res.get('files', [])))
                except Exception:
                    logging.exception('Failed to load fallback analysis_result.json; falling back to run_analyze')
                    with st.spinner("Scanning and summarizing..."):
                        res = run_analyze(root=root, out=None, llm_client=client)
            else:
                with st.spinner("Scanning and summarizing..."):
                    try:
                        res = run_analyze(root=root, out=None, llm_client=client)
                        try:
                            logging.debug('run_analyze returned keys=%s files_count=%d', list(res.keys()), len(res.get('files', [])))
                        except Exception:
                            pass
                    except Exception:
                        try:
                            logging.exception('run_analyze failed')
                        except Exception:
                            pass
                        raise

    st.header("Project Summary")
    ps = res.get("project_summary", {})
    st.write(ps)

    st.header("Analysis Summary")
    st.code(res.get("analysis_summary", "(no summary)"))

    st.header("Files")
    files = res.get("files", [])
    if files:
        # display limited columns
        rows = [{"path": f["path"], "size": f["size"], "lang": f["lang"]} for f in files]
        st.table(rows)

    st.header("Full JSON")
    st.json(res)
