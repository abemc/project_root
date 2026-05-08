"""
Phase 3: A/B Testing - Comprehensive Test Suite
================================================

Tests for auto A/B testing mechanism:
  - CandidateGenerator: variation generation
  - ExperimentManager: parallel experiment execution
  - StatisticalAnalyzer: t-test, effect size, significance
  - ABTestingEngine: integrated workflow + auto-selection
"""

import unittest
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class TestCandidateGenerator(unittest.TestCase):
    """Test candidate generation"""

    def setUp(self):
        from src.self_improvement.ab_testing import CandidateGenerator

        self.prompt_templates = {
            "system": "You are a helpful assistant.",
            "user": "Answer the question: {question}",
        }
        self.hyperparams = {
            "temperature": 0.8,
            "top_k": 50,
            "max_tokens": 200,
        }
        self.generator = CandidateGenerator(self.prompt_templates, self.hyperparams)

    def test_generate_prompt_variations(self):
        """Test prompt template variation generation"""
        logger.info("TEST: Prompt variations generation")
        variations = self.generator.generate_prompt_variations(count=3)

        # Assertions
        self.assertEqual(len(variations), 3)
        for var in variations:
            self.assertIsNotNone(var.candidate_id)
            self.assertEqual(var.variation_type, "prompt")
            self.assertIsNotNone(var.prompt_template)
            logger.info(f"  ✓ Generated: {var.candidate_id} - {var.description}")

        self.assertTrue(all(v.prompt_template != self.prompt_templates for v in variations))
        logger.info("✅ PASS: Prompt variations generated correctly\n")

    def test_generate_hyperparameter_variations(self):
        """Test hyperparameter variation generation"""
        logger.info("TEST: Hyperparameter variations generation")
        variations = self.generator.generate_hyperparameter_variations(count=3)

        # Assertions
        self.assertEqual(len(variations), 3)
        for var in variations:
            self.assertIsNotNone(var.candidate_id)
            self.assertEqual(var.variation_type, "hyperparameter")
            self.assertIsNotNone(var.hyperparameters)
            logger.info(f"  ✓ Generated: {var.candidate_id} - {var.description}")

        # Verify hyperparameters differ
        self.assertTrue(all(v.hyperparameters != self.hyperparams for v in variations))
        logger.info("✅ PASS: Hyperparameter variations generated correctly\n")

    def test_generate_combined_variations(self):
        """Test combined prompt + hyperparameter variations"""
        logger.info("TEST: Combined variations generation")
        variations = self.generator.generate_combined_variations(count=2)

        # Assertions
        self.assertEqual(len(variations), 2)
        for var in variations:
            self.assertIsNotNone(var.candidate_id)
            self.assertEqual(var.variation_type, "combined")
            self.assertIsNotNone(var.prompt_template)
            self.assertIsNotNone(var.hyperparameters)
            logger.info(f"  ✓ Generated: {var.candidate_id}")

        logger.info("✅ PASS: Combined variations generated correctly\n")


class TestExperimentManager(unittest.TestCase):
    """Test parallel experiment execution"""

    def setUp(self):
        from src.self_improvement.ab_testing import (
            CandidateVariation, ExperimentManager, ExperimentResult
        )
        self.CandidateVariation = CandidateVariation
        self.ExperimentManager = ExperimentManager
        self.ExperimentResult = ExperimentResult
        self.manager = ExperimentManager(max_workers=2)

    def test_parallel_experiments(self):
        """Test parallel experiment execution"""
        logger.info("TEST: Parallel experiment execution")

        # Create candidates
        candidates = [
            self.CandidateVariation(
                candidate_id=f"cand_{i}",
                variation_type="hyperparameter",
                description=f"Variant {i}",
                hyperparameters={"temperature": 0.5 + i * 0.2},
            )
            for i in range(3)
        ]

        # Mock inference function
        def mock_inference(text, prompt_template=None, hyperparameters=None):
            import random
            return f"Response: {text[:20]}...", random.uniform(50, 150)

        # Run parallel experiments
        results = self.manager.run_parallel_experiments(
            candidates=candidates,
            test_input="test query",
            inference_fn=mock_inference,
            samples_per_candidate=5,
        )

        # Assertions
        self.assertEqual(len(results), 3)
        for candidate_id, exp_results in results.items():
            self.assertGreater(len(exp_results), 0)
            logger.info(f"  ✓ {candidate_id}: {len(exp_results)} results")

        logger.info("✅ PASS: Parallel experiments completed\n")


