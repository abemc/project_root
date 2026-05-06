import streamlit as st
from .cli import run_analyze
from .llm_client import MockLLMClient
import json


st.title("Project Analyzer — プロトタイプ")

root = st.text_input("Workspace path", value=".")

use_mock = st.checkbox("Use Mock LLM (no external API)", value=True)

if st.button("Run Analysis"):
    client = MockLLMClient() if use_mock else None
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
