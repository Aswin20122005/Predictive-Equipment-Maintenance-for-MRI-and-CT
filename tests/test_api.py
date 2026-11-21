import pytest
from fastapi.testclient import TestClient

from backend.agent.agent import reset_agent_state
from backend.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_agent():
    reset_agent_state()


def test_health():
    assert client.get("/api/health").json()["status"] == "ok"


def test_dashboard_lists_both_machines_with_risk():
    machines = client.get("/api/dashboard").json()["machines"]
    assert {m["machine_id"] for m in machines} == {"MRI_01", "CT_01"}
    assert all("sensor_tier" in m["risk"] for m in machines)


@pytest.mark.parametrize("days, expected", [(1, 1), (7, 7), (30, 30), (365, 30)])
def test_telemetry_days(days, expected):
    body = client.get(f"/api/telemetry/MRI_01?days={days}").json()
    assert body["count"] == len(body["records"]) == expected


@pytest.mark.parametrize("days", [0, -5, 1000])
def test_telemetry_rejects_bad_days(days):
    assert client.get(f"/api/telemetry/MRI_01?days={days}").status_code == 422


@pytest.mark.parametrize(
    "path",
    ["/api/telemetry/XYZ", "/api/anomalies/XYZ", "/api/risk/XYZ", "/api/schedule/XYZ", "/api/cost/XYZ"],
)
def test_unknown_machine_is_404(path):
    res = client.get(path)
    assert res.status_code == 404
    assert "MRI_01" in res.json()["detail"]


def test_chart_returns_baseline_band():
    point = client.get("/api/chart/MRI_01/helium_pressure_psi").json()["data"][0]
    assert point["lower"] < point["mean"] < point["upper"]


def test_chart_unknown_sensor_is_404():
    assert client.get("/api/chart/MRI_01/bogus").status_code == 404


def test_agent_run_and_reset():
    assert client.post("/api/agent/run/CT_01").status_code == 200
    assert len(client.get("/api/agent/logs").json()["vendor_tickets"]) == 1
    cleared = client.delete("/api/agent/logs").json()
    assert cleared["vendor_tickets"] == []


def test_run_all_covers_every_machine():
    assert set(client.post("/api/agent/run-all").json()["results"]) == {"MRI_01", "CT_01"}
