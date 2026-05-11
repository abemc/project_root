"""
推論チェーン & 自己改善エンジン - テストスイート
"""

import pytest
from src.reasoning_chain.reasoning_engine import (
    ReasoningType, ThoughtStep, ChainOfThoughtGenerator, TreeOfThoughtPlanner, FewShotExampleSelector,
    SelfVerificationEngine, IterativeRefinementLoop, ReasoningTraceLogger,
    ReasoningEngine
)


# ==================== ChainOfThoughtGenerator Tests ====================

class TestChainOfThoughtGenerator:
    """Chain-of-Thoughtジェネレータのテスト"""
    
    def test_generator_initialization(self):
        """ジェネレータ初期化テスト"""
        generator = ChainOfThoughtGenerator()
        assert len(generator.step_templates) > 0
        assert len(generator.generated_chains) == 0
    
    @pytest.mark.asyncio
    async def test_generate_chain(self):
        """CoTチェーン生成テスト"""
        generator = ChainOfThoughtGenerator()
        result = await generator.generate_chain(
            question="What is 2+2?",
            max_steps=3
        )
        
        assert result.question == "What is 2+2?"
        assert len(result.steps) == 3
        assert result.final_answer != ""
        assert result.confidence_score > 0
    
    @pytest.mark.asyncio
    async def test_chain_with_context(self):
        """コンテキスト付きChainテスト"""
        generator = ChainOfThoughtGenerator()
        result = await generator.generate_chain(
            question="Solve this problem",
            context="Mathematical context provided",
            max_steps=5
        )
        
        assert result.steps != []
        assert result.reasoning_trace != ""
    
    def test_thought_step_creation(self):
        """ThoughtStep作成テスト"""
        step = ThoughtStep(
            step_number=1,
            content="Analyzing problem",
            reasoning_type=ReasoningType.CHAIN_OF_THOUGHT,
            confidence=0.9
        )
        
        assert step.step_number == 1
        assert step.confidence == 0.9
        assert step.reasoning_type == ReasoningType.CHAIN_OF_THOUGHT


# ==================== TreeOfThoughtPlanner Tests ====================

class TestTreeOfThoughtPlanner:
    """Tree-of-Thoughtプランナーのテスト"""
    
    def test_planner_initialization(self):
        """プランナー初期化テスト"""
        planner = TreeOfThoughtPlanner()
        assert planner.max_depth == 4
        assert planner.branching_factor == 3
    
    @pytest.mark.asyncio
    async def test_build_thought_tree(self):
        """思考木構築テスト"""
        planner = TreeOfThoughtPlanner()
        tree = await planner.build_thought_tree(
            root_question="How to solve complex problem?",
            max_depth=2
        )
        
        assert tree.content != ""
        assert tree.depth == 0
        assert tree.is_terminal is False
    
    @pytest.mark.asyncio
    async def test_find_best_path(self):
        """最適パス発見テスト"""
        planner = TreeOfThoughtPlanner()
        tree = await planner.build_thought_tree("Test question", max_depth=2)
        best_path = await planner.find_best_path(tree)
        
        assert len(best_path) > 0
        assert best_path[0] == tree
    
    @pytest.mark.asyncio
    async def test_tree_statistics(self):
        """木統計テスト"""
        planner = TreeOfThoughtPlanner()
        tree = await planner.build_thought_tree("Test", max_depth=2)
        stats = planner.get_tree_statistics(tree)
        
        assert "total_nodes" in stats
        assert "max_depth" in stats
        assert stats["total_nodes"] > 0


# ==================== FewShotExampleSelector Tests ====================

class TestFewShotExampleSelector:
    """Few-shotサンプルセレクターのテスト"""
    
    def test_selector_initialization(self):
        """セレクター初期化テスト"""
        selector = FewShotExampleSelector()
        assert len(selector.example_database) == 0
    
    def test_register_examples(self):
        """例登録テスト"""
        selector = FewShotExampleSelector()
        examples = [
            {"input": "What is capital of France?", "output": "Paris"},
            {"input": "What is capital of Japan?", "output": "Tokyo"}
        ]
        success = selector.register_examples("geography", examples)
        
        assert success
        assert "geography" in selector.example_database
    
    @pytest.mark.asyncio
    async def test_select_relevant_examples(self):
        """関連例選択テスト"""
        selector = FewShotExampleSelector()
        examples = [
            {"input": "What is 2+2?", "output": "4"},
            {"input": "What is 3*3?", "output": "9"},
            {"input": "What is capital of France?", "output": "Paris"}
        ]
        selector.register_examples("general", examples)
        
        selected = await selector.select_relevant_examples(
            "What is mathematical operation?",
            "general",
            num_examples=2
        )
        
        assert len(selected) <= 2
    
    @pytest.mark.asyncio
    async def test_build_few_shot_prompt(self):
        """Few-shotプロンプト構築テスト"""
        selector = FewShotExampleSelector()
        examples = [
            {"input": "Test input 1", "output": "Test output 1"}
        ]
        selector.register_examples("test", examples)
        
        prompt = await selector.build_few_shot_prompt(
            "New query",
            "test",
            num_examples=1
        )
        
        assert "Examples:" in prompt
        assert "Test input 1" in prompt


# ==================== SelfVerificationEngine Tests ====================