class TestStatisticalAnalyzer(unittest.TestCase):
    """Test statistical analysis"""

    def setUp(self):
        from src.self_improvement.ab_testing import StatisticalAnalyzer, ExperimentResult
        self.analyzer = StatisticalAnalyzer(significance_level=0.01)
        self.ExperimentResult = ExperimentResult

    def test_candidate_analysis(self):
        """Test candidate analysis (mean, std dev, etc)"""
        logger.info("TEST: Candidate analysis")

        # Create experiment results
        results = [
            self.ExperimentResult(
                experiment_id=f"exp_{i}",
                candidate_id="cand_1",
                sample_num=i,
                rating=0.7 + (i % 3) * 0.1,
                response_time_ms=100 + i * 5,
                error_occurred=False,
            )
            for i in range(10)
        ]

        analysis = self.analyzer.analyze_candidate(results)

        # Assertions
        self.assertEqual(analysis.candidate_id, "cand_1")
        self.assertGreater(analysis.mean_rating, 0.0)
        self.assertGreater(analysis.std_dev, 0.0)
        self.assertEqual(analysis.sample_count, 10)
        logger.info(f"  ✓ Mean: {analysis.mean_rating:.3f}")
        logger.info(f"  ✓ StdDev: {analysis.std_dev:.3f}")
        logger.info(f"  ✓ Error rate: {analysis.error_rate:.1%}")

        logger.info("✅ PASS: Candidate analysis completed\n")

    def test_candidate_comparison_significant(self):
        """Test comparison with significant improvement"""
        logger.info("TEST: Candidate comparison (significant)")

        # Baseline results (lower ratings)
        baseline_results = [
            self.ExperimentResult(
                experiment_id=f"baseline_{i}",
                candidate_id="baseline",
                sample_num=i,
                rating=0.5 + (i % 3) * 0.05,
                response_time_ms=100,
                error_occurred=False,
            )
            for i in range(30)
        ]

        # Candidate results (higher ratings - significant improvement)
        candidate_results = [
            self.ExperimentResult(
                experiment_id=f"cand_{i}",
                candidate_id="cand_test",
                sample_num=i,
                rating=0.8 + (i % 3) * 0.05,
                response_time_ms=100,
                error_occurred=False,
            )
            for i in range(30)
        ]

        baseline_analysis = self.analyzer.analyze_candidate(baseline_results)
        candidate_analysis = self.analyzer.analyze_candidate(candidate_results)

        # Compare
        comparison = self.analyzer.compare_candidates(baseline_analysis, candidate_analysis)

        # Assertions
        self.assertEqual(comparison.candidate_id, "cand_test")
        logger.info(f"  ✓ t-statistic: {comparison.t_statistic:.3f}")
        logger.info(f"  ✓ p-value: {comparison.p_value:.4f}")
        logger.info(f"  ✓ Cohen's d: {comparison.cohens_d:.3f}")
        logger.info(f"  ✓ Improvement: {comparison.improvement_direction}")
        logger.info(f"  ✓ Recommendation: {comparison.recommendation}")

        # Should show improvement
        self.assertEqual(comparison.improvement_direction, "better")
        self.assertGreater(abs(comparison.cohens_d), 0.2)  # At least some effect size

        logger.info("✅ PASS: Significant improvement detected\n")

    def test_candidate_comparison_no_improvement(self):
        """Test comparison with no significant difference"""
        logger.info("TEST: Candidate comparison (no improvement)")

        # Similar ratings for baseline and candidate
        baseline_results = [
            self.ExperimentResult(
                experiment_id=f"baseline_{i}",
                candidate_id="baseline",
                sample_num=i,
                rating=0.7 + (i % 3) * 0.05,
                response_time_ms=100,
                error_occurred=False,
            )
            for i in range(30)
        ]

        candidate_results = [
            self.ExperimentResult(
                experiment_id=f"cand_{i}",
                candidate_id="cand_test",
                sample_num=i,
                rating=0.7 + ((i + 1) % 3) * 0.05,
                response_time_ms=100,
                error_occurred=False,
            )
            for i in range(30)
        ]

        baseline_analysis = self.analyzer.analyze_candidate(baseline_results)
        candidate_analysis = self.analyzer.analyze_candidate(candidate_results)

        comparison = self.analyzer.compare_candidates(baseline_analysis, candidate_analysis)

        # No significant improvement expected
        logger.info(f"  ✓ Improvement direction: {comparison.improvement_direction}")
        logger.info(f"  ✓ Recommendation: {comparison.recommendation}")

        self.assertNotEqual(comparison.recommendation, "ADOPT")
        logger.info("✅ PASS: No improvement case handled\n")


