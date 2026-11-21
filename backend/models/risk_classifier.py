from typing import Dict, List, Any, Optional
from datetime import datetime

from backend.models.thresholds import check_thresholds, threshold_tier

RISK_TIERS = {
    0: {"code": "NORMAL",               "label": "Normal",               "emoji": "🟢", "color": "#34c759"},
    1: {"code": "MONITOR",              "label": "Monitor",              "emoji": "🟡", "color": "#ff9f0a"},
    2: {"code": "SCHEDULE_MAINTENANCE", "label": "Schedule Maintenance", "emoji": "🔴", "color": "#ff3b30"},
    # FIX: was "#6b7280" (gray) — CRITICAL must be visually distinct (purple)
    3: {"code": "CRITICAL",             "label": "Critical",             "emoji": "⚫", "color": "#af52de"},
}

FAILURE_DESCRIPTIONS = {
    "cryogen_leak":      "Cryogen Leak / Helium Quench Risk",
    "gradient_fault":    "Gradient Coil Failure",
    "rf_fault":          "RF Coil Degradation",
    "calibration_drift": "Detector Calibration Drift",
    "tube_burnout":      "X-Ray Tube Burnout",
    "rotation_fault":    "Gantry Rotation Fault",
    "thermal_fault":     "Thermal / Cooling System Failure",
    "electrical_fault":  "Electrical Fault",
    "None":              "No Failure Predicted",
    None:                "No Failure Predicted",
}


def classify_risk(
    latest_record: Dict,
    anomaly_summary: Dict,
    cost_row: Dict,
    machine_type: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Classify risk for a machine.

    Two signals are combined and the more severe one wins (a missed failure costs far
    more than an unnecessary inspection):
    - the dataset's pre-labelled risk_tier
    - a tier computed from the live readings vs the manufacturer limits (thresholds.py)
    """
    tier_raw = latest_record.get("risk_tier", 0)
    try:
        dataset_tier = int(float(tier_raw)) if tier_raw is not None else 0
    except (TypeError, ValueError):
        dataset_tier = 0
    dataset_tier = max(0, min(3, dataset_tier))

    machine_type = machine_type or latest_record.get("machine_type")
    breaches = check_thresholds(latest_record, machine_type) if machine_type else []
    sensor_tier = threshold_tier(breaches)
    tier = max(dataset_tier, sensor_tier)

    tier_info = RISK_TIERS[tier]
    failure_type = str(latest_record.get("predicted_failure_type") or "None")
    failure_desc = FAILURE_DESCRIPTIONS.get(failure_type, failure_type)

    days_raw = latest_record.get("predicted_days_to_failure")
    try:
        days = int(float(days_raw)) if days_raw is not None else 999
    except (TypeError, ValueError):
        days = 999

    conf_raw = latest_record.get("confidence_score", 0.5)
    try:
        confidence = float(conf_raw) if conf_raw is not None else 0.5
    except Exception:
        confidence = 0.5

    # Cost impact from dataset
    cost_impact = None
    if cost_row:
        cost_impact = {
            "preventive_cost_inr":       int(cost_row.get("preventive_cost_inr") or 0),
            "emergency_repair_cost_inr": int(cost_row.get("emergency_repair_cost_inr") or 0),
            "lost_revenue_per_day_inr":  int(cost_row.get("lost_revenue_per_day_inr") or 0),
            "downtime_days":             float(cost_row.get("downtime_days") or 0),
            "total_breakdown_cost_inr":  int(cost_row.get("total_breakdown_cost_inr") or 0),
            "net_saving_inr":            int(cost_row.get("net_saving_inr") or 0),
        }

    reasoning = _build_reasoning(latest_record, tier, days, anomaly_summary)

    return {
        "risk_tier":            tier,
        "dataset_tier":         dataset_tier,
        "sensor_tier":          sensor_tier,
        "threshold_breaches":   breaches,
        "risk_code":            tier_info["code"],
        "risk_label":           tier_info["label"],
        "risk_emoji":           tier_info["emoji"],
        "risk_color":           tier_info["color"],
        "confidence":           round(confidence, 2),
        "failure_type":         failure_type,
        "failure_description":  failure_desc,
        "days_to_failure":      days,
        "reasoning":            reasoning,
        "requires_action":      tier >= 2,
        "requires_suspension":  tier >= 3,
        "cost_impact":          cost_impact,
        "flagged_parameters":   anomaly_summary.get("latest_flags", []),
        "anomaly_count_last7d": anomaly_summary.get("total_anomaly_days_last7d", 0),
        "assessed_at":          datetime.now().isoformat(),
    }

def _build_reasoning(record: Dict, tier: int, days: int, anomaly_summary: Dict) -> str:
    parts = []
    if tier == 0:
        parts.append("All sensor parameters within baseline operating range.")
    elif tier == 1:
        parts.append("Anomaly detected — not yet urgent, continue monitoring.")
    elif tier == 2:
        parts.append(f"Predicted failure within {days} days — schedule preventive maintenance immediately.")
    elif tier == 3:
        parts.append("Failure imminent — suspend use and escalate to emergency repair.")

    helium = record.get("helium_pressure_psi")
    if helium is not None:
        try:
            h = float(helium)
            if h < 13:
                parts.append(f"Helium pressure critically low: {h:.2f} PSI (critical min 12).")
            elif h < 14:
                parts.append(f"Helium pressure warning: {h:.2f} PSI (normal ≥ 14).")
        except Exception:
            pass

    cryo = record.get("cryogen_level_percent")
    if cryo is not None:
        try:
            c = float(cryo)
            if c < 90:
                parts.append(f"Cryogen level at {c:.1f}% (critical min 85%).")
        except Exception:
            pass

    tube_heat = record.get("tube_heat_unit_percent")
    if tube_heat is not None:
        try:
            t = float(tube_heat)
            if t > 70:
                parts.append(f"X-ray tube heat units at {t:.1f}% (critical max 80%).")
        except Exception:
            pass

    drift = record.get("detector_calibration_drift_score")
    if drift is not None:
        try:
            d = float(drift)
            if d > 1.2:
                parts.append(f"Detector calibration drift score {d:.3f} (critical max 1.5).")
        except Exception:
            pass

    n_anom = anomaly_summary.get("total_anomaly_days_last7d", 0)
    if n_anom > 0:
        parts.append(f"{n_anom} anomaly day(s) detected in last 7 days (Z-score + Isolation Forest).")

    return " ".join(parts) if parts else "Assessment complete."
