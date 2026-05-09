import sys
import pathlib
import importlib
import types
import streamlit as st
from datetime import date

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


st.title("Project Analyzer — プロトタイプ")

root = st.text_input("Workspace path", value=".")

use_mock = st.checkbox("Use Mock LLM (no external API)", value=True)

if st.button("Run Analysis"):
    # provide current date in Japanese format to the LLM client as default context
    today = date.today()
    date_str = f"{today.year}年{today.month}月{today.day}日"
    client = MockLLMClient(default_context=date_str) if use_mock else None
    with st.spinner("Scanning and summarizing..."):
        res = run_analyze(root=root, out=None, llm_client=client)

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