class TestABTestingEngine(unittest.TestCase):
    """Test integrated A/B testing"""

    def setUp(self):
        from src.self_improvement.ab_testing import ABTestingEngine
        self.engine = ABTestingEngine(max_workers=3)

    def test_ab_testing_workflow(self):
        """Test full A/B testing workflow"""
        logger.info("TEST: Full A/B testing workflow")

        # Initialize engine
        prompts = {"system": "You are helpful.", "user": "Q: {q}"}
        hyperparams = {"temperature": 0.8, "top_k": 50}
        self.engine.initialize(prompts, hyperparams)
        logger.info("  ✓ Engine initialized")

        # Create baseline results
        from src.self_improvement.ab_testing import ExperimentResult
        baseline_results = [
            ExperimentResult(
                experiment_id=f"baseline_{i}",
                candidate_id="baseline",
                sample_num=i,
                rating=0.6 + (i % 4) * 0.08,
                response_time_ms=100,
                error_occurred=False,
            )
            for i in range(30)
        ]
        logger.info("  ✓ Baseline established (30 samples)")

        # Mock inference
        def mock_inference(text, prompt_template=None, hyperparameters=None):
            import random
            return f"Response: {text[:20]}...", random.uniform(80, 120)

        # Run A/B test
        test_report = self.engine.run_ab_test(
            test_input="test query",
            inference_fn=mock_inference,
            baseline_results=baseline_results,
            num_candidates=5,
            samples_per_candidate=20,  # Reduced for test speed
        )

        # Assertions
        self.assertIn("test_id", test_report)
        self.assertIn("best_candidate_id", test_report)
        self.assertIn("comparisons", test_report)
        self.assertGreater(len(test_report["comparisons"]), 0)

        logger.info(f"  ✓ Candidates evaluated: {test_report.get('num_candidates')}")
        logger.info(f"  ✓ Best candidate: {test_report.get('best_candidate_id')}")
        logger.info(f"  ✓ Recommendation: {test_report.get('best_recommendation')}")

        # Show top 2 candidates by Cohen's d
        sorted_comps = sorted(
            test_report.get("comparisons", []),
            key=lambda x: abs(x.get("cohens_d", 0)),
            reverse=True
        )
        for i, comp in enumerate(sorted_comps[:2]):
            logger.info(
                f"  {'✨' if comp.get('recommendation') == 'ADOPT' else '  '} "
                f"Top {i+1}: {comp.get('candidate_id')} - "
                f"d={comp.get('cohens_d'):.3f}, rec={comp.get('recommendation')}"
            )

        logger.info("✅ PASS: A/B testing workflow completed\n")

    def test_test_history(self):
        """Test history tracking"""
        logger.info("TEST: Test history tracking")

        # Initialize and run test
        prompts = {"system": "Helper", "user": "Q: {q}"}
        hyperparams = {"temperature": 0.8}
        self.engine.initialize(prompts, hyperparams)

        from src.self_improvement.ab_testing import ExperimentResult
        baseline = [
            ExperimentResult(
                experiment_id=f"base_{i}",
                candidate_id="baseline",
                sample_num=i,
                rating=0.7,
                response_time_ms=100,
                error_occurred=False,
            )
            for i in range(10)
        ]

        def mock_infer(text, **kwargs):
            return "Response", 100

        self.engine.run_ab_test(
            test_input="test",
            inference_fn=mock_infer,
            baseline_results=baseline,
            num_candidates=2,
            samples_per_candidate=10,
        )

        history = self.engine.get_test_history()
        self.assertGreater(len(history), 0)
        logger.info(f"  ✓ Test history entries: {len(history)}")
        logger.info("✅ PASS: History tracking works\n")


class Phase3IntegrationTest(unittest.TestCase):
    """Integration tests with scheduler"""

    def test_ab_testing_in_automation_engine(self):
        """Test A/B testing integrated into AutomationEngine"""
        logger.info("TEST: Integration with AutomationEngine")

        from src.self_improvement.ab_testing import ABTestingEngine
        from src.self_improvement.scheduler import create_automation_engine

        # Create engine with A/B testing
        ab_engine = ABTestingEngine()
        ab_engine.initialize({"system": "Helper"}, {"temperature": 0.8})

        engine = create_automation_engine(
            ab_testing_engine=ab_engine,
        )

        # Verify integration
        self.assertIsNotNone(engine.ab_testing_engine)
        logger.info("  ✓ A/B testing engine integrated")

        # Verify status includes all components
        status = engine.get_status()
        self.assertIn("scheduled_jobs", status)
        logger.info(f"  ✓ Status available: {status}")

        logger.info("✅ PASS: Integration with AutomationEngine works\n")


def run_test_suite():
    """Run all Phase 3 tests"""
    logger.info("=" * 80)
    logger.info("PHASE 3: AUTO A/B TESTING - TEST SUITE")
    logger.info("=" * 80 + "\n")

    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test suites
    suite.addTests(loader.loadTestsFromTestCase(TestCandidateGenerator))
    suite.addTests(loader.loadTestsFromTestCase(TestExperimentManager))
    suite.addTests(loader.loadTestsFromTestCase(TestStatisticalAnalyzer))
    suite.addTests(loader.loadTestsFromTestCase(TestABTestingEngine))
    suite.addTests(loader.loadTestsFromTestCase(Phase3IntegrationTest))

    # Run with detailed output
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("PHASE 3 TEST SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Tests run: {result.testsRun}")
    logger.info(f"Passed: {result.testsRun - len(result.failures) - len(result.errors)}")
    logger.info(f"Failed: {len(result.failures)}")
    logger.info(f"Errors: {len(result.errors)}")

    if result.wasSuccessful():
        logger.info("\n✅ ALL PHASE 3 TESTS PASSED!")
    else:
        logger.info("\n❌ SOME TESTS FAILED")

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_test_suite()
    exit(0 if success else 1)
