# Project Context

**This document serves as the single source of truth for the project. All future AI assistants (Claude, GPT, Gemini, Cursor, Copilot) MUST read this file before generating any code or proposing architectural changes.**

---

## 🎯 Project Vision

To build a production-quality, enterprise-grade Security Operations Center (SOC) platform for analyzing Windows Event Logs (`.evtx`). The system bridges the gap between machine learning and traditional SIEMs by using an **Isolation Forest** anomaly detection model, eventually augmented by a **Retrieval-Augmented Generation (RAG)** layer to explain anomalies to security analysts in plain English.

---

## 📊 Current Status

- **Current Version**: `v0.10.1` (RC Stabilization)
- **Implemented Modules**: `ml_engine` (Parsing, Feature Engineering, Training, Prediction, Pipeline orchestrator, Flask REST API), `web_dashboard` (Django ORM models, custom managers, admin registrations, SQLite migrations, authentication, RBAC/permissions, Upload workflow, API client, Dashboard Foundation with Sidebar layout, reusable templates, Alerts system with search/filter/pagination, Incident detail pages).

### Completed Phases
- **Phase 1**: Project Setup & Repository Initialization
- **Phase 2**: Dataset Collection (Scripts for synthetic/malicious `.evtx` generation)
- **Phase 3**: EVTX Parser Implementation
- **Phase 4**: Feature Engineering Pipeline
- **Phase 5**: Model Training (Isolation Forest)
- **Phase 6**: Prediction Engine
- **Phase 7A**: ML Engine Refactoring (Packaged `ml_engine`, decoupled training/prediction, created `AnalysisPipeline`).
- **Phase 7B**: Flask REST API (Application factory, `/health`, `/analyze`, `/stats` endpoints, JSON serialization, error handling).
- **Phase 8**: Django Database Models (User, AnalysisJob, Anomaly, AuditLog models, custom managers, admin interface, SQLite migrations).
- **Phase 9A**: Django Authentication (Login, Logout, Registration, Profile, Password Change, Session Security, Audit Logging).
- **Phase 9B**: Django Role-Based Access Control (Groups, Permissions, User Isolation).
- **Phase 10**: Upload & Analysis Workflow UI
- `Phase 11A`: Dashboard Foundation (Sidebar navigation, Breadcrumbs, Reusable UI Components, User Profile, Enhanced Home Page).
- `Phase 11B`: Dashboard Features (Alerts table, Incident detail, Search/Filter/Pagination, Status/Severity badges, Role-specific dashboards, Navigation improvements, Responsive tables).
- `Phase 11C`: UI/UX Redesign (Enterprise cybersecurity aesthetics, CSS variables for theming, enhanced responsive sidebar, Bootstrap component refactoring, premium card layouts, interactive theme toggle).
- `Phase 12`: Analytics & Visualization Framework (Chart.js integration, Django JSON API, role-aware scoped chart data, interactive themed charts, dynamic updates).

### Pending Phases (Immediate)
- **Phase 13**: RAG Knowledge Base Setup

*(See [ROADMAP.md](ROADMAP.md) for full phase details)*

---

## 🏛️ Architecture Summary

The project strictly follows a **Decoupled Hybrid Architecture**:

1. **ML Microservice (`ml_engine`)**: A Flask-based backend responsible solely for heavy data processing (parsing binary logs, feature extraction, model inference). It is stateless per request.
2. **Web Dashboard (`web_dashboard`)**: A Django application that handles everything user-facing (authentication, file uploads, database persistence, UI rendering). It communicates with the ML engine exclusively via HTTP REST APIs.

*(See [ARCHITECTURE.md](ARCHITECTURE.md) and [ARCHITECTURE_DECISIONS.md](ARCHITECTURE_DECISIONS.md) for deep dives).*

---

## 📂 Folder Summary

| Directory | Purpose | Future Evolution |
|-----------|---------|------------------|
| `data/raw_logs/` | Original `.evtx` files uploaded by users. | Will be managed by Django's media storage. |
| `data/processed/` | Intermediary CSVs (`features.csv`, etc.). | Used primarily for batch training/testing. |
| `ml_engine/` | The core Python package for ML operations. | Will host the Flask app (`app.py`). |
| `ml_engine/models/`| Joblib artifacts (model, scaler, metadata). | Will support versioned models. |
| `web_dashboard/` | Django project root. | Will connect to PostgreSQL in production. |
| `scripts/` | Dataset generation and validation utilities. | - |

---

## ⚙️ Current Implementations

### Current ML Pipeline
- **Parser**: Extracts XML from `.evtx` using `python-evtx`, normalizes into a Pandas DataFrame.
- **Feature Engineering**: Groups events into 1-hour windows (configurable), extracting 15 specific numerical features (e.g., `failed_logins`, `process_creation_events`).
- **Training**: Fits an Isolation Forest model and a StandardScaler, saving both to disk via `joblib`.
- **Prediction**: Loads artifacts, scales incoming features, and scores them. Outputs `PredictionResult` with anomaly flags, scores, and severity (Critical, High, Medium, Low).
- **Orchestration**: `AnalysisPipeline` chains these steps in-memory for single-file processing.

*(See [ML_PIPELINE.md](ML_PIPELINE.md))*

### Current Flask Pipeline
- **Implemented** in `ml_engine/app.py` (Phase 7B).
- Application factory pattern (`create_app()`) with Blueprint architecture (`/api/v1`).
- Endpoints: `GET /health`, `POST /analyze`, `GET /stats`.
- Custom `SafeJSONEncoder` for numpy/NaN-safe JSON serialization.
- Global error handlers for structured JSON error responses.
- `AnalysisPipeline` loaded once at startup, reused across requests.

