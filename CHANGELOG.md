# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/), and this project loosely adheres to Semantic Versioning as it progresses through development phases.

---

## [0.4.0] - 2026-06-29 — Phase 8: Django Database Models

### Completed Phase
- **Phase 8**: Django Database Models Design & Implementation

### Added
- `web_dashboard/dashboard/models.py`: Full ORM implementation replacing the placeholder stub.
  - `User` — Custom user model extending `AbstractUser` with RBAC roles (ADMIN, ANALYST) and required email field.
  - `AnalysisJob` — Tracks `.evtx` file upload lifecycle (PENDING → RUNNING → COMPLETED → FAILED) with `FileField`, status transitions (`mark_running()`, `mark_completed()`, `mark_failed()`), and computed `anomaly_rate` property.
  - `Anomaly` — Stores anomalous time windows with `anomaly_score`, `severity` (CRITICAL/HIGH/MEDIUM/LOW), `feature_data` JSONField, and `rag_explanation` (reserved for Phase 14).
  - `AuditLog` — Append-only compliance log with user, job, action, IP address, and timestamp fields. Uses `SET_NULL` on deletion to preserve audit trail.
- `web_dashboard/dashboard/managers.py`: Custom `UserManager` extending `BaseUserManager`.
  - `create_user()` — Enforces role assignment, normalizes email, defaults to ANALYST.
  - `create_superuser()` — Forces ADMIN role, `is_staff=True`, `is_superuser=True`.
- `web_dashboard/dashboard/admin.py`: Full Django admin registrations for all 4 models.
  - `UserAdmin` — Extends Django's built-in `UserAdmin` with role field integration.
  - `AnalysisJobAdmin` — Status filtering, readonly timestamps, collapsible result fields.
  - `AnomalyAdmin` — Severity-based filtering, collapsible feature data and RAG explanation.
  - `AuditLogAdmin` — Read-only enforcement via `has_add/change/delete_permission = False`.
- `web_dashboard/dashboard/apps.py`: `DashboardConfig` with `BigAutoField` default and proper app label.
- `web_dashboard/dashboard/migrations/0001_initial.py`: Auto-generated initial migration creating all 4 tables and 5 composite indexes.

### Files Modified
- `web_dashboard/dashboard/models.py` — Replaced stub with full implementation (536 lines).
- `web_dashboard/dashboard/admin.py` — Replaced stub with full implementation (256 lines).
- `web_dashboard/web_dashboard/settings.py` — Added `AUTH_USER_MODEL`, `DashboardConfig`, `MEDIA_ROOT/MEDIA_URL`, crispy forms config, login redirects.

### Files Created
- `web_dashboard/dashboard/managers.py` — Custom UserManager (131 lines).
- `web_dashboard/dashboard/apps.py` — DashboardConfig (30 lines).
- `web_dashboard/dashboard/migrations/__init__.py` — Migration package init.
- `web_dashboard/dashboard/migrations/0001_initial.py` — Initial migration (124 lines).

### Architecture Changes
- No architectural changes. Django models are the planned persistence layer per `DATABASE_DESIGN.md`.
- `AUTH_USER_MODEL` set to `dashboard.User` — must remain set before any migrations are run.

### Database Changes
- **4 tables created**: `dashboard_user`, `dashboard_analysisjob`, `dashboard_anomaly`, `dashboard_auditlog`.
- **5 composite indexes**: `idx_job_status_uploaded`, `idx_anomaly_severity_score`, `idx_anomaly_job_severity`, `idx_audit_action_created`, `idx_audit_user_created`.
- SQLite migrations applied successfully.

### API Changes
- None. No new endpoints added in this phase.

### ML Changes
- None. Models store ML results received via HTTP from Flask.

### Security Changes
- Custom `UserManager` enforces role assignment on all user creation paths.
- `AuditLogAdmin` is fully read-only (no add, change, or delete).
- `AuditLog.user` uses `SET_NULL` to preserve logs after user deletion.

### Documentation Updated
- `PROJECT_CONTEXT.md` — Version bump to v0.4.0, Phase 8 moved to completed, Django pipeline status updated.
- `ROADMAP.md` — Phase 8 milestones marked complete, moved to "Completed — Awaiting Approval".
- `CHANGELOG.md` — This entry.

### Dependencies Added
- `django-crispy-forms` — Required by `INSTALLED_APPS` (already in `requirements.txt`).
- `crispy-bootstrap5` — Required by `INSTALLED_APPS` (already in `requirements.txt`).

### Summary
The Django persistence layer is now fully implemented. All four database models (`User`, `AnalysisJob`, `Anomaly`, `AuditLog`) are production-ready with proper indexes, relationships, lifecycle methods, and admin interface. The schema matches `DATABASE_DESIGN.md` exactly.

### Known Issues
- SQLite is used for development. Production deployments require PostgreSQL migration.
- `requirements.txt` pins older Django/crispy versions than those actually installed. Should be reconciled during a future dependency audit.

### Future Work
- Phase 9: Django Authentication & Role-Based Access Control (Login, Logout, RBAC enforcement).

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
