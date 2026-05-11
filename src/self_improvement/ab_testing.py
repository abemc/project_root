"""
Phase 3: Auto A/B Testing Mechanism
===================================

Auto-generate multiple improvement candidates, run parallel experiments,
perform statistical analysis, and auto-select best improvement.

Classes:
  - CandidateGenerator: Generate prompt & hyperparameter variations
  - ExperimentRun: Single experiment execution with feedback collection
  - ExperimentManager: Parallel experiment orchestration
  - StatisticalAnalyzer: t-test, effect size, significance testing (99% CI)
  - ABTestingEngine: Integrated A/B testing with auto-selection

Configuration:
  - Experiment samples per candidate: 30 (for t-test power)
  - Significance level (alpha): 0.01 (99% confidence)
  - Min effect size: 0.5 (medium effect, Cohen's d)
  - Parallel experiment limit: 5
"""

import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import math

logger = logging.getLogger(__name__)


@dataclass
class CandidateVariation:
    """Single improvement candidate variation."""
    candidate_id: str
    variation_type: str  # 'prompt', 'hyperparameter', 'combined'
    description: str
    prompt_template: Optional[Dict] = None  # Modified template
    hyperparameters: Optional[Dict] = None  # Modified params (temperature, top_k, etc)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ExperimentResult:
    """Result for single experiment run."""
    experiment_id: str
    candidate_id: str
    sample_num: int
    rating: float  # User feedback rating (0-1)
    response_time_ms: float
    error_occurred: bool
    feedback_text: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CandidateAnalysis:
    """Statistical analysis results for candidate."""
    candidate_id: str
    mean_rating: float
    std_dev: float
    sample_count: int
    avg_response_time_ms: float
    error_rate: float  # Fraction of errors
    min_rating: float
    max_rating: float
    results: List[ExperimentResult] = field(default_factory=list)


@dataclass
class ComparisonResult:
    """Comparison between baseline and candidate."""
    candidate_id: str
    t_statistic: float
    p_value: float
    cohens_d: float  # Effect size
    is_significant: bool  # p < 0.01 (99% CI)
    improvement_direction: str  # 'better', 'worse', 'neutral'
    recommendation: str  # 'ADOPT', 'REJECT', 'INVESTIGATE'
    confidence_level: float  # 99.0 for significant comparisons


