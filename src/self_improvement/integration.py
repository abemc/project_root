import json
import os
from datetime import datetime
from typing import Any, Dict, Optional, Tuple
from rag_agent_config import RAGAgentConfig

AGG_PATH = os.path.join(os.getcwd(), 'results', 'human_metrics_aggregated.json')
AI_AGG_PATH = os.path.join(os.getcwd(), 'results', 'ai_feedback_aggregated.json')
FEEDBACK_HISTORY_PATH = os.path.join(os.getcwd(), 'logs', 'feedback', 'feedback_history.jsonl')


def _append_gate_log(payload: dict):
    """Write RLHF gate decision logs without breaking the main flow."""
    try:
        log_path = os.path.join(os.getcwd(), 'logs', 'feedback', 'rlhf_gate.jsonl')
        os.makedirs(os.path.dirname(log_path), exist_ok=True)
        with open(log_path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(payload, ensure_ascii=False) + '\n')
    except Exception:
        pass


def _should_apply_reward_adjustments(
    summary: dict,
    min_entries: int = 20,
    min_csat: float = 3.2,
    min_adoption_rate: float = 0.30,
    min_nps: float = 0.0,
):
    """Guardrail to prevent unstable online RLHF updates on sparse/poor data."""
    total_entries = int(summary.get('total_entries') or 0)
    csat = summary.get('csat_mean')
    nps = summary.get('nps_mean')
    adoption = summary.get('adoption_rate')

    reasons = []
    if total_entries < min_entries:
        reasons.append(f"insufficient_entries:{total_entries}<{min_entries}")
    if isinstance(csat, (int, float)) and csat < min_csat:
        reasons.append(f"low_csat:{csat}<{min_csat}")
    if isinstance(adoption, (int, float)) and adoption < min_adoption_rate:
        reasons.append(f"low_adoption:{adoption}<{min_adoption_rate}")
    if isinstance(nps, (int, float)) and nps < min_nps:
        reasons.append(f"low_nps:{nps}<{min_nps}")

    return (len(reasons) == 0), reasons


def _load_json_if_exists(path: Optional[str]) -> Optional[Dict[str, Any]]:
    """Safely load JSON if a file exists."""
    if not path:
        return None
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None


def _as_float(value: Any) -> Optional[float]:
    """Convert value to float when possible."""
    try:
        if value is None:
            return None
        return float(value)
    except Exception:
        return None


