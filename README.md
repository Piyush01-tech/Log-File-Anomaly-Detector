# AI-Based Windows Event Log Anomaly Detection System

> **A production-quality hybrid Flask-Django system for detecting anomalous behavior in Windows Event Logs using Isolation Forest.**

---

## Architecture

```
EVTX Files → Parser → Feature Engineering → Isolation Forest
           → Flask Inference API → Django Dashboard → SQLite
```

## Tech Stack

| Layer | Technology |
|---|---|
| ML Inference API | Flask 3.0 |
| Frontend Dashboard | Django 5.0 |
| ML Algorithm | Isolation Forest (scikit-learn) |
| EVTX Parsing | python-evtx |
| Model Persistence | joblib |
| Database | SQLite (PostgreSQL-ready) |
| Charts | Chart.js |
| UI Framework | Bootstrap 5 |

## Project Structure

```
Log-File-Anomaly-Detector/
├── data/
│   ├── raw_logs/          ← Drop .evtx files here
│   └── processed/         ← Auto-generated CSVs
├── ml_engine/             ← Flask microservice
│   ├── config.py
│   ├── logger.py
│   ├── parser.py
│   ├── feature_engineering.py
│   ├── train.py
│   ├── predict.py
│   ├── app.py
│   └── models/
└── web_dashboard/         ← Django project
    ├── manage.py
    ├── web_dashboard/     ← Settings, URLs, WSGI
    └── dashboard/         ← App: views, models, templates
```

## Quick Start

```bash
# 1. Clone and navigate
cd Log-File-Anomaly-Detector

# 2. Create virtual environment
python -m venv venv
venv\Scripts\activate          # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment
copy .env.example .env
# Edit .env with your values

# 5. Run Django dashboard (Terminal 1)
cd web_dashboard
python manage.py migrate
python manage.py runserver 8000

# 6. Run Flask ML engine (Terminal 2)
cd ml_engine
python app.py
```

## Phases

| Phase | Description | Status |
|---|---|---|
| 1 | Project Setup & Folder Structure | ✅ Complete |
| 2 | Dataset Collection | ⏳ Pending |
| 3 | EVTX Parser | ⏳ Pending |
| 4 | Feature Engineering | ⏳ Pending |
| 5 | Model Training | ⏳ Pending |
| 6 | Prediction Engine | ⏳ Pending |
| 7 | Flask REST API | ⏳ Pending |
| 8 | Django Dashboard | ⏳ Pending |
| 9 | Database Integration | ⏳ Pending |
| 10 | Charts & Visualization | ⏳ Pending |
| 11 | Authentication | ⏳ Pending |
| 12 | Report Generation | ⏳ Pending |
| 13 | Documentation | ⏳ Pending |

## Dataset

Source: [sbousseaden/EVTX-ATTACK-SAMPLES](https://github.com/sbousseaden/EVTX-ATTACK-SAMPLES)

## Monitored Event IDs

| Event ID | Description |
|---|---|
| 4624 | Successful Login |
| 4625 | Failed Login |
| 4672 | Admin Privilege Assigned |
| 4688 | Process Creation |
| 4697 | Service Installed |
| 4720 | User Created |
| 4728 | Group Membership Changed |
| 7045 | Suspicious Service Creation |
| 1102 | Audit Log Cleared |

## License

MIT — For educational and internship purposes.
