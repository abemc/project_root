import ast
from typing import Dict, List


def _extract_from_python(source: str) -> Dict:
    tree = ast.parse(source)
    funcs: List[str] = []
    classes: List[str] = []
    imports: List[str] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            funcs.append(node.name)
        elif isinstance(node, ast.AsyncFunctionDef):
            funcs.append(node.name)
        elif isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, ast.Import):
            for n in node.names:
                imports.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for n in node.names:
                imports.append(f"{module}.{n.name}" if module else n.name)

    # get module docstring (top-level)
    doc = ast.get_docstring(tree)

    return {
        "functions": funcs,
        "classes": classes,
        "imports": imports,
        "docstring": doc,
    }


def extract(path: str) -> Dict:
    """Extract metadata from a file. Currently supports Python files.

    Returns a dict with keys depending on file type.
    """
    if path.endswith(".py"):
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            src = f.read()
        return _extract_from_python(src)
    # fallback: return minimal metadata
    return {"note": "unsupported file type"}


if __name__ == "__main__":
    import sys, json
    res = extract(sys.argv[1])
    print(json.dumps(res, indent=2, ensure_ascii=False))
