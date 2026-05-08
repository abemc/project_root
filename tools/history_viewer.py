# tools/history_viewer.py

import json
from pathlib import Path

HTML_TEMPLATE = """
<html>
<head>
<meta charset="utf-8">
<title>RAG History Viewer</title>
<style>
body { font-family: sans-serif; margin: 20px; }
.step { border-left: 4px solid #888; padding: 10px 20px; margin: 20px 0; }
.plan { border-color: #4CAF50; }
.search { border-color: #2196F3; }
.grade { border-color: #FF9800; }
.rewrite { border-color: #9C27B0; }
.answer { border-color: #F44336; }
pre { background: #f0f0f0; padding: 10px; white-space: pre-wrap; }
</style>
</head>
<body>

<h1>RAG History Viewer</h1>

{content}

</body>
</html>
"""

def render_step(step):
    t = step["type"]

    if t == "plan":
        cls = "plan"
        body = f"<b>Plan → {step['action']}</b><br>理由: {step['reason']}"

    elif t == "search_doc":
        cls = "search"
        body = f"<b>SearchDoc</b><br>クエリ: {step['query']}<br>件数: {step['num_docs']}"

    elif t == "grade":
        cls = "grade"
        body = f"<b>Grade → {step['verdict']}</b>"

    elif t == "rewrite":
        cls = "rewrite"
        body = f"<b>Rewrite</b><br>{step['old']} → {step['new']}"

    elif t == "answer":
        cls = "answer"
        body = f"<b>Answer</b><pre>{step['answer']}</pre>"

    else:
        cls = ""
        body = str(step)

    return f'<div class="step {cls}">{body}</div>'


def build_html(history_path):
    history = json.load(open(history_path, encoding="utf-8"))
    content = "\n".join(render_step(s) for s in history)
    html = HTML_TEMPLATE.replace("{content}", content)

    out_path = history_path.replace(".json", ".html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)

    print("HTML saved to:", out_path)


if __name__ == "__main__":
    import sys
    build_html(sys.argv[1])