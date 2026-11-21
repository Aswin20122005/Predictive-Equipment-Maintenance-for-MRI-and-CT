import pytest

from backend.data.data_loader import get_telemetry
from backend.models.anomaly_detection import compute_baseline, full_anomaly_report, reference_records
from backend.models.thresholds import check_thresholds, threshold_tier


def test_reading_inside_normal_range_is_not_flagged():
    assert check_thresholds({"helium_pressure_psi": 14.5}, "MRI") == []


@pytest.mark.parametrize(
    "value, status, direction",
    [
        (13.5, "WARNING", "LOW"),
        (12.0, "CRITICAL", "LOW"),
        (15.5, "WARNING", "HIGH"),
        (16.5, "CRITICAL", "HIGH"),
    ],
)
def test_helium_pressure_limits(value, status, direction):
    [breach] = check_thresholds({"helium_pressure_psi": value}, "MRI")
    assert (breach["status"], breach["direction"]) == (status, direction)


def test_limits_only_apply_to_the_right_machine_type():
    assert check_thresholds({"helium_pressure_psi": 5}, "CT") == []
    assert check_thresholds({"internal_temp_celsius": 35}, "CT")[0]["status"] == "CRITICAL"


def test_non_numeric_readings_are_ignored():
    assert check_thresholds({"helium_pressure_psi": "n/a"}, "MRI") == []


@pytest.mark.parametrize(
    "statuses, tier",
    [([], 0), (["WARNING"], 1), (["WARNING"] * 3, 2), (["WARNING", "CRITICAL"], 3)],
)
def test_threshold_tier(statuses, tier):
    assert threshold_tier([{"status": s} for s in statuses]) == tier


def test_baseline_excludes_the_last_week():
    records = [{"helium_pressure_psi": 14.5}] * 23 + [{"helium_pressure_psi": 12.0}] * 7
    assert len(reference_records(records)) == 23
    assert compute_baseline(records, "MRI")["helium_pressure_psi"]["mean"] == pytest.approx(14.5)


def test_short_history_uses_all_records():
    records = [{"helium_pressure_psi": 14.0}] * 10
    assert reference_records(records) == records


def test_degrading_mri_is_flagged_in_the_latest_reading():
    report = full_anomaly_report(get_telemetry("MRI_01"), "MRI")
    flagged = {f["parameter"] for f in report["summary"]["latest_flags"]}
    assert "helium_pressure_psi" in flagged
    assert len(report["chart_data"]) == 30