class CandidateGenerator:
    """Generate multiple improvement variations."""

    def __init__(self, prompt_templates: Dict, current_hyperparams: Dict):
        """
        Args:
            prompt_templates: Current prompt templates
            current_hyperparams: Current model hyperparameters
        """
        self.prompt_templates = prompt_templates
        self.current_hyperparams = current_hyperparams
        self.variation_counter = 0

    def generate_prompt_variations(self, count: int = 3) -> List[CandidateVariation]:
        """Generate N prompt template variations through parameter tuning."""
        variations = []
        list(self.prompt_templates.keys())

        # Variation strategies
        strategies = [
            self._add_role_emphasis,  # Add explicit role description
            self._enhance_clarity,     # Enhance instruction clarity
            self._add_examples,        # Add in-context examples
        ]

        for i in range(count):
            strategy = strategies[i % len(strategies)]
            varied_template = strategy(self.prompt_templates.copy())

            variation = CandidateVariation(
                candidate_id=f"prompt_v{self.variation_counter}",
                variation_type="prompt",
                description=f"{strategy.__name__} variation",
                prompt_template=varied_template,
            )
            variations.append(variation)
            self.variation_counter += 1

        logger.info(f"Generated {count} prompt variations")
        return variations

    def generate_hyperparameter_variations(self, count: int = 3) -> List[CandidateVariation]:
        """Generate N hyperparameter variations."""
        variations = []

        # Variation patterns (temperature, top_k adjustments)
        patterns = [
            {"temperature": 0.7, "top_k": 40},  # More deterministic
            {"temperature": 0.9, "top_k": 50},  # Balanced
            {"temperature": 1.0, "top_k": 60},  # More creative
        ]

        for i, pattern in enumerate(patterns[:count]):
            varied_params = self.current_hyperparams.copy()
            varied_params.update(pattern)

            variation = CandidateVariation(
                candidate_id=f"hyper_v{self.variation_counter}",
                variation_type="hyperparameter",
                description=f"temperature={pattern['temperature']}, top_k={pattern['top_k']}",
                hyperparameters=varied_params,
            )
            variations.append(variation)
            self.variation_counter += 1

        logger.info(f"Generated {count} hyperparameter variations")
        return variations

    def generate_combined_variations(self, count: int = 2) -> List[CandidateVariation]:
        """Generate combined prompt + hyperparameter variations."""
        variations = []
        prompt_vars = self.generate_prompt_variations(count)
        hyper_vars = self.generate_hyperparameter_variations(count)

        for j in range(count):
            combined = CandidateVariation(
                candidate_id=f"combined_v{self.variation_counter}",
                variation_type="combined",
                description=f"prompt:{prompt_vars[j].description} + hyper:{hyper_vars[j].description}",
                prompt_template=prompt_vars[j].prompt_template,
                hyperparameters=hyper_vars[j].hyperparameters,
            )
            variations.append(combined)
            self.variation_counter += 1

        logger.info(f"Generated {count} combined variations")
        return variations

    def _add_role_emphasis(self, templates: Dict) -> Dict:
        """Strategy: Add explicit role description."""
        modified = templates.copy()
        for key in modified:
            if isinstance(modified[key], str):
                modified[key] = f"[ROLE-EXPERT]\n{modified[key]}"
        return modified

    def _enhance_clarity(self, templates: Dict) -> Dict:
        """Strategy: Enhance instruction clarity."""
        modified = templates.copy()
        for key in modified:
            if isinstance(modified[key], str):
                modified[key] = modified[key].replace(".", ".\n- ").strip()
        return modified

    def _add_examples(self, templates: Dict) -> Dict:
        """Strategy: Add in-context examples."""
        modified = templates.copy()
        for key in modified:
            if isinstance(modified[key], str):
                modified[key] += "\n\nExample format:\nInput: <example>\nOutput: <desired format>"
        return modified


class ExperimentRun:
    """Execute single experiment and collect feedback."""

    def __init__(
        self, 
        candidate_id: str,
        prompt_template: Optional[Dict] = None,
        hyperparameters: Optional[Dict] = None,
    ):
        """
        Args:
            candidate_id: Unique candidate identifier
            prompt_template: Optional modified prompt template
            hyperparameters: Optional modified hyperparameters
        """
        self.candidate_id = candidate_id
        self.prompt_template = prompt_template
        self.hyperparameters = hyperparameters

    def run_experiment(self, test_input: str, inference_fn, max_samples: int = 30) -> List[ExperimentResult]:
        """
        Run experiment with N test samples and collect ratings.

        Args:
            test_input: Test query/prompt
            inference_fn: Callback function for inference (returns tuple: response, time_ms)
            max_samples: Number of test samples (default 30 for t-test power)

        Returns:
            List of ExperimentResult objects with ratings
        """
        results = []

        for sample_num in range(max_samples):
            try:
                # Run inference
                response, time_ms = inference_fn(
                    test_input,
                    prompt_template=self.prompt_template,
                    hyperparameters=self.hyperparameters,
                )

                # Simulate rating collection (0-1 scale)
                # In production: collect from real user feedback
                rating = self._simulate_feedback_rating(response)

                result = ExperimentResult(
                    experiment_id=f"{self.candidate_id}_exp_{sample_num}",
                    candidate_id=self.candidate_id,
                    sample_num=sample_num,
                    rating=rating,
                    response_time_ms=time_ms,
                    error_occurred=False,
                    feedback_text=f"Sample {sample_num}: {response[:50]}...",
                )
                results.append(result)

            except Exception as e:
                logger.error(f"Experiment error for {self.candidate_id} sample {sample_num}: {e}")
                results.append(
                    ExperimentResult(
                        experiment_id=f"{self.candidate_id}_exp_{sample_num}",
                        candidate_id=self.candidate_id,
                        sample_num=sample_num,
                        rating=0.0,
                        response_time_ms=0.0,
                        error_occurred=True,
                        feedback_text=f"Error: {str(e)[:50]}",
                    )
                )

        logger.info(f"Completed {max_samples} experiments for candidate {self.candidate_id}")
        return results

    def _simulate_feedback_rating(self, response: str) -> float:
        """
        Simulate user feedback rating based on response quality.
        In production: collect real user ratings.
        """
        # Simple heuristic: length and has common positive markers
        length_score = min(len(response) / 500, 1.0)  # Prefer longer responses
        quality_markers = sum(
            1 for marker in ["helpful", "correct", "complete", "clear"]
            if marker in response.lower()
        )
        quality_score = min(quality_markers * 0.2, 1.0)

        # Combined score with randomness (simulate user variance)
        import random
        combined = (length_score * 0.6 + quality_score * 0.4)
        rating = combined + random.gauss(0, 0.1)  # Add normal noise
        return max(0.0, min(1.0, rating))  # Clamp to [0, 1]


