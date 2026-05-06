"""
推論チェーン & 自己改善エンジン

Chain-of-Thought、Tree-of-Thought、Few-shot学習、自動検証・修正
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple, Any, Callable
import math
import logging
from datetime import datetime


logger = logging.getLogger(__name__)


class ReasoningType(Enum):
    """推論タイプ"""
    CHAIN_OF_THOUGHT = "cot"  # CoT
    TREE_OF_THOUGHT = "tot"  # ToT
    SELF_CRITIQUE = "critique"  # 自己批判


@dataclass
class ThoughtStep:
    """思考ステップ"""
    step_number: int
    content: str
    reasoning_type: ReasoningType
    confidence: float = 0.0
    validation_score: float = 0.0
    alternative_paths: List[str] = field(default_factory=list)


@dataclass
class ChainOfThoughtResult:
    """CoT結果"""
    question: str
    steps: List[ThoughtStep] = field(default_factory=list)
    final_answer: str = ""
    reasoning_trace: str = ""
    confidence_score: float = 0.0
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TreeNode:
    """思考木のノード"""
    content: str
    depth: int
    parent: Optional['TreeNode'] = None
    children: List['TreeNode'] = field(default_factory=list)
    score: float = 0.0
    is_terminal: bool = False


class ChainOfThoughtGenerator:
    """Chain-of-Thoughtジェネレータ"""
    
    def __init__(self):
        """初期化"""
        self.step_templates = {
            "analysis": "Let me analyze this step by step: ",
            "decompose": "First, I need to break this down into parts: ",
            "verify": "Let me verify this reasoning: ",
            "conclude": "Therefore, the answer is: "
        }
        self.generated_chains: List[ChainOfThoughtResult] = []
    
    async def generate_chain(
        self,
        question: str,
        context: Optional[str] = None,
        max_steps: int = 5
    ) -> ChainOfThoughtResult:
        """CoTチェーンを生成"""
        
        result = ChainOfThoughtResult(question=question)
        reasoning_steps = []
        
        # ステップ1: 問題分析
        step1 = ThoughtStep(
            step_number=1,
            content=f"Analyzing question: {question}",
            reasoning_type=ReasoningType.CHAIN_OF_THOUGHT,
            confidence=0.9
        )
        reasoning_steps.append(step1)
        
        # ステップ2: 問題分解
        step2 = ThoughtStep(
            step_number=2,
            content="Breaking down the problem into components",
            reasoning_type=ReasoningType.CHAIN_OF_THOUGHT,
            confidence=0.85
        )
        reasoning_steps.append(step2)
        
        # ステップ3: 推論展開
        step3 = ThoughtStep(
            step_number=3,
            content="Applying logical reasoning to each component",
            reasoning_type=ReasoningType.CHAIN_OF_THOUGHT,
            confidence=0.8,
            alternative_paths=[
                "Alternative approach 1: Inductive reasoning",
                "Alternative approach 2: Deductive reasoning"
            ]
        )
        reasoning_steps.append(step3)
        
        # ステップ4: 検証
        step4 = ThoughtStep(
            step_number=4,
            content="Verifying intermediate conclusions",
            reasoning_type=ReasoningType.CHAIN_OF_THOUGHT,
            confidence=0.88,
            validation_score=0.92
        )
        reasoning_steps.append(step4)
        
        # ステップ5: 結論
        step5 = ThoughtStep(
            step_number=5,
            content="Formulating final answer based on reasoning chain",
            reasoning_type=ReasoningType.CHAIN_OF_THOUGHT,
            confidence=0.85
        )
        reasoning_steps.append(step5)
        
        result.steps = reasoning_steps[:max_steps]
        result.final_answer = "The solution follows from the chain of reasoning above"
        result.confidence_score = sum(s.confidence for s in result.steps) / len(result.steps)
        
        # 推論トレース生成
        result.reasoning_trace = " -> ".join([f"Step {s.step_number}: {s.content[:40]}" for s in result.steps])
        
        self.generated_chains.append(result)
        
        logger.info(f"Generated CoT chain with {len(result.steps)} steps, confidence={result.confidence_score:.2f}")
        
        return result


class TreeOfThoughtPlanner:
    """Tree-of-Thoughtプランナー"""
    
    def __init__(self):
        """初期化"""
        self.max_depth = 4
        self.branching_factor = 3
        self.trees: List[TreeNode] = []
    
    async def build_thought_tree(
        self,
        root_question: str,
        max_depth: Optional[int] = None
    ) -> TreeNode:
        """思考木を構築"""
        
        if max_depth is None:
            max_depth = self.max_depth
        
        root = TreeNode(
            content=root_question,
            depth=0,
            is_terminal=False
        )
        
        # BFS で木を構築
        queue = [(root, 0)]
        node_count = 0
        
        while queue and node_count < 50:  # ノード数制限
            current_node, depth = queue.pop(0)
            node_count += 1
            
            if depth >= max_depth:
                current_node.is_terminal = True
                continue
            
            # 子ノードを生成
            for i in range(self.branching_factor):
                child_content = f"Approach {i+1}: Exploring branch at depth {depth+1}"
                child = TreeNode(
                    content=child_content,
                    depth=depth + 1,
                    parent=current_node,
                    score=0.8 - (depth * 0.1)  # 深さで減少
                )
                current_node.children.append(child)
                queue.append((child, depth + 1))
        
        self.trees.append(root)
        
        logger.info(f"Built ToT tree with {node_count} nodes, max depth={max_depth}")
        
        return root
    
    async def find_best_path(
        self,
        tree: TreeNode
    ) -> List[TreeNode]:
        """最適パスを発見"""
        
        path = []
        current = tree
        
        while current is not None:
            path.append(current)
            
            # 最高スコアの子ノードを選択
            if current.children:
                current = max(current.children, key=lambda x: x.score)
            else:
                break
        
        logger.info(f"Found best path with {len(path)} nodes")
        
        return path
    
    def get_tree_statistics(self, tree: TreeNode) -> Dict[str, Any]:
        """木の統計を取得"""
        
        def count_nodes(node: TreeNode) -> int:
            return 1 + sum(count_nodes(child) for child in node.children)
        
        total_nodes = count_nodes(tree)
        
        def max_depth_func(node: TreeNode) -> int:
            if not node.children:
                return node.depth
            return max(max_depth_func(child) for child in node.children)
        
        depth = max_depth_func(tree)
        
        return {
            "total_nodes": total_nodes,
            "max_depth": depth,
            "branching_factor": self.branching_factor,
            "structure": f"{total_nodes} nodes at depth {depth}"
        }


class FewShotExampleSelector:
    """Few-shotサンプルセレクター"""
    
    def __init__(self):
        """初期化"""
        self.example_database: Dict[str, List[Dict]] = {}
        self.embeddings_cache: Dict[str, List[float]] = {}
    
    def register_examples(
        self,
        task_type: str,
        examples: List[Dict]
    ) -> bool:
        """例を登録"""
        
        try:
            self.example_database[task_type] = examples
            logger.info(f"Registered {len(examples)} examples for task '{task_type}'")
            return True
        except Exception as e:
            logger.error(f"Failed to register examples: {e}")
            return False
    
    async def select_relevant_examples(
        self,
        query: str,
        task_type: str,
        num_examples: int = 3
    ) -> List[Dict]:
        """関連例を選択"""
        
        if task_type not in self.example_database:
            logger.warning(f"No examples found for task '{task_type}'")
            return []
        
        examples = self.example_database[task_type]
        
        # キーワード類似度で選択（シンプル実装）
        query_tokens = set(query.lower().split())
        
        scored_examples = []
        for example in examples:
            example_text = str(example).lower()
            example_tokens = set(example_text.split())
            
            # Jaccardの類似度
            intersection = len(query_tokens & example_tokens)
            union = len(query_tokens | example_tokens)
            similarity = intersection / union if union > 0 else 0
            
            scored_examples.append((example, similarity))
        
        # スコア順に並べ替え
        scored_examples.sort(key=lambda x: x[1], reverse=True)
        
        selected = [ex for ex, score in scored_examples[:num_examples]]
        
        logger.info(f"Selected {len(selected)} relevant examples")
        
        return selected
    
    async def build_few_shot_prompt(
        self,
        query: str,
        task_type: str,
        num_examples: int = 3
    ) -> str:
        """Few-shotプロンプトを構築"""
        
        examples = await self.select_relevant_examples(query, task_type, num_examples)
        
        prompt = f"Solve the following task:\n\nExamples:\n"
        
        for i, example in enumerate(examples, 1):
            prompt += f"\n{i}. Input: {example.get('input', '')}\n"
            prompt += f"   Output: {example.get('output', '')}\n"
        
        prompt += f"\nNow solve: {query}\n"
        
        return prompt


class SelfVerificationEngine:
    """自己検証エンジン"""
    
    def __init__(self):
        """初期化"""
        self.verification_rules: Dict[str, Callable] = {}
        self.verification_history: List[Dict] = []
    
    def register_verification_rule(
        self,
        rule_name: str,
        rule_func: Callable
    ) -> None:
        """検証ルールを登録"""
        self.verification_rules[rule_name] = rule_func
    
    async def verify_answer(
        self,
        answer: str,
        context: Optional[str] = None,
        task_type: str = "general"
    ) -> Dict[str, Any]:
        """回答を検証"""
        
        verification_result = {
            "answer": answer,
            "is_valid": True,
            "confidence": 1.0,
            "issues": [],
            "checks_performed": []
        }
        
        # 基本的な検証
        # チェック1: 長さ
        if len(answer.strip()) == 0:
            verification_result["issues"].append("Answer is empty")
            verification_result["is_valid"] = False
            verification_result["confidence"] = 0.0
        
        # チェック2: 一貫性
        if context and "contradiction" in answer.lower():
            verification_result["issues"].append("Potential contradiction detected")
            verification_result["confidence"] *= 0.8
        
        # チェック3: 完全性
        if len(answer.split()) < 5:
            verification_result["issues"].append("Answer too short")
            verification_result["confidence"] *= 0.7
        
        verification_result["checks_performed"] = [
            "length_check",
            "consistency_check",
            "completeness_check"
        ]
        
        self.verification_history.append(verification_result)
        
        return verification_result


class IterativeRefinementLoop:
    """反復的精緻化ループ"""
    
    def __init__(self):
        """初期化"""
        self.max_iterations = 5
        self.refinement_history: List[Dict] = []
    
    async def refine_answer(
        self,
        initial_answer: str,
        verification_result: Dict,
        context: Optional[str] = None
    ) -> str:
        """回答を精緻化"""
        
        if verification_result["is_valid"] and verification_result["confidence"] > 0.8:
            return initial_answer
        
        # 問題に基づいて改善
        refined_answer = initial_answer
        
        for issue in verification_result["issues"]:
            if "empty" in issue:
                refined_answer = "Unable to generate answer"
            elif "short" in issue:
                refined_answer += "\n\nAdditional details: "
                refined_answer += "This requires further analysis and consideration."
        
        self.refinement_history.append({
            "original": initial_answer,
            "refined": refined_answer,
            "issues_addressed": verification_result["issues"]
        })
        
        return refined_answer
    
    async def iterative_improvement(
        self,
        initial_answer: str,
        verifier: SelfVerificationEngine,
        max_iterations: Optional[int] = None
    ) -> Tuple[str, List[Dict]]:
        """反復的改善を実行"""
        
        if max_iterations is None:
            max_iterations = self.max_iterations
        
        current_answer = initial_answer
        history = []
        
        for iteration in range(max_iterations):
            # 検証
            verification = await verifier.verify_answer(current_answer)
            history.append(verification)
            
            # 合格判定
            if verification["is_valid"] and verification["confidence"] > 0.85:
                logger.info(f"Improvement converged at iteration {iteration + 1}")
                break
            
            # 精緻化
            current_answer = await self.refine_answer(
                current_answer,
                verification
            )
        
        return current_answer, history


class ReasoningTraceLogger:
    """推論トレースロガー"""
    
    def __init__(self):
        """初期化"""
        self.traces: List[Dict] = []
        self.detailed_logs: Dict[str, List[str]] = {}
    
    async def log_reasoning_trace(
        self,
        trace_id: str,
        question: str,
        reasoning_steps: List[str],
        final_answer: str,
        metadata: Optional[Dict] = None
    ) -> None:
        """推論トレースをログ記録"""
        
        trace_record = {
            "trace_id": trace_id,
            "timestamp": datetime.utcnow().isoformat(),
            "question": question,
            "num_steps": len(reasoning_steps),
            "final_answer": final_answer,
            "metadata": metadata or {}
        }
        
        self.traces.append(trace_record)
        self.detailed_logs[trace_id] = reasoning_steps
        
        logger.info(f"Logged reasoning trace {trace_id} with {len(reasoning_steps)} steps")
    
    def get_trace_statistics(self) -> Dict[str, Any]:
        """トレース統計を取得"""
        
        if not self.traces:
            return {"total_traces": 0}
        
        num_steps_list = [t["num_steps"] for t in self.traces]
        
        return {
            "total_traces": len(self.traces),
            "average_steps": sum(num_steps_list) / len(num_steps_list),
            "max_steps": max(num_steps_list),
            "min_steps": min(num_steps_list)
        }
    
    def export_trace(self, trace_id: str) -> Optional[Dict]:
        """トレースをエクスポート"""
        
        trace = next((t for t in self.traces if t["trace_id"] == trace_id), None)
        
        if trace:
            trace["detailed_steps"] = self.detailed_logs.get(trace_id, [])
        
        return trace


class ReasoningEngine:
    """推論エンジン統合"""
    
    def __init__(self):
        """初期化"""
        self.cot_generator = ChainOfThoughtGenerator()
        self.tot_planner = TreeOfThoughtPlanner()
        self.example_selector = FewShotExampleSelector()
        self.verifier = SelfVerificationEngine()
        self.refiner = IterativeRefinementLoop()
        self.trace_logger = ReasoningTraceLogger()
    
    async def reason_with_cot(
        self,
        question: str,
        context: Optional[str] = None
    ) -> ChainOfThoughtResult:
        """CoTで推論"""
        
        result = await self.cot_generator.generate_chain(question, context)
        
        # 検証
        verification = await self.verifier.verify_answer(result.final_answer, context)
        result.confidence_score = verification["confidence"]
        
        return result
    
    async def reason_with_tot(
        self,
        question: str
    ) -> Tuple[TreeNode, List[TreeNode]]:
        """ToTで推論"""
        
        tree = await self.tot_planner.build_thought_tree(question)
        best_path = await self.tot_planner.find_best_path(tree)
        
        return tree, best_path
    
    async def reason_with_few_shot(
        self,
        query: str,
        task_type: str,
        num_examples: int = 3
    ) -> str:
        """Few-shotで推論"""
        
        prompt = await self.example_selector.build_few_shot_prompt(
            query, task_type, num_examples
        )
        
        return prompt
    
    async def reason_with_self_improvement(
        self,
        initial_answer: str
    ) -> Tuple[str, List[Dict]]:
        """自己改善で推論"""
        
        improved_answer, history = await self.refiner.iterative_improvement(
            initial_answer,
            self.verifier
        )
        
        return improved_answer, history
