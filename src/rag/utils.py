import re
import json
from pathlib import Path

def find_prompt_file():
    """prompt.txt をプロジェクトルートから順に探索する"""
    current = Path(__file__).resolve().parent
    
    # 優先順位:
    # 1. プロジェクトルート (src/rag/ などの階層から2階層上)
    project_root_prompt = current.parents[2] / "prompt.txt"
    if project_root_prompt.exists():
        return project_root_prompt
    
    # 2. src/rag ディレクトリ内
    rag_dir_prompt = current / "prompt.txt"
    if rag_dir_prompt.exists():
        return rag_dir_prompt
    
    # 3. カレントワーキングディレクトリ
    if (Path.cwd() / "prompt.txt").exists():
        return Path.cwd() / "prompt.txt"
    
    return None

def safe_json_loads(text):
    """LLMの出力テキストからJSONオブジェクトを安全に抽出・パースする"""
    if not text:
        return None
    cleaned = text.strip()
    cleaned = re.sub(r"```(?:json)?", "", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("```", "")
    json_match = re.search(r"(\{.*\})", cleaned, re.DOTALL | re.MULTILINE)
    if json_match:
        cleaned = json_match.group(1)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None

def clean_markdown(text):
    """LLMの回答から不要な記号を除去し、数式を整形する"""
    if not text or not isinstance(text, str):
        return text
    
    basic_norms = {
        '\u200b': '', '\u200c': '', '\u200d': '', '\ufeff': '',
        '　': ' ', ' ': ' ', '⁡': '', '（': '(', '）': ')',
        '＝': '=', '→': r'\to ', '∞': r"\infty", 'Δ': r'\Delta ', '−': '-'
    }
    for old, new in basic_norms.items():
        text = text.replace(old, new)

    # 垂直スタック（1行1文字）の解消
    lines = text.split('\n')
    merged_lines = []
    buffer = ""
    for line in lines:
        s = line.strip()
        if (len(s) == 1 and re.match(r'[a-zA-Z0-9\(\)\+\-\*/=∫∂∇⋅∂ρdf\'′\^_\{\}\[\]\.,\\リ、ム罪コス夕ンx i t 私一]', s)) or \
           s.lower() in ['lim', 'sin', 'cos', 'tan', 'limit', 'int', 'log', 'リム']:
            buffer += s
            if s in ['=', '→']:
                merged_lines.append(buffer)
                buffer = ""
        else:
            if buffer:
                merged_lines.append(buffer)
                buffer = ""
            merged_lines.append(line)
    if buffer: merged_lines.append(buffer)
    text = '\n'.join(merged_lines)

    # 誤翻訳・誤認識の修正
    math_corrections = {
        'リム': 'lim', 'l私m': 'lim', '罪': 'sin', 'コス': 'cos', 'タン': 'tan', 'へ': r' \to ',
        '私nt': 'int', '1nt': 'int', '∫': r'\int ',
        '⋅': r' \cdot ', '∇': r' \nabla ', 'Δ': r' \Delta ',
        'fr1c': 'frac', 'Delt1x': 'Delta x', 'Delt1': 'Delta', 'Deltax': 'Delta x',
        'De lt a': 'Delta', 't o': 'to', '1 b': 'a b', 'F（1）': 'F(a)',
        'デルタx': r'\Delta x',
        '微に関する分': '微分', '表にします': '表します', '積分はを': '積分は',
        'に関する分': '微分', '終わらない式': '記述する式', '速度制御': '速度ベクトル',
        'らプラシアン': 'ナブラ', '圧力階段瞬間': '圧力勾配', '自己対流': '対流項',
        '守るためには': '記述するためには', '不可圧流体': '非圧縮性流体',
        '階段瞬間': '勾配', 'の微に関する分': 'の微分', '流体の速度制御': '流体の速度ベクトル',
        '微分を終わらない式': '運動方程式', '描写します': '記述します',
        '自己対流項目': '対流項', '漸進の': '勾配や', '階段瞬間重力': '圧力勾配や重力',
        '方程': '方程式', '导数': '導関数', '偏导': '偏微分', '梯度': '勾配',
        '散度': '発散', '旋度': '回転', '矢量': 'ベクトル', '标量': 'スカラー',
        '质量': '質量', '能量': 'エネルギー', '守恒': '保存',
        '終わらない式のことを言います': '記述する方程式のことです',
        '完全に守るためには': '完全に記述するためには'
    }
    for old, new in math_corrections.items():
        text = text.replace(old, new)

    # 重複の除去
    text = re.sub(r'\b([a-zA-Z0-9])\s+\1\b', r'\1', text)
    text = re.sub(r'([a-zA-Z])私', r'\1_i', text)
    text = re.sub(r'(\$.*?\$)\s*\1', r'\1', text)
    text = re.sub(r'(\b\w+\b)(?:\s+\1)+', r'\1', text)

    # LaTeX 化
    text = re.sub(r'\bint\b', r'\\int ', text, flags=re.IGNORECASE)
    text = re.sub(r'∂\s*([a-zA-Z])\s*/*\s*∂\s*([a-zA-Z])', r'\\frac{\\partial \1}{\\partial \2}', text)
    text = re.sub(r'∂\s*/\s*∂\s*([a-zA-Z])', r'\\frac{\\partial}{\\partial \1}', text)
    text = text.replace('∂', r'\partial ').replace('ρ', r'\rho ')
    text = re.sub(r'd\s*/\s*d([a-zA-Z])', r'\\frac{d}{d\1}', text)
    text = re.sub(r'\bd\s*d\s*([a-zA-Z])\b', r'\\frac{d}{d\1}', text)
    text = re.sub(r'\\int\s+([0-9a-zA-Z\\]+)\s+([0-9a-zA-Z\\]+)', r'\\int_{\1}^{\2}', text)
    text = re.sub(r'∑\s*([0-9a-zA-Z=]+)\s+([0-9a-zA-Z\\]+)', r'\\sum_{\1}^{\2}', text)
    text = re.sub(r'lim\s*([^\s\$]+)\s*\\to\s*([^\s\$]+)', r'\\lim_{\1 \\to \2} ', text)
    text = re.sub(r'\blim\b', r'\\lim ', text)

    # ブロック形式
    text = re.sub(r'\\{1,2}\[\s*(.*?)\s*\\{1,2}\]', r'\n\n$$\1$$\n\n', text, flags=re.DOTALL)
    text = re.sub(r'\\{1,2}\(\s*(.*?)\s*\\{1,2}\)', r' $\1$ ', text, flags=re.DOTALL)

    # 数式行の自動検出
    lines = text.split('\n')
    wrapped = []
    for line in lines:
        s = line.strip()
        if re.search(r'(\\int|\\lim|\\frac|\\partial|\\nabla|\\Delta|d/d[a-z]|f\')', s) and '$' not in s:
            wrapped.append(f"$${s}$$")
        else:
            wrapped.append(line)
    text = '\n'.join(wrapped)
    text = re.sub(r'^([ \t]*[-*+])([^\s])', r'\1 \2', text, flags=re.MULTILINE)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text

def format_tools_for_prompt(tools_dict):
    """ツール定義をプロンプト用の文字列にフォーマットする"""
    tool_descriptions = [f'- "{name}": {description}' for name, description in tools_dict.items()]
    tool_names = " または ".join([f'"{name}"' for name in tools_dict.keys()])
    return "\n".join(tool_descriptions), tool_names