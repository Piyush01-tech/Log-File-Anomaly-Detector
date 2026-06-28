# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project loosely adheres to Semantic Versioning as it progresses through development phases.

---

## [0.3.0] - 2026-06-28 — Phase 7B: Flask REST API

### Completed Phase
- **Phase 7B**: Flask REST API Implementation

### Added
- `ml_engine/app.py`: Full Flask REST API replacing the 15-line placeholder stub.
  - Application factory pattern (`create_app()`) for WSGI deployment compatibility.
  - Blueprint `api_v1` under `/api/v1` prefix for API versioning.
  - `GET /api/v1/health` — Liveness probe with model load status and version.
  - `POST /api/v1/analyze` — Full ML pipeline integration (parse → features → predict) accepting `file_path` and optional `job_id`.
  - `GET /api/v1/stats` — Model metadata (hyperparameters, training timestamp, feature count).
  - `SafeJSONEncoder` — Recursive sanitizer for numpy int64/float64, NaN, Infinity, datetime, and Path objects.
  - Global error handlers (404, 405, 500) returning structured JSON — never HTML error pages.
  - Graceful startup — app starts even if model is not trained; `/health` reports `models_loaded: false`, `/analyze` returns `503`.

### Files Modified
- `ml_engine/app.py` — Replaced stub with full implementation.

### Architecture Changes
- No architectural changes. Flask REST API is the planned HTTP interface wrapping the existing `AnalysisPipeline` (Phase 7A).
- `AnalysisPipeline` initialized once at startup and reused across requests.

### Database Changes
- None.

### API Changes
- Three endpoints now operational: `/health`, `/analyze`, `/stats`.
- Error responses standardized with `{"status": "error", "message": "..."}` schema.
- New status code: `503 Service Unavailable` when model is not loaded.

### ML Changes
- None. The Flask API wraps the existing pipeline without modifications.

### Security Changes
- None. Internal network deployment model unchanged. PSK auth remains a future enhancement.

### Documentation Updated
- `API_SPECIFICATION.md` — Complete rewrite with field tables, all status codes, startup instructions.
- `PROJECT_CONTEXT.md` — Version bump to v0.3.0, Phase 7B moved to completed, Flask pipeline status updated.
- `ROADMAP.md` — Phase 7B milestones marked complete.
- `DEVELOPMENT_GUIDE.md` — Updated Flask startup instructions (removed "stubbed" note).
- `CHANGELOG.md` — This entry.

### Summary
The Flask ML Inference microservice is now fully operational. Django can invoke the ML pipeline via HTTP REST calls to analyze `.evtx` files, check model health, and query model statistics.

### Known Issues
- Synchronous processing: Large `.evtx` files may cause HTTP timeouts. Future mitigation via Celery async queue.
- No authentication on the Flask API (designed for internal network only).

### Future Work
- Phase 8: Django Database Models (User, AnalysisJob, Anomaly, AuditLog).

---

## [0.2.0] - Post-Phase 7A Refactoring

### Added
- `ml_engine/__init__.py`: Converted the ML engine into a proper Python package.
- `ml_engine/scaler.py`: Extracted `FeatureScaler` to decouple training from prediction.
- `ml_engine/pipeline.py`: Added `AnalysisPipeline` to orchestrate end-to-end single-file analysis in memory.
- Comprehensive Engineering Documentation Suite (README, Architecture, Roadmap, etc.).

### Changed
- Refactored all `ml_engine` modules to use relative imports instead of `sys.path` hacks.
- Updated module usage docstrings to reflect standard `python -m` invocation.

### Removed
- `FeatureScaler` class declaration removed from `train.py`.

---

## [0.1.0] - Phase 6 Completion

### Added
- Core Data Science Pipeline completed.
- `parser.py`: Implementation of `EVTXFileParser` and `EVTXBatchParser`.
- `feature_engineering.py`: Implementation of `EventFeatureBuilder` (15 MITRE-aligned features).
- `train.py`: Implementation of `AnomalyModelTrainer` using Isolation Forest.
- `predict.py`: Implementation of `AnomalyPredictor`.
- `web_dashboard`: Scaffolded Django application with stubbed models and views.
- `scripts/`: Utilities for dataset downloading and validation.

### Changed
- Project configuration unified into `ml_engine/config.py` driven by `.env`.

### Initial Release
- Setup of virtual environment, dependencies (`requirements.txt`), and `.gitignore`.
