from src.evaluation.evaluation_diff_viewer import compute_diff


def test_compute_diff_basic():
    baseline = [
        {"id": "a", "score": 0.9},
        {"id": "b", "score": 0.8},
        {"id": "c", "score": 0.5},
    ]
    current = [
        {"id": "a", "score": 0.92},  # improved
        {"id": "b", "score": 0.6},   # regressed
        {"id": "d", "score": 0.7},   # added
    ]
    report = compute_diff(baseline, current)
    s = report["summary"]
    assert s["total_baseline"] == 3
    assert s["total_current"] == 3
    assert s["added"] == 1
    assert s["removed"] == 1
    assert s["improved"] == 1
    assert s["regressed"] == 1
    assert s["unchanged"] == 0


def test_compute_diff_predicted_expected():
    baseline = [
        {"id": "x", "predicted": "A", "expected": "A"},
        {"id": "y", "predicted": "B", "expected": "C"},
    ]
    current = [
        {"id": "x", "predicted": "A", "expected": "A"},
        {"id": "y", "predicted": "C", "expected": "C"},
    ]
    report = compute_diff(baseline, current)
    s = report["summary"]
    # x unchanged, y improved
    assert s["improved"] == 1
    assert s["unchanged"] == 1


def test_compute_diff_ids_only_added_removed():
    baseline = [{"id": "only_base", "score": 0.5}]
    current = [{"id": "only_current", "score": 0.5}]
    report = compute_diff(baseline, current)
    s = report["summary"]
    assert s["added"] == 1
    assert s["removed"] == 1


def test_report_to_csv_bytes():
    baseline = [{"id": "a", "score": 0.9}, {"id": "b", "score": 0.4}]
    current = [{"id": "a", "score": 0.85}, {"id": "b", "score": 0.6}]
    report = compute_diff(baseline, current)
    from src.evaluation.evaluation_diff_viewer import report_to_csv_bytes
    b = report_to_csv_bytes(report)
    assert isinstance(b, (bytes, bytearray))
    s = b.decode('utf-8')
    assert 'id,type,baseline_score,current_score,delta' in s
    assert 'a' in s and 'b' in s
