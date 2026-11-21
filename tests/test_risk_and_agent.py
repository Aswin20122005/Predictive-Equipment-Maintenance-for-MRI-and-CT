import pytest

from backend.agent.agent import get_agent_logs, reset_agent_state, run_agent, tool_classify_risk
from backend.models.risk_classifier import classify_risk


@pytest.fixture(autouse=True)
def clean_agent():
    reset_agent_state()
    yield
    reset_agent_state()


def test_sensor_breach_raises_tier_above_dataset_label():
    record = {"risk_tier": 0, "helium_pressure_psi": 11.0}  # past the critical low of 12 PSI
    risk = classify_risk(record, {}, {}, "MRI")
    assert (risk["dataset_tier"], risk["sensor_tier"], risk["risk_tier"]) == (0, 3, 3)
    assert risk["requires_suspension"] is True
    assert "helium_pressure_psi" in risk["reasoning"]


def test_dataset_label_is_kept_when_sensors_look_normal():
    risk = classify_risk({"risk_tier": 2, "helium_pressure_psi": 14.5}, {}, {}, "MRI")
    assert risk["risk_tier"] == 2 and risk["sensor_tier"] == 0


def test_bad_tier_values_fall_back_to_normal():
    assert classify_risk({"risk_tier": "abc"}, {}, {}, "MRI")["dataset_tier"] == 0
    assert classify_risk({"risk_tier": 9}, {}, {}, "MRI")["dataset_tier"] == 3


def test_classify_risk_tool_includes_breaches():
    risk = tool_classify_risk("CT_01")
    assert risk["machine_id"] == "CT_01"
    assert any(b["parameter"] == "detector_calibration_drift_score" for b in risk["threshold_breaches"])


def test_agent_opens_ticket_reschedules_and_notifies_for_critical_machine():
    result = run_agent("MRI_01")
    assert result["vendor_ticket"]["existing"] is False
    assert 0 < len(result["reschedules"]) <= 3
    assert result["notification"] is not None


def test_second_run_takes_no_new_actions():
    run_agent("MRI_01")
    second = run_agent("MRI_01")
    logs = get_agent_logs()
    assert second["vendor_ticket"]["existing"] is True
    assert second["reschedules"] == [] and second["notification"] is None
    assert len(logs["vendor_tickets"]) == 1 and len(logs["notifications"]) == 1


def test_mri_goes_to_siemens_and_ct_to_ge():
    assert "Siemens" in run_agent("MRI_01")["vendor_ticket"]["ticket"]["vendor_name"]
    assert "GE" in run_agent("CT_01")["vendor_ticket"]["ticket"]["vendor_name"]
