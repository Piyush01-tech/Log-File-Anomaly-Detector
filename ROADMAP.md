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

---

## 🚧 Current Phase: Completed — Awaiting Approval

### Phase 8: Django Database Models ✅
- [x] Implement schema for `User`, `AnalysisJob`, `Anomaly`, and `AuditLog`.
- [x] Implement custom `UserManager` with role enforcement.
- [x] Implement Django admin registrations for all models.
- [x] Configure `AUTH_USER_MODEL` and `DashboardConfig`.
- [x] Generate and apply SQLite migrations.

### Phase 9A: Django Authentication ✅
- [x] Implement login, logout, and registration views.
- [x] Create authentication forms with crispy-bootstrap5.
- [x] Add "Remember Me" session control.
- [x] Integrate AuditLog for LOGIN/LOGOUT events.
- [x] Create dark SOC-themed templates with Bootstrap 5.
- [x] Implement auth-aware navigation (navbar).
- [x] Add SessionSecurityMiddleware (idle timeout, security headers).
- [x] Implement profile management (name, email).
- [x] Implement password change with validation.
- [x] Configure session security settings and CSRF protection.

### Phase 9B: Django Role-Based Access Control ✅
- [x] Implement Analyst and Super Admin permission enforcement (Django Groups).
- [x] Add view-level permission decorators and mixins (`rbac_mixins.py`, `rbac_decorators.py`).
- [x] Restrict admin panel access to ADMIN role (middleware + UserAdmin).
- [x] Implement `setup_rbac` management command.

---

### Phase 10: Upload & Analysis Workflow ✅
- [x] Create UI for uploading `.evtx` files.
- [x] Implement `FlaskAPIClient` in Django to trigger analysis.
- [x] Save results to the database upon API completion.

### Phase 11A: Dashboard Foundation ✅
- [x] Implement reusable layout with Sidebar and Breadcrumbs.
- [x] Enhance Home page with stats and recent activity tables.
- [x] Create reusable UI components (empty states, loading states, stats cards).
- [x] Create dedicated user profile page.

### Phase 11B: Dashboard Features ✅
- [x] Build the main SOC view (Alerts table with search, filter, pagination).
- [x] Build incident detail pages (single anomaly drill-down).
- [x] Add search and filter to Analysis History.
- [x] Create reusable template components (pagination, status/severity badges, filter bar).
- [x] Implement role-specific dashboards (Admin: system-wide, Analyst: personal).
- [x] Add critical alert banner and recent alerts to home page.
- [x] Update sidebar navigation with Alerts link.
- [x] Implement responsive tables for mobile.

## 🔜 Near-Term Milestones (Web UI)

### Phase 11B: Dashboard Data ✅
- [x] Build the main SOC view (Alerts table).
- [x] Build incident detail pages.

### Phase 12: Charts & Visualization
- [ ] Integrate Chart.js to visualize anomaly distributions over time.

---

## 🧠 Mid-Term Milestones (AI Integration)

### Phase 13: RAG Knowledge Base Setup
- [ ] Set up Vector Database (e.g., ChromaDB).
- [ ] Ingest MITRE ATT&CK patterns and Windows Event ID definitions.

### Phase 14: RAG Explanation Layer
- [ ] Integrate LLM (OpenAI or local Ollama).
- [ ] Generate incident reports for High/Critical anomalies.

---

## 🚀 Long-Term Milestones (Production Readiness)

### Phase 15: Automated Reporting
- [ ] PDF generation for weekly/monthly SOC executive summaries.

### Phase 16: Admin & Settings
- [ ] System settings panel for tweaking ML thresholds from the UI.

### Phase 17: Deployment Infrastructure
- [ ] Dockerize Flask and Django into separate containers.
- [ ] Migrate from SQLite to PostgreSQL.
- [ ] Add Nginx for reverse proxying.

---

## 🔮 Future / Stretch Goals

- **Live Ingestion**: Replace manual uploads with a REST endpoint that accepts streaming JSON from Windows Event Forwarding (WEF).
- **Asynchronous Queues**: Add Celery + Redis to handle concurrent analysis of massive log files without HTTP timeouts.
- **Model Feedback Loop**: Allow analysts to mark false positives in the UI, which are periodically fed back to retrain the Isolation Forest model.