class ExperimentManager:
    """Manage parallel experiment execution."""

    def __init__(self, max_workers: int = 5):
        """
        Args:
            max_workers: Max concurrent experiments
        """
        self.max_workers = max_workers
        self.all_results: Dict[str, List[ExperimentResult]] = {}

    def run_parallel_experiments(
        self,
        candidates: List[CandidateVariation],
        test_input: str,
        inference_fn,
        samples_per_candidate: int = 30,
    ) -> Dict[str, List[ExperimentResult]]:
        """
        Run experiments for all candidates in parallel.

        Args:
            candidates: List of variations to test
            test_input: Test query
            inference_fn: Inference callback function
            samples_per_candidate: Samples per candidate (default 30)

        Returns:
            Dict mapping candidate_id -> list of ExperimentResults
        """
        logger.info(f"Starting parallel experiments for {len(candidates)} candidates")

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {}
            future_to_candidate = {}

            for candidate in candidates:
                run = ExperimentRun(
                    candidate.candidate_id,
                    prompt_template=candidate.prompt_template,
                    hyperparameters=candidate.hyperparameters,
                )
                future = executor.submit(
                    run.run_experiment,
                    test_input,
                    inference_fn,
                    samples_per_candidate,
                )
                futures[candidate.candidate_id] = future
                future_to_candidate[future] = candidate.candidate_id

            # Collect results as they complete
            for future in as_completed(future_to_candidate.keys()):
                candidate_id = future_to_candidate[future]
                try:
                    results = future.result()
                    self.all_results[candidate_id] = results
                    logger.info(f"Completed experiments for {candidate_id}")
                except Exception as e:
                    logger.error(f"Experiment failed for {candidate_id}: {e}")

        return self.all_results