class TestSelfVerificationEngine:
    """自己検証エンジンのテスト"""
    
    def test_engine_initialization(self):
        """エンジン初期化テスト"""
        engine = SelfVerificationEngine()
        assert len(engine.verification_rules) == 0
    
    def test_register_verification_rule(self):
        """検証ルール登録テスト"""
        engine = SelfVerificationEngine()
        def rule(x):
            return len(x) > 0
        engine.register_verification_rule("non_empty", rule)
        
        assert "non_empty" in engine.verification_rules
    
    @pytest.mark.asyncio
    async def test_verify_valid_answer(self):
        """有効な回答検証テスト"""
        engine = SelfVerificationEngine()
        result = await engine.verify_answer(
            "This is a valid and complete answer with sufficient length."
        )
        
        assert result["is_valid"]
        assert result["confidence"] > 0
        assert len(result["checks_performed"]) > 0
    
    @pytest.mark.asyncio
    async def test_verify_invalid_answer(self):
        """無効な回答検証テスト"""
        engine = SelfVerificationEngine()
        result = await engine.verify_answer("")
        
        assert result["is_valid"] is False
        assert len(result["issues"]) > 0


# ==================== IterativeRefinementLoop Tests ====================

class TestIterativeRefinementLoop:
    """反復的精緻化ループのテスト"""
    
    def test_loop_initialization(self):
        """ループ初期化テスト"""
        loop = IterativeRefinementLoop()
        assert loop.max_iterations == 5
    
    @pytest.mark.asyncio
    async def test_refine_answer(self):
        """回答精緻化テスト"""
        loop = IterativeRefinementLoop()
        verification = {
            "is_valid": False,
            "confidence": 0.5,
            "issues": ["Answer too short"]
        }
        
        refined = await loop.refine_answer(
            "Short answer",
            verification
        )
        
        assert len(refined) > len("Short answer")
    
    @pytest.mark.asyncio
    async def test_iterative_improvement(self):
        """反復的改善テスト"""
        loop = IterativeRefinementLoop()
        verifier = SelfVerificationEngine()
        
        improved, history = await loop.iterative_improvement(
            "Initial answer",
            verifier,
            max_iterations=2
        )
        
        assert len(history) <= 2
        assert improved != ""


# ==================== ReasoningTraceLogger Tests ====================

class TestReasoningTraceLogger:
    """推論トレースロガーのテスト"""
    
    def test_logger_initialization(self):
        """ロガー初期化テスト"""
        logger = ReasoningTraceLogger()
        assert len(logger.traces) == 0
    
    @pytest.mark.asyncio
    async def test_log_reasoning_trace(self):
        """推論トレースログ記録テスト"""
        logger = ReasoningTraceLogger()
        steps = [
            "Step 1: Analyze",
            "Step 2: Reason",
            "Step 3: Conclude"
        ]
        
        await logger.log_reasoning_trace(
            trace_id="trace_001",
            question="Test question",
            reasoning_steps=steps,
            final_answer="Test answer"
        )
        
        assert len(logger.traces) == 1
        assert "trace_001" in logger.detailed_logs
    
    @pytest.mark.asyncio
    async def test_get_trace_statistics(self):
        """トレース統計取得テスト"""
        logger = ReasoningTraceLogger()
        
        await logger.log_reasoning_trace(
            "trace_001",
            "Q1",
            ["Step 1", "Step 2"],
            "Answer 1"
        )
        
        stats = logger.get_trace_statistics()
        assert stats["total_traces"] == 1
        assert stats["average_steps"] == 2
    
    @pytest.mark.asyncio
    async def test_export_trace(self):
        """トレースエクスポートテスト"""
        logger = ReasoningTraceLogger()
        
        await logger.log_reasoning_trace(
            "trace_001",
            "Question",
            ["Step 1", "Step 2"],
            "Answer"
        )
        
        exported = logger.export_trace("trace_001")
        assert exported is not None
        assert exported["trace_id"] == "trace_001"
        assert "detailed_steps" in exported


# ==================== ReasoningEngine Tests ====================

class TestReasoningEngine:
    """推論エンジン統合のテスト"""
    
    def test_engine_initialization(self):
        """エンジン初期化テスト"""
        engine = ReasoningEngine()
        
        assert engine.cot_generator is not None
        assert engine.tot_planner is not None
        assert engine.example_selector is not None
        assert engine.verifier is not None
        assert engine.refiner is not None
        assert engine.trace_logger is not None
    
    @pytest.mark.asyncio
    async def test_reason_with_cot(self):
        """CoT推論テスト"""
        engine = ReasoningEngine()
        result = await engine.reason_with_cot("What is 2+2?")
        
        assert result.question == "What is 2+2?"
        assert result.final_answer != ""
        assert result.confidence_score > 0
    
    @pytest.mark.asyncio
    async def test_reason_with_tot(self):
        """ToT推論テスト"""
        engine = ReasoningEngine()
        tree, path = await engine.reason_with_tot("Complex question")
        
        assert tree is not None
        assert len(path) > 0
    
    @pytest.mark.asyncio
    async def test_reason_with_few_shot(self):
        """Few-shot推論テスト"""
        engine = ReasoningEngine()
        examples = [
            {"input": "Input 1", "output": "Output 1"}
        ]
        engine.example_selector.register_examples("test", examples)
        
        prompt = await engine.reason_with_few_shot("Query", "test")
        
        assert "Examples:" in prompt
    
    @pytest.mark.asyncio
    async def test_reason_with_self_improvement(self):
        """自己改善推論テスト"""
        engine = ReasoningEngine()
        improved, history = await engine.reason_with_self_improvement(
            "Initial answer"
        )
        
        assert improved != ""
        assert isinstance(history, list)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
