import argparse
import json
import logging
from .scanner import scan
from .summarizer import summarize_files
from .llm_client import MockLLMClient

logger = logging.getLogger(__name__)
if not logger.handlers:
    handler = logging.FileHandler('/tmp/cli_run.log')
    handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s %(message)s'))
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)


def run_analyze(root: str = ".", out: str | None = None, llm_client=None):
    if llm_client is None:
        llm_client = MockLLMClient()
    logger.debug('run_analyze start root=%s use_mock=%s', root, isinstance(llm_client, MockLLMClient))
    res = scan(root)
    logger.debug('scan completed total_files=%d', len(res.get('files', [])))
    summary = summarize_files(res.get("files", []), root, llm_client)
    logger.debug('summarize completed summary_len=%d', len(summary) if isinstance(summary, str) else 0)
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