class StatisticalAnalyzer:
    """Perform statistical analysis on experiment results."""

    def __init__(self, significance_level: float = 0.01):
        """
        Args:
            significance_level: Alpha level (default 0.01 for 99% confidence)
        """
        self.significance_level = significance_level

    def analyze_candidate(self, results: List[ExperimentResult]) -> CandidateAnalysis:
        """Compute statistics for single candidate."""
        ratings = [r.rating for r in results if not r.error_occurred]
        response_times = [r.response_time_ms for r in results if not r.error_occurred]

        if not ratings:
            logger.warning("No valid results for analysis")
            return CandidateAnalysis(
                candidate_id=results[0].candidate_id if results else "unknown",
                mean_rating=0.0,
                std_dev=0.0,
                sample_count=0,
                avg_response_time_ms=0.0,
                error_rate=1.0,
                min_rating=0.0,
                max_rating=0.0,
                results=results,
            )

        mean_rating = statistics.mean(ratings)
        std_dev = statistics.stdev(ratings) if len(ratings) > 1 else 0.0
        error_rate = sum(1 for r in results if r.error_occurred) / len(results)
        avg_time = statistics.mean(response_times) if response_times else 0.0

        return CandidateAnalysis(
            candidate_id=results[0].candidate_id,
            mean_rating=mean_rating,
            std_dev=std_dev,
            sample_count=len(ratings),
            avg_response_time_ms=avg_time,
            error_rate=error_rate,
            min_rating=min(ratings),
            max_rating=max(ratings),
            results=results,
        )

    def compare_candidates(
        self,
        baseline_analysis: CandidateAnalysis,
        candidate_analysis: CandidateAnalysis,
    ) -> ComparisonResult:
        """
        Perform t-test between baseline and candidate.
        Calculate Cohen's d effect size and determine significance.
        """
        # Extract samples
        baseline_ratings = [r.rating for r in baseline_analysis.results if not r.error_occurred]
        candidate_ratings = [r.rating for r in candidate_analysis.results if not r.error_occurred]

        if not baseline_ratings or not candidate_ratings:
            logger.warning("Insufficient samples for comparison")
            return ComparisonResult(
                candidate_id=candidate_analysis.candidate_id,
                t_statistic=0.0,
                p_value=1.0,
                cohens_d=0.0,
                is_significant=False,
                improvement_direction="neutral",
                recommendation="REJECT",
                confidence_level=0.0,
            )

        # Two-sample t-test (independent samples)
        t_stat, p_value = self._ttest_ind(baseline_ratings, candidate_ratings)

        # Cohen's d effect size
        cohens_d = self._cohens_d(baseline_ratings, candidate_ratings)

        # Determine significance at alpha=0.01
        is_significant = p_value < self.significance_level

        # Improvement direction
        mean_diff = candidate_analysis.mean_rating - baseline_analysis.mean_rating
        if mean_diff > 0.02:
            improvement_direction = "better"
        elif mean_diff < -0.02:
            improvement_direction = "worse"
        else:
            improvement_direction = "neutral"

        # Recommendation logic
        if is_significant and improvement_direction == "better" and abs(cohens_d) >= 0.5:
            recommendation = "ADOPT"
        elif is_significant and improvement_direction == "worse":
            recommendation = "REJECT"
        else:
            recommendation = "INVESTIGATE"

        return ComparisonResult(
            candidate_id=candidate_analysis.candidate_id,
            t_statistic=t_stat,
            p_value=p_value,
            cohens_d=cohens_d,
            is_significant=is_significant,
            improvement_direction=improvement_direction,
            recommendation=recommendation,
            confidence_level=99.0 if is_significant else 95.0,
        )

    def _ttest_ind(self, group1: List[float], group2: List[float]) -> Tuple[float, float]:
        """
        Welch's t-test for independent samples.
        Returns: (t_statistic, p_value)
        """
        n1, n2 = len(group1), len(group2)
        mean1 = statistics.mean(group1)
        mean2 = statistics.mean(group2)
        var1 = statistics.variance(group1) if len(group1) > 1 else 0.0
        var2 = statistics.variance(group2) if len(group2) > 1 else 0.0

        # Welch's t-test (doesn't assume equal variance)
        if var1 + var2 == 0:
            return 0.0, 1.0

        se = math.sqrt(var1 / n1 + var2 / n2)
        t_stat = (mean1 - mean2) / se if se > 0 else 0.0

        # Approximate p-value using t-distribution (simplified)
        # For large samples (n >= 30), use normal approximation
        df = n1 + n2 - 2
        p_value = self._pvalue_from_tstat(t_stat, df)

        return t_stat, p_value

    def _pvalue_from_tstat(self, t_stat: float, df: int) -> float:
        """Approximate p-value from t-statistic (two-tailed t-test)."""
        # Simplified: use normal approximation for large df (> 30)
        if df > 30:
            from math import erfc, sqrt
            p_value = erfc(abs(t_stat) / sqrt(2))  # Simplified normal approximation
        else:
            # For smaller df, estimate based on t-stat magnitude
            p_value = 0.01 if abs(t_stat) > 2.576 else 0.05  # Rough approximation
        return p_value

    def _cohens_d(self, group1: List[float], group2: List[float]) -> float:
        """
        Calculate Cohen's d effect size.
        Interpretation:
          0.2: small effect
          0.5: medium effect
          0.8: large effect
        """
        mean1 = statistics.mean(group1)
        mean2 = statistics.mean(group2)
        var1 = statistics.variance(group1) if len(group1) > 1 else 0.0
        var2 = statistics.variance(group2) if len(group2) > 1 else 0.0

        pooled_std = math.sqrt((var1 + var2) / 2)
        if pooled_std == 0:
            return 0.0

        cohens_d = (mean1 - mean2) / pooled_std
        return cohens_d


