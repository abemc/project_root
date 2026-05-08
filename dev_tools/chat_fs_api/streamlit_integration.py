import streamlit as st
import requests
import difflib
from typing import List

API_BASE = "http://127.0.0.1:8001/api"


def list_dir(path: str) -> List[dict]:
    r = requests.get(f"{API_BASE}/list", params={"path": path})
    r.raise_for_status()
    return r.json()["entries"]


def read_file(path: str) -> str:
    r = requests.get(f"{API_BASE}/read", params={"path": path})
    r.raise_for_status()
    return r.json()["text"]


def check_patch(patch: str) -> dict:
    r = requests.post(f"{API_BASE}/patch/check", json={"patch": patch})
    r.raise_for_status()
    return r.json()


def apply_patch(patch: str, branch: str | None = None) -> dict:
    payload = {"patch": patch}
    if branch:
        payload["branch"] = branch
    r = requests.post(f"{API_BASE}/patch/apply", json=payload)
    r.raise_for_status()
    return r.json()


def make_unified_diff(path: str, old: str, new: str) -> str:
    old_lines = old.splitlines(keepends=True)
    new_lines = new.splitlines(keepends=True)
    diff = difflib.unified_diff(old_lines, new_lines, fromfile=path, tofile=path)
    return "".join(diff)


def run():
    st.set_page_config(page_title="Chat FS Explorer", layout="wide")
    st.title("Chat: ファイルブラウザ & エディタ")

    with st.sidebar:
        st.header("ブラウズ")
        base = st.text_input("パス", value=".")
        if st.button("一覧表示"):
            st.session_state["entries"] = list_dir(base)

        entries = st.session_state.get("entries", [])
        for e in entries:
            label = f"[DIR] {e['name']}" if e["is_dir"] else e["name"]
            if st.button(label, key=e["path"]):
                st.session_state["selected"] = e["path"]

    sel = st.session_state.get("selected")
    if sel:
        st.subheader(f"編集: {sel}")
        try:
            text = read_file(sel)
        except Exception as ex:
            st.error(f"読み込み失敗: {ex}")
            return

        edited = st.text_area("ファイル内容", value=text, height=600)

        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("差分作成"):
                patch = make_unified_diff(sel, text, edited)
                st.session_state["patch"] = patch
                st.session_state["patch_preview"] = patch
        with col2:
            if st.button("パッチ検証"):
                patch = st.session_state.get("patch")
                if not patch:
                    st.warning("先に差分を作成してください")
                else:
                    try:
                        res = check_patch(patch)
                        st.json(res)
                    except Exception as ex:
                        st.error(f"検証失敗: {ex}")
        with col3:
            if st.button("パッチ適用 (新ブランチ)"):
                patch = st.session_state.get("patch")
                if not patch:
                    st.warning("先に差分を作成してください")
                else:
                    branch = st.text_input("新ブランチ名（空で自動生成）", value="")
                    try:
                        res = apply_patch(patch, branch or None)
                        st.success(f"パッチ適用完了: {res}")
                    except Exception as ex:
                        st.error(f"適用失敗: {ex}")

        if st.session_state.get("patch_preview"):
            st.subheader("パッチプレビュー")
            st.code(st.session_state.get("patch_preview"), language="diff")


if __name__ == "__main__":
    run()
