import re
import uuid
import html
import streamlit as st
import streamlit.components.v1 as components

_MERMAID_BLOCK_RE = re.compile(r"```mermaid(?:\s*\n|\s+)(.*?)```", re.DOTALL | re.IGNORECASE)

def _has_mermaid_block(text: str) -> bool:
    return bool(text and _MERMAID_BLOCK_RE.search(text))

def _normalize_mermaid_blocks(text: str) -> str:
    """Mermaid フェンスの揺れを正規化する（1行記法や余分空白を吸収）。"""
    s = str(text or "")
    if not s:
        return s

    def _repl(match):
        body = (match.group(1) or "").strip()
        return f"```mermaid\n{body}\n```"

    # ```mermaid graph TD; ... ``` のような1行/崩れた表記を正規化
    s = re.sub(r"```mermaid\s+([\s\S]*?)```", _repl, s, flags=re.IGNORECASE)
    return s

def _fallback_mermaid_for_query(query: str) -> str:
    q = (query or "質問").strip().replace("\n", " ")[:60]
    escaped_q = q.replace("\"", "'")
    if re.search(r"構造|仕組み|流れ|関係|説明|解説", q, re.IGNORECASE):
        step2 = "要素を分解"
        step3 = "関係を整理"
        step4 = "全体の流れ"
    else:
        step2 = "要点を整理"
        step3 = "根拠を確認"
        step4 = "結論"
    return (
        "\n\n```mermaid\n"
        "flowchart TD\n"
        f"    A[質問: {escaped_q}] --> B[{step2}]\n"
        f"    B --> C[{step3}]\n"
        f"    C --> D[{step4}]\n"
        "    D --> E[結論]\n"
        "```\n"
    )

def _render_markdown_with_mermaid(markdown_text: str) -> None:
    """Markdown 内の Mermaid ブロックを図として描画し、それ以外は通常表示する。"""
    if not markdown_text:
        return

    parts = []
    last_end = 0
    for m in _MERMAID_BLOCK_RE.finditer(markdown_text):
        if m.start() > last_end:
            parts.append(("md", markdown_text[last_end:m.start()]))
        parts.append(("mermaid", m.group(1).strip()))
        last_end = m.end()
    if last_end < len(markdown_text):
        parts.append(("md", markdown_text[last_end:]))

    # Mermaid ブロックが無ければ従来表示
    if not any(kind == "mermaid" for kind, _ in parts):
        st.markdown(markdown_text, unsafe_allow_html=True)
        return

    for kind, chunk in parts:
        if kind == "md":
            if chunk and chunk.strip():
                st.markdown(chunk, unsafe_allow_html=True)
            continue

        if not chunk:
            continue

        block_id = f"mermaid-{uuid.uuid4().hex}"
        escaped_code = html.escape(chunk)
        est_height = max(260, min(1200, 180 + (chunk.count("\n") + 1) * 26))
        mermaid_html = f"""
<style>
    body {{ margin: 0; background: transparent; }}
    .mermaid-wrap {{
        overflow-x: auto;
        border: 1px solid #e2e8f0;
        border-radius: 10px;
        background: linear-gradient(180deg, #f8fafc 0%, #ffffff 100%);
        padding: 10px 12px;
    }}
    .mermaid svg {{ max-width: 100%; height: auto; }}
</style>
<div class="mermaid-wrap"> 
    <pre class="mermaid" id="{block_id}">{escaped_code}</pre>
</div>
<script type="module"> 
    import mermaid from 'https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.esm.min.mjs';
        mermaid.initialize({{
            startOnLoad: false,
            securityLevel: 'loose',
            theme: 'neutral',
            fontFamily: '"Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif',
            flowchart: {{ useMaxWidth: true, htmlLabels: false, curve: 'linear' }},
            themeVariables: {{
                primaryColor: '#e8f0ff',
                primaryBorderColor: '#5b7fd1',
                lineColor: '#5b7fd1',
                textColor: '#0f172a',
                fontSize: '14px'
            }}
        }});
    const el = document.getElementById('{block_id}');
    if (el) {{
            try {{
                const src = (el.textContent || '').strip();
                // まずパース検証し、文法エラー時は Mermaid エラーカードを出さずにコード表示へフォールバック
                await mermaid.parse(src);
                const renderId = '{block_id}-svg';
                const r = await mermaid.render(renderId, src);
                const host = document.createElement('div');
                host.innerHTML = r.svg;
                el.replaceWith(host);
            }} catch (e) {{
                console.error('Mermaid render/parse error:', e);
                const fallback = document.createElement('pre');
                fallback.style.margin = '0';
                fallback.style.padding = '8px';
                fallback.style.whiteSpace = 'pre-wrap';
                fallback.style.wordBreak = 'break-word';
                fallback.textContent = (el.textContent || '').strip();
                el.replaceWith(fallback);
            }}
    }}
</script>
"""
        components.html(mermaid_html, height=est_height, scrolling=True)

