from src.evaluation.dataset_sanity_checker import DatasetSanityChecker


def test_missing_required_keys():
    data = [
        {"query": "Q1", "expected_answer": "A1"},
        {"query": "Q2"},
        {"expected_answer": "A3"},
    ]
    checker = DatasetSanityChecker(data=data)
    report = checker.run_checks()
    assert report["summary"]["missing_required_keys"] == 2


def test_empty_values_and_type_mismatch():
    data = [
        {"query": "Q1", "expected_answer": "A1"},
        {"query": "Q2", "expected_answer": ""},
        {"query": "Q3", "expected_answer": None},
        {"query": "Q4", "expected_answer": ["list_instead_of_str"]},
    ]
    checker = DatasetSanityChecker(data=data)
    report = checker.run_checks()
    assert report["summary"]["empty_values"] >= 2
    assert report["summary"]["type_mismatches"] >= 1


def test_duplicate_queries():
    data = [
        {"query": "same", "expected_answer": "A1"},
        {"query": "same", "expected_answer": "A2"},
        {"query": "unique", "expected_answer": "A3"},
    ]
    checker = DatasetSanityChecker(data=data)
    report = checker.run_checks()
    assert report["summary"]["duplicates"] == 1


def test_length_ratio_issue():
    long_text = "x" * 5000
    short_text = "y"
    data = [
        {"query": long_text, "expected_answer": short_text},
        {"query": "normal", "expected_answer": "also normal"},
    ]
    checker = DatasetSanityChecker(data=data)
    report = checker.run_checks()
    assert report["summary"]["length_ratio_issues"] >= 1


def test_save_report(tmp_path):
    data = [{"query": "q", "expected_answer": "a"}]
    checker = DatasetSanityChecker(data=data)
    out = tmp_path / "report.json"
    checker.save_report(str(out))
    assert out.exists()


def test_dict_format_and_fallback(tmp_path):
    import json
    # Dict format evaluation file containing 'samples'
    eval_data = {
        "model_name": "test-model",
        "samples": [
            {"query": "What is A?", "ground_truth": "A is A"},
            {"query": "What is B?", "ground_truth": ""},
        ]
    }
    
    file_path = tmp_path / "eval_data.json"
    file_path.write_text(json.dumps(eval_data), encoding="utf-8")
    
    # Check that initialization automatically unpacks 'samples'
    checker = DatasetSanityChecker(file_path=str(file_path))
    assert len(checker.data) == 2
    assert checker.required_keys == ["query", "ground_truth"] # auto-fallback from expected_answer to ground_truth
    
    report = checker.run_checks()
    assert report["summary"]["empty_values"] == 1 # ground_truth is empty for second record