### Current Django Pipeline
- **Models (Phase 8)**: Four production-grade ORM models implemented in `web_dashboard/dashboard/models.py`:
  - `User` — Custom user extending `AbstractUser` with RBAC roles (ADMIN, ANALYST).
  - `AnalysisJob` — Tracks `.evtx` file upload lifecycle (PENDING → RUNNING → COMPLETED/FAILED).
  - `Anomaly` — Stores individual anomalous time windows with scores, severity, and feature snapshots (JSONField).
  - `AuditLog` — Append-only compliance log for user actions.
- **Managers**: Custom `UserManager` in `managers.py` enforces role assignment during user creation.
- **Admin**: Full Django admin registrations in `admin.py` with read-only AuditLog enforcement.
- **App Config**: `DashboardConfig` in `apps.py` with `BigAutoField` default.
- **Settings**: `AUTH_USER_MODEL = 'dashboard.User'`, `MEDIA_ROOT` configured for `.evtx` uploads.
- **Database**: SQLite with initial migration applied (all 4 tables + 5 composite indexes).
- **Authentication (Phase 9A)**: Production-grade authentication system:
  - `CustomLoginView` — Login with audit logging and "Remember Me" session control.
  - `CustomLogoutView` — Logout with audit logging.
  - `RegistrationView` — User self-registration (auto-assigns ANALYST role).
  - `ProfileView` — View/update user profile (name, email).
  - `CustomPasswordChangeView` — Secure password change with validation.
  - `SessionSecurityMiddleware` — Idle session timeout, security headers.
  - `CustomLoginForm` — Extended login form with Remember Me checkbox.
  - `UserRegistrationForm` — Registration with email and password validation.
  - Dark SOC-themed templates with Bootstrap 5 and auth-aware navigation.
  - AuditLog integration for LOGIN/LOGOUT events with IP capture.
  - Session security: HttpOnly cookies, SameSite, configurable timeout.
- **Authorization (Phase 9B)**: Production-grade RBAC system:
  - Django Groups: `Super Admin` and `Analyst`.
  - 14 Custom Permissions covering all capabilities.
  - Signal-based automatic group assignment on user save.
  - View-level mixins (`RBACPermissionRequiredMixin`, `OwnershipMixin`) and decorators (`@permission_required_with_audit`).
  - Middleware-enforced block on `/admin/` routes for non-admins.
- **Dashboard Features (Phase 11B)**: Complete operational dashboard:
  - `AlertsListView` — Paginated, searchable, filterable list of all anomalies with user isolation.
  - `AlertDetailView` — Incident detail page with full feature data, severity banner, prev/next navigation.
  - Enhanced `AnalysisHistoryView` — Search by filename, filter by status.
  - Enhanced `home` view — Role-specific dashboards with critical alert counts and recent alerts table.
  - Reusable template components: `_pagination.html`, `_status_badge.html`, `_severity_badge.html`, `_table_filter.html`.
  - Custom template tag `query_transform` for query string preservation during pagination.
  - Sidebar navigation updated with Alerts link.
  - Responsive tables with mobile-friendly filter bars.

---

## ⚠️ Current Limitations

1. **No Live Ingestion**: The system currently only analyzes static `.evtx` files. Live streaming via Windows Event Forwarding (WEF) is out of scope for the current roadmap but planned for the future.
2. **Synchronous Processing**: The planned Flask API is currently designed to be synchronous. Very large `.evtx` files might cause HTTP timeouts. Future versions may require Celery/Redis for asynchronous task queues.
3. **SQLite**: The Django database is currently SQLite, which is unfit for concurrent enterprise deployments.

---

## 🔮 Future Architecture

1. **RAG Explanation Layer**: Integration of an LLM and Vector Database to automatically generate human-readable incident summaries for detected anomalies. *(See [RAG_DESIGN.md](RAG_DESIGN.md))*
2. **PostgreSQL Migration**: Moving Django from SQLite to PostgreSQL for concurrent writes and scalable storage.
3. **Dockerization**: Containerizing Flask and Django into separate orchestrated containers for deployment.

---

## 📜 Development Principles & AI Rules

When contributing to this codebase, developers and AI assistants MUST adhere to the following rules:

1. **Strict Decoupling**: Django NEVER imports from `ml_engine` directly. Flask NEVER imports from Django or touches the SQLite database. They communicate strictly via HTTP.
2. **Single Source of Truth**: This `PROJECT_CONTEXT.md` file must be updated if architectural paradigms shift.
3. **Model Reusability**: The ML prediction workflow (`predict.py`) must NEVER re-fit the `StandardScaler`. It must load the exact scaler used during training (`scaler.py`).
4. **No Code Generation from Scratch**: Always build upon the existing codebase. Read the existing implementations before writing new ones.
5. **Database Agnosticism**: Write Django models such that switching from SQLite to PostgreSQL requires zero code changes (avoid database-specific fields unless necessary).

---

## 📖 Glossary / Terminology

- **EVTX**: Windows XML Event Log format. The primary raw data source.
- **Feature Matrix**: A numeric DataFrame where rows represent time windows (e.g., 1 hour) and columns represent aggregated event counts.
- **Isolation Forest**: An unsupervised machine learning algorithm used to detect anomalies by isolating outliers.
- **Contamination**: A hyperparameter in Isolation Forest defining the expected proportion of outliers in the dataset (currently set to `0.05` or 5%).
- **RAG (Retrieval-Augmented Generation)**: A pattern where an LLM is provided with contextual documents (e.g., MITRE ATT&CK data) retrieved from a vector database before generating an answer.
- **Joblib**: A Python library used to serialize (save) and deserialize (load) the trained ML models and scalers.