class ABTestingEngine:
    """Integrated A/B testing with auto-selection."""

    def __init__(self, max_workers: int = 5):
        """
        Args:
            max_workers: Max concurrent experiments
        """
        self.candidate_generator = None
        self.experiment_manager = ExperimentManager(max_workers=max_workers)
        self.statistical_analyzer = StatisticalAnalyzer(significance_level=0.01)
        self.test_history: List[Dict] = []

    def initialize(self, prompt_templates: Dict, hyperparameters: Dict):
        """Initialize with current templates and hyperparameters."""
        self.candidate_generator = CandidateGenerator(prompt_templates, hyperparameters)
        logger.info("ABTestingEngine initialized")

    def run_ab_test(
        self,
        test_input: str,
        inference_fn,
        baseline_results: List[ExperimentResult],
        num_candidates: int = 5,
        samples_per_candidate: int = 30,
    ) -> Dict:
        """
        Full A/B testing workflow.

        Args:
            test_input: Test query
            inference_fn: Inference callback
            baseline_results: Control group results
            num_candidates: Number of candidates to test
            samples_per_candidate: Samples per candidate

        Returns:
            Test results with recommendations
        """
        if not self.candidate_generator:
            raise ValueError("Engine not initialized. Call initialize() first.")

        logger.info(f"Starting A/B test with {num_candidates} candidates")

        # Step 1: Analyze baseline
        baseline_analysis = self.statistical_analyzer.analyze_candidate(baseline_results)
        logger.info(f"Baseline: mean={baseline_analysis.mean_rating:.3f}, std={baseline_analysis.std_dev:.3f}")

        # Step 2: Generate candidates
        candidates = []
        candidates.extend(self.candidate_generator.generate_prompt_variations(num_candidates // 3))
        candidates.extend(
            self.candidate_generator.generate_hyperparameter_variations(num_candidates // 3)
        )
        candidates.extend(
            self.candidate_generator.generate_combined_variations(num_candidates - 2 * (num_candidates // 3))
        )

        # Step 3: Run parallel experiments
        experiment_results = self.experiment_manager.run_parallel_experiments(
            candidates, test_input, inference_fn, samples_per_candidate
        )

        # Step 4: Statistical analysis
        comparisons: List[ComparisonResult] = []
        for candidate_id, results in experiment_results.items():
            candidate_analysis = self.statistical_analyzer.analyze_candidate(results)
            comparison = self.statistical_analyzer.compare_candidates(
                baseline_analysis, candidate_analysis
            )
            comparisons.append(comparison)

        # Step 5: Auto-select best
        best_candidate = self._select_best_candidate(comparisons)

        # Step 6: Create report
        test_report = {
            "test_id": f"abtest_{datetime.now().isoformat()}",
            "baseline_mean_rating": baseline_analysis.mean_rating,
            "num_candidates": len(candidates),
            "comparisons": [asdict(c) for c in comparisons],
            "best_candidate_id": best_candidate.candidate_id if best_candidate else None,
            "best_recommendation": best_candidate.recommendation if best_candidate else "REJECT",
            "timestamp": datetime.now().isoformat(),
        }

        self.test_history.append(test_report)
        logger.info(f"A/B test complete. Best candidate: {best_candidate.candidate_id if best_candidate else 'NONE'}")

        return test_report

    def _select_best_candidate(self, comparisons: List[ComparisonResult]) -> Optional[ComparisonResult]:
        """Auto-select best candidate based on criteria."""
        # Filter ADOPT recommendations
        adopt_candidates = [c for c in comparisons if c.recommendation == "ADOPT"]

        if not adopt_candidates:
            logger.info("No ADOPT candidates found")
            return None

        # Sort by Cohen's d (largest effect size)
        best = max(adopt_candidates, key=lambda c: c.cohens_d)
        logger.info(
            f"Selected candidate {best.candidate_id}: d={best.cohens_d:.3f}, "
            f"improvement={best.improvement_direction}"
        )
        return best

    def get_test_history(self) -> List[Dict]:
        """Return test history."""
        return self.test_history
