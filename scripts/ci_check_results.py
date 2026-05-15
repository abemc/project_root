import json
from pathlib import Path
import sys
import argparse


# Enhanced CI checker
def load_json(path: Path):
    try:
        return json.load(path.open('r', encoding='utf-8'))
    except Exception as e:
        print('Failed to load', path, e)
        return None


def check_deleted_doc(results):
    p = results.get('faiss_after_delete') or {}
    ids = []
    try:
        ids = p.get('ids', [[]])[0]
    except Exception:
        ids = []
    if 'doc2' in ids:
        print('Failure: deleted doc2 still returned by FAISS:', ids)
        return False
    return True


def check_search_quality(threshold: float = 0.3):
    p = Path('results/search_quality_metrics.json')
    if not p.exists():
        print('search quality metrics missing:', p)
        return False
    data = load_json(p)
    if data is None:
        return False
    # Example: expect key 'avg_overlap' in metrics
    avg_overlap = data.get('avg_overlap')
    if avg_overlap is None:
        print('avg_overlap missing in metrics')
        return False
    if avg_overlap < threshold:
        print(f'Failure: avg_overlap {avg_overlap:.3f} below threshold {threshold:.3f}')
        return False
    print(f'avg_overlap {avg_overlap:.3f} >= threshold {threshold:.3f}')
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--smoke-file', default='results/ci_smoke_after.json')
    ap.add_argument('--overlap-threshold', type=float, default=0.3)
    args = ap.parse_args()

    smoke = Path(args.smoke_file)
    if not smoke.exists():
        print('Missing results file:', smoke)
        sys.exit(2)

    smoke_data = load_json(smoke)
    if smoke_data is None:
        sys.exit(2)

    ok1 = check_deleted_doc(smoke_data)
    ok2 = check_search_quality(args.overlap_threshold)

    if ok1 and ok2:
        print('CI check passed')
        sys.exit(0)
    else:
        print('CI check failed')
        sys.exit(1)


if __name__ == '__main__':
    main()
