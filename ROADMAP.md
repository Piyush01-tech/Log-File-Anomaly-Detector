# Project Roadmap

The Log File Anomaly Detector is being built in distinct phases. This roadmap outlines the journey from initial conceptualization to a production-ready enterprise SOC platform.

---

## ✅ Completed Phases

- **Phase 1: Project Setup** 
  - Repository initialization, virtual environment, and dependency locking.
- **Phase 2: Dataset Collection** 
  - Scripts created (`download_dataset.py`, `validate_dataset.py`) to generate/download synthetic and malicious `.evtx` files.
- **Phase 3: EVTX Parser** 
  - Implemented `EVTXFileParser` to translate binary logs to DataFrames.
- **Phase 4: Feature Engineering** 
  - Developed `EventFeatureBuilder` to aggregate logs into 1-hour windows with 15 numerical features.
- **Phase 5: Model Training** 
  - Built `AnomalyModelTrainer` using Isolation Forest.
- **Phase 6: Prediction Engine** 
  - Built `AnomalyPredictor` to score incoming data against the trained baseline.
- **Phase 7A: ML Engine Refactoring** 
  - Packaged the `ml_engine`, decoupled `train.py` from `predict.py`, and introduced `AnalysisPipeline`.
- **Phase 7B: Flask REST API** 
  - Application factory, `/health`, `/analyze`, `/stats` endpoints, JSON serialization, error handling.
- **Phase 8: Django Database Models**
  - Implemented schema for `User`, `AnalysisJob`, `Anomaly`, and `AuditLog`.
  - Implemented custom `UserManager` with role enforcement.
  - Implemented Django admin registrations for all models.
  - Configured `AUTH_USER_MODEL` and `DashboardConfig`.
  - Generated and applied SQLite migrations.
- **Phase 9A: Django Authentication**
  - Implemented login, logout, and registration views.
  - Created authentication forms with crispy-bootstrap5.
  - Added "Remember Me" session control and AuditLog for LOGIN/LOGOUT events.
  - Created dark SOC-themed templates with Bootstrap 5.
  - Implemented auth-aware navigation, profile management, and password change.
  - Configured session security settings and CSRF protection.
- **Phase 9B: Django Role-Based Access Control**
  - Implemented Analyst and Super Admin permission enforcement (Django Groups).
  - Added view-level permission decorators and mixins (`rbac_mixins.py`, `rbac_decorators.py`).
  - Restricted admin panel access to ADMIN role (middleware + UserAdmin).
  - Implemented `setup_rbac` management command.
- **Phase 10: Upload & Analysis Workflow**
  - Created UI for uploading `.evtx` files.
  - Implemented `FlaskAPIClient` in Django to trigger analysis.
  - Saved results to the database upon API completion.
- **Phase 11A: Dashboard Foundation**
  - Implemented reusable layout with Sidebar and Breadcrumbs.
  - Enhanced Home page with stats and recent activity tables.
  - Created reusable UI components (empty states, loading states, stats cards).
  - Created dedicated user profile page.
- **Phase 11B: Dashboard Features**
  - Built the main SOC view (Alerts table with search, filter, pagination).
  - Built incident detail pages (single anomaly drill-down).
  - Added search and filter to Analysis History.
  - Created reusable template components (pagination, status/severity badges, filter bar).
  - Implemented role-specific dashboards (Admin: system-wide, Analyst: personal).
  - Added critical alert banner and recent alerts to home page.
  - Updated sidebar navigation with Alerts link.
  - Implemented responsive tables for mobile.
- **Phase 11C: UI/UX Redesign**
  - Overhauled CSS with a premium variable system for colors (dark/light themes).
  - Added JS interactivity for theme toggling via `localStorage`.
  - Modernized all pages with custom layout components for a professional cybersecurity layout.
- **Phase 12: Charts & Visualization**
  - Integrated Chart.js to visualize anomaly distributions over time.
  - Created backend JSON API for aggregating stats from DB.
  - Created modular JS framework for rendering charts with dynamic themes.

---

## 🔮 Futuristic Scope

These phases are planned for future major releases to evolve the platform into a fully automated, AI-driven SIEM and ensure production readiness at scale.

### Phase 13: RAG Knowledge Base Setup
- Set up Vector Database (e.g., ChromaDB).
- Ingest MITRE ATT&CK patterns and Windows Event ID definitions.

### Phase 14: RAG Explanation Layer
- Integrate LLM (OpenAI or local Ollama).
- Generate incident reports for High/Critical anomalies.

### Phase 15: Automated Reporting
- PDF generation for weekly/monthly SOC executive summaries.

### Phase 16: Admin & Settings
- System settings panel for tweaking ML thresholds from the UI.

### Phase 17: Deployment Infrastructure
- Dockerize Flask and Django into separate containers.
- Migrate from SQLite to PostgreSQL.
- Add Nginx for reverse proxying.

### Additional Stretch Goals
- **Live Ingestion**: Replace manual uploads with a REST endpoint that accepts streaming JSON from Windows Event Forwarding (WEF).
- **Asynchronous Queues**: Add Celery + Redis to handle concurrent analysis of massive log files without HTTP timeouts.
- **Model Feedback Loop**: Allow analysts to mark false positives in the UI, which are periodically fed back to retrain the Isolation Forest model.