def _blend_human_and_ai_summary(
    human: Dict[str, Any],
    ai: Optional[Dict[str, Any]],
    ai_weight: float = 0.35,
    min_ai_entries: int = 30,
    min_ai_confidence: float = 0.60,
) -> Tuple[Dict[str, Any], Dict[str, Any], str]:
    """Blend human metrics with AI feedback metrics for RLAIF.

    Returns:
        summary: blended summary compatible with RLHF weight update logic
        details: diagnostics for audit/debug
        source: one of human_only/human_ai_blended
    """
    human_entries = int(human.get('total_entries') or 0)
    human_csat = _as_float(human.get('csat_mean'))
    human_nps = _as_float(human.get('nps_mean'))
    human_adoption = _as_float(human.get('adoption_rate'))

    if not ai:
        return dict(human), {'ai_used': False, 'reason': 'missing_ai_summary'}, 'human_only'

    ai_entries = int(ai.get('total_entries') or 0)
    ai_confidence = _as_float(ai.get('confidence_mean'))
    ai_csat = _as_float(ai.get('csat_mean'))
    ai_nps = _as_float(ai.get('nps_mean'))
    ai_adoption = _as_float(ai.get('adoption_rate'))

    # Fallback mappings for common AI-evaluator schemas
    ai_quality = _as_float(ai.get('quality_mean'))
    if ai_csat is None and ai_quality is not None:
        # Convert quality(0-1) to CSAT-like scale(1-5)
        ai_csat = 1.0 + 4.0 * max(0.0, min(1.0, ai_quality))
    if ai_nps is None:
        ai_nps = _as_float(ai.get('recommendation_mean'))

    if ai_entries < min_ai_entries:
        return dict(human), {
            'ai_used': False,
            'reason': f'insufficient_ai_entries:{ai_entries}<{min_ai_entries}',
            'ai_entries': ai_entries,
        }, 'human_only'

    if ai_confidence is not None and ai_confidence < min_ai_confidence:
        return dict(human), {
            'ai_used': False,
            'reason': f'low_ai_confidence:{ai_confidence}<{min_ai_confidence}',
            'ai_entries': ai_entries,
            'ai_confidence': ai_confidence,
        }, 'human_only'

    # Dynamic down-weighting when human/AI disagree strongly.
    effective_ai_weight = max(0.0, min(1.0, float(ai_weight)))
    disagreement = 0.0
    components = 0
    if human_csat is not None and ai_csat is not None:
        disagreement += abs(human_csat - ai_csat) / 4.0
        components += 1
    if human_adoption is not None and ai_adoption is not None:
        disagreement += abs(human_adoption - ai_adoption)
        components += 1
    if human_nps is not None and ai_nps is not None:
        disagreement += abs(human_nps - ai_nps) / 10.0
        components += 1
    if components > 0:
        avg_disagreement = disagreement / components
        damping = max(0.2, 1.0 - avg_disagreement)
        effective_ai_weight = round(effective_ai_weight * damping, 4)

    def blend(h: Optional[float], a: Optional[float]) -> Optional[float]:
        if h is None and a is None:
            return None
        if h is None:
            return a
        if a is None:
            return h
        return (1.0 - effective_ai_weight) * h + effective_ai_weight * a

    summary = {
        'total_entries': human_entries + ai_entries,
        'csat_mean': blend(human_csat, ai_csat),
        'nps_mean': blend(human_nps, ai_nps),
        'adoption_rate': blend(human_adoption, ai_adoption),
    }
    details = {
        'ai_used': True,
        'ai_entries': ai_entries,
        'ai_confidence': ai_confidence,
        'configured_ai_weight': ai_weight,
        'effective_ai_weight': effective_ai_weight,
        'human_entries': human_entries,
    }
    return summary, details, 'human_ai_blended'


