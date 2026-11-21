# MediWatch: Predictive Equipment Maintenance 🏥
## GKM_11 · GLITCHCON 2.0 · Team FASTENERS

> A maintenance agent for MRI and CT scanners: it spots failing sensors from telemetry, rates each machine's risk, opens a vendor ticket, moves affected patient scans, and alerts the radiology team, with the preventive vs breakdown cost alongside.

---

## How it works

```
30-day telemetry (MRI_01, CT_01)
    ↓
Anomaly detection
  • Z-scores against a baseline built from the period BEFORE the last week
  • Isolation Forest fitted on that same reference period
  • 7-day trend per critical sensor
    ↓
Risk classification  →  🟢 Normal / 🟡 Monitor / 🔴 Schedule Maintenance / ⚫ Critical
  • dataset risk label  +  live readings vs manufacturer limits (baselines.json)
  • the more severe of the two wins
    ↓ (if 🔴 or ⚫, and no ticket is already open)
contact_service_vendor()   →  ticket with Siemens (MRI) or GE (CT)
reschedule_appointment()   →  move up to 3 affected patient scans
notify_engineering_team()  →  alert with preventive vs breakdown cost
```

The agent is a plain Python pipeline (`backend/agent/agent.py`). Each step is a "tool" function, so it can be wired into an LLM agent framework later. Repeated runs are idempotent: while a machine has an open ticket, no more patients are moved and no duplicate alerts are sent.

## Tech stack

| Layer | Technology |
| --- | --- |
| Anomaly detection | Z-score + Isolation Forest (scikit-learn, pandas) |
| Risk classification | Rule-based: dataset label combined with manufacturer limit checks |
| Backend | FastAPI (Python) |
| Frontend | Vue 3 + Vite + Tailwind CSS + SVG charts |
| Data | JSON extracted from `GKM11_Predictive_Maintenance_Dataset.xlsx` |
| Quality | pytest, flake8, black, GitHub Actions |

---

## Quick start

```bash
./start.sh
```

This installs dependencies and starts the API on http://localhost:8000 (docs at `/docs`) and the dashboard on http://localhost:5173.

Or start them separately, **from the project root**:

```bash
# Backend
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload --port 8000

# Frontend
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api to :8000)
```

### Production (single server)

```bash
cd frontend && npm run build && cd ..
uvicorn backend.main:app --host 0.0.0.0 --port 8000   # serves the built dashboard at /
```

---

## API

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/health` | Health check |
| GET | `/api/dashboard` | Full state for all machines |
| GET | `/api/telemetry/{machine_id}?days=30` | Telemetry (days 1–365) |
| GET | `/api/telemetry/{machine_id}/latest` | Latest reading |
| GET | `/api/anomalies/{machine_id}` | Anomaly report (z-scores, Isolation Forest, trends) |
| GET | `/api/risk/{machine_id}` | Risk tier with dataset tier, sensor tier and limit breaches |
| GET | `/api/chart/{machine_id}/{sensor}` | One sensor with its baseline ±2σ band |
| GET | `/api/schedule[/{machine_id}]` | Patient appointments |
| GET | `/api/vendors` | Vendor directory |
| GET | `/api/cost[/{machine_id}]` | Preventive vs breakdown cost |
| POST | `/api/agent/run/{machine_id}` | Run the agent for one machine |
| POST | `/api/agent/run-all` | Run the agent for all machines |
| GET | `/api/agent/logs` | Tickets, reschedules and notifications |
| DELETE | `/api/agent/logs` | Reset agent state (for demos) |

Unknown machines or sensors return `404` with the list of valid values.

---

## Dataset
The app uses data from `GKM11_Predictive_Maintenance_Dataset.xlsx`, exported to JSON in `backend/data/`:
- **MRI_01**: 30-day telemetry with a cryogen leak developing (escalates to ⚫ Critical on day 30)
- **CT_01**: 30-day telemetry with calibration drift and tube wear (escalates to ⚫ Critical on day 30)
- **Baselines**: normal ranges and critical limits for 20 sensor parameters
- **Vendors**: Siemens Healthineers and GE Healthcare Biomedical
- **Schedule**: 20 patient appointments (10 per machine, 7-day window)
- **Cost impact**: preventive vs breakdown cost at each risk tier

---

## Development

```bash
pip install -r requirements-dev.txt
pytest                      # 39 tests: thresholds, anomalies, risk, agent, API
flake8 backend tests
black --check backend tests
```

## Project structure

```
├── backend/
│   ├── main.py                 # FastAPI app and routes
│   ├── agent/agent.py          # maintenance agent and its tools
│   ├── models/
│   │   ├── anomaly_detection.py
│   │   ├── thresholds.py       # manufacturer limit checks
│   │   └── risk_classifier.py
│   └── data/                   # JSON dataset + loader
├── frontend/                   # Vue 3 dashboard
├── tests/                      # pytest suite
└── start.sh
```
