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

---

## 🚧 Current Phase: Completed — Awaiting Approval

### Phase 7B: Flask REST API ✅
- [x] Implement `/health` endpoint.
- [x] Implement `/analyze` endpoint integrating `AnalysisPipeline`.
- [x] Implement `/stats` endpoint for model metadata.
- [x] Add basic request validation and error handling.


---

## 🔜 Near-Term Milestones (Web UI)

### Phase 8: Django Database Models
- [ ] Implement schema for `User`, `AnalysisJob`, `Anomaly`, and `AuditLog`.
- [ ] Generate and apply SQLite migrations.

### Phase 9: Django Authentication
- [ ] Setup login, logout, and password management.
- [ ] Implement Analyst and Super Admin roles.

### Phase 10: Upload & Analysis Workflow
- [ ] Create UI for uploading `.evtx` files.
- [ ] Implement `FlaskAPIClient` in Django to trigger analysis.
- [ ] Save results to the database upon API completion.

### Phase 11: Dashboard UI
- [ ] Build the main SOC view (Alerts table, KPI cards).
- [ ] Build incident detail pages.

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