def _apply_weight_delta_cap(
    current: Dict[str, Any],
    proposed: Dict[str, float],
    max_delta: float = 0.25,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Cap per-key absolute weight delta to reduce sudden policy shifts."""
    cap = max(0.0, float(max_delta))
    out: Dict[str, float] = {}
    details: Dict[str, Any] = {
        'enabled': True,
        'max_delta': cap,
        'clamped_keys': {},
    }

    for key, p_val in proposed.items():
        c_val = _as_float((current or {}).get(key))
        p = float(p_val)
        if c_val is None:
            out[key] = p
            continue

        low = c_val - cap
        high = c_val + cap
        clamped = min(max(p, low), high)
        out[key] = round(clamped, 3)
        if abs(clamped - p) > 1e-9:
            details['clamped_keys'][key] = {
                'from': round(c_val, 3),
                'proposed': round(p, 3),
                'applied': round(clamped, 3),
            }

    details['was_clamped'] = bool(details['clamped_keys'])
    return out, details


def _apply_value_tuning_bias(
    proposed: Dict[str, float],
    value_summary: Optional[Dict[str, Any]],
    min_items: int = 5,
    max_bias: float = 0.12,
) -> Tuple[Dict[str, float], Dict[str, Any]]:
    """Apply a small value-alignment bias to reward weights.

    Value tuning only nudges weights; it must not dominate the main metrics.
    """
    details: Dict[str, Any] = {
        'enabled': True,
        'applied': False,
        'min_items': int(min_items),
        'max_bias': float(max_bias),
        'dimension_scores': {},
        'weight_biases': {},
    }
    if not value_summary:
        details['reason'] = 'missing_value_summary'
        return dict(proposed), details

    counts = value_summary.get('signal_counts') or {}
    means = value_summary.get('signal_means') or {}
    if not means:
        details['reason'] = 'missing_signal_means'
        return dict(proposed), details

    def dim_avg(keys):
        vals = []
        min_count_seen = None
        for key in keys:
            if key not in means:
                continue
            count = int(counts.get(key) or 0)
            if count < min_items:
                continue
            vals.append(float(means[key]))
            min_count_seen = count if min_count_seen is None else min(min_count_seen, count)
        if not vals:
            return None, 0
        return sum(vals) / len(vals), int(min_count_seen or 0)

    dimension_map = {
        'csat': ['accuracy', 'clarity', 'transparency'],
        'adoption': ['helpfulness', 'clarity'],
        'nps': ['safety', 'neutrality', 'transparency'],
    }

    adjusted = dict(proposed)
    applied_any = False
    for weight_key, signal_keys in dimension_map.items():
        avg, supporting_count = dim_avg(signal_keys)
        if avg is None:
            continue
        details['dimension_scores'][weight_key] = {
            'signals': signal_keys,
            'mean': round(avg, 3),
            'supporting_count': supporting_count,
        }
        # Center around 0.5 and keep influence intentionally small.
        bias = max(-max_bias, min(max_bias, (avg - 0.5) * 2.0 * max_bias))
        if abs(bias) < 1e-9:
            continue
        adjusted[weight_key] = round(float(adjusted.get(weight_key, 0.0)) + bias, 3)
        details['weight_biases'][weight_key] = round(bias, 3)
        applied_any = True

    details['applied'] = applied_any
    if not applied_any and 'reason' not in details:
        details['reason'] = 'insufficient_supported_value_signals'
    return adjusted, details


def apply_reward_adjustments(
    agg_path: str = AGG_PATH,
    ai_agg_path: str = AI_AGG_PATH,
    feedback_history_path: str = FEEDBACK_HISTORY_PATH,
    min_entries: int = 20,
    min_csat: float = 3.2,
    min_adoption_rate: float = 0.30,
    min_nps: float = 0.0,
    ai_weight: float = 0.35,
    min_ai_entries: int = 30,
    min_ai_confidence: float = 0.60,
    auto_aggregate_ai: bool = True,
    enable_rlaif_delta_cap: bool = True,
    rlaif_max_weight_delta: float = 0.25,
    enable_value_tuning_bias: bool = True,
    value_tuning_min_items: int = 5,
    value_tuning_max_bias: float = 0.12,
):
    """Simple heuristic: increase weight for metrics with higher mean.

    This is a safe, explainable placeholder. It reads aggregated metrics and
    updates `reward_weights` in `rag_agent_config.json` proportionally.
    """
    if not os.path.exists(agg_path):
        return {'status': 'missing_agg'}
    with open(agg_path, 'r', encoding='utf-8') as f:
        human_agg = json.load(f)

    ai_agg = _load_json_if_exists(ai_agg_path)
    auto_ai_aggregate = None
    if ai_agg is None and auto_aggregate_ai:
        try:
            from src.self_improvement.rlaif_aggregator import aggregate_ai_feedback
            auto_ai_aggregate = aggregate_ai_feedback(
                feedback_history_path=feedback_history_path,
                output_path=ai_agg_path,
            )
            ai_agg = _load_json_if_exists(ai_agg_path)
        except Exception as e:
            auto_ai_aggregate = {'status': 'failed', 'error': str(e)}
    agg, blend_details, source = _blend_human_and_ai_summary(
        human=human_agg,
        ai=ai_agg,
        ai_weight=ai_weight,
        min_ai_entries=min_ai_entries,
        min_ai_confidence=min_ai_confidence,
    )

    should_apply, reasons = _should_apply_reward_adjustments(
        agg,
        min_entries=min_entries,
        min_csat=min_csat,
        min_adoption_rate=min_adoption_rate,
        min_nps=min_nps,
    )
    if not should_apply:
        payload = {
            'timestamp': datetime.now().isoformat(),
            'status': 'skipped',
            'agg_path': agg_path,
            'ai_agg_path': ai_agg_path,
            'feedback_history_path': feedback_history_path,
            'auto_ai_aggregate': auto_ai_aggregate,
            'source': source,
            'blend_details': blend_details,
            'reasons': reasons,
            'summary': {
                'total_entries': agg.get('total_entries'),
                'csat_mean': agg.get('csat_mean'),
                'nps_mean': agg.get('nps_mean'),
                'adoption_rate': agg.get('adoption_rate'),
            },
            'human_summary': {
                'total_entries': human_agg.get('total_entries'),
                'csat_mean': human_agg.get('csat_mean'),
                'nps_mean': human_agg.get('nps_mean'),
                'adoption_rate': human_agg.get('adoption_rate'),
            },
            'ai_summary': ai_agg or {},
        }
        _append_gate_log(payload)
        return payload

    csat = agg.get('csat_mean') or 0
    nps = agg.get('nps_mean') or 0
    adoption = agg.get('adoption_rate') or 0

    # normalize to 0-1
    csat_norm = (csat - 1) / 4 if csat else 0
    nps_norm = nps / 10 if nps else 0
    adoption_norm = adoption

    # simple weights proportional to norms (plus baseline)
    proposed_weights = {
        'csat': round(0.5 + csat_norm, 3),
        'nps': round(0.5 + nps_norm, 3),
        'adoption': round(0.5 + adoption_norm, 3)
    }

    value_tuning = {
        'enabled': bool(enable_value_tuning_bias),
        'applied': False,
        'reason': 'disabled',
    }
    value_summary = {}
    if enable_value_tuning_bias:
        try:
            from src.self_improvement.feedback_manager import FeedbackManager
            value_summary = FeedbackManager(storage_dir=os.path.dirname(feedback_history_path)).get_value_tuning_summary(min_rating=0.0)
            proposed_weights, value_tuning = _apply_value_tuning_bias(
                proposed=proposed_weights,
                value_summary=value_summary,
                min_items=value_tuning_min_items,
                max_bias=value_tuning_max_bias,
            )
        except Exception as e:
            value_tuning = {
                'enabled': True,
                'applied': False,
                'reason': f'error:{e}',
            }

    cfg = RAGAgentConfig()
    conf = cfg.load_config()
    current_weights = conf.get('reward_weights') if isinstance(conf, dict) else {}

    cap_details = {
        'enabled': bool(enable_rlaif_delta_cap and source == 'human_ai_blended'),
        'was_clamped': False,
        'clamped_keys': {},
        'max_delta': float(rlaif_max_weight_delta),
    }
    if enable_rlaif_delta_cap and source == 'human_ai_blended':
        weights, cap_details = _apply_weight_delta_cap(
            current=current_weights if isinstance(current_weights, dict) else {},
            proposed=proposed_weights,
            max_delta=rlaif_max_weight_delta,
        )
    else:
        weights = proposed_weights

    conf['reward_weights'] = weights
    cfg.save_config(conf)
    payload = {
        'timestamp': datetime.now().isoformat(),
        'status': 'ok',
        'agg_path': agg_path,
        'ai_agg_path': ai_agg_path,
        'feedback_history_path': feedback_history_path,
        'auto_ai_aggregate': auto_ai_aggregate,
        'source': source,
        'blend_details': blend_details,
        'value_tuning': value_tuning,
        'value_summary': value_summary,
        'weight_cap': cap_details,
        'proposed_weights': proposed_weights,
        'weights': weights,
        'summary': {
            'total_entries': agg.get('total_entries'),
            'csat_mean': agg.get('csat_mean'),
            'nps_mean': agg.get('nps_mean'),
            'adoption_rate': agg.get('adoption_rate'),
        },
        'human_summary': {
            'total_entries': human_agg.get('total_entries'),
            'csat_mean': human_agg.get('csat_mean'),
            'nps_mean': human_agg.get('nps_mean'),
            'adoption_rate': human_agg.get('adoption_rate'),
        },
        'ai_summary': ai_agg or {},
    }
    _append_gate_log(payload)
    return payload
