"""Check sensor readings against the manufacturer limits in baselines.json.

Each limit row has a normal band (Min/Max Normal) and hard limits (Critical Low/High).
The file was loaded by data_loader.get_baselines_by_machine() but never used.
"""

from typing import Dict, List

from backend.data.data_loader import get_baselines_by_machine


def check_thresholds(record: Dict, machine_type: str) -> List[Dict]:
    """Return one entry per monitored parameter that is outside its normal band.

    status is "CRITICAL" when the reading is at or beyond a critical limit, otherwise "WARNING".
    """
    breaches = []
    for limit in get_baselines_by_machine(machine_type):
        param = limit["Parameter"]
        try:
            value = float(record.get(param))
        except (TypeError, ValueError):
            continue
        lo, hi = limit["Min Normal"], limit["Max Normal"]
        crit_lo, crit_hi = limit["Critical Low"], limit["Critical High"]
        if lo <= value <= hi:
            continue
        too_low = value < lo
        critical = value <= crit_lo if too_low else value >= crit_hi
        breaches.append(
            {
                "parameter": param,
                "value": round(value, 4),
                "unit": limit.get("Unit"),
                "normal_range": [lo, hi],
                "critical_limit": crit_lo if too_low else crit_hi,
                "direction": "LOW" if too_low else "HIGH",
                "status": "CRITICAL" if critical else "WARNING",
            }
        )
    return breaches


def threshold_tier(breaches: List[Dict]) -> int:
    """Map limit breaches to the 0-3 risk scale.

    3 any critical breach · 2 three or more warnings · 1 any warning · 0 all normal
    """
    if any(b["status"] == "CRITICAL" for b in breaches):
        return 3
    if len(breaches) >= 3:
        return 2
    if breaches:
        return 1
    return 0
