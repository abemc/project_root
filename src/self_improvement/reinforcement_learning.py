"""
Reinforcement Learning: Optimize decisions based on rewards and penalties.

This module implements reinforcement learning mechanisms that help the AI agent
learn the best strategies by maximizing cumulative rewards. It combines multiple
reward signals to guide learning toward optimal behaviors.

Key Features:
- Multi-factor reward computation (time, quality, resource usage)
- Policy gradient-based strategy optimization
- Exploration vs exploitation balance
- Value function learning
- Experience replay for stable learning
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum
import json
import random


class RewardSignal(Enum):
    """Types of rewards the agent can receive."""
    TASK_SUCCESS = "success"           # Task completed successfully
    EXECUTION_TIME = "speed"           # Fast execution
    QUALITY = "quality"                # High-quality output
    RESOURCE_EFFICIENCY = "efficiency" # Low resource usage
    LEARNING_GAIN = "learning"         # Learned something useful
    ERROR_AVOIDANCE = "safety"         # Avoided errors
    USER_SATISFACTION = "satisfaction" # User feedback


@dataclass
class Reward:
    """A single reward signal."""
    signal_type: RewardSignal
    value: float                   # -1.0 to 1.0 (negative = penalty)
    weight: float                  # 0-1: Importance of this signal
    reason: str                    # Explanation
    timestamp: datetime = field(default_factory=datetime.now)
    
    def weighted_value(self) -> float:
        """Get weighted reward value."""
        return self.value * self.weight


@dataclass
class Decision:
    """A decision made by the agent."""
    decision_id: str
    context: Dict[str, Any]
    action_chosen: str              # What was chosen
    alternatives: List[str]         # Other options considered
    confidence: float               # 0-1: How confident?
    timestamp: datetime
    rewards: List[Reward] = field(default_factory=list)
    
    def compute_total_reward(self) -> float:
        """Compute total reward for this decision."""
        if not self.rewards:
            return 0.0
        return sum(r.weighted_value() for r in self.rewards)
    
    def compute_regret(self) -> float:
        """
        Compute regret: how much better could we have done?
        
        Regret = best_possible_reward - actual_reward
        
        Returns:
            Regret score (higher = worse decision)
        """
        actual_reward = self.compute_total_reward()
        # Assume best possible would be 1.0
        return max(0.0, 1.0 - actual_reward)


@dataclass
@dataclass
class Policy:
    """A learned strategy for decision-making."""
    policy_id: str
    description: str                # What does this policy do?
    context_conditions: Dict[str, Any]  # When to apply
    action_distribution: Dict[str, float]  # action → probability
    success_history: List[float]    # Rewards from past applications
    application_count: int = 0
    
    def select_action(self, use_exploration: bool = False) -> str:
        """
        Select an action according to this policy.
        
        Args:
            use_exploration: Use exploration (random) vs exploitation (best).
            
        Returns:
            Selected action.
        """
        if use_exploration and random.random() < 0.1:  # 10% exploration
            return random.choice(list(self.action_distribution.keys()))
        else:
            # Choose highest probability action
            return max(self.action_distribution, key=self.action_distribution.get)
    
    def average_reward(self) -> float:
        """Compute average reward for this policy (0-1)."""
        if not self.success_history:
            return 0.5
        return sum(self.success_history) / len(self.success_history)
    
    def compute_value(self) -> float:
        """
        Compute value of this policy (0-1).
        
        Factors:
        - Average reward (60%)
        - Application frequency (30%)
        - Stability (10%)
        
        Returns:
            Value score (0-1).
        """
        avg_reward = self.average_reward()
        freq_factor = min(self.application_count / 100, 1.0)
        
        # Stability: how consistent are rewards?
        if len(self.success_history) < 2:
            stability = 0.5
        else:
            variance = sum((r - avg_reward) ** 2 for r in self.success_history) / len(self.success_history)
            std_dev = variance ** 0.5
            stability = max(0.0, 1.0 - std_dev)
        
        value = (avg_reward * 0.6) + (freq_factor * 0.3) + (stability * 0.1)
        return min(max(value, 0.0), 1.0)


@dataclass
class ExperienceEntry:
    """A single experience (state-action-reward-next_state)."""
    state: Dict[str, Any]           # Current context
    action: str                      # Action taken
    reward: float                    # Immediate reward
    next_state: Dict[str, Any]      # Resulting state
    done: bool                       # Is episode finished?
    timestamp: datetime = field(default_factory=datetime.now)


class ReinforcementLearningManager:
    """
    Manages reinforcement learning for decision optimization.
    
    Responsibilities:
    - Collect reward signals from task execution
    - Learn optimal policies from experiences
    - Balance exploration vs exploitation
    - Adapt strategy based on feedback
    - Generate Q-values for actions
    """
    
    def __init__(self, learning_rate: float = 0.1, discount_factor: float = 0.99):
        """
        Initialize RL manager.
        
        Args:
            learning_rate: How fast to learn (0-1)
            discount_factor: Value of future rewards (0-1)
        """
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        
        self.decisions: Dict[str, Decision] = {}
        self.policies: Dict[str, Policy] = {}
        self.experience_replay: List[ExperienceEntry] = []
        self.q_values: Dict[Tuple[str, str], float] = {}  # (state_hash, action) → Q-value
        self.reward_weights: Dict[RewardSignal, float] = {
            RewardSignal.TASK_SUCCESS: 0.4,
            RewardSignal.EXECUTION_TIME: 0.2,
            RewardSignal.QUALITY: 0.2,
            RewardSignal.RESOURCE_EFFICIENCY: 0.1,
            RewardSignal.LEARNING_GAIN: 0.05,
            RewardSignal.ERROR_AVOIDANCE: 0.15,
            RewardSignal.USER_SATISFACTION: 0.1,
        }
    
    def record_decision(
        self,
        decision_id: str,
        context: Dict,
        action_chosen: str,
        alternatives: List[str],
        confidence: float,
    ) -> Decision:
        """
        Record a decision made by the agent.
        
        Args:
            decision_id: Unique decision ID.
            context: Decision context.
            action_chosen: What was selected.
            alternatives: Other options.
            confidence: Confidence level (0-1).
            
        Returns:
            The recorded Decision.
        """
        decision = Decision(
            decision_id=decision_id,
            context=context,
            action_chosen=action_chosen,
            alternatives=alternatives,
            confidence=confidence,
            timestamp=datetime.now(),
        )
        
        self.decisions[decision_id] = decision
        return decision
    
    def add_reward(
        self,
        decision_id: str,
        signal_type: RewardSignal,
        value: float,
        reason: str = "",
    ):
        """
        Add a reward signal to a decision.
        
        Args:
            decision_id: The decision being rewarded.
            signal_type: Type of reward.
            value: Reward value (-1.0 to 1.0).
            reason: Explanation.
        """
        if decision_id not in self.decisions:
            return
        
        decision = self.decisions[decision_id]
        weight = self.reward_weights.get(signal_type, 0.1)
        
        reward = Reward(
            signal_type=signal_type,
            value=max(-1.0, min(1.0, value)),
            weight=weight,
            reason=reason,
        )
        
        decision.rewards.append(reward)
    
    def create_policy(
        self,
        policy_id: str,
        description: str,
        context_conditions: Dict,
        action_distribution: Dict[str, float],
    ) -> Policy:
        """
        Create a new policy.
        
        Args:
            policy_id: Unique policy ID.
            description: What the policy does.
            context_conditions: When to apply.
            action_distribution: action → probability
            
        Returns:
            The created Policy.
        """
        # Normalize action distribution
        total = sum(action_distribution.values())
        if total > 0:
            normalized = {a: p / total for a, p in action_distribution.items()}
        else:
            normalized = action_distribution
        
        policy = Policy(
            policy_id=policy_id,
            description=description,
            context_conditions=context_conditions,
            action_distribution=normalized,
            success_history=[],
        )
        
        self.policies[policy_id] = policy
        return policy
    
    def update_policy_with_reward(self, policy_id: str, reward: float):
        """
        Update policy based on received reward.
        
        Args:
            policy_id: Policy to update.
            reward: Reward signal (0-1).
        """
        if policy_id not in self.policies:
            return
        
        policy = self.policies[policy_id]
        policy.success_history.append(reward)
        policy.application_count += 1
        
        # Update action distribution (policy gradient)
        avg_reward = policy.average_reward()
        for action in policy.action_distribution:
            if reward > avg_reward:
                # Increase probability of this action
                policy.action_distribution[action] *= (1 + self.learning_rate * 0.1)
            else:
                # Decrease probability
                policy.action_distribution[action] *= (1 - self.learning_rate * 0.05)
        
        # Renormalize
        total = sum(policy.action_distribution.values())
        if total > 0:
            policy.action_distribution = {
                a: p / total for a, p in policy.action_distribution.items()
            }
    
    def add_experience(
        self,
        state: Dict,
        action: str,
        reward: float,
        next_state: Dict,
        done: bool = False,
    ):
        """
        Add experience to replay buffer.
        
        Args:
            state: Current state.
            action: Action taken.
            reward: Reward received.
            next_state: Resulting state.
            done: Is episode done?
        """
        experience = ExperienceEntry(
            state=state,
            action=action,
            reward=max(-1.0, min(1.0, reward)),
            next_state=next_state,
            done=done,
        )
        
        self.experience_replay.append(experience)
        
        # Keep only recent experiences (memory limit)
        if len(self.experience_replay) > 1000:
            self.experience_replay = self.experience_replay[-1000:]
    
    def learn_from_experience(self, batch_size: int = 32):
        """
        Learn from stored experiences (experience replay).
        
        Args:
            batch_size: Number of experiences to sample.
        """
        if len(self.experience_replay) < batch_size:
            return
        
        # Sample random batch
        batch = random.sample(self.experience_replay, batch_size)
        
        for experience in batch:
            # Compute Q-value update
            state_hash = hash(str(sorted(experience.state.items())))
            state_action = (str(state_hash), experience.action)
            
            # Current Q-value
            old_q = self.q_values.get(state_action, 0.0)
            
            # Max Q-value for next state
            next_state_hash = hash(str(sorted(experience.next_state.items())))
            max_next_q = 0.0
            for action in set(e.action for e in batch):
                next_state_action = (str(next_state_hash), action)
                max_next_q = max(max_next_q, self.q_values.get(next_state_action, 0.0))
            
            # Q-learning update
            if experience.done:
                new_q = experience.reward
            else:
                new_q = experience.reward + (self.discount_factor * max_next_q)
            
            # Update Q-value with learning rate
            updated_q = old_q + self.learning_rate * (new_q - old_q)
            self.q_values[state_action] = updated_q
    
    def get_best_policy(self) -> Optional[Tuple[str, Policy]]:
        """
        Get the best performing policy.
        
        Returns:
            (policy_id, policy) or None.
        """
        if not self.policies:
            return None
        
        best_id = max(self.policies, key=lambda p: self.policies[p].compute_value())
        return (best_id, self.policies[best_id])
    
    def get_learning_progress(self) -> Dict:
        """Get progress of learning."""
        if not self.decisions:
            return {
                "total_decisions": 0,
                "avg_reward": 0.0,
                "best_decision_reward": 0.0,
                "worst_decision_reward": 0.0,
            }
        
        decisions_with_rewards = [
            d for d in self.decisions.values() if d.rewards
        ]
        
        if not decisions_with_rewards:
            return {
                "total_decisions": len(self.decisions),
                "decisions_with_rewards": 0,
                "avg_reward": 0.0,
            }
        
        rewards = [d.compute_total_reward() for d in decisions_with_rewards]
        
        return {
            "total_decisions": len(self.decisions),
            "decisions_with_rewards": len(decisions_with_rewards),
            "avg_reward": sum(rewards) / len(rewards),
            "best_decision_reward": max(rewards),
            "worst_decision_reward": min(rewards),
            "std_dev": (sum((r - (sum(rewards) / len(rewards))) ** 2 for r in rewards) / len(rewards)) ** 0.5,
        }
    
    def get_policy_statistics(self) -> Dict:
        """Get policy performance statistics."""
        if not self.policies:
            return {
                "total_policies": 0,
                "avg_policy_value": 0.0,
                "best_policy_value": 0.0,
            }
        
        policies = self.policies.values()
        values = [p.compute_value() for p in policies]
        
        return {
            "total_policies": len(self.policies),
            "avg_policy_value": sum(values) / len(values),
            "best_policy_value": max(values),
            "worst_policy_value": min(values),
            "experience_replay_size": len(self.experience_replay),
            "q_values_learned": len(self.q_values),
        }
    
    def export_learning_report(self, filepath: str):
        """
        Export reinforcement learning report to JSON.
        
        Args:
            filepath: Output file path.
        """
        best_policy = self.get_best_policy()
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "learning_progress": self.get_learning_progress(),
            "policy_statistics": self.get_policy_statistics(),
            "best_policy": {
                "id": best_policy[0],
                "description": best_policy[1].description,
                "value": best_policy[1].compute_value(),
                "avg_reward": best_policy[1].average_reward(),
                "applications": best_policy[1].application_count,
            } if best_policy else None,
            "reward_weights": {
                signal.value: weight
                for signal, weight in self.reward_weights.items()
            },
            "hyperparameters": {
                "learning_rate": self.learning_rate,
                "discount_factor": self.discount_factor,
            },
        }
        
        with open(filepath, "w") as f:
            json.dump(report, f, indent=2)
