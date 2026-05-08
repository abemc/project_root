import argparse
import json
from .scanner import scan
from .summarizer import summarize_files
from .llm_client import MockLLMClient


def run_analyze(root: str = ".", out: str | None = None, llm_client=None):
    if llm_client is None:
        llm_client = MockLLMClient()

    res = scan(root)
    summary = summarize_files(res.get("files", []), root, llm_client)
    res["analysis_summary"] = summary

    out_json = json.dumps(res, ensure_ascii=False, indent=2)
    if out:
        with open(out, "w", encoding="utf-8") as f:
            f.write(out_json)
    else:
        print(out_json)
    return res


def main():
    p = argparse.ArgumentParser(description="Analyze a project workspace")
    p.add_argument("--path", "-p", default=".", help="Path to workspace")
    p.add_argument("--out", "-o", default=None, help="Output JSON file (optional)")
    args = p.parse_args()
    run_analyze(args.path, args.out)


if __name__ == "__main__":
    main()