def _render_mermaid_blocks_only(markdown_text: str) -> bool:
    """Markdown から Mermaid ブロックのみ抽出して描画する。描画したら True を返す。"""
    if not markdown_text:
        return False
    found = False
    for m in _MERMAID_BLOCK_RE.finditer(markdown_text):
        code = (m.group(1) or "").strip()
        if not code:
            continue
        found = True
        _render_markdown_with_mermaid(f"```mermaid\n{code}\n```")
    return found

def _safe_render_mermaid_blocks(markdown_text: str) -> None:
    """Mermaid 図の描画を安全に行い、失敗時はコード表示へフォールバックする。"""
    try:
        rendered = _render_mermaid_blocks_only(markdown_text)
        if not rendered:
            return
    except Exception as e:
        # st.session_state を利用するロギングを呼び出せるよう、またはコンソールに出力
        logger = st.session_state.get("logger")
        if logger:
            logger.warning(f"mermaid_render_error: {e}")
        st.info("図の再表示で問題が発生したため、図コードを表示します。")
        # フォールバック: Mermaid コードをそのまま表示
        for m in _MERMAID_BLOCK_RE.finditer(markdown_text or ""):
            code = (m.group(1) or "").strip()
            if code:
                st.code(code, language="mermaid")

def _render_safe_flow_diagram(title: str, steps: list[str]) -> None:
    """Streamlit/preview で安定して表示できる純HTMLの図解を描画する。"""
    safe_steps = [str(step).strip() for step in steps if str(step).strip()]
    if not safe_steps:
        safe_steps = ["要点を整理", "根拠を確認", "結論をまとめる"]

    boxes = []
    for idx, step in enumerate(safe_steps, start=1):
        boxes.append(
            '<div class="diag-node">'
            f'<span class="diag-badge">{idx}</span>'
            f'<span class="diag-text">{html.escape(step)}</span>'
            '</div>'
        )
        if idx < len(safe_steps):
            boxes.append('<div class="diag-arrow" aria-hidden="true">→</div>')

    est_height = 180 if len(safe_steps) <= 4 else 230
    html_body = f"""
<style>
    .diag-wrap {{
        margin: 10px 0 6px 0;
        padding: 14px 16px;
        border: 1px solid #cfd8e6;
        border-radius: 14px;
        background:
            radial-gradient(circle at 8% 14%, #fff7e6 0 18%, transparent 20%),
            radial-gradient(circle at 92% 80%, #e8f4ff 0 20%, transparent 22%),
            linear-gradient(180deg, #f7fbff 0%, #ffffff 100%);
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.06);
    }}
    .diag-title {{
        font-weight: 700;
        color: #102a43;
        margin-bottom: 10px;
        font-size: 0.98rem;
        letter-spacing: 0.02em;
    }}
    .diag-flow {{
        display: flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 10px;
        color: #102a43;
        font-family: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", sans-serif;
    }}
    .diag-node {{
        display: inline-flex;
        align-items: center;
        gap: 9px;
        min-height: 46px;
        padding: 8px 12px;
        border: 1px solid #7b9bd6;
        border-radius: 999px;
        background: #edf4ff;
        color: #1f3a67;
        font-weight: 600;
        line-height: 1.35;
        box-sizing: border-box;
        max-width: 100%;
    }}
    .diag-badge {{
        width: 22px;
        height: 22px;
        border-radius: 999px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        background: #2f5fb7;
        color: #ffffff;
        font-size: 0.78rem;
        font-weight: 700;
        flex: 0 0 22px;
    }}
    .diag-text {{
        word-break: break-word;
    }}
    .diag-arrow {{
        font-size: 1.1rem;
        font-weight: 700;
        color: #6c7d93;
        padding: 0 2px;
    }}
    @media (max-width: 640px) {{
        .diag-flow {{
            align-items: stretch;
        }}
        .diag-arrow {{
            width: 100%;
            text-align: center;
            transform: rotate(90deg);
            padding: 0;
            margin: -3px 0;
        }}
        .diag-node {{
            width: 100%;
            border-radius: 12px;
        }}
    }}
</style>
<div class="diag-wrap">
    <div class="diag-title">{html.escape(title)}</div>
    <div class="diag-flow">
        {''.join(boxes)}
    </div>
</div>
"""
    components.html(html_body, height=est_height, scrolling=False)
