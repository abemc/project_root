import json
import os
from datetime import datetime
from rag_agent_config import RAGAgentConfig

AGG_PATH = os.path.join(os.getcwd(), 'results', 'human_metrics_aggregated.json')


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


def apply_reward_adjustments(
    agg_path: str = AGG_PATH,
    min_entries: int = 20,
    min_csat: float = 3.2,
    min_adoption_rate: float = 0.30,
    min_nps: float = 0.0,
):
    """Simple heuristic: increase weight for metrics with higher mean.

    This is a safe, explainable placeholder. It reads aggregated metrics and
    updates `reward_weights` in `rag_agent_config.json` proportionally.
    """
    if not os.path.exists(agg_path):
        return {'status': 'missing_agg'}
    with open(agg_path, 'r', encoding='utf-8') as f:
        agg = json.load(f)

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
            'reasons': reasons,
            'summary': {
                'total_entries': agg.get('total_entries'),
                'csat_mean': agg.get('csat_mean'),
                'nps_mean': agg.get('nps_mean'),
                'adoption_rate': agg.get('adoption_rate'),
            },
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
    weights = {
        'csat': round(0.5 + csat_norm, 3),
        'nps': round(0.5 + nps_norm, 3),
        'adoption': round(0.5 + adoption_norm, 3)
    }

    cfg = RAGAgentConfig()
    conf = cfg.load_config()
    conf['reward_weights'] = weights
    cfg.save_config(conf)
    payload = {
        'timestamp': datetime.now().isoformat(),
        'status': 'ok',
        'weights': weights,
        'summary': {
            'total_entries': agg.get('total_entries'),
            'csat_mean': agg.get('csat_mean'),
            'nps_mean': agg.get('nps_mean'),
            'adoption_rate': agg.get('adoption_rate'),
        },
    }
    _append_gate_log(payload)
    return payload
